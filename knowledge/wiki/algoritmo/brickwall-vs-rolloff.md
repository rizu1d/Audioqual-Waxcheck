---
title: Brickwall vs rolloff natural
created: 2026-04-27
updated: 2026-06-03
sources: [MEJORAS_EN_ALGORITMO.txt, ALGORITMO.txt]
tags: [algoritmo, brickwall, falsos-positivos, tfg]
---

# Brickwall vs rolloff natural

Implementado en `frequency_detector.py → is_natural_rolloff()` y `compute_band_peak_energy()`. Este sistema se añadió en abril 2026 (commits e4647df, 0f6330f) para resolver falsos positivos en archivos legítimos.

## El problema

El algoritmo de detección encontraba "cutoffs" donde la energía bajaba, pero **no distinguía** entre:
- Caídas **abruptas** de codec (brickwall) — un corte artificial
- Caídas **graduales** naturales (rolloff) — una decisión de mezcla/mastering
- Rolloff gradual de YouTube (doble encoding AAC→MP3) — técnicamente transcode pero sin brickwall

Esto causaba falsos positivos en archivos legítimos cuyo contenido frecuencial simplemente decaía naturalmente en los agudos.

## Filosofía

> "Solo penalizar los cortes de codec. Si un artista decide tener menos contenido frecuencial en sus agudos, no debería ser penalizado."

## Dos métricas discriminantes

El hallazgo clave: **gradiente + varianza temporal** combinadas discriminan con alta fiabilidad.

### Gradiente (dB/kHz en energía media)

| Tipo | Gradiente | Ejemplos |
|------|-----------|----------|
| Transcodes | > 9 dB/kHz | Manu Chao: 11.9, Portishead: 9.8 |
| Naturales | < 6.1 dB/kHz | Summerbreeze: 6.1 (máximo legítimo) |
| **Umbral** | **9.0 dB/kHz** | Margen de 2.9 dB/kHz |

### Varianza temporal post-corte

| Tipo | Varianza | Ejemplos |
|------|----------|----------|
| Transcodes | < 0.5 | Manu Chao: 0.02, Portishead: 0.15 |
| Naturales | > 0.3 en al menos algunas bandas | |
| **Umbral** | **0.5** | |

## Arquitectura de is_natural_rolloff()

Opera en 3 capas, de más definitivo a más permisivo:

### Capa 1: Brickwall en energía media
Busca gradiente ≥ 9 dB/kHz con varianza post-corte ≤ 0.5. Si se encuentra → corte de codec **definitivo** → return False.

### Capa 2: Brickwall en energía pico (solo < 17 kHz)
Busca el mismo patrón pero en peak energy. Si se encuentra → **posible** codec o transición natural. Override solo si ≥ 4 bandas con peak > -65 dB por encima del corte.

Regla: ningún codec real genera un brickwall detectable solo en peak energy por encima de 17 kHz.

### Capa 3: Verificación de contenido persistente
Sin brickwall encontrado. Verifica si la peak energy se mantiene elevada por encima del cutoff. Umbral adaptativo:
- Cutoffs ≥ 17 kHz: -76 dB (relajado, cualquier contenido es significativo cerca de Nyquist)
- Cutoffs < 17 kHz: -70 dB (estándar)
- Ratio mínimo: 50% de bandas deben estar elevadas

## Caso difícil: YouTube rips

Los YouTube rips (doble encoding AAC→MP3) crean rolloff gradual sin brickwall. Son el caso más difícil porque parecen rolloff natural pero son transcodes. La Capa 2 los captura: tienen como máximo 2 bandas con peak fuerte por encima del corte (insuficiente para el override de ≥ 4 bandas).

Known bug: `YT_012 (NTM Boogie Man)` — YouTube rip indistinguible de rolloff natural sin análisis de metadata.

## Evolución de la implementación

La función pasó por 5 iteraciones. Ver [Investigación falsos positivos cluster-4](../decisiones/investigacion-cluster4.md) para el proceso completo.

## Criterio complementario (no implementado)

La varianza temporal post-corte mira la zona del codec como *muerta en el tiempo*. Un ángulo complementario es el [suelo de ruido hasta Nyquist](suelo-ruido-nyquist.md): un lossless conserva alfombra de ruido de banda ancha hasta el borde del espectro; un lossy la trunca. Es una vía de mejora futura del algoritmo (medir energía de ruido en `[cutoff, Nyquist]`), por ahora solo criterio de inspección manual.

## Constantes (en `constants.py`)

```
BRICKWALL_MIN_GRADIENT_DB_PER_KHZ = 9.0
BRICKWALL_MAX_POST_VARIANCE = 0.5
BRICKWALL_ELEVATED_ENERGY_DB = -76.0
BRICKWALL_OVERRIDE_ENERGY_DB = -65.0
BRICKWALL_ELEVATED_RATIO = 0.5
```
