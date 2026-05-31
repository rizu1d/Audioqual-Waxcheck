---
title: "Decisión: PollingObserver en vez de FSEventsObserver"
created: 2026-04-27
updated: 2026-06-01
sources: [DIAGNOSTICO_CPU.txt]
tags: [decision, arquitectura, rendimiento]
---

# Decisión: PollingObserver en vez de FSEventsObserver

## Contexto

El FolderWatcher (`src/core/folder_watcher.py`) monitoriza una carpeta para auto-analizar archivos nuevos. La librería watchdog ofrece múltiples backends.

## Decisión

Se usa `watchdog.observers.PollingObserver` en vez del `FSEventsObserver` nativo de macOS.

## Razón

FSEventsObserver tiene un bug conocido con Unicode en macOS: los nombres de archivo con caracteres especiales (acentos, ñ, etc.) pueden llegar con encoding incorrecto, causando que los archivos no se encuentren al intentar abrirlos.

PollingObserver es más lento (chequea cada N segundos vs. notificación instantánea) pero funciona correctamente con cualquier nombre de archivo en cualquier plataforma.

## Trade-off

- Latencia: PollingObserver tiene delay configurable (intervalo de polling actual: 3s) vs. instantáneo de FSEvents
- Fiabilidad: funciona correctamente en todos los casos
- Portabilidad: mismo comportamiento en macOS, Windows y Linux

## Coste de CPU y ajuste del intervalo (junio 2026)

El `PollingObserver` ejecuta un `os.walk()` recursivo completo cada intervalo. El informe `DIAGNOSTICO_CPU.txt` lo identificó como el mayor consumidor: con el intervalo original de **1s**, monitorizar consumía **~29% de CPU** de forma sostenida (cientos de `stat()` por segundo).

Subir el intervalo a **3s** (`_POLLING_INTERVAL` en `folder_watcher.py`) bajó la monitorización a **~4%** en una carpeta de ~100 archivos — prácticamente el mismo coste que la app en reposo. La latencia añadida es invisible: el bucle de estabilidad ya espera ~2s de tamaño constante antes de despachar.

Reemplazar PollingObserver por FSEventsObserver (con workaround Unicode) lo bajaría a ~0.1%, pero sigue descartado por el bug de Unicode y el esfuerzo. Ver metodología de medición en [Medición de CPU](medicion-cpu.md).
