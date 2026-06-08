---
title: "Análisis en procesos auxiliares con paralelismo adaptativo a la RAM"
created: 2026-06-08
updated: 2026-06-08
tags: [rendimiento, threading, arquitectura, decision]
---

# Análisis en procesos auxiliares con paralelismo adaptativo a la RAM

El análisis por lotes pasa de hilos (`ThreadPoolExecutor`) a **procesos auxiliares** (`multiprocessing.Pool`), y decide cuántos auxiliares lanzar y cada cuánto reciclarlos **según la RAM disponible en cada lote**. Resuelve el RSS residual que se quedaba pegado tras analizar y acota el pico durante el análisis. Todo en [`src/core/analyzer.py`](../../../src/core/analyzer.py).

Es la acción correctiva del hallazgo de [log 2026-06-08](../log.md) (high-water-mark del allocator). Contexto de producto: el objetivo es distribuir a DJs/productores con la DAW abierta comiendo varios GB, así que el consumo de RAM es un requisito real (ver [medición de CPU](medicion-cpu.md)).

## El problema

Con `ThreadPoolExecutor`, los workers comparten el espacio de memoria del proceso principal. Cada archivo monta un working set de STFT de ~1-1.5 GB que numpy/scipy liberan al terminar, **pero el allocator no devuelve las páginas al SO** (macOS no tiene `malloc_trim`). Resultado: tras analizar 130 archivos, la app se quedaba en **~1.9-2 GB de RSS en reposo** y no bajaba hasta cerrarla. No es una fuga (la 2ª tanda reutiliza esa RAM, no crece), pero es RSS real que el escritorio retiene. El pico durante el análisis llegaba a 6-8 GB.

## La solución: tres piezas

### 1. Procesos en vez de hilos (libera la RAM al SO)

Lotes de ≥ `PROCESS_POOL_MIN_FILES` (4) corren en `multiprocessing.Pool`. Cada worker (`_analyze_file_worker`) analiza, **vuelca el espectrograma a la caché de disco ahí mismo** (`save_to_cache`, ~4 MB) y devuelve un resultado ligero (solo texto y números). Los ~100-200 MB pesados nacen y mueren dentro del auxiliar: al cerrar el pool, el SO recupera **toda** esa RAM → reposo vuelve a ~100-260 MB.

Lotes pequeños (1-3 archivos: watcher, drag pequeño) siguen en **hilos**: arrancar un proceso reimporta numpy/scipy (~0.5 s) y no compensa. En modo hilos el resultado conserva el espectrograma en memoria y la UI lo cachea, como antes.

Esto obligó a refactorizar el núcleo a una función a nivel de módulo (`_analyze`), no un método, porque los procesos exigen objetos serializables y no transfieren bien los métodos enlazados. También `multiprocessing.freeze_support()` al inicio de `main.py` — **crítico** para el bundle de PyInstaller (sin él, cada spawn relanza la app entera en bucle).

### 2. Reciclado de workers (acota el pico)

`multiprocessing.Pool(maxtasksperchild=N)` mata y renace cada worker tras N archivos. Sin reciclar, **un worker de vida larga arrastra la marca de agua del allocator de cada archivo y se infla a ~4 GB** tras 34 archivos (medido); reciclando vuelve a su coste real (~1.5 GB). Se usa `multiprocessing.Pool` y no `ProcessPoolExecutor` precisamente porque en Python 3.9 solo el primero tiene `maxtasksperchild` (`ProcessPoolExecutor` ganó `max_tasks_per_child` en 3.11, y el target es 3.9+).

### 3. Plan adaptativo a la RAM **disponible** (`_plan_parallelism`)

Decide `(workers, recycle_every)` leyendo la RAM **disponible AHORA**, no la total — el usuario pudo abrir la DAW desde el último lote. Se usa **psutil** (`virtual_memory().available`); en macOS la "libre" cruda engaña (el SO usa RAM como caché y la comprime), por eso no basta `sysconf`. psutil pasó a `requirements.txt` (producción) por esto.

```
budget  = disponible − RAM_RESERVED_GB (2.0)
workers = clamp(1, budget / RAM_PER_WORKER_GB (1.8), MAX_WORKERS_CAP (3), nucleos)
recycle = RELAXED (3) si budget cubre el pico goloso; si no, AGGRESSIVE (1)
```

Con holgura → más workers + reciclado relajado (rápido). Justo → menos workers + reciclar cada archivo (pico mínimo, más lento, pero no ahoga el equipo). Si psutil falla → 2 workers + reciclado agresivo (conservador). Los overrides `max_workers`/`recycle_every` del constructor fijan el plan (útil en tests).

**`MAX_WORKERS_CAP = 3` a propósito (no 4):** con 4 el pico se dispara a ~8 GB; con 3 queda en ~5-6 GB, techo razonable para un escritorio. Cuesta algo de velocidad en máquinas muy potentes, pero "8 GB es una burrada" para una app que debe convivir con la DAW.

## Resultado medido

| | Antes (hilos) | Ahora (procesos adaptativo) |
|---|---|---|
| RSS reposo tras analizar | ~1945 MB | ~215 MB |
| Pico durante análisis | 6-8 GB | acotado ~5-6 GB |
| Velocidad | baseline | ≈ igual con RAM holgada; más lento si va justa (es el trade-off buscado) |

Verificación: suite 83/93, 0 fallos (10 known bugs); espectrogramas cacheados a disco; app arranca limpia.

## Trade-offs aceptados

- **Velocidad variable**: con poca RAM libre el análisis va más lento (menos workers, reciclado por archivo). Es deliberado: preferimos lento a ahogar el equipo. El cálculo pesado ya corre en C (numpy/scipy); el overhead de arrancar procesos es el precio de liberar RAM al SO.
- **El pico irreducible** lo fija el coste de STFT de un archivo × concurrencia. `gc.collect()` no lo baja (medido); el único modo de bajar el techo más sería acotar el STFT en pistas largas (aplazado).
- **No reescribir en nativo**: la referencia [Fakin' the Funk](medicion-cpu.md) (39 MB nativo) es más rápida, pero son meses de Python y el grueso ya es C; la lentitud es overhead de arranque de proceso, no el lenguaje.

## Estado

En la rama `perf/process-pool-analysis`. Pendiente: QA de m4a en Windows/Linux y merge a `main`.
