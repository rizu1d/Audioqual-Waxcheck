---
title: "Medición de CPU y rendimiento"
created: 2026-06-01
updated: 2026-06-05
sources: [DIAGNOSTICO_CPU.txt]
tags: [rendimiento, threading, herramientas]
---

# Medición de CPU y rendimiento

Guía de referencia para medir el consumo de CPU de la app y decidir, con datos, si una optimización merece la pena. Nace de la sesión de optimización de junio 2026 (ver [Threading y macOS](../arquitectura/threading-macos.md) y [PollingObserver](polling-observer.md)).

## Estados a medir

Siempre comparar los **mismos estados** antes/después de un cambio:

1. **Reposo** — app abierta, sin archivos, sin tocar nada.
2. **Reposo con archivos cargados** — tabla llena, nada en marcha.
3. **Analizando** — durante un lote de análisis.
4. **Monitorizando** — watcher activo sobre una carpeta, sin archivos nuevos llegando.

## Herramientas: tres capas según el problema

Hay **dos problemas de medición distintos** y piden herramientas distintas: carga de trabajo determinista (el pipeline analizando archivos) vs. estados interactivos en vivo (la GUI en reposo, watcher, reproducción).

### Capa 1 — `tests/benchmark.py` (regresión determinista, periódico/CI)

La herramienta **primaria** para detectar regresiones cada X días. Corre el pipeline sobre los archivos de `tests.json` de forma reproducible y **solo con stdlib** (`time`, `resource`, `tracemalloc`) — cero dependencias, encaja con el criterio de peso del bundle.

```bash
python3 tests/benchmark.py                  # mide y compara contra baseline
python3 tests/benchmark.py --update-baseline    # fija el run actual como referencia
python3 tests/benchmark.py --save           # vuelca detalle por-archivo
```

Mide en **dos pasadas separadas** (para no contaminar el tiempo con el overhead de tracemalloc):

- **Pasada A** (tracemalloc OFF): `wall_s` (`perf_counter`), `cpu_s` (`getrusage` user+sys) y `rss_peak_mb` (`ru_maxrss`, marca de agua alta del RSS).
- **Pasada B** (tracemalloc ON): `heap_peak_mb`, pico del heap de Python.

Sale con **código 1 si alguna métrica supera su umbral** (tiempo/CPU +10%, RSS/heap +15%). Resultados:

- `tests/benchmark_baseline.json` — referencia maestra, **commiteada** (como `tests.json`).
- `tests/benchmark_history.jsonl` — una línea por run (fecha, git SHA, máquina, métricas), **commiteado**: serie temporal.
- `tests/benchmark_results_*.json` — dump verboso por-archivo, **gitignored**.

**Clave sobre comparar entre máquinas:** `wall_s`/`cpu_s`/`rss_peak_mb` dependen del hardware → solo válidos contra un baseline de la **misma** máquina (por eso cada run guarda el campo `machine` y avisa si no coincide). `heap_peak_mb` es **determinista e independiente del hardware** — se verificó empíricamente: dos runs consecutivos dieron 1246.6 MB clavado. Es la señal fiable en CI con hardware distinto.

> ⚠️ Habría cazado al instante el STFT roto de `f91cb5e` (4× más lento, +2 GB): `wall_s` y `heap_peak_mb` se habrían disparado muy por encima del umbral.

### Capa 2 — `tests/benchmark_live.py` (estados GUI en vivo, manual)

El benchmark de Capa 1 no cubre los estados interactivos. Para esos, este script se engancha al proceso de la app y muestrea `cpu_percent()` y RSS cada 0.5 s durante N segundos → media/mediana/pico, **atribuido solo a ese proceso**. Requiere `psutil` (dependencia **solo de dev**, `requirements-dev.txt`; no se empaqueta). Sustituye al antiguo `ps %cpu`, **demasiado ruidoso para resolver diferencias de ~2%** a niveles bajos.

```bash
python3 src/main.py                              # la app, en una terminal
python3 tests/benchmark_live.py --list           # guion de montaje de cada estado
python3 tests/benchmark_live.py --state reposo   # en otra terminal
python3 tests/benchmark_live.py --state analizando --seconds 20
```

Autodetecta el PID exigiendo `name=python` (el wrapper de shell también tiene `src/main.py` en su cmdline → falso positivo descartado). **No** falla con código 1 (los estados en vivo son demasiado ruidosos para umbrales); anexa cada run a `benchmark_live_history.jsonl` etiquetado por estado, y muestra el delta contra el run anterior del mismo estado para ver la deriva. CPU% > 100% es normal (varios cores; 100% = 1 core).

Validación contra `powermetrics`: el reposo medido aquí (~3.4% CPU, ~220 MB RSS) coincide con el ~3.4% que dio `powermetrics`, confirmando que ambas miden lo mismo en reposo.

### Capa 3 — perfilado de diagnóstico (puntual, cuando algo regresa)

**Reactiva, no periódica.** No se instala "por tener": las Capas 1 y 2 dicen *que* hay una regresión; la Capa 3 dice *dónde* está. Las herramientas viven **comentadas** en `requirements-dev.txt`; se activan el día que hacen falta.

**Activar:**
```bash
pip install memray py-spy   # o descomenta sus líneas en requirements-dev.txt
```

**`memray` — cuando se dispara la RAM** (`rss_peak_mb`/`heap_peak_mb` en Capa 1, o `rss` en Capa 2). Da un flamegraph del pico: qué función/línea reserva la memoria. El `--native` es clave aquí porque el grueso de la RAM está en numpy/scipy (C), no en Python puro:
```bash
# Perfilar el batch (reutiliza el corpus de la Capa 1)
python3 -m memray run --native -o profile.bin tests/benchmark.py
python3 -m memray flamegraph profile.bin        # genera profile.html
# Engancharse a la app viva (no hace falta reiniciarla)
python3 -m memray attach <PID>
```
Habría señalado al instante el STFT roto de `f91cb5e` (+2 GB en una función).

