---
title: Threading y event loop en macOS
created: 2026-04-27
updated: 2026-04-27
sources: [BLOQUEOS_MACOS.txt]
tags: [threading, gui, arquitectura, tfg]
---

# Threading y event loop en macOS

La app usa múltiples hilos de fondo (análisis de audio, renderizado de espectrograma, reproducción, waveform) con una GUI Tkinter. En macOS, el backend Cocoa tiene comportamientos problemáticos que requirieron una arquitectura de callbacks especial.

## El problema raíz

En macOS, Tkinter usa el backend Cocoa (Tk 8.6). Cuando no hay actividad de I/O ni timers pendientes, el run loop de Cocoa puede entrar en estado "dormant":
- `root.after(ms, callback)` se registra pero no se ejecuta hasta que algo despierte el loop
- `event_generate()` desde un hilo de fondo puede no despertar el loop
- El primer clic en una ventana sin foco solo otorga foco, no se entrega como evento

Estos problemas **no existen** en Windows/Linux.

## Solución: sistema de callbacks thread→UI con 3 capas

Implementado en `src/utils/tk_utils.py`:

### Capa 1 (primaria): pipe + createfilehandler
- Se crea un `os.pipe()` → (read_fd, write_fd)
- Se registra read_fd con `Tk createfilehandler` (backed by kqueue en macOS)
- Los callbacks van a una `queue.Queue` thread-safe
- Cuando un thread encola un callback, escribe un byte al pipe
- kqueue detecta I/O → dispara el file handler → drena la queue

### Capa 2 (backup): poller basado en after()
Timer `after(50ms)` independiente del pipe, como safety net.

### Capa 3 (último recurso): heartbeat
Timer `after(100ms)` en `app.py` que llama `process_pending_callbacks()`.

**Regla de oro**: NUNCA llamar métodos de Tkinter desde un hilo que no sea el principal. SIEMPRE usar `schedule_callback_from_thread()`.

## Problemas resueltos

| Problema | Causa | Solución | Commit |
|----------|-------|----------|--------|
| UI se congela tras análisis | Callbacks no se ejecutaban (event loop dormido) | pipe + createfilehandler | cb4ebe1 |
| Primer clic no responde | acceptsFirstMouse de Cocoa | bind_all + focus_force | 0603f4d |
| Pérdida de foco tras modal | grab_release + destroy demasiado rápido | Delay 50ms + focus_force | cb4ebe1 |
| App cada vez más lenta | bind_all handlers zombis acumulados | Patrón singleton click watcher | 0603f4d |
| Memory leak matplotlib | Figuras sin plt.close() | try/finally | e580ff2 |
| Race condition audio | Stream obsoleto ejecutando callbacks | Generation counter | e580ff2 |

## Antipatrones documentados

Ver `knowledge/BLOQUEOS_MACOS.txt` sección 10 para la lista completa de 10 antipatrones con sus alternativas correctas.

## Relevancia para el TFG

Este trabajo documenta un problema real de ingeniería de software: la interacción entre frameworks GUI y concurrencia en sistemas operativos modernos. Las soluciones aplicadas (pipe+kqueue, generation counters, singleton watchers) son patrones transferibles a cualquier aplicación desktop multithreaded.
