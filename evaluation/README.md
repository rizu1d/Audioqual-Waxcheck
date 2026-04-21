# Sistema de Evaluacion Automatizado

Genera variantes de audio desde archivos lossless, las analiza con AudioAnalyzer y produce un informe visual de precision.

## Requisitos

- FFmpeg instalado y en el PATH
- Al menos 1 archivo WAV o FLAC en `originals/`

## Uso

```bash
# 1. Poner archivos lossless en originals/
cp ~/Music/track.wav evaluation/originals/

# 2. Generar variantes (11 por archivo fuente)
python3 evaluation/generate_dataset.py

# 3. Analizar variantes y producir CSV
python3 evaluation/evaluate.py

# 4. Generar informe HTML (se abre en navegador)
python3 evaluation/report.py
```

## Opciones

```bash
# Regenerar variantes existentes
python3 evaluation/generate_dataset.py --force

# Solo mostrar resumen (sin detalle por archivo)
python3 evaluation/evaluate.py --summary
```

## Variantes generadas

Por cada archivo fuente se generan 11 variantes:

| Tipo | Descripcion |
|------|-------------|
| legit_320k | MP3 320kbps directo desde lossless |
| legit_256k | MP3 256kbps directo desde lossless |
| legit_192k | MP3 192kbps directo desde lossless |
| legit_128k | MP3 128kbps directo desde lossless |
| legit_96k | MP3 96kbps directo desde lossless |
| transcode_128to320 | Lossless -> 128k -> 320k (upscale) |
| transcode_96to320 | Lossless -> 96k -> 320k (upscale) |
| transcode_128to256 | Lossless -> 128k -> 256k (upscale) |
| transcode_192to320 | Lossless -> 192k -> 320k (upscale) |
| transcode_yt_128to320 | Lossless -> AAC 128k -> MP3 320k (YouTube rip) |

## Estructura de archivos

```
evaluation/
  generate_dataset.py    # Genera variantes con FFmpeg
  evaluate.py            # Analiza con AudioAnalyzer, produce CSV
  report.py              # Genera informe HTML desde CSV
  README.md              # Este archivo
  originals/             # Archivos WAV/FLAC fuente (gitignored)
  dataset/               # Variantes generadas (gitignored)
    manifest.json
  results.csv            # Salida de evaluate.py (gitignored)
  report.html            # Salida de report.py (gitignored)
```
