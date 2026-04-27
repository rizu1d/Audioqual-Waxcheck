---
title: Método primario — Detección por transición
created: 2026-04-27
updated: 2026-04-27
sources: [ALGORITMO.txt]
tags: [algoritmo, tfg]
---

# Método primario: Detección por transición

Implementado en `frequency_detector.py → find_cutoff_by_transition()`. Es el método primario de detección porque detecta directamente la firma de un codec: el punto donde el contenido musical termina y empieza el ruido.

## Concepto clave: varianza temporal

El contenido musical tiene **alta varianza temporal** — la energía sube y baja siguiendo la dinámica de la música. El ruido de codificación tiene **baja varianza** — energía constante y monótona.

Esta distinción es la base de la detección: recorrer las bandas de frecuencia buscando dónde la señal pasa de "musical" a "ruido".

## Procedimiento

1. Calcular espectrograma (STFT) del audio completo
2. Dividir el rango 10-21 kHz en bandas de 500 Hz
3. Para cada banda calcular:
   - Energía media (dB)
   - Varianza temporal (cuánto varía la energía entre frames)
4. Recorrer las bandas buscando la **primera transición** de musical a ruido

## Umbral de varianza dependiente de frecuencia

Una banda se considera "musical" si su varianza supera un umbral que varía con la frecuencia:

- A 14 kHz: varianza ≥ 0.30 (frecuencias bajas tienen más varianza naturalmente)
- A 20 kHz: varianza ≥ 0.15 (las altas frecuencias, especialmente en acapellas, tienen menos)
- Entre medias: interpolación lineal

Esta adaptación evita falsos positivos en contenido con poco contenido HF natural (acapellas, grabaciones antiguas).

## Cuatro mecanismos de detección de transición

Cualquiera puede disparar la detección:

### (a) Caída de energía ≥ 8 dB entre bandas adyacentes
El caso clásico de "brick-wall" de un codec MP3. Confianza base: 0.60, sube con la magnitud.

### (b) Transición de varianza musical → ruido
- Varianza post-banda cae por debajo del umbral musical de su frecuencia, O
- Varianza cae ≥ 35% entre bandas adyacentes, O
- Dos bandas más adelante la varianza < 0.20 (mirada anticipada)

**Guarda HF**: a partir de 18 kHz, el lookahead de 2 bandas se desactiva si la banda siguiente aún tiene varianza musical. Previene falsos positivos con el rolloff natural de las altas frecuencias.

Confianza base: 0.65.

### (c) Caída acumulada ≥ 12 dB en 3 bandas consecutivas
Detecta rolloffs graduales donde cada paso individual es < 8 dB. Confianza base: 0.60.

### (d) Decaimiento de varianza en ventana deslizante
Si la varianza cae ≥ 50% a lo largo de 3 bandas consecutivas, terminando por debajo de 0.25, con descenso monótono. Detecta rolloffs muy graduales como YouTube rips de acapellas. Confianza base: 0.60, máximo 0.85.

**Guarda HF**: misma protección que (b) a partir de 18 kHz.

## Protección anti-sibilancia

Antes de confirmar una transición, se verifica que la energía **no se recupere** después. Los sonidos sibilantes (S, T, CH) crean picos aislados de energía en altas frecuencias que podrían confundirse con contenido musical.

Para considerarlo "recuperación real", se exigen **2+ bandas consecutivas** con energía Y varianza ≥ 0.30.

## Fallback (Phase 2)

Si Phase 1 no encuentra ninguna transición (típico en archivos lossless o de muy alta calidad), Phase 2 usa un método de puntuación combinada energía+varianza como fallback.

## Niveles de confianza

| Detección | Confianza base |
|-----------|---------------|
| Caída de energía ≥ 8 dB | 0.60, sube con magnitud |
| Caída acumulada ≥ 12 dB | 0.60 |
| Transición de varianza | 0.65 |
| Decaimiento gradual | 0.60, máx 0.85 |
