---
title: Principio fundamental de detección
created: 2026-04-27
updated: 2026-04-27
sources: [ALGORITMO.txt]
tags: [algoritmo, codec, tfg]
---

# Principio fundamental de detección

AudioQual detecta si un archivo de audio tiene la calidad real que declara. Un MP3 etiquetado como "320kbps" que fue convertido desde un archivo de menor calidad (128kbps, YouTube rip, etc.) es un **transcode** — la etiqueta miente sobre la calidad real.

## Base física: filtros pasa-bajos de los codecs

Los codecs de audio con pérdida (MP3, AAC, OGG) aplican un filtro pasa-bajos que elimina frecuencias altas. Esto es una consecuencia directa del modelo psicoacústico: el codec descarta información que considera menos perceptible para ahorrar bits, y las frecuencias más altas son las primeras en caer.

Cuanto menor es el bitrate, más bajo es el corte:

| Bitrate | Corte real aproximado |
|---------|----------------------|
| 320 kbps | ~20 kHz |
| 256 kbps | ~19 kHz |
| 192 kbps | ~17-18 kHz |
| 128 kbps | ~15-16 kHz |
| 96 kbps | ~13-15 kHz |

Estos valores son aproximados porque dependen del encoder específico (LAME, Fraunhofer, iTunes AAC) y del contenido del audio. Pero son consistentes: un MP3 de 128kbps **nunca** tendrá contenido real por encima de ~17 kHz, por limitación física del codec.

## El principio de detección

Si alguien toma un MP3 de 128kbps (corte a ~16 kHz) y lo re-codifica a 320kbps, el archivo resultante dirá "320kbps" pero **no tendrá contenido real por encima de 16 kHz**. Solo habrá ruido de cuantización o silencio en esas frecuencias.

AudioQual detecta exactamente dónde termina el contenido musical real (la **frecuencia de corte**) y la compara con lo que el bitrate declarado debería tener. Si hay discrepancia significativa, es un transcode.

## Distinción clave: corte artificial vs. rolloff natural

No toda caída de energía en altas frecuencias es un transcode. Muchas producciones musicales tienen un **rolloff natural** — la energía simplemente decae gradualmente en los agudos por decisiones de mezcla y mastering.

La diferencia está en la **firma del corte**:
- **Brickwall de codec**: caída abrupta (>9 dB/kHz), varianza temporal post-corte prácticamente cero. Es un muro artificial.
- **Rolloff natural**: caída gradual (<6 dB/kHz), varianza temporal sostenida. El contenido sigue existiendo, solo baja de nivel.

Ver [Brickwall vs rolloff natural](brickwall-vs-rolloff.md) para la implementación de esta distinción.

## Relevancia para el TFG

Este principio conecta directamente con:
- **Modelo psicoacústico MPEG**: ISO/IEC 11172-3 define cómo los encoders deciden qué frecuencias descartar
- **Teorema de Nyquist-Shannon**: el sample rate limita la frecuencia máxima representable
- **Análisis espectral**: la STFT como herramienta para visualizar el contenido frecuencial en el tiempo

Ver [Tutorial MPEG audio compression](../fuentes/tutorial-mpeg-compression.md) para la referencia académica.
