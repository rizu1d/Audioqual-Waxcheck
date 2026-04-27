---
title: Herramientas de referencia para análisis de audio
created: 2026-04-27
updated: 2026-04-27
sources: [MEJORAS_EN_ALGORITMO.txt]
tags: [herramientas, tfg]
---

# Herramientas de referencia

Herramientas externas usadas durante el desarrollo de AudioQual para validar resultados.

## Spek

- **Tipo**: analizador de espectro open source
- **Uso**: primera impresión visual rápida del contenido frecuencial
- **Limitación descubierta**: su colormap crea fronteras visuales artificiales a -70/-75 dB. Lo que parece un "corte" puede ser simplemente una transición de color. Ver [Spek vs MusicScope](../decisiones/spek-vs-musicscope.md)
- **Veredicto**: útil para screening rápido, no fiable para decisiones de clasificación

## MusicScope

- **Tipo**: analizador de audio profesional con múltiples vistas
- **Vista clave**: Linear Frequency Spectrum — muestra la energía real por frecuencia sin distorsiones de colormap
- **Uso**: referencia definitiva para determinar si existe contenido real en una frecuencia
- **Veredicto**: gold standard para validación

## librosa (usada internamente)

- **Tipo**: librería Python para análisis de audio
- **Funciones usadas**: `load()` (carga de audio), STFT (espectrograma), `amplitude_to_db()`
- **Quirk importante**: `amplitude_to_db()` aplica `top_db=80` por defecto, recortando todo por debajo de -80 dB. En archivos con pocas secciones activas, esto aplana el contenido HF al mismo nivel.

## mutagen (usada internamente)

- **Tipo**: librería Python para metadatos de audio
- **Uso**: extracción de bitrate declarado, formato, tags ID3/Vorbis/FLAC
- **Función en AudioQual**: provee el "bitrate declarado" contra el que se compara el corte detectado