**`py-spy` — cuando se dispara la CPU/tiempo** (`wall_s`/`cpu_s` en Capa 1, o `cpu` en Capa 2). Sampling profiler que se **engancha a la app viva sin tocar el código ni reiniciar**:
```bash
py-spy top --pid <PID>                       # vista tipo top, en vivo
py-spy record -o profile.svg --pid <PID>     # flamegraph de N segundos
py-spy dump --pid <PID>                       # volcado puntual de stacks
```
El `<PID>` es el mismo que usa la Capa 2 (proceso `python` de `src/main.py`).

Ninguna de las dos se empaqueta (son solo de dev); no afectan al peso del bundle.

### `powermetrics` (nicho: wakeups y energía/batería)

Mide **wakeups** reales, que es lo que de verdad importa para el consumo en reposo en macOS:

```bash
sudo powermetrics --samplers tasks -i 1000 -n 5 2>/dev/null | grep -iE "^Name|python"
```

Con `-i 1000` las cifras son por segundo. Columnas relevantes de la fila `Python`:

- **Intr Wakeups** — despertares por interrupción/timer. Bajan al reducir timers.
- **Pkg idle wakeups** — despertares que sacan al chip del sueño profundo. **Son los caros** (batería/energía). Mantenerlos bajos es el objetivo real.
- **CPU ms/s** — tiempo de CPU; 10 ms/s ≈ 1% de un core.

## Cómo interpretar (lecciones aprendidas)

- **`%cpu` puede exceder 100%**: se normaliza por núcleo. Durante el análisis vimos ~330% = ~3.3 cores ocupados por los 4 workers paralelos. Es trabajo real y transitorio, **no** un problema.
- **Pkg-idle wakeups era el miedo, y resultó infundado**: el informe `DIAGNOSTICO_CPU.txt` temía que el run loop de Cocoa "nunca entrara en bajo consumo". La medición mostró pkg-idle wakeups ~1/s — el chip **sí** duerme bien. La preocupación original estaba sobredimensionada.
- **El grueso de los Intr Wakeups (~54/s) no viene de nuestro código**, sino del notifier propio de Tcl/Tk. Nuestras 3 capas de callbacks son una fracción menor.

## Verdicto registrado de R3 (intervalos de callbacks)

Subir los intervalos de las 3 capas de drenaje de callbacks (poller 50→250ms, heartbeat 100→500ms, keepalive 200→500ms), medido con `powermetrics`:

| Métrica | R3 activado | R3 desactivado | Efecto |
|---------|-------------|----------------|--------|
| Intr Wakeups | ~54/s | ~69/s | −22% |
| CPU | ~3.3% | ~3.8% | −0.5% |
| Pkg idle wakeups | ~0.8/s | ~1.2/s | igual (ambos bajísimos) |

Beneficio real pero modesto, sin contrapartida en los wakeups caros. Se mantiene. La ruta primaria (pipe event-driven) sigue entregando callbacks al instante; solo cambia la latencia de la red de seguridad anti-freeze.

## Verificación post-reemplazo de librosa (2026-06-05)

Tras quitar librosa (commit `cee3da6`, bundle 202→87 MB) el usuario sospechó que el análisis consumía más recursos. Se midió con `powermetrics` (M-series, MacBook Air) en los cuatro estados y se comparó contra el baseline **con** librosa de 2026-06-01. Promedios de 5 muestras (`-i 1000 -n 5`):

| Estado | CPU ms/s (≈% de core) | Intr Wakeups/s | Pkg idle/s | Baseline con librosa |
|--------|----------------------|----------------|------------|----------------------|
| Reposo | ~34 (≈3.4%) | ~53.6 | ~0.98 | ~3.3% / ~54 / ~0.8 → **idéntico** |
| Tabla llena (300, en reposo) | ~34 (≈3.4%) | ~51.7 | ~0.98 | ≈ reposo → **la tabla no añade coste** |
| Analizando 300 | ~3568 (≈357%, ~3.5 cores) | ~90–105 (pico 215) | 0.00 | ~330% (~3.3 cores) → **igual, dentro de ruido** |
| Tabla llena + watcher | ~80 (≈8%) | ~54.7 | ~0.99–4.9 | ~4–10% (PollingObserver 3s) → **en rango** |

**Conclusión:** el reemplazo de librosa **no introdujo regresión de consumo** en ninguno de los cuatro estados. El ~357% durante el análisis son los 4 workers paralelos haciendo trabajo real y transitorio (mismo perfil que con librosa), no una fuga. La lentitud que el usuario había percibido antes era el STFT roto de `f91cb5e` (4× más lento, +2 GB RAM), ya corregido en `cee3da6` — ver [log.md](../log.md) 2026-06-03. Reposo/tabla/watcher salen clavados porque el reemplazo no toca timers ni watcher. Se descartó volver a `218ce95`.

## Si en el futuro hay que bajar más el reposo

El siguiente objetivo sería reducir los ~54/s de base del notifier de Tcl/Tk, no más ajustes de nuestros timers. Opciones (no implementadas): reemplazar PollingObserver por FSEventsObserver con workaround Unicode (ver [PollingObserver](polling-observer.md)), o investigar el modo de bajo consumo del notifier de Tk. Validar siempre con `powermetrics`, nunca solo con `ps`.
