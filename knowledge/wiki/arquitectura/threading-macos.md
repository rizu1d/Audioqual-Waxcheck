---
title: Threading y event loop en macOS
created: 2026-04-27
updated: 2026-06-01
sources: [BLOQUEOS_MACOS.txt, DIAGNOSTICO_CPU.txt]
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
Timer `after(250ms)` independiente del pipe, como safety net.

### Capa 3 (último recurso): heartbeat
Timer `after(500ms)` en `app.py` que llama `process_pending_callbacks()`.

El hilo keep-alive (escribe al pipe para evitar dormancia de Cocoa) corre cada 500ms.

**Regla de oro**: NUNCA llamar métodos de Tkinter desde un hilo que no sea el principal. SIEMPRE usar `schedule_callback_from_thread()`.

## Consumo de CPU en reposo (medido, junio 2026)

El informe `DIAGNOSTICO_CPU.txt` temía que estas 3 capas (originalmente 50/100/200ms ≈ 35 despertares/s) impidieran que el run loop de Cocoa entrara en bajo consumo. La medición con `powermetrics` lo desmintió:

- **Pkg-idle wakeups ~1/s** — el chip **sí** entra en sueño profundo; el miedo original estaba sobredimensionado.
- **Intr wakeups ~54/s** — y el grueso **no** viene de nuestras capas, sino del notifier propio de Tcl/Tk.

Subir los intervalos a 250/500/500ms (cambio "R3") recortó los intr wakeups un ~22% y ~0.5% de CPU, sin tocar los pkg-idle wakeups. Beneficio modesto pero real; se mantuvo. La ruta primaria (pipe) sigue entregando callbacks al instante, así que solo cambia la latencia de la red de seguridad. Metodología completa en [Medición de CPU](../decisiones/medicion-cpu.md).

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
