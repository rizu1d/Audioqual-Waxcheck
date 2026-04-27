---
title: Pipeline de análisis
created: 2026-04-27
updated: 2026-04-27
sources: [ALGORITMO.txt]
tags: [algoritmo, arquitectura]
---

# Pipeline de análisis

El análisis se ejecuta en tres etapas secuenciales, implementadas en `src/core/`:

## Etapa 1: Carga del audio (`audio_loader.py`)

- **librosa** carga el audio como array numpy (mono, sample rate nativo)
- **mutagen** extrae metadatos: bitrate declarado, formato, duración, tags ID3/Vorbis
- Pre-validación de MP3: verifica estructura del archivo para prevenir crashes SIGBUS con archivos corruptos

## Etapa 2: Detección de corte (`frequency_detector.py`)

El corazón del algoritmo. Usa **dos métodos independientes** y una lógica de decisión que combina sus resultados:

1. **Método primario**: [Detección por transición](deteccion-transicion.md) — busca la primera transición de contenido musical a ruido/silencio
2. **Método secundario**: [Análisis por segmentos](analisis-segmentos.md) — divide el audio en 50 segmentos temporales y calcula el corte predominante
3. **Lógica de decisión**: [Combinación de métodos](logica-decision.md) — decide cuál usar según confianza, concordancia y patrones

Después de determinar el corte, se aplica la [verificación de brickwall](brickwall-vs-rolloff.md) para distinguir cortes artificiales de codec del rolloff natural.

## Etapa 3: Clasificación (`bitrate_classifier.py`)

Con la frecuencia de corte detectada, clasifica la calidad real:

| Corte detectado | Calidad real estimada |
|----------------|----------------------|
| > 20.5 kHz | Lossless |
| 19.5 - 20.5 kHz | 320 kbps |
| 18.5 - 19.5 kHz | 256 kbps |
| 17.0 - 18.5 kHz | 192 kbps |
| 16.0 - 17.0 kHz | 160 kbps |
| 15.0 - 16.0 kHz | 128 kbps |
| 13.0 - 15.0 kHz | 96 kbps |
| < 13.0 kHz | Baja calidad |

Luego compara con el bitrate declarado para emitir un **estado**:
- **OK**: coincide y corte ≥ 18 kHz
- **Baja calidad**: coincide pero corte < 18 kHz (archivo genuino pero pobre)
- **Transcode detectado**: calidad real muy inferior a la declarada
- **Lossless**: calidad de nivel lossless
- **Incierto**: confianza insuficiente

### Red de seguridad MP3

Un MP3 de 128 kbps **físicamente no puede** tener contenido real por encima de ~17 kHz (límite del codec LAME). Si el algoritmo detecta un corte superior, se limita al máximo físico del bitrate declarado. Esto previene falsos "OK" en transcodes con ruido residual.

## Flujo de datos

```
audio_file → audio_loader → (samples, metadata)
                                ↓
                        frequency_detector → (cutoff_hz, confidence)
                                ↓
                        bitrate_classifier → (quality, status, detected_bitrate)
                                ↓
                          AnalysisResult
```

El `AnalysisResult` contiene todos los datos del análisis. El campo `frequency_analysis` (con el espectrograma completo, ~100-200MB) es transitorio y se libera después de cachearse a disco. Ver [Caché de espectrogramas](../arquitectura/cache-espectrogramas.md).
