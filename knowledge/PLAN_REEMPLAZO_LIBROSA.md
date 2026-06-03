# Plan: reemplazar librosa (objetivo de peso −110 a −130 MB)

> Estado: **plan, sin implementar.** Redactado el 2026-06-03 tras los recortes baratos
> (Pillow + strip, 211 → 202 MB). Es el mayor objetivo de peso pendiente.
> Contexto en `knowledge/wiki/decisiones/limpieza-codigo-muerto-y-peso.md` §"Fuera de alcance".

## Por qué

En el build de macOS (202 MB), la cadena **librosa → numba → llvmlite** domina el bundle:
`llvmlite/binding` ≈ **110 MB (~52 %)**, más numba (~25 MB) y parte de scipy. Verificado:
**numba/llvmlite NO se usan en ningún sitio del repo fuera de librosa** (0 imports directos), así
que quitar librosa elimina toda la cadena. No se puede excluir numba/llvmlite manteniendo librosa:
`import librosa` los exige al cargar.

Estimación: bundle 202 MB → **~70-90 MB** según qué decoder se elija para m4a/aac/wma.

## Inventario exacto de usos de librosa (4 call sites)

| Archivo | Llamada | Dificultad |
|---|---|---|
| `frequency_detector.py:84` | `librosa.stft(samples, n_fft, hop_length)` | **Trivial** (verificado bit-exacto) |
| `frequency_detector.py:88` | `librosa.amplitude_to_db(magnitude, ref=np.max)` | **Trivial** (verificado bit-exacto) |
| `frequency_detector.py:91` | `librosa.fft_frequencies(sr, n_fft)` | **Trivial** (verificado bit-exacto) |
| `audio_loader.py:204` (`_load_with_librosa`) | `librosa.load(path, sr, mono=True)` | **BLOQUEO** (solo m4a/aac/wma) |
| `audio_player.py:162` | `librosa.load(path, sr, mono=True)` | mismo bloqueo |

`audio_loader.py:235` y `:238` llaman a `_load_with_librosa`. La ruta rápida ya usa **soundfile**
(libsndfile 1.2.2), que en este entorno soporta **wav/flac/ogg/aiff/mp3**. Solo quedan fuera de
soundfile: **m4a, aac, wma** (3 de los 9 formatos de `SUPPORTED_FORMATS`).

## Fase 1 — Reemplazos espectrales (RIESGO BAJO, hacer primero)

Los tres se han verificado **bit a bit** contra librosa 0.11 con ruido sintético (diff máx **0.0**).
Código probado, listo para pegar en `frequency_detector.py` (sustituye `compute_spectrogram`):

```python
import numpy as np
from scipy.signal import get_window

def _stft_magnitude(samples, n_fft, hop_length):
    # Equivalente bit-exacto a np.abs(librosa.stft(...)) en librosa 0.11:
    # ventana Hann periódica (fftbins=True), center=True con pad de ZEROS
    # (pad_mode='constant', que es el default de librosa >= 0.10), rfft.
    win = get_window('hann', n_fft, fftbins=True).astype(np.float32)
    pad = n_fft // 2
    yp = np.pad(samples, pad, mode='constant')          # <-- 'constant', NO 'reflect'
    n_frames = 1 + (len(yp) - n_fft) // hop_length
    idx = np.arange(n_fft)[:, None] + hop_length * np.arange(n_frames)[None, :]
    frames = yp[idx] * win[:, None]
    return np.abs(np.fft.rfft(frames, n=n_fft, axis=0)).astype(np.float32)

def _amplitude_to_db_refmax(magnitude, amin=1e-5, top_db=80.0):
    # Equivalente bit-exacto a librosa.amplitude_to_db(magnitude, ref=np.max).
    mag = np.abs(magnitude)
    ref_power = mag.max() ** 2
    power = mag ** 2
    db = 10.0 * np.log10(np.maximum(amin**2, power)) \
       - 10.0 * np.log10(np.maximum(amin**2, ref_power))
    return np.maximum(db, db.max() - top_db).astype(np.float32)

def compute_spectrogram(samples, sample_rate, n_fft, hop_length):
    magnitude = _stft_magnitude(samples, n_fft, hop_length)
    spectrogram_db = _amplitude_to_db_refmax(magnitude)
    frequencies = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)   # == librosa.fft_frequencies
    return spectrogram_db, frequencies
```

**OJO con el pad:** un primer intento con `mode='reflect'` daba diff 48.9 (los bordes). librosa 0.11
usa `pad_mode='constant'`. Si en algún momento se actualiza librosa para la comparación, re-verificar
el default. (`librosa.stft` con `center=False` evitaría el pad pero cambia el nº de frames → NO usar.)

**Verificación Fase 1:** correr `bash tests/full_check.sh` — la suite de detección debe quedar
**idéntica** (mismos cutoffs en los 32 archivos). Adicional recomendado: harness que compare
`compute_spectrogram` nuevo vs librosa sobre los 32 archivos reales y asserte diff < 1e-3 en el
`spectrogram_db` y cutoff idéntico (la prueba sintética ya dio 0.0, pero validar con audio real).

## Fase 2 — Carga de audio (EL BLOQUEO: m4a/aac/wma)

