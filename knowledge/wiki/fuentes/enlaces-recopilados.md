---
title: Enlaces y recursos recopilados
created: 2026-04-27
updated: 2026-06-05
sources: [Artículos.rtf]
tags: [tfg, herramientas]
---

# Enlaces y recursos recopilados

Fuentes externas recopiladas desde el material del TFG (`Artículos.rtf`).

## Paper académico

- **A Tutorial on MPEG/Audio Compression** (Pan, 1995)
  IEEE MultiMedia. [IEEE Xplore](https://ieeexplore.ieee.org/abstract/document/388209)
  Ver [resumen detallado](tutorial-mpeg-compression.md)

## Herramientas de análisis espectral

- **The Well-Tempered Computer — Spectrum Analysis Tools**
  [thewelltemperedcomputer.com](https://www.thewelltemperedcomputer.com/SW/AudioTools/Spectrum.htm)
  Comparativa de herramientas de análisis espectral. Útil para el TFG como referencia de herramientas existentes.

## Comunidad y conocimiento práctico

- **Reddit: How to determine the true quality of an audio file**
  [r/skrillex thread](https://www.reddit.com/r/skrillex/comments/3l0yxp/how_to_determine_the_true_quality_of_an_audio_file/)
  Discusión comunitaria sobre detección manual de calidad usando Spek. Muestra el problema que AudioQual automatiza.

## Dither y suelo de ruido (cuantización)

Fuentes que respaldan el criterio de [suelo de ruido hasta Nyquist](../algoritmo/suelo-ruido-nyquist.md) (id `tonmeister-high-res-noise`).

- **High-Res Audio: Part 6 — Noise, noise, noise** (Geoff Martin / Tonmeister, 2021)
  [tonmeister.ca](https://www.tonmeister.ca/wordpress/2021/06/24/high-res-audio-part-6-noise-noise-noise/)
  Explica por qué un PCM correctamente *dithered* conserva un suelo de ruido de banda ancha hasta Nyquist (dither TPDF, ~−93 dBFS a 16 bits, noise shaping). Base física del tell lossless vs. lossy en agudos.

- **What is dither, and how does it work?** (SoundGuys)
  [soundguys.com](https://www.soundguys.com/what-is-dither-23700/)
  Introducción accesible al dither y la distorsión de cuantización. Complemento divulgativo a la fuente de Tonmeister para el marco teórico del TFG.

## Estándares

- **EBU Tech 3342: Loudness Range**
  [tech.ebu.ch](https://tech.ebu.ch/docs/tech/tech3342.pdf)
  Especificación de la European Broadcasting Union sobre rango de loudness. Relevante como contexto de estándares de calidad de audio en broadcast.

## Fuentes pendientes de añadir

Para completar el marco teórico del TFG, sería útil buscar e ingestar:

- **ISO/IEC 11172-3**: Estándar MPEG-1 Audio (Layer III / MP3). Define el decoder y los límites del formato.
- **LAME encoder documentation**: Documentación del encoder MP3 más usado. Tablas de filtros pasa-bajos por bitrate.
- **Documentación de librosa**: Particularmente la implementación de STFT y el parámetro `top_db`.
- **Papers sobre detección de transcodes**: Si existen trabajos previos sobre detección automática de calidad de audio.
- **Especificación AAC (ISO/IEC 13818-7)**: Para entender los cortes de YouTube (AAC).
