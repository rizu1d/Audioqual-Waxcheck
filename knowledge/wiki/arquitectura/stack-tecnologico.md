---
title: Stack tecnológico
created: 2026-04-27
updated: 2026-04-27
sources: [DISTRIBUCION-15march.txt]
tags: [arquitectura, distribucion, tfg]
---

# Stack tecnológico

## Lenguaje y runtime

- **Python 3.9+** — elegido por el ecosistema científico (numpy, scipy, librosa) y la velocidad de prototipado
- **Tkinter/customtkinter** — GUI nativa multiplataforma, con look moderno gracias a customtkinter
- **tkinterdnd2** — drag & drop nativo (no disponible en Tk estándar)

## Dependencias principales

| Librería | Propósito | Peso |
|----------|-----------|------|
| **librosa** | Análisis de audio (carga, STFT, features) | ~3 MB |
| **numpy** | Arrays numéricos, operaciones matriciales | ~30 MB |
| **scipy** | Cálculo científico (complemento de STFT) | ~83 MB |
| **matplotlib** | Visualización de espectrogramas | ~25 MB |
| **mutagen** | Metadatos de audio (ID3, Vorbis, FLAC) | ~1.5 MB |
| **sounddevice** | Reproducción de audio (callback-based) | ~0.2 MB |
| **watchdog** | Monitorización de carpetas | ~0.4 MB |
| **Pillow** | Procesamiento de imágenes | ~3 MB |
| **cairosvg/cairocffi** | Conversión SVG→PNG para iconos | ~1 MB |

## Estructura del proyecto

```
src/
├── main.py              Punto de entrada
├── app.py               Clase principal AudioQualApp
├── core/                Pipeline de análisis (4 módulos)
├── gui/                 Interfaz gráfica (12 módulos)
├── utils/               Utilidades (8 módulos)
├── assets/              Fuentes, iconos, logos
└── locales/             Traducciones (es.json, en.json)
```

31 módulos Python, ~3.8 MB de código fuente total.

## Plataformas soportadas

- **macOS**: 10.15+ (Intel y Apple Silicon). Backend Cocoa requiere workarounds específicos para threading (ver [Threading y macOS](threading-macos.md))
- **Windows**: 10+ (64-bit). Backend Win32
- **Linux**: Ubuntu 20.04+, Fedora 34+, Debian 11+. Requiere Tcl/Tk 8.6, portaudio, libsndfile

## Distribución

Empaquetado con **PyInstaller**. Tamaño final: ~100-130 MB comprimido. Ver [Distribución](distribucion.md).
