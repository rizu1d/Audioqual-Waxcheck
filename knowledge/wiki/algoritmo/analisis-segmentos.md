---
title: Método secundario — Análisis por segmentos temporales
created: 2026-04-27
updated: 2026-04-27
sources: [ALGORITMO.txt]
tags: [algoritmo]
---

# Método secundario: Análisis por segmentos temporales

Implementado en `frequency_detector.py → find_segment_cutoffs()` + `calculate_predominant_cutoff()`.

En vez de analizar todo el audio junto, lo divide en **50 segmentos temporales** y obtiene un cutoff por segmento. Esto lo hace más robusto para archivos con secciones silenciosas o con calidad variable a lo largo del tiempo.

## Procedimiento

1. Dividir el audio en 50 segmentos temporales
2. Cada segmento se analiza independientemente (método de energía relativa)
3. Se obtienen 50 valores de corte
4. Se usa el **percentil 90** como corte "predominante" (ignora el 10% superior: picos, silencios, anomalías)
5. Si hay gran diferencia entre el máximo y el percentil (> 3 kHz), se marca como **"tiene outliers"** (distribución bimodal)

## Cuándo es útil

- Archivos con secciones de silencio prolongado (intros, outros largas)
- Archivos con calidad variable (sampleo de radio, compilaciones)
- Como contraste del método primario para aumentar confianza cuando ambos coinciden

## Indicador de outliers

La detección de distribución bimodal es importante para la [lógica de decisión](logica-decision.md): indica que el archivo tiene zonas con contenidos frecuenciales muy diferentes, lo cual puede apuntar a una "meseta de ruido" entre el contenido real y el silencio.

## Relación con el método primario

Este método tiende a dar cortes **más altos** que el de transición en archivos transcodeados, porque el ruido residual post-corte engaña a los segmentos individuales haciéndoles ver un corte más alto. Por eso, cuando la transición da un corte más bajo que los segmentos, es firma de transcode (ver [lógica de decisión](logica-decision.md)).
