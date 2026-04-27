---
title: "A Tutorial on MPEG/Audio Compression (Pan, 1995)"
created: 2026-04-27
updated: 2026-04-27
sources: [A_tutorial_on_MPEG_audio_compression.pdf]
tags: [codec, tfg]
---

# A Tutorial on MPEG/Audio Compression

**Autor**: Davis Pan
**Publicación**: IEEE MultiMedia, Vol. 2, No. 2, Summer 1995, pp. 60-74
**IEEE**: [10.1109/93.388209](https://ieeexplore.ieee.org/abstract/document/388209)
**Ubicación local**: `sources/A_tutorial_on_MPEG_audio_compression.pdf` (pendiente de copiar desde TFG/Material)

## Resumen

Tutorial fundacional sobre la compresión de audio MPEG (Layers I, II y III / MP3). Explica el modelo psicoacústico que subyace a la compresión con pérdida.

## Conceptos clave para AudioQual

### Modelo psicoacústico
Los codecs MPEG explotan las limitaciones del oído humano:
- **Umbral de audición absoluto**: frecuencias muy altas o muy bajas requieren más energía para ser percibidas
- **Enmascaramiento frecuencial**: un tono fuerte "oculta" tonos cercanos más débiles
- **Enmascaramiento temporal**: un sonido fuerte enmascara sonidos débiles que ocurren justo antes o después

El encoder calcula qué componentes frecuenciales son imperceptibles y las descarta o cuantiza agresivamente.

### Banco de filtros
- Layer III (MP3) usa un **banco de filtros híbrido**: polifásico (32 sub-bandas) + MDCT (18 coeficientes por sub-banda = 576 líneas frecuenciales)
- La resolución frecuencial de este banco es la que determina la precisión del filtro pasa-bajos del codec

### Filtro pasa-bajos del encoder
A menor bitrate, el encoder tiene menos bits disponibles → descarta más frecuencias altas → filtro pasa-bajos más agresivo. Esta es la **base física** de la detección de AudioQual: el corte de frecuencia es una consecuencia directa de la asignación de bits.

### Diferencias entre encoders
El estándar MPEG define el **decoder**, no el encoder. Diferentes encoders (LAME, Fraunhofer, iTunes) pueden tomar decisiones diferentes sobre qué descartar, lo que explica por qué los cortes de frecuencia varían ligeramente entre encoders para el mismo bitrate.

## Relevancia para el TFG

Este paper es la referencia primaria para explicar **por qué** funciona la detección de AudioQual. Conecta el principio fundamental (corte de frecuencia proporcional al bitrate) con la teoría subyacente del modelo psicoacústico.

Sección del TFG donde encaja: **Marco teórico / Estado del arte**.
