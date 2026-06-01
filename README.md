# AudioQual

Aplicación de escritorio para analizar la calidad real de archivos de audio mediante
análisis espectral. Detecta archivos "falsos" de alto bitrate (upscaleados o transcodificados
desde fuentes de menor calidad) examinando los patrones de corte de frecuencia.

## Requisitos

- **Python 3.9+**
- Dependencias de Python: `pip install -r requirements.txt`

### Dependencias de sistema (librerías nativas)

Algunas dependencias de Python necesitan librerías nativas del sistema. En máquinas de
desarrollo con estas librerías instaladas la app funciona en los tres sistemas; sin ellas
fallan la reproducción de audio, la carga de ciertos formatos o el renderizado de iconos.

| Función | Librería del sistema | Notas |
|---------|----------------------|-------|
| Reproducción de audio (`sounddevice`) | PortAudio | Los *wheels* recientes suelen incluirla |
| Carga WAV/FLAC/OGG (`soundfile`) | libsndfile | Los *wheels* recientes suelen incluirla |
| Carga M4A/AAC/WMA (`librosa`) | ffmpeg | Opcional; sin él esos formatos no cargan |
| Iconos SVG (`cairosvg`) | libcairo | Hay *fallback* a PNG si falta |
| Papelera (Linux) | `gio` (glib2) | Para enviar archivos a la papelera |

**macOS** (Homebrew):
```bash
brew install portaudio libsndfile cairo ffmpeg
```

**Linux** (Debian/Ubuntu):
```bash
sudo apt install libportaudio2 libsndfile1 libcairo2 ffmpeg
# 'gio' viene con glib2 (paquete libglib2.0-bin)
```

**Windows:** normalmente cubierto por los *wheels* de PyPI. Para soportar M4A/AAC instala
`ffmpeg` y añádelo al `PATH`.

## Uso

```bash
# Ejecutar la aplicación
python3 src/main.py

# Ejecutar tests
python3 tests/run_tests.py
```

## Compilar la app standalone

```bash
pyinstaller build/audioqual_macos.spec     # macOS
pyinstaller build/audioqual_windows.spec   # Windows
pyinstaller build/audioqual_linux.spec     # Linux
```

Los *specs* empaquetan `src/assets` (fuentes, iconos) y `src/locales` (traducciones), e
intentan incluir las librerías nativas de audio (PortAudio/libsndfile) desde los *wheels*.
Si el audio falla en un build limpio, instala las dependencias de sistema de la tabla anterior.
