---
title: Sistema de caché de espectrogramas
created: 2026-04-27
updated: 2026-04-27
sources: [CACHE.txt]
tags: [cache, rendimiento, arquitectura]
---

# Sistema de caché de espectrogramas

## Problema

El análisis espectral genera una matriz de ~100-200 MB por archivo (float32, resolución STFT completa). Mantenerla en RAM para 30+ archivos es inviable (~6 GB). Sin caché, cada visualización requiere re-análisis completo (~2-3 segundos).

## Arquitectura: 3 niveles

### Nivel 1: Resultado fresco (efímero)
- Fuente: `AnalysisResult.frequency_analysis`
- Tamaño: ~100-200 MB por archivo
- Vida: se libera inmediatamente después de cachear a disco
- Es un paso transitorio, nunca se retiene

### Nivel 2: Caché de disco (~5 MB por archivo)
- Implementación: `src/utils/spectrogram_cache.py`
- Ubicación: `~/.audioqual/cache/<hash>.npz`
- Compresión: float32 → uint8 (256 niveles, pierde ~0.3 dB de precisión)
- Downsample: 1024 bins frecuencia × 4096 frames temporales
- Tiempo de carga: ~6-10 ms (vs ~2-3s de re-análisis)
- Se borra al cerrar la app

### Nivel 3: Caché LRU en memoria (máx. 10 entradas)
- Implementación: `app.py → self._spectrogram_cache` (OrderedDict)
- Tamaño: ~5 MB × 10 = ~50 MB máximo
- Para alternar entre archivos con la ventana de espectrograma abierta

## Flujo completo

```
Análisis → Nivel 1 (150MB) → cachear a disco → liberar Nivel 1
                                    ↓
Usuario selecciona archivo → Nivel 3 (hit?) → Nivel 2 (hit?) → re-análisis
                                                   ↓
                                            promover a Nivel 3
```

## Datos de tamaño en disco

- ~4.9 MB por archivo analizado
- 100 archivos → ~500 MB
- 400 archivos → ~2 GB
- Se limpia todo al cerrar la app
