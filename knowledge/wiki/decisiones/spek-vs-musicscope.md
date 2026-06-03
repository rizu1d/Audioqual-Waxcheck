---
title: "Decisión: Spek vs MusicScope como referencia"
created: 2026-04-27
updated: 2026-06-03
sources: [MEJORAS_EN_ALGORITMO.txt]
tags: [decision, herramientas, tfg]
---

# Decisión: Spek vs MusicScope como referencia

## Contexto

Hasta febrero 2026, usábamos **Spek** como herramienta de referencia visual para validar los resultados del algoritmo. Spek es un analizador de espectro libre y ampliamente usado en la comunidad de audio.

## El descubrimiento

En abril 2026, durante la investigación de falsos positivos (cluster-4), descubrimos que **Spek engaña**:

- Spek usa un colormap que crea **fronteras visuales artificiales** en las transiciones de -70 a -75 dB
- La transición de color azul→negro hace que parezca que el contenido "se corta" cuando en realidad simplemente baja de nivel
- **MusicScope** (Linear Frequency Spectrum) muestra la realidad: hay contenido musical real por encima de esas frecuencias

### Ejemplo concreto: Future (MP3 320kbps)

| Herramienta | Lo que mostraba | Interpretación |
|-------------|-----------------|----------------|
| Spek | Corte aparente a ~17-18 kHz | "Parece transcode de 192 kbps" |
| MusicScope | Contenido >-60 dB hasta 17.5 kHz, rolloff gradual | "MP3 legítimo con rolloff natural" |

## Decisión

MusicScope (Linear Frequency Spectrum) se convirtió en la **referencia definitiva** para determinar la verdad sobre un archivo. Spek sigue siendo útil para una primera impresión visual, pero sus conclusiones deben contrastarse.

## Implicaciones

1. Varios archivos que creíamos "conocer" habían sido mal clasificados por suposiciones basadas en Spek
2. El algoritmo necesitaba una función de verificación que fuera más allá de lo que Spek podía mostrar
3. Se desarrolló `compute_band_peak_energy()` para replicar lo que MusicScope muestra
4. Se revisaron todos los casos de test con MusicScope como referencia

## Lección

Las herramientas de visualización tienen sesgos inherentes (colormap, escalas, promedios). Nunca confiar en una sola herramienta visual para decisiones de clasificación.

## Técnicas de inspección manual con MusicScope

Dos reglas visuales útiles cuando se valida un archivo a ojo (sesión de análisis 2026-06-03):

### 1. Variabilidad temporal del muro

Un lowpass de codec es **constante en el tiempo** (es una propiedad fija del bitrate). Por tanto:

> Si un "muro" en, p. ej., 16 kHz **aparece y desaparece** según avanza el tema (presente en una intro tranquila, ausente en el drop), **no es un corte de codec** — es simplemente ausencia/presencia de contenido musical agudo.

Para confirmarlo: comparar la intro con el **clímax/drop** (máxima energía de agudos). Un transcode mantiene el muro clavado en el clímax; un real lo "abre". Es la versión visual de la [varianza temporal post-corte](../algoritmo/brickwall-vs-rolloff.md) que el algoritmo ya mide.

### 2. Suelo de ruido hasta Nyquist

> Un lossless conserva una alfombra de ruido tenue hasta los 22 kHz aunque no haya contenido musical; un lossy la trunca en seco en su corte.

Requiere **subir la sensibilidad** del display para verlo (el suelo está a ~−93 dBFS). Ver [suelo de ruido hasta Nyquist](../algoritmo/suelo-ruido-nyquist.md) para la base física y las excepciones.
