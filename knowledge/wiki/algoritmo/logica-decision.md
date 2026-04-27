---
title: Lógica de decisión — Combinación de métodos
created: 2026-04-27
updated: 2026-04-27
sources: [ALGORITMO.txt]
tags: [algoritmo]
---

# Lógica de decisión: Combinación de métodos

Implementada en `frequency_detector.py → analyze_frequency_cutoff()`. Recibe los resultados de ambos métodos ([transición](deteccion-transicion.md) y [segmentos](analisis-segmentos.md)) y decide cuál usar.

## Reglas de decisión (en orden de prioridad)

### 1. Transición con alta confianza (≥ 70%)

Normalmente se usa la transición. **Excepción (meseta de ruido)**: si los segmentos dan un corte mucho más bajo (gap > 2 kHz) Y detectaron distribución bimodal (outliers) Y tienen confianza ≥ 60%, se **verifica** que las bandas entre ambos cortes realmente carezcan de contenido musical (varianza por debajo del umbral dependiente de frecuencia).

- Si se confirma la meseta → se prefieren los segmentos
- Si las bandas intermedias tienen varianza musical → la transición se mantiene

Razón: la transición puede estar viendo la transición ruido→silencio en vez de música→ruido cuando hay una "meseta" de ruido plano. La verificación evita falsos positivos en grabaciones antiguas con contenido genuino en altas frecuencias (caso LaTour).

### 2. Ambos métodos coinciden (diferencia < 2 kHz)

Se promedian y se aumenta la confianza. Cuando los dos métodos independientes coinciden, la certeza es mayor.

### 3. Transición más baja que segmentos (con confianza ≥ 50%)

Se prefiere la transición (más conservador). Si el gap es ≥ 1 kHz, se aplica un boost de confianza (hasta +0.15) porque este patrón — transición < segmentos — es **firma de transcode**: el contenido real termina en la transición, pero el ruido residual engaña a los segmentos haciéndoles ver un corte más alto.

### 4. Cualquier otro caso

Se usa el método de segmentos como fallback.

## Post-procesamiento

Después de esta lógica, se aplica la [verificación de brickwall](brickwall-vs-rolloff.md) como último filtro antes de pasar al clasificador.
