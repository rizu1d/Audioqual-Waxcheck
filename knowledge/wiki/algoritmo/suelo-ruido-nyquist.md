---
title: Suelo de ruido hasta Nyquist
created: 2026-06-03
updated: 2026-06-03
sources: [tonmeister-high-res-noise, romi-transcodes-spectral, robust-lossy-identification-koops]
tags: [algoritmo, codec, brickwall, herramientas, tfg]
---

# Suelo de ruido hasta Nyquist

Criterio de discriminación lossless vs. lossy complementario al de [brickwall vs. rolloff](brickwall-vs-rolloff.md). Surgió de una sesión de análisis manual con MusicScope (2026-06-03) y se confirmó con fuentes técnicas externas. **Aún no implementado en código** — por ahora es un criterio de inspección manual y una vía de mejora futura del algoritmo.

## El principio

> Un lossless genuino conserva una **alfombra de ruido de banda ancha que se extiende hasta Nyquist** (el borde del espectro). Un lossy la **trunca en seco** en su frecuencia de corte.

La clave es que **no depende del contenido musical**. Aunque la música muera en 13 kHz (producción oscura, ambient, sub-bajos), en un lossless **siempre** hay "algo" por encima: el suelo de ruido del propio formato. En un lossy, por encima del lowpass no hay ni eso.

## Base física: el dither

Todo PCM correctamente *dithered* lleva un **dither TPDF** (Triangular Probability Density Function), que es **ruido blanco** — energía igual por banda — repartido de 0 Hz hasta Nyquist. Para 16 bits su nivel es:

```
6.02 × bits − 3 dB  =  6.02 × 16 − 3  ≈  −93 dBFS
```

Ese ruido es el "papel de fondo" del formato: existe para evitar la distorsión de cuantización al truncar bits, y por construcción ocupa **todo el ancho de banda** hasta el techo de Nyquist (22.05 kHz a 44.1 kHz). No es contenido musical; es una propiedad del contenedor PCM.

A esto se suman el ruido térmico/electrónico del ADC y el aire de la sala en cualquier grabación real — también de banda ancha. **Nunca hay silencio digital perfecto en los agudos de un lossless.**

### Refuerzo: noise shaping

El *noise shaping* (dither con forma espectral) **empuja deliberadamente el ruido hacia los agudos** (por encima de ~15 kHz) para sacarlo de la zona más audible. En muchos másters modernos esto **realza** la alfombra de ruido en la región alta del espectro — justo donde miramos. Es decir, el tell tiende a ser **más** visible, no menos.

## Por qué el lossy lo destruye

El lowpass del codec descarta todas las líneas frecuenciales por encima de su corte para ahorrar bits (ver [principio fundamental](principio-fundamental.md)). Eso elimina también el dither/ruido que hubiera ahí. El resultado es un **shelf** o corte plano seguido de vacío, en una frecuencia **estándar y fija** según bitrate.

| | Lossless genuino | Lossy / transcode |
|---|---|---|
| Forma del final | Decaimiento orgánico | Brickwall / shelf recto |
| Frecuencia del corte | Difusa, variable | Fija y estándar (16/18/19/20.5 kHz) |
| **Por encima del corte** | **Alfombra de ruido hasta 22 kHz** | **Vacío / silencio muerto** |
| Consistencia temporal | El "muro" aparece/desaparece con el contenido | Muro constante todo el tema |

## Matices y excepciones (importante)

El tell es robusto pero **no absoluto**. Hay que enunciarlo con rigor:

1. **Visibilidad ≠ existencia.** A −93 dBFS el suelo puede caer **por debajo del rango visible** del analizador. Hay que **subir la sensibilidad** de MusicScope para verlo. "No lo veo" ≠ "no está".
2. **Lowpass de mastering legítimo.** Un ingeniero puede aplicar un lowpass o denoising agresivo en agudos por decisión artística. Un corte limpio **puede** existir sin ser transcode — coincide con el aviso de que "los archivos lossless pueden tener cortes".
3. **No es prueba en sentido inverso.** Tener ruido/contenido en agudos **no garantiza** lossless: se puede inyectar ruido o hacer upsampling para falsear el espectro (ver [ficha del paper de Koops](../fuentes/robust-lossy-identification-koops.md)).
4. **Lossy no siempre deja silencio absoluto** — deja su propio ruido de cuantización, pero **truncado en seco** en el lowpass. El discriminante es la **forma** (alfombra que llega a Nyquist vs. shelf cortado), no la mera presencia de energía.

## Relación con la varianza temporal

Este criterio y el de [varianza temporal post-corte](brickwall-vs-rolloff.md) miran lo mismo desde dos ángulos:

- **Varianza temporal**: la zona post-corte de un codec está *muerta en el tiempo* (no fluctúa frame a frame). Ya implementado.
- **Suelo de ruido hasta Nyquist**: la zona post-corte de un lossless tiene *estructura de ruido de banda ancha*. No implementado aún.

Ambos formalizan que un lowpass de codec es una frontera artificial y estática, mientras que el borde de un lossless es difuso y "vivo".

## Vía de mejora futura

Una métrica candidata: medir si existe energía de ruido coherente y de banda ancha en la región `[cutoff, Nyquist]` por encima de un umbral mínimo. Si hay alfombra → refuerza "lossless"; si hay vacío plano → refuerza "lossy". Encajaría como capa adicional en `is_natural_rolloff()`. **Aplazado** mientras la prioridad sea el peso del bundle; documentado aquí para no perder el hallazgo.

## Relevancia para el TFG

Conecta el teorema de cuantización (dither, TPDF, relación bits→ruido) con la detección práctica de transcodes. Sección del TFG: **Marco teórico** (junto al [tutorial MPEG](../fuentes/tutorial-mpeg-compression.md)) y **Trabajo futuro** (la métrica no implementada).
