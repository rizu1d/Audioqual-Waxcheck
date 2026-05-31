---
title: "Medición de CPU y rendimiento"
created: 2026-06-01
updated: 2026-06-01
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

## Herramientas, de menos a más fiable

### `scripts/measure_cpu.sh` (rápido, orientativo)

Muestrea `%cpu` del proceso cada 2s y promedia. Uso:

```bash
python3 src/main.py            # en una terminal
bash scripts/measure_cpu.sh    # en otra; o "bash scripts/measure_cpu.sh 60"
```

Autodetecta el PID por `pgrep -f "src/main.py"`.

**Limitación crítica:** `ps %cpu` es un promedio decadente y **demasiado ruidoso para resolver diferencias de ~2%** a niveles bajos. Sirve para ver cambios grandes (29% → 4%), NO para validar microoptimizaciones de reposo.

### `powermetrics` (preciso, para deltas pequeños)

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

## Si en el futuro hay que bajar más el reposo

El siguiente objetivo sería reducir los ~54/s de base del notifier de Tcl/Tk, no más ajustes de nuestros timers. Opciones (no implementadas): reemplazar PollingObserver por FSEventsObserver con workaround Unicode (ver [PollingObserver](polling-observer.md)), o investigar el modo de bajo consumo del notifier de Tk. Validar siempre con `powermetrics`, nunca solo con `ps`.
