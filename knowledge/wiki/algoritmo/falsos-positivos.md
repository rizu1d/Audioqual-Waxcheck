---
title: Casos de falsos positivos y soluciones
created: 2026-04-27
updated: 2026-04-27
sources: [MEJORAS_EN_ALGORITMO.txt]
tags: [algoritmo, falsos-positivos, tfg]
---

# Falsos positivos: casos estudiados y soluciones

Los falsos positivos — archivos legítimos marcados incorrectamente como transcode — han sido el mayor reto de calibración del algoritmo. Este documento recoge los casos estudiados, sus causas raíz y las soluciones aplicadas.

## Taxonomía de falsos positivos

### 1. Rolloff natural de mezcla
**Archivos**: Future, Summerbreeze, Plaisir de France
**Síntoma**: contenido frecuencial que decae gradualmente en agudos
**Causa**: el algoritmo detectaba la caída como un cutoff de codec
**Solución**: [verificación de brickwall](brickwall-vs-rolloff.md) — si no hay gradiente ≥ 9 dB/kHz, es natural

### 2. Producción con poco contenido HF
**Archivos**: Space Rodeo
**Síntoma**: electro oldschool con contenido HF limitado naturalmente
**Causa**: armónicos escasos en altas frecuencias interpretados como ausencia de contenido
**Solución**: verificación de contenido persistente con peak energy

### 3. Archivos con pocas secciones activas
**Archivos**: Pirate Material (10.5% frames activos)
**Síntoma**: la media temporal enterraba el contenido real bajo el ruido de fondo
**Causa**: `compute_energy_per_frequency()` calculaba media de TODOS los frames, incluyendo silencios
**Solución**: `compute_band_peak_energy()` que usa max del mean por frame (coincide con lo que MusicScope muestra)

### 4. Archivos lossless con rolloff
**Archivos**: notaiff-detected, notaiff-undetected
**Síntoma**: archivos AIFF lossless marcados como transcode
**Causa**: rolloff natural en el mastering original
**Solución**: verificación brickwall + umbral adaptativo por frecuencia

## Casos verificados como transcodes reales

Estos archivos fueron correctamente detectados y sirven como controles:

| Archivo | Brickwall | Gradiente | Varianza post | Notas |
|---------|-----------|-----------|---------------|-------|
| Manu Chao | 13-14 kHz | 11.9 dB/kHz | 0.02 | Caso clásico, silencio total post-corte |
| Portishead | 13-14 kHz | 9.8 dB/kHz | 0.15 | Gradiente justo por encima del umbral |
| Sicko Mode | 16-17 kHz | — | — | Artefactos de ruido post-brickwall (energía alta, varianza baja) |
| The Box | 15-16 kHz | 2.9 dB/kHz (media) | — | Brickwall en peak pero rolloff gradual en media |

## Capas de protección contra falsos positivos

El algoritmo tiene múltiples capas de seguridad:

1. **Umbral de varianza dependiente de frecuencia**: evita detecciones en zona de rolloff natural HF
2. **Guarda HF (18+ kHz)**: desactiva lookahead en las últimas bandas
3. **Protección anti-sibilancia**: exige 2+ bandas consecutivas para "recuperación"
4. **Red de seguridad MP3**: caps cutoff al máximo físico del bitrate
5. **Verificación brickwall (is_natural_rolloff)**: última línea de defensa post-detección
6. **detect_transcode() bidireccional**: gap de +2 para evitar clasificaciones erróneas

## Lecciones para el TFG

- El overfitting es un riesgo real: ajustar umbrales para un archivo específico puede romper otros
- Las reglas deben basarse en **principios físicos** (cómo funcionan los codecs), no en valores de archivos individuales
- "Known bug" es una respuesta honesta cuando un caso es genuinamente ambiguo
- El test suite (93 tests) fue crítico para iterar sin regresiones
