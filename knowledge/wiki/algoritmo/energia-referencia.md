---
title: Referencia de niveles de energía
created: 2026-04-27
updated: 2026-04-27
sources: [ALGORITMO.txt, MEJORAS_EN_ALGORITMO.txt]
tags: [algoritmo]
---

# Referencia de niveles de energía

Valores de energía (dB) del espectrograma y su significado.

## Escala general

| Nivel (dB) | Significado |
|------------|-------------|
| -40 y arriba | Contenido con buena presencia |
| -50 a -60 | Contenido audible, frecuencias altas típicas |
| -60 a -70 | Contenido muy tenue, armónicos débiles |
| -70 a -75 | Zona gris, probablemente artefactos en alta frecuencia |
| -75 y abajo | Ruido / piso de ruido, no es contenido musical útil |
| -80 | Silencio efectivo (piso de ruido del formato MP3) |

## Relevancia para la detección

- **Spek**: su colormap hace transición azul→negro justo en la zona -70 a -75 dB, creando fronteras visuales artificiales
- **MusicScope**: muestra la energía real sin distorsiones de color
- **top_db=80 de librosa**: recorta todo por debajo de -80 dB. En archivos con pocas secciones activas, esto aplana las bandas HF al mismo nivel

## Energía media vs peak

- **Energía media** (mean across all frames): refleja el "nivel sostenido" del contenido. Archivos con pocas secciones activas (ej: 10% de frames) tienen su contenido real enterrado ~10 dB por debajo de lo que MusicScope muestra.
- **Peak energy** (max of mean per frame): coincide con MusicScope. Captura contenido real incluso en archivos con pocos frames activos. Se usa para la verificación de [brickwall](brickwall-vs-rolloff.md).

## Umbrales del algoritmo

| Umbral | Valor | Uso |
|--------|-------|-----|
| Caída de energía "brickwall" | ≥ 8 dB entre bandas | Detección de corte de codec |
| Caída acumulada | ≥ 12 dB en 3 bandas | Detección de rolloff gradual |
| Gradiente brickwall | ≥ 9.0 dB/kHz | Verificación de brickwall |
| Contenido elevado (HF) | > -76 dB | Verificación rolloff natural (≥17kHz) |
| Contenido elevado (estándar) | > -70 dB | Verificación rolloff natural (<17kHz) |
| Override de brickwall | > -65 dB, ≥4 bandas | Override en peak brickwall |
