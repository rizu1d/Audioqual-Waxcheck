---
title: "Robust Lossy Audio Compression Identification (Koops et al., 2024)"
created: 2026-06-03
updated: 2026-06-03
sources: [arxiv-2407.21545]
tags: [codec, algoritmo, tfg]
---

# Robust Lossy Audio Compression Identification

**Autor principal**: Hendrik Vincent Koops et al.
**Publicación**: arXiv:2407.21545 (2024)
**Enlace**: [arxiv.org/html/2407.21545v1](https://arxiv.org/html/2407.21545v1)
**Ubicación local**: `sources/Koops_2024_Robust_Lossy_Audio_Compression_Identification_arXiv-2407.21545.pdf`

## Resumen

Estudia por qué los detectores de compresión lossy basados en aprendizaje automático reportan precisión casi perfecta en su test set pero **se hunden cuando cambian los parámetros del codec** (cortes no vistos en entrenamiento). Propone una técnica de entrenamiento para generalizar mejor.

## Método

- **Entrada**: 2 s de audio mono 44.1 kHz → espectrograma de magnitud (FFT 1024).
- **Arquitectura**: CNN (4 bloques convolucionales) + BiLSTM (128 unidades, 2 capas) → clasificador binario lossy/lossless.
- **Datos**: 10.000 temas comerciales (WAV 16-bit). `ds1` con parámetros por defecto (mp3/AAC/Ogg a 128/256/320). `ds2` con cortes forzados variados (14/16/18/20 kHz).

## Hallazgo clave: el corte de frecuencia es una muleta frágil

| Modelo | Test | Precisión |
|--------|------|-----------|
| Naïve | ds1 (cortes vistos) | 99.79 % |
| Naïve | ds2 (cortes **no** vistos) | **63.7 %** (−70 pts en AAC) |
| Con *random masking* | ds2 | 98.4 % |

El modelo ingenuo aprende a usar **la frecuencia de corte como frontera de decisión**, y por eso falla con codecs/cortes nuevos. La solución (**random masking**: anular aleatoriamente las frecuencias por encima de un corte entre 14 kHz y Nyquist durante el entrenamiento) **oculta el corte a propósito**, forzando al modelo a fijarse en los **"agujeros espectrales"** que deja la cuantización psicoacústica — no en el borde del rolloff.

## El AAC es duro también para ellos

Incluso con la técnica robusta, el AAC (libfdk_aac) se resiste: **~81 %** a 14 kHz, porque "produce menos artefactos visibles" en el espectrograma. Coincide con el punto débil conocido de AudioQual (YouTube rips AAC→MP3, p. ej. el known bug `YT_012`).

## Utilidad para AudioQual

**No se integra** — es deep learning (CNN+LSTM), sin código publicado, y añadir una red neuronal va en contra de la [vigilancia de peso del bundle](../decisiones/limpieza-codigo-muerto-y-peso.md). Su valor es **conceptual y académico**:

1. **Valida el enfoque multi-señal y avisa de un riesgo.** Depender solo del cutoff es frágil (99.8 % → 63.7 %). Refuerza combinar gradiente + varianza temporal + suelo de ruido en lugar de "¿dónde corta?".
2. **Respalda el tell del [suelo de ruido hasta Nyquist](../algoritmo/suelo-ruido-nyquist.md).** Su *random masking* obliga al modelo a leer la **estructura del ruido y los huecos**, no el borde — la misma intuición, con aval revisado.
3. **Justifica la dificultad del AAC** con literatura: no es un fallo de nuestro algoritmo, es intrínseco al codec.

## Relevancia para el TFG

Cita primaria para **Estado del arte** (detección de compresión por ML) y para justificar dos decisiones de diseño: por qué no depender solo del corte, y por qué el AAC/doble-encoding es el caso difícil. Sección: **Estado del arte / Discusión**.
