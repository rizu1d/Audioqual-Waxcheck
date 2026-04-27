---
title: "Investigación: falsos positivos cluster-4"
created: 2026-04-27
updated: 2026-04-27
sources: [MEJORAS_EN_ALGORITMO.txt]
tags: [decision, falsos-positivos, algoritmo, tfg]
---

# Investigación: falsos positivos cluster-4

Documentación del proceso de investigación y resolución de los falsos positivos del cluster-4 (archivos legítimos con rolloff natural). Sesiones del 22-24 abril 2026.

## Enfoque metodológico

Se siguió un enfoque **cluster-by-cluster, zero-regression**: resolver un grupo de archivos relacionados antes de pasar al siguiente, verificando con la suite completa de tests que no se introduzcan regresiones.

## Los 10 archivos investigados con MusicScope

### Falsos positivos (legítimos marcados como transcode)

| Archivo | AudioQual decía | MusicScope mostró | Realidad |
|---------|----------------|-------------------|----------|
| Future (320kbps) | cutoff 18kHz → transcode 192 | contenido >-60dB hasta 17.5kHz | Rolloff natural, 4% frames activos |
| Space Rodeo (320kbps) | cutoff 14.5kHz → transcode 96 | armónicos naturales >15kHz | Electro oldschool, poco HF |
| Pirate Material (320kbps) | cutoff 10.5kHz → "low" | peak hasta 20kHz, 10.5% activos | Sampleo de radio, media engañaba |
| Summerbreeze (320kbps) | cutoff 18kHz → transcode 192 | contenido hasta 18.8kHz | Rolloff natural |
| notaiff-detected (AIFF) | cutoff 17kHz → transcode 192 | contenido real, sin brickwall | Lossless legítimo |
| notaiff-undetected (AIFF) | cutoff 16kHz → transcode 160 | contenido real, sin brickwall | Lossless legítimo |
| Plaisir de France (320kbps) | cutoff 16kHz → transcode 160 | rolloff natural | Mezcla del año 2002 |

### Transcodes reales (correctos, controles)

| Archivo | Brickwall | Gradiente | Varianza post |
|---------|-----------|-----------|---------------|
| Manu Chao | 13-14kHz | 11.9 dB/kHz | 0.02 |
| Portishead | 13-14kHz | 9.8 dB/kHz | 0.15 |
| Sicko Mode | 16-17kHz | — | artefactos post-brickwall |

## Las 5 iteraciones

### Iteración 1: verify_brickwall_signature() con peak energy
Overrideaba todos los cutoffs sin brickwall. Demasiado agresivo: rompió 47 tests. Los YouTube rips sin brickwall también quedaban exonerados.

### Iteración 2: is_natural_rolloff() con verificación de contenido
Añadió segundo requisito (contenido elevado por encima del cutoff). Umbral de -70dB no capturaba Future (-74.4dB) ni Summerbreeze (-70.1dB).

### Iteración 3: Energía media para brickwall + peak para contenido
Separó métricas. Portishead escapaba (gradiente 9.8, umbral era 10.0). Se bajó umbral a 9.0.

### Iteración 4: Doble escaneo (mean + peak brickwall)
Añadió peak brickwall para YouTube rips. Summerbreeze y notaiff-undetected tenían peak brickwall falso a ≥17kHz.

### Iteración 5 (final): Límite de frecuencia para peak brickwall
Ningún codec real genera brickwall solo en peak por encima de 17kHz. Se limitó la detección. Umbral de energía adaptativo (-76dB para cutoffs ≥17kHz).

**Resultado**: 93 tests, 83 pasan, 0 fallos, 10 known bugs.

## Hallazgos técnicos

1. **Energía media vs peak**: la media temporal no refleja archivos con pocas secciones activas. Peak energy (max del mean por frame) coincide con MusicScope.
2. **Gradiente + varianza**: estas dos métricas combinadas discriminan brickwall de rolloff natural con alta fiabilidad.
3. **Regla de los 17kHz**: ningún codec genera brickwall detectable solo en peak por encima de esta frecuencia.

## Caso Supadrug (investigación paralela)

Archivo MP3 320kbps analizado en profundidad para verificar si era transcode o legítimo. MusicScope confirmó: contenido real hasta 20kHz, 320kbps legítimo. Spek creaba la ilusión de un corte a ~17kHz. Ver [Spek vs MusicScope](spek-vs-musicscope.md).
