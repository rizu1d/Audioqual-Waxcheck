---
title: Distribución y empaquetado
created: 2026-04-27
updated: 2026-06-01
sources: [DISTRIBUCION-15march.txt]
tags: [distribucion, arquitectura]
---

# Distribución y empaquetado

## PyInstaller

La app se empaqueta con PyInstaller para distribución standalone. Specs en `build/`:
- `audioqual_macos.spec` — macOS (Intel + Apple Silicon)
- `audioqual_windows.spec` — Windows 64-bit
- `audioqual_linux.spec` — Linux (sin `BUNDLE` ni `argv_emulation`)

### Datos y binarios empaquetados (los tres specs)

Tras la auditoría de compatibilidad multiplataforma (2026-06-01) los specs incluyen:

- **`datas`**: `src/assets` (fuentes, iconos) y `src/locales` (traducciones), mapeados a
  `src/assets` y `src/locales` bajo `sys._MEIPASS`. Coincide con lo que esperan
  `resource_path.py` (`get_assets_dir()`) e `i18n.py` (`_locales_dir()`, ya consciente de
  modo *frozen*). Antes estaban a `[]`, lo que dejaba la app empaquetada sin fuentes,
  iconos ni i18n en todas las plataformas.
- **`binaries`**: libs nativas de audio recogidas con `collect_dynamic_libs('_soundfile_data')`
  (libsndfile) y `collect_dynamic_libs('_sounddevice_data')` (PortAudio). Los hooks oficiales
  de `pyinstaller-hooks-contrib` ya las recogen; el spec lo hace explícito como red de
  seguridad. `soundfile`/`sounddevice` son módulos sueltos: los binarios viven en los
  paquetes de datos `_soundfile_data` / `_sounddevice_data`, no en el módulo.

Los hooks oficiales también cubren `tkinterdnd2` (incluye los `tkdnd/win-x64` etc., por lo que
el drag-out debería funcionar en Windows empaquetado), `librosa` y `customtkinter`.

## Tamaño del distribuible

| Componente | Tamaño |
|------------|--------|
| Código + assets | ~3.8 MB |
| Dependencias Python | ~153 MB |
| Python runtime + Tcl/Tk | ~50 MB |
| Binarios nativos | ~10 MB |
| **Total sin comprimir** | **~220-250 MB** |
| **DMG comprimido (macOS)** | **~100-130 MB** |
| **Instalador (Windows)** | **~100-130 MB** |

scipy es la dependencia más pesada (~83 MB). Eliminarla reduciría ~40-50 MB.

## Problemas pendientes

1. **PNG fallback incompleto** (Windows): cuando cairosvg no está disponible, los SVGs V2/V3 no tienen PNGs equivalentes → iconos invisibles
2. **Sin firma de código**: macOS mostrará "app de desarrollador no identificado"
3. **Falsos positivos antivirus**: PyInstaller en Windows sin certificado de code signing
4. **QA manual del build**: validar en VM Windows/Linux que fuentes, iconos, i18n, audio y
   drag-out (`tkinterdnd2`) funcionan en un empaquetado real. No es testeable desde el código.

### Resuelto (2026-06-01)

- ~~Specs con `datas=[]`~~ → ahora empaquetan assets y locales.
- ~~Libs nativas de audio sin empaquetar~~ → recogidas vía hooks + `collect_dynamic_libs`.
- ~~Sin build Linux~~ → `build/audioqual_linux.spec` creado.
- Dependencias de sistema por SO documentadas en `README.md`.

## Requisitos mínimos

- CPU: dual-core x86_64 o ARM64 (2 GHz+), sin GPU
- RAM: 4 GB mínimo, 8 GB recomendado
- Disco: ~400-500 MB + ~4.5 MB por archivo en caché
- Pantalla: 1280×720 mínimo, soporta HiDPI/Retina
