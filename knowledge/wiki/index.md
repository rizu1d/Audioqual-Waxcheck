---
title: Índice del Wiki AudioQual
created: 2026-04-27
updated: 2026-06-01
---

# AudioQual Wiki — Índice

## Algoritmo de detección

- [Principio fundamental](algoritmo/principio-fundamental.md) — Base física: filtros pasa-bajos de codecs y detección de transcodes
- [Pipeline de análisis](algoritmo/pipeline-analisis.md) — Las 3 etapas: carga, detección de corte, clasificación
- [Detección por transición](algoritmo/deteccion-transicion.md) — Método primario: buscar transición musical→ruido (varianza temporal)
- [Análisis por segmentos](algoritmo/analisis-segmentos.md) — Método secundario: 50 segmentos temporales, percentil 90
- [Lógica de decisión](algoritmo/logica-decision.md) — Cómo se combinan ambos métodos
- [Brickwall vs rolloff natural](algoritmo/brickwall-vs-rolloff.md) — Verificación post-detección: gradiente + varianza
- [Falsos positivos](algoritmo/falsos-positivos.md) — Casos estudiados, taxonomía y capas de protección
- [Referencia de energía](algoritmo/energia-referencia.md) — Escala de dB, umbrales, media vs peak

## Arquitectura

- [Stack tecnológico](arquitectura/stack-tecnologico.md) — Python, customtkinter, librosa, dependencias
- [Threading y macOS](arquitectura/threading-macos.md) — Event loop Cocoa, pipe+kqueue, 3 capas de callbacks
- [Caché de espectrogramas](arquitectura/cache-espectrogramas.md) — 3 niveles: efímero, disco, LRU en memoria
- [Sistema de verificación](arquitectura/sistema-verificacion.md) — Tests con 32 archivos reales, 3 capas de checks
- [Distribución](arquitectura/distribucion.md) — PyInstaller, tamaños, problemas pendientes

## Fuentes externas

- [Tutorial MPEG compression (Pan, 1995)](fuentes/tutorial-mpeg-compression.md) — Paper fundacional sobre compresión MP3
- [Enlaces recopilados](fuentes/enlaces-recopilados.md) — IEEE, EBU, Reddit, herramientas + fuentes pendientes
- [Herramientas de referencia](fuentes/herramientas-referencia.md) — Spek, MusicScope, librosa, mutagen

## Decisiones de diseño

- [Spek vs MusicScope](decisiones/spek-vs-musicscope.md) — Por qué MusicScope es la referencia definitiva
- [No virtual scroll](decisiones/no-virtual-scroll.md) — Por qué el intento de virtualización falló
- [Investigación cluster-4](decisiones/investigacion-cluster4.md) — Proceso de 5 iteraciones para resolver falsos positivos
- [PollingObserver](decisiones/polling-observer.md) — Por qué no FSEventsObserver (bug Unicode macOS)
- [Medición de CPU](decisiones/medicion-cpu.md) — Cómo medir rendimiento: powermetrics vs ps, wakeups, verdicto de R3
- [Desarrollo con LLM](decisiones/desarrollo-con-llm.md) — Modelo de trabajo humano + Claude Code

## Cronología

- [Log del proyecto](log.md) — Historia completa desde el primer commit (28 enero 2026)
