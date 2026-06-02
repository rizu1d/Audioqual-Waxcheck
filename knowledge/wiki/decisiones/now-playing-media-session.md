---
title: "Decisión: Integración Now Playing / Media Session (aplazada)"
created: 2026-06-03
updated: 2026-06-03
sources: []
tags: [decision, gui, distribucion, threading]
---

# Decisión: Integración Now Playing / Media Session (aplazada)

## Contexto

Se planteó que, al reproducir un archivo, AudioQual aparezca como reproductor de medios activo del
sistema operativo — igual que Spotify: el widget **"Reproduciendo ahora"** del Centro de Control de
macOS, el panel multimedia de Windows (SMTC) y el control MPRIS de Linux, con título/artista/álbum +
carátula y respondiendo a las teclas de medios y a los botones del widget.

Es una feature "de detalle": baja prioridad funcional, pero pulida.

## Estado: APLAZADA (2026-06-03)

Diseñada por completo pero **no implementada**. Se aparca por el **coste en peso del binario final**:
no hay certeza de poder asumirlo. El plan completo y el apéndice técnico (anclajes de código y
particularidades de cada API nativa) viven en
`~/.claude/plans/seguimos-con-las-implementaciones-parsed-fox.md`.

## Diseño propuesto

No existe una librería cross-platform para esto: cada SO usa una API nativa distinta. El diseño es
un **adaptador por plataforma** detrás de una interfaz común, con **carga perezosa**: la lib nativa
se importa solo en su SO y de forma opcional; si falta o falla la init, la feature se autodesactiva
en silencio (mismo patrón que `watchdog` en `folder_watcher.py` o `HAS_SOUNDDEVICE` en
`audio_player.py`).

- **macOS** → `MPNowPlayingInfoCenter` + `MPRemoteCommandCenter` vía `pyobjc-framework-MediaPlayer`.
- **Windows** → `SystemMediaTransportControls` vía `winsdk` (requiere interop `GetForWindow(hwnd)`
  para ventana Win32; es el backend más frágil).
- **Linux** → MPRIS2 sobre D-Bus de sesión vía `jeepney` (Python puro).

Puntos de enganche en el código existente (todos ya disponibles, mínimamente invasivos):
- Listeners aditivos en `AudioPlayer._set_state()` / `seek()` / `stop()` para no pisar la API
  `set_callbacks` que ya consume `PlayerControls`.
- Metadatos leídos reutilizando el patrón mutagen de `metadata_editor._read_header_info()`.
- Cableado de comandos remotos y `teardown()` en `app.py` (ciclo de vida en `_cleanup`), con
  marshalado al hilo de tk vía `schedule_callback_from_thread` (ver [Threading y macOS](../arquitectura/threading-macos.md)).

## Razón del aplazamiento (trade-off de peso)

Cada backend añade una dependencia nativa **solo en su plataforma** (markers de entorno), por lo que
el peso extra de cada SO se limita a su propio backend:

| Plataforma | Dependencia | Coste aprox. |
|-----------|-------------|--------------|
| macOS | `pyobjc-framework-MediaPlayer` (arrastra `pyobjc-core` + Cocoa) | ~10-20 MB sobre un `.app` que ya ronda 230 MB |
| Windows | `winsdk` | ~30-50 MB (no afecta al bundle de macOS) |
| Linux | `jeepney` | ligero (Python puro) |

El coste de macOS es el que frena la decisión: es notable para una feature de bajo valor funcional,
y choca con la vigilancia de tamaño del proyecto (ver [Distribución](../arquitectura/distribucion.md),
donde ya se excluyó `sklearn` para ahorrar peso). Antes de implementar, **reevaluar este trade-off**.

## Pendiente al retomar

1. Decidir si el peso es asumible (¿solo Linux+macOS? ¿solo macOS? ¿las 3?).
2. Ejecutar el plan guardado y su sección de verificación (manual por SO + `quick_check.sh`).
