---
title: "Decisión: limpieza de código muerto y adelgazamiento del bundle"
created: 2026-06-03
updated: 2026-06-03
sources: []
tags: [decision, distribucion, mantenimiento, tfg]
---

# Decisión: limpieza de código muerto y adelgazamiento del bundle

## Contexto

El `.app` de macOS rondaba los ~230 MB, considerado excesivo para lo que ofrece la app, y
existía la sospecha de código muerto acumulado tras meses de iteración. Se lanzó una
investigación (3 agentes de exploración + verificación manual directa) sobre dos frentes:
código sin uso y origen del peso.

**Hallazgo metodológico importante:** el primer análisis de peso afirmó que se podían recortar
150-200 MB excluyendo paquetes gigantes (jupyter, pandas, nltk, spacy, cv2, torch). **Era
falso.** Se basaba en `build/waxcheck_macos/Analysis-00.toc`, un artefacto de PyInstaller del
**18 de marzo** generado con el nombre viejo del proyecto ("WaxCheck") y un entorno Python
contaminado. El spec actual (`audioqual_*.spec`) es limpio y minimalista; esos paquetes nunca
estuvieron en el bundle real. El peso legítimo viene de: numpy, scipy, **librosa (+numba +
llvmlite)**, matplotlib y las libs nativas de audio (PortAudio/libsndfile).

## Decisiones tomadas

### 1. Eliminación de código muerto (~1030 líneas, 0 referencias verificadas)

Borrado de símbolos con cero referencias en `src/ tests/ scripts/`, confirmado con búsquedas
exactas (no por substring) descartando invocación dinámica:

- **`src/gui/file_drop_zone.py`** entero — clase `FileDropZone` nunca instanciada (229 líneas).
- **`frequency_detector.py`** — el camino de detección antiguo completo, ya sustituido por
  `analyze_frequency_cutoff` / `find_cutoff_by_transition`: `find_cutoff_frequency_basic`,
  `find_cutoff_frequency_gradient`, `combine_detection_methods`, y la sección *shelf detection*
  en cascada (`find_cutoff_shelf_detection` + sus únicos llamados `validate_cutoff`,
  `smooth_energy_spectrum`, `estimate_noise_floor`, `estimate_signal_reference`). ~430 líneas +
  11 constantes `SHELF_*`/`GRADIENT_THRESHOLD`/`NOISE_FLOOR_DB` del import.
- Métodos/funciones sueltos: `analyzer.create_analyzing_result`, `audio_loader.load_audio_segment`,
  `audio_player.{get_volume,get_duration,is_loaded}`, `icons.icon_settings` (+ `import math`),
  `player_controls.update_track_info` (+ atributo `_current_track_name`),
  `results_table.{add_results,get_all_results,select_first,remove_result}`, `i18n.get_language`.

**No tocados (falsos positivos):** `folder_watcher.on_created/on_moved` (callbacks de watchdog
por reflection).

### 2. Eliminar matplotlib (riesgo bajo, ahorro real)

matplotlib solo se usaba para `plt.style.use('dark_background')` (sin efecto, no se plotea) y
`LinearSegmentedColormap.from_list` para la colormap Spek del espectrograma — que ya se
convertía en un LUT numpy de 256 entradas. Se reconstruye el LUT con `np.interp` directa en
`spectrogram_window.py` (`_build_colormap_lut`), **replicando bit-a-bit** el de matplotlib
(verificado: diff máx 0 en las 256 entradas, replicando su muestreo interno N=256 y el mapeo
`int(x*N)`). matplotlib sale de `requirements.txt`, de `hiddenimports` y entra en `excludes`.

### 3. Eliminar cairosvg / libcairo (riesgo bajo)

cairosvg solo rasterizaba iconos SVG en runtime, y `icon_utils.py` ya tenía fallback a PNG. Los
8 iconos cargados en runtime ya existían como PNG 256×256, así que `load_svg_icon` pasa a cargar
siempre el PNG (downscale Pillow LANCZOS a 2× el tamaño pedido). `app.py` usa
`logo-waxcheckV2.png` (256, 17 KB) en lugar de rasterizar el SVG, lo que permitió borrar
`logo-WaxCheck.png` (990 KB). Los SVG fuente se conservan; se regeneran con el nuevo
`scripts/render_icons.py` (build-time, único punto que necesita cairosvg). cairosvg sale de
`requirements.txt` y entra en `excludes` (con `cairocffi`, `cffi`).

### 4. Limpieza de repo y assets

- `build/waxcheck_macos/` (96 MB, output de build viejo, ya gitignored) eliminado del disco.
- Specs obsoletas `waxcheck_macos.spec` / `waxcheck_windows.spec` eliminadas; los scripts
  locales `build_macos.sh` / `build_windows.bat` / `BUILD.md` actualizados al naming AudioQual y
  a los specs `audioqual_*` (CI ya los usaba; los scripts locales habían quedado desincronizados).
- Assets huérfanos borrados de `src/assets/`: `clean.jpg`, `spectrum.jpg`, `logo-WaxCheck.png`,
  variantes `waxcheck-empty-cover{,-medium}.png` y 11 iconos PNG/SVG de versiones antiguas.
  `src/assets/` quedó en ~528 KB (8 PNG activos + 8 SVG fuente + cover + fuentes).

## Fuera de alcance (trabajo futuro): reemplazar librosa

Reemplazar **librosa** por `scipy.signal`/numpy se evaluó pero se **aplazó** por riesgo sobre el
algoritmo (núcleo del TFG):

- Usos triviales de portar: `frequency_detector` usa `librosa.stft`, `amplitude_to_db`,
  `fft_frequencies` → equivalentes directos en `scipy.signal`/numpy (scipy ya es dependencia).
- **Bloqueo real:** `audio_loader`/`audio_player` usan `librosa.load` como fallback para
  **m4a/aac/wma** (vía audioread). Sustituirlo requiere otra ruta de decodificación.
- **Beneficio medido (clave):** en el build de macOS de 211 MB, la cadena
  librosa→numba→**llvmlite** domina el bundle: `llvmlite/binding` ocupa **110 MB (≈52 % del
  `.app`)**, más numba y la propia librosa. Es, con diferencia, el mayor objetivo de peso
  pendiente — mucho mayor que matplotlib/cairosvg. No se puede simplemente excluir numba/llvmlite
  manteniendo librosa porque `import librosa` los requiere al cargar. Pendiente de una iteración
  dedicada con verificación end-to-end de los 3 SO.

Ver también [features-conscientes-del-peso] y la nota de Now Playing aplazada por el mismo motivo
de peso en [now-playing-media-session](now-playing-media-session.md).

## Verificación

- Suite completa: **83/93, 0 fallos**, 10 known bugs preexistentes (sin regresiones). La suite de
  detección (algoritmo) pasó intacta tras vaciar el camino de detección antiguo.
- App arranca sin errores; `matplotlib`/`cairosvg` ya no se importan en runtime
  (`'matplotlib' in sys.modules` → False tras importar `spectrogram_window`).
- LUT de la colormap idéntico al anterior (diff 0/256).