`librosa.load` internamente intenta soundfile y, si falla, cae a **audioread**, que usa el decoder
nativo del SO (CoreAudio en macOS, Media Foundation en Windows, gstreamer/ffmpeg en Linux). Nosotros
ya tenemos la ruta soundfile; solo hay que sustituir el *fallback* para m4a/aac/wma.

### Opción recomendada: `audioread` directo (peso ~0)

Replicar lo que librosa ya hace, sin el resto de librosa. `audioread` es **Python puro (~50 KB)**,
sin numba/llvmlite. Usa los decoders nativos del SO:
- **macOS:** CoreAudio (vía ctypes) → m4a/aac OK. **WMA: no nativo** (rara vez en macOS).
- **Windows:** Media Foundation → m4a/aac/wma OK.
- **Linux:** gstreamer **o** ffmpeg CLI. ← **PUNTO A INVESTIGAR**: el AppImage tendría que
  empaquetar ffmpeg/gstreamer o documentar la dependencia de sistema. Es el mayor riesgo del plan.

Esbozo (`audio_loader.py`, sustituye `_load_with_librosa`):

```python
def _load_with_audioread(filepath, target_sr):
    import audioread
    with audioread.audio_open(filepath) as f:
        sr_native, channels = f.samplerate, f.channels
        buf = b"".join(f.read_data())
    samples = np.frombuffer(buf, dtype="<i2").astype(np.float32) / 32768.0  # int16 -> [-1,1)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)               # downmix a mono
    if sr_native != target_sr:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(target_sr, sr_native)
        samples = resample_poly(samples, target_sr // g, sr_native // g).astype(np.float32)
    return samples, target_sr
```

**Paridad de muestras (crítico para no mover cutoffs):**
- librosa normaliza int16 dividiendo por 32768 y hace mono por **media** de canales → replicado arriba.
- **Resampler:** librosa.load 0.10+ resamplea con **`soxr_hq`**, no con `resample_poly`. La ruta
  soundfile actual ya usa `resample_poly`, así que ya hay una pequeña divergencia entre rutas. Para
  m4a/aac/wma, cambiar de soxr a resample_poly **puede mover el cutoff unas décimas de kHz**.
  Mitigación barata: mantener la dep **`soxr`** (lib pequeña, ~1-2 MB, sin numba) y resamplear con
  `soxr.resample` para paridad exacta. Decidir en implementación tras medir el delta de cutoff.

### Opción alternativa (si audioread no es fiable cross-OS): PyAV

`av` (bindings de ffmpeg) decodifica m4a/aac/wma en los 3 SO sin depender de tooling del sistema.
Coste: ~40-60 MB de libs ffmpeg en el bundle. Aun así el neto sería **−80 a −95 MB** (quitas ~130,
añades ~50). Licencia ffmpeg LGPL OK con linking dinámico. Más pesado pero el más robusto y uniforme.

### Opción C: decoders nativos por SO vía ctypes (peso 0, complejidad alta)

CoreAudio (macOS) / Media Foundation (Windows) / gstreamer (Linux) directos. Cero peso pero 3
implementaciones y WMA-en-macOS sigue sin estar. Solo si las otras dos no convencen.

## Orden de implementación

1. **Fase 1** (espectral) en `frequency_detector.py`; quitar `import librosa`; `full_check` → debe
   quedar idéntico. *Esta fase sola ya es segura y desbloquea casi todo el algoritmo.*
2. **Fase 2** (carga) en `audio_loader.py` (`_load_with_audioread`) y `audio_player.py`; quitar
   `import librosa`. Validar paridad de samples y cutoff en m4a/aac/wma reales (old librosa.load vs
   nuevo) → cutoff idéntico (o decidir mantener `soxr`).
3. `requirements.txt`: quitar `librosa`, añadir `audioread` (y quizá `soxr`). Mantener `soundfile`,
   `scipy`, `numpy`, `mutagen`.
4. Specs: quitar `librosa` de `hiddenimports` de los 3; añadir `numba`/`llvmlite` a `excludes` como
   cinturón-y-tirantes (no deberían recogerse ya sin librosa). Añadir `audioread` a `hiddenimports`.
5. **Build en los 3 SO vía CI**, medir tamaño, y **validar la carga de m4a/aac/wma en cada SO**
   (especialmente Linux/AppImage: confirmar que audioread encuentra backend, o bundlear ffmpeg).

## Verificación end-to-end (gate antes de mergear)

- `bash tests/full_check.sh` sin regresiones (detección idéntica) tras Fase 1 **y** tras Fase 2.
- Comparación archivo-a-archivo del cutoff: corpus de los 32 tests + un set de m4a/aac/wma reales,
  cutoff con librosa (rama main) vs sin librosa (rama nueva) → diferencia 0 (o justificada y < 0.2 kHz).
- Arranque de la `.app`/exe/AppImage en los 3 SO y análisis real de un m4a, un aac y un wma.
- Medir el `.app`: confirmar que `llvmlite`/`numba` tienen **0 archivos** en el bundle.

## Riesgos

- **Linux + audioread** (backend de decodificación): el mayor riesgo. Resolver antes de comprometerse
  con la Opción A; si no hay solución limpia sin tooling de sistema, ir a PyAV.
- **Divergencia de resampler** (soxr vs resample_poly) moviendo cutoffs: medir y, si molesta, mantener
  `soxr`.
- Toca el núcleo de detección del TFG → hacer en rama aislada, no mergear sin el gate completo.
```
