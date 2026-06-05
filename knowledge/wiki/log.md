---
title: Cronología del proyecto AudioQual
created: 2026-04-27
updated: 2026-06-03
---

# Log del proyecto

Cronología reconstruida desde el historial de git y documentación interna. Append-only.

---

## [2026-01-28] inicio | Primer commit: AudioQual audio quality analyzer
Nace el proyecto. Primer commit con el analizador de calidad de audio funcional. El mismo día se corrige la detección de transcodes y se reducen falsos positivos. Tres commits en un día.

## [2026-01-29] algoritmo | Grandes avances en detección de transcodes
Se mejora TranscodeTheBox, se mejora el etiquetado de archivos de baja calidad usando frecuencia de corte, y se añade soporte para AIFF.

## [2026-01-31] gui | Renderizado y selección de archivos mejorado
Pulido de soporte AIFF y mejoras de rendering en la tabla.

## [2026-02-02] gui | Primeros diseños de interfaz
Colores aplicados, fuente Lowpress incorporada, primera versión de scrollbar. La interfaz empieza a tomar forma.

## [2026-02-03] gui | Iteraciones rápidas de diseño
Panel lateral desplegable → mejoras → exportar eliminado → botones de limpieza y espectro → nuevo diseño completo → burbujas de estado. 6 commits en un día — período de exploración intensa de diseño.

## [2026-02-04] gui | Zona de arrastre y fluidez de clics
Nuevo diseño con zona de arrastre, mejora de responsividad de botones.

## [2026-02-05] gui | Reproductor de audio y visualizador DJ
Se implementa el reproductor de audio con visualizador DJ. Luego dos rondas de optimización y corrección del bloqueo de tkinter. Panel lateral eliminado a favor de render por ventana.

## [2026-02-06] algoritmo | Algoritmo mejorado
Mejoras en la detección de frecuencia de corte.

## [2026-02-09] algoritmo | Fiabilidad y corrección de detección
Implementación del sistema de fiabilidad (niveles de confianza). Corrección del caso LaTour (meseta de ruido). Se crea CLAUDE.md y ALGORITMO.txt. Se añaden atajos de teclado y expand/contract de columnas.

## [2026-02-10] gui | Metadatos, espectro y configuración
Pestaña de metadatos con autocomplete de géneros musicales, prototipo de panel de configuración, pestaña de ilustración con bordes redondeados. Corrección de algoritmo para LaTour (estado incierto).

## [2026-02-11] arquitectura | Monitorización de carpeta (FolderWatcher)
Implementación del watcher de carpeta con watchdog. Botón reposicionado junto al de añadir archivos.

## [2026-02-16] bugfix | Corrección de errores y optimización
Ronda de corrección de bugs acumulados.

## [2026-02-17] arquitectura | Estabilidad macOS, tests y rebranding
Mejora crítica de estabilidad: sistema pipe+queue para threading en macOS, restauración de foco en ventanas modales. Implementación de la primera suite de tests. Rebranding de AudioQual → WaxCheck. Fix de flickering en ordenación de columnas.

## [2026-02-19] testing | Sistema de verificación
Incorporación del algoritmo de búsqueda con lupita. Creación del sistema de testeo y verificación. Creación de la carpeta knowledge/.

## [2026-02-20] gui | Cambio de iconos y logo
Dos iteraciones de iconos y logo (V1 → V2).

## [2026-02-22] algoritmo | Calibración de algoritmo
Arreglar barra espaciadora. Bangapella, GoldenBoy, LaTour arreglados. Casos inciertos de YouTube arreglados. Sesión intensiva de calibración del algoritmo.

## [2026-02-23] gui | Nueva UI y estados de calidad
Nueva interfaz completa. Burbujas de estado con hover glow. Popup de explicación V1→V2→V3 con animación. Algoritmo: umbrales tocados V1→V2, guard HF bajado a 18kHz. Espectrograma ajustado para parecerse a Spek.

## [2026-02-24] bugfix | Fix clics macOS y clasificación YouTube
Fix del problema de primer clic no respondiendo en macOS (acceptsFirstMouse). Fix de clasificación de YouTube rips ≤192kbps.

## [2026-02-25] testing | Sistema de evaluación automatizado
Se crea sistema de evaluación automatizado para testing a escala. Fix de generación de YouTube rips (descartar streams de video embebidos).

## [2026-03-03] algoritmo | Actualización de umbrales y espectrograma sin matplotlib
Reescritura del espectrograma sin dependencia directa de matplotlib para el rendering. Mejoras de waveform: RMS, doble resolución. Fix de seek lento.

## [2026-03-04] gui | Funcionalidades avanzadas de UI
Pestaña "Archivo" en editor de metadatos (header iTunes-style). Selector de dispositivo de audio. Menú contextual con clic derecho. Multiselección en tabla. Fix consumo masivo de RAM. Deduplicación de re-análisis. Caché de espectrogramas en disco con apertura instantánea.

## [2026-03-05] rendimiento | Optimización ~50% velocidad de análisis
HOP_LENGTH 512→1024, soundfile como backend, 4 workers paralelos. Reducción significativa del tiempo de análisis.

## [2026-03-06] gui | Overlay de análisis con progreso real
Implementación de overlay de análisis con barra de progreso real y bloqueo de interacción durante el análisis.

## [2026-03-15] gui | Mejora visibilidad de selección
Fondo más visible para fila seleccionada + barra lateral morada. Intento de virtual scroll que fracasó (ver decisiones/no-virtual-scroll.md).

## [2026-03-19] distribucion | Sistema de build y empaquetado
Specs de PyInstaller para macOS y Windows. Scripts de build. Documento de análisis de distribución. Review encontró 3 problemas (PNG fallback, NSMicrophone, constante huérfana).

## [2026-03-21] algoritmo | Mejora precisión y nivel "medio"
Fix falsos positivos en samples WAV de percusión cortos. Se añade nivel de calidad "medio" (entre bueno y bajo). Mejora de precisión de detección de corte.

## [2026-04-14] gui | Watcher animation e i18n
Animación glow en botón watcher. Fix pérdida de indicador de monitorización. Implementación completa de internacionalización (i18n) con soporte español/inglés.

## [2026-04-17] rendimiento | Mejora de resize con archivos
Optimización de rendimiento del resize de ventana cuando hay archivos en la tabla.

## [2026-04-19] bugfix | Watcher no detecta subcarpetas
Fix: el watcher no detectaba archivos en subcarpetas añadidas después de iniciar la monitorización.

## [2026-04-21] algoritmo | Pre-validación MP3 y cluster-4
Pre-validación de estructura MP3 para prevenir crashes SIGBUS con archivos corruptos. Simplificación de CLAUDE.md. Fix de python→python3. Eliminación de test EDGE_005. Fix de falsos positivos cluster-4 (archivos con rolloff natural).

## [2026-04-24] algoritmo | Verificación brickwall
Implementación de is_natural_rolloff() con verificación de brickwall. Discriminación entre cortes de codec y rolloff natural usando gradiente + varianza temporal. 5 iteraciones hasta llegar a la solución final. Resultado: 93 tests, 83 pasan, 0 fallos, 10 known bugs.

## [2026-04-27] inicio | Creación del wiki del proyecto
Se crea el wiki de conocimiento del proyecto, con páginas sobre algoritmo, arquitectura, fuentes y decisiones de diseño. Ingesta de los 7 archivos de knowledge/ existentes. Reconstrucción de cronología desde git.

## [2026-06-01] rendimiento | Optimización de CPU y medición con powermetrics
Aplicadas las recomendaciones del informe DIAGNOSTICO_CPU.txt. Polling del watcher 1s→3s: monitorización 29%→~4%. Eliminado thread_watchdog.py (código muerto) y la animación glow (redundante con el overlay de análisis). Intervalos de las 3 capas de callbacks subidos (R3): −22% intr wakeups, −0.5% CPU, validado con powermetrics. Hallazgo clave: el run loop de Cocoa sí entra en bajo consumo (pkg-idle wakeups ~1/s) y el grueso de los wakeups viene del notifier de Tcl/Tk, no de nuestro código; la preocupación del informe estaba sobredimensionada. MP3 enrutado por soundfile (libsndfile lo soporta), evitando el audioread deprecado; warning de librosa silenciado por message=. Nueva página decisiones/medicion-cpu.md con la metodología.

## [2026-06-01] gui | Drag-out de archivos desde la tabla de resultados
Las filas (`ResultRow`) ahora son drag-source: se pueden arrastrar archivos a Finder u otras apps. Multi-selección exporta todas las filas seleccionadas. Bug corregido: el `<Button-1>` colapsaba la selección antes de que el drag la leyera (exportaba solo 1 archivo); solución con colapso diferido press→release cancelado al iniciar el arrastre. En macOS arrastra como "mover" (limitación de tkdnd); ⌥ Option fuerza copia. Nueva página decisiones/drag-out-archivos.md.

## [2026-06-01] distribucion | Empaquetado multiplataforma: assets, locales y libs nativas
Implementado el plan de la auditoría de compatibilidad. Los tres specs ahora empaquetan `src/assets` y `src/locales` (antes `datas=[]` → app empaquetada sin fuentes/iconos/i18n en todas las plataformas) y recogen las libs nativas de audio (libsndfile vía `_soundfile_data`, PortAudio vía `_sounddevice_data`) con `collect_dynamic_libs`, como red de seguridad sobre los hooks oficiales de pyinstaller-hooks-contrib. `i18n.py` ahora resuelve `locales` consciente de modo *frozen* (`sys._MEIPASS`). Creado `build/audioqual_linux.spec`. `_sanitize_filename()` devuelve "Sin nombre" si el resultado queda vacío. Nuevo `README.md` con dependencias de sistema por SO. Hallazgo: `tkinterdnd2` trae los binarios de Windows en el wheel (`tkdnd/win-x64`) y su hook oficial los recoge → drag-out viable en Windows empaquetado (pendiente QA manual en VM). Verificación: `verify_implementation.py --quick` OK.

## [2026-06-01] distribucion | CI de builds + QA real en Windows (Guacamole)
Workflow `.github/workflows/build.yml` que compila los 3 SO en GitHub Actions y produce instaladores como artefactos: DMG (macos-14 arm64), instalador Inno Setup (`build/installer_windows.iss`) y AppImage (`build/linux/` AppRun + .desktop). Dispara en `workflow_dispatch` y tags `vX.Y.Z`. Primera corrida verde a la primera en los 3 (~1-3 min/job). Requirió añadir el scope `workflow` al token de gh para poder pushear el yml. **QA real**: la build de Windows se probó en una VM universitaria vía Apache Guacamole (subida por la unidad compartida, sin login en GitHub). Resultado: instala y arranca; SmartScreen avisa por `.exe` sin firmar (esperado). **Bug encontrado y corregido (R6)**: los iconos de toolbar salían en blanco porque sin libcairo `cairosvg` no renderiza los SVG V2/V3 y no existían PNG de fallback → `icon_utils` caía a placeholder transparente. Fix: pre-rasterizados los 8 SVG cargados en runtime a PNG 256×256 (commit 9184ba0); confirmado en Windows real que ya se ven. Pendiente: icono de app/taskbar genérico (specs con `icon=None`, falta `.ico`/`.icns`), y QA de Linux/AppImage en máquina real.

## [2026-06-02] rendimiento | Virtualización de la tabla de resultados (scroll fluido con 400+)
Resuelto el scroll lento/trabado con 100+ archivos (muy pesado a ~400). Causa: `CTkScrollableFrame` renderizaba **todas** las filas (~17 widgets × 400 = ~6800 widgets vivos en el Canvas). Solución: virtualización con pool de filas recicladas en `src/gui/results_table.py`, **manteniendo** `CTkScrollableFrame` (al contrario del intento fallido de 2026-04). Separación modelo/vista: `_order`/`_visible`/`_selected_fps` (selección por filepath, persiste fuera del viewport) vs un pool de ~27 `ResultRow`. Un spacer empacado de altura `N·ROW_HEIGHT` controla el `scrollregion`; las filas se posicionan con `place(y)` absoluto. El `yscrollcommand` se envuelve en un proxy con debounce de 16 ms + caché de ventana `(first,last)`; `ResultRow.rebind()` reconfigura *in situ* (sin destruir/crear) y el reciclaje inteligente con guards `_cur_y`/`_selected` deja el scroll de 1 fila en 1 solo `rebind`. **Medido**: widgets vivos ~6800 → ~28; `add_result` ×400 = 2 ms; refresh de scroll incremental (800 archivos) ~1,6 ms mediana (3 ms máx). Eliminado el "detach del scroll frame durante resize" (innecesario con pocos widgets). Verificación: 83/93 tests OK (10 known bugs), `verify_ui` 15/15, y un test funcional ad-hoc (400/800 filas: selección persistente, sort, filtro, update en vivo, remove, clear recicla el pool). Actualizada [decisiones/no-virtual-scroll.md](decisiones/no-virtual-scroll.md): el intento de 2026-04 falló por usar Canvas crudo, sin throttle y con reciclaje destructivo; este corrige las tres causas.

## [2026-06-03] gui | Diseño de integración Now Playing del SO (aplazada por peso)
Diseñada al completo la feature "media session" del sistema operativo: que AudioQual aparezca como reproductor activo (widget Centro de Control en macOS, SMTC en Windows, MPRIS en Linux) con metadatos + carátula y control bidireccional por teclas de medios. Arquitectura: adaptador por plataforma con carga perezosa (autodesactivación si falta la lib nativa), listeners aditivos en AudioPlayer, reutilización del patrón mutagen de metadata_editor. **Aplazada** por el coste en peso del binario: pyobjc-framework-MediaPlayer arrastra Cocoa (~10-20 MB en el .app de ~230 MB) y winsdk pesa ~30-50 MB en Windows; choca con la vigilancia de tamaño del proyecto. Plan y apéndice técnico completos en ~/.claude/plans/seguimos-con-las-implementaciones-parsed-fox.md. Nueva página decisiones/now-playing-media-session.md. No se escribió código.

## [2026-06-03] mantenimiento | Limpieza de código muerto + adelgazamiento del bundle (matplotlib y cairosvg fuera)
Investigación (3 agentes + verificación manual directa) sobre código muerto y peso. **Desmontado un falso hallazgo**: el primer análisis prometía recortar 150-200 MB excluyendo paquetes gigantes (jupyter, pandas, nltk, spacy, cv2, torch) — venían de `build/waxcheck_macos/Analysis-00.toc`, un `.toc` del 18 de marzo del nombre viejo "WaxCheck" con entorno contaminado; el spec actual nunca los incluyó. **Código muerto (~1030 líneas, 0 refs verificadas):** borrado `src/gui/file_drop_zone.py` entero, el camino de detección antiguo completo en `frequency_detector.py` (basic/gradient/combine + sección *shelf* en cascada: shelf_detection, validate_cutoff, smooth_energy_spectrum, estimate_noise_floor, estimate_signal_reference, ~430 líneas + 11 constantes del import), y ~13 métodos/funciones sueltos (create_analyzing_result, load_audio_segment, get_volume/get_duration/is_loaded, icon_settings, update_track_info, add_results/get_all_results/select_first/remove_result, get_language). **Peso (Nivel B, sin tocar el algoritmo):** eliminado **matplotlib** — su única utilidad era la colormap Spek, reconstruida como LUT numpy `_build_colormap_lut()` en `spectrogram_window.py`, **bit-idéntica** al original (diff 0/256). Eliminado **cairosvg/libcairo** — `load_svg_icon` carga ya los PNG 256×256 pre-renderizados (que ya existían), `app.py` usa `logo-waxcheckV2.png` y se borró `logo-WaxCheck.png` (990 KB); nuevo `scripts/render_icons.py` para regenerar los PNG (build-time). Ambos quitados de `requirements.txt`/`hiddenimports` y añadidos a `excludes` en los 3 specs. **Limpieza de repo:** `build/waxcheck_macos/` (96 MB, gitignored) fuera; specs viejas `waxcheck_*.spec` eliminadas y scripts locales (`build_macos.sh`/`build_windows.bat`/`BUILD.md`) actualizados al naming AudioQual + specs `audioqual_*` (CI ya los usaba); assets huérfanos purgados → `src/assets/` 1,5 MB→528 KB. **Verificación:** suite 83/93, 0 fallos (10 known bugs); app de código y `.app` empaquetado arrancan sin errores; matplotlib/cairo/sklearn confirmados con 0 archivos en el bundle. **Build medido: 211 MB** (antes ~230). **Hallazgo clave para el futuro:** el peso restante lo domina la cadena librosa→numba→**llvmlite**: `llvmlite/binding` = **110 MB (≈52 % del .app)**. Reemplazar librosa por scipy.signal/numpy (aplazado por riesgo sobre el algoritmo del TFG; bloqueo = `librosa.load` para m4a/aac/wma) es el mayor objetivo de peso pendiente, mucho mayor que matplotlib/cairosvg. Nueva página [decisiones/limpieza-codigo-muerto-y-peso.md](decisiones/limpieza-codigo-muerto-y-peso.md).

## [2026-06-03] distribucion | Poda de Pillow + strip en los specs (211 → 202 MB)
Segundo lote de recortes baratos de peso. La app solo decodifica **PNG y JPEG** (iconos + carátulas APIC/FLAC); el espectrograma es un array RGB en memoria e `ImageDraw` solo dibuja formas (sin `ImageFont`/truetype). **Hallazgo con `otool -L`:** el core `_imaging` enlaza **obligatoriamente** libtiff/libjpeg/libopenjp2/libz/libxcb → esos no se pueden quitar (un primer intento que borró libtiff/libopenjp2 crasheó la `.app` al arrancar). Solo eliminables las libs de plugins *lazy*: `_avif`→libavif (3 MB), `_webp`→libwebp+mux+demux+sharpyuv (0,8 MB), `_imagingft`→freetype+harfbuzz+brotli (3,2 MB), `_imagingcms`→lcms2 (0,5 MB). Implementado como filtro `_is_unused_pil_binary` de `a.binaries` en los 3 specs (match por basename con guarda de ruta `/pil/`, cross-platform); borra dylibs + sus `.so` plugin. `PIL.init()` importa WebP/AVIF en `try/except` → degrada con elegancia; ImageFont/ImageCms nunca se importan. Conservados `_imaging`/`_imagingmath`/`_imagingtk` (este para ImageTk). Además `strip=True` en EXE+COLLECT de los 3; `upx=True` en Win/Linux pero **`upx=False` en macOS** (rompe firma arm64). **Build medido: 211 → 202 MB**, firma OK, arranca, JPEG/PNG intactos. Verificación: `verify_implementation.py --quick` OK. Documentado en [decisiones/limpieza-codigo-muerto-y-peso.md](decisiones/limpieza-codigo-muerto-y-peso.md) §5.

## [2026-06-03] algoritmo | Reemplazo de librosa Fase 1 (espectral) sin tocar resultados
Primera fase del plan de quitar librosa (`knowledge/PLAN_REEMPLAZO_LIBROSA.md`). En `frequency_detector.py` se sustituyen los 3 usos espectrales por numpy/scipy y se elimina `import librosa` del fichero: `librosa.stft` → `_stft_magnitude` (ventana Hann periódica + `center` con pad de **zeros** `pad_mode='constant'`, el default de librosa 0.10+, NO 'reflect' — un pad 'reflect' daba diff 48.9; las dudas de padding se zanjaron empíricamente), `librosa.amplitude_to_db(ref=np.max)` → `_amplitude_to_db_refmax` (trabaja en potencia, floor `amin**2` con amin=1e-5, clip `top_db=80`), `librosa.fft_frequencies` → `np.fft.rfftfreq`. **Verificación:** sintético diff 0.0; audio real (16 archivos del corpus) `spectrogram_db` diff máx **~3e-4 dB** (la FFT nuestra va en float64→cast, librosa en float32/complex64 → la nuestra es más precisa; los 3e-4 son su redondeo, ~6 órdenes bajo cualquier umbral y el espectro se cuantiza a uint8), `fft_frequencies` diff 0.0. `bash tests/full_check.sh` TODO OK, suite de detección sin regresiones. **OJO:** esto **no baja el peso todavía** — librosa sigue importado en `audio_loader.py`/`audio_player.py` (`librosa.load` para m4a/aac/wma) → numba/llvmlite siguen en el bundle hasta la Fase 2. Esta fase desactiva el riesgo sobre el núcleo del algoritmo (TFG).

## [2026-06-03] investigacion | Suelo de ruido hasta Nyquist + ficha del paper de Koops
Sesión de análisis manual con MusicScope (3 capturas) que destapó dos criterios. **(1) Variabilidad temporal del muro**: ya estaba en el algoritmo como "varianza temporal post-corte" (`is_natural_rolloff`), pero faltaba enunciarlo como regla de inspección manual → añadido a [decisiones/spek-vs-musicscope.md](decisiones/spek-vs-musicscope.md). **(2) Suelo de ruido hasta Nyquist** (genuinamente nuevo, no estaba en ninguna página): un lossless conserva alfombra de dither de banda ancha (~−93 dBFS, TPDF, blanco hasta el borde) aunque la música muera antes; un lossy la trunca en seco. Confirmado con fuentes (tonmeister, romi docs, Wikipedia noise shaping). Nueva página [algoritmo/suelo-ruido-nyquist.md](algoritmo/suelo-ruido-nyquist.md) con base física, 4 excepciones (visibilidad≠existencia, lowpass de mastering legítimo, no es prueba inversa, lossy deja su propio ruido truncado) y propuesta de métrica futura (energía de ruido en `[cutoff, Nyquist]`, aplazada por peso). **Ficha de paper**: [fuentes/robust-lossy-identification-koops.md](fuentes/robust-lossy-identification-koops.md) (arXiv:2407.21545) — depender solo del corte es frágil (99.8%→63.7% en cortes no vistos), su *random masking* respalda el tell del suelo de ruido, y confirma que el AAC es intrínsecamente duro (~81%, coincide con known bug `YT_012`). No se integra (deep learning, choca con el peso); valor académico para el TFG. **Dato de dataset**: sondeo con ffprobe de los 38 archivos de test → 33 mp3, 4 pcm_s24be, 1 pcm_s16be, **0 AAC nativo**; el "problema AAC" es indirecto (YouTube rips MP3 con linaje AAC→MP3, varios a 48 kHz). Sin cambios de código.

## [2026-06-03] distribucion | Reemplazo de librosa Fase 2 (carga de audio): el .app cae a 87 MB
Cerrado el reemplazo de librosa. `librosa.load` (fallback para **m4a/aac/wma**) → nueva `load_via_audioread` en `audio_loader.py` (audioread → PCM int16/32768 → downmix mono → resample con **soxr** para paridad con el resampler `soxr_hq` de librosa); `audio_player.py` reusa esa función; `import librosa` fuera de ambos. **Decisión audioread vs PyAV:** se eligió **audioread directo** (peso ~0) porque es el mismo backend que `librosa.load` usaba por dentro (CoreAudio en macOS, ffmpeg/GStreamer en Linux/Windows) → **comportamiento idéntico, sin regresión** (librosa tampoco empaquetaba decoder; el AppImage ya dependía de ffmpeg del sistema para m4a). PyAV habría dado m4a autónomo en Win/Linux pero a +50 MB en los 3 SO, sin mejorar macOS. `requirements.txt`: fuera librosa, dentro `audioread`+`soxr`+**`scipy`** (era transitiva de librosa, ahora explícita). Los 3 specs: librosa fuera de `hiddenimports`; `audioread`(+backends macca/ffdec/gstdec/rawread)/`soxr`/`scipy` dentro; `librosa`/`numba`/`llvmlite` en `excludes`. **Resultado: build macOS 202 → 87 MB (−115 MB), llvmlite/numba/librosa = 0 archivos** en el bundle. **Verificación:** paridad de samples m4a **bit-exacta** (maxdiff 0.0 vs `librosa.load`); `full_check` TODO OK sin regresiones; prueba con la cadena librosa/numba/llvmlite **bloqueada** en el import → decodifica m4a y analiza OK (0 dependencia oculta); `.app` firma y arranca. README actualizado (tabla de deps de sistema: M4A vía audioread, macOS nativo CoreAudio, Linux/Windows ffmpeg; quitada la fila obsoleta de cairosvg). **Pendiente antes de mergear:** QA de m4a/aac/wma en Windows y Linux empaquetados (CI). WMA en macOS sigue sin soporte (CoreAudio no lo decodifica, igual que antes). Documentado en [decisiones/limpieza-codigo-muerto-y-peso.md](decisiones/limpieza-codigo-muerto-y-peso.md) §6 y `knowledge/PLAN_REEMPLAZO_LIBROSA.md`.

## [2026-06-03] rendimiento | Fix de regresión grave en _stft_magnitude (4× más lento + 2 GB de RAM)
El usuario detectó tras el reemplazo de librosa que el análisis era 3-4× más lento y comía muchísima más memoria. Causa: la primera `_stft_magnitude` (Fase 1) usaba `padded[idx]` con fancy-indexing (materializaba un índice int64 de >0,5 GB + gather hostil a caché) y `np.fft.rfft` (numpy fuerza float64 → doble cómputo/memoria), sin procesar por bloques como hace librosa. **Medido (canción de ~7 min):** `analyze_file` 8828 ms y pico de RSS **+2253 MB** para UN archivo. **Fix:** framing con `sliding_window_view` (view, sin copia) + `scipy.fft.rfft` en float32→complex64 **por bloques** de ~8 MB. **Tras el fix:** `analyze_file` 2267 ms (3,9× más rápido) y pico ~1059 MB (≈ footprint original con librosa); el STFT aislado quedó incluso un 24% más rápido que `librosa.stft`. Diff numérico vs librosa intacto (~1e-4, sin cambio en cutoffs); `full_check` TODO OK. Docstring de la función avisa explícitamente de no reintroducir el gather ingenuo. Lección: replicar una función de librosa no es solo igualar el número — hay que igualar su estrategia de cómputo (views, float32, bloques).

## [2026-06-05] rendimiento | Verificación con powermetrics: el reemplazo de librosa no regresó el consumo
El usuario midió con `powermetrics` los cuatro estados (reposo, analizando 300, tabla llena, tabla llena + watcher) sobre el código actual (`cee3da6`, sin librosa) para zanjar la duda de si quitar librosa había hecho la app más golosa. **Resultado: idéntico al baseline con librosa en los cuatro estados** — reposo ~3.4%/~54 wakeups/~0.98 pkg-idle (vs ~3.3%/~54/~0.8), tabla llena ≈ reposo, analizando ~357% (~3.5 cores = 4 workers, igual que el ~330% medido con librosa), watcher ~8% (PollingObserver, no librosa). Pkg-idle ~1/s en reposo (chip duerme bien). Confirma que la lentitud previa era solo el STFT roto de `f91cb5e`, ya arreglado; **se descarta volver a `218ce95`**. Tabla completa en [decisiones/medicion-cpu.md](decisiones/medicion-cpu.md).

## [2026-06-05] rendimiento | Harness de benchmark determinista (Capa 1) para detectar regresiones de tiempo/RAM
Montado `tests/benchmark.py`: corre el pipeline sobre los archivos de `tests.json` y mide tiempo (`perf_counter`), CPU (`getrusage` user+sys), RSS pico (`ru_maxrss`) y pico de heap de Python (`tracemalloc`), **solo con stdlib** (cero deps nuevas, respeta el criterio de peso). Dos pasadas separadas para que el overhead de tracemalloc no contamine el tiempo. Sale con código 1 si una métrica supera su umbral (tiempo/CPU +10%, RSS/heap +15%). Resultados: `benchmark_baseline.json` (referencia maestra, commiteada) + `benchmark_history.jsonl` (serie temporal, commiteada) + `benchmark_results_*.json` (dump por-archivo, gitignored). **Decisión de diseño clave**: `wall_s`/`cpu_s`/`rss_peak_mb` dependen del hardware → solo comparables contra baseline de la misma máquina (campo `machine` lo marca y avisa si difiere); `heap_peak_mb` es **determinista** — validado empíricamente: dos runs dieron 1246.6 MB clavado. Por eso el heap es la señal fiable en CI con otro hardware. Baseline inicial en `cee3da6` (Darwin-arm64-8c, 34 archivos): wall 20.3s, cpu 19.8s, RSS pico 3690 MB, heap pico 1247 MB. Reemplaza al difunto `scripts/measure_cpu.sh` (borrado en la limpieza, la wiki aún lo citaba — referencia rota corregida). Es la **Capa 1** de un plan de 3: Capa 1 determinista (ésta, periódica/CI), Capa 2 muestreo en vivo con `psutil` de los estados GUI (reposo/watcher/reproducción, pendiente de montar), Capa 3 perfilado puntual (`memray` RAM / `py-spy` CPU). `powermetrics` queda relegado a su único nicho real: wakeups y energía/batería en reposo. Documentado en [decisiones/medicion-cpu.md](decisiones/medicion-cpu.md).

## [2026-06-05] rendimiento | Capa 2 del benchmarking: muestreo en vivo de la GUI con psutil
Montado `tests/benchmark_live.py` (Capa 2 del plan de 3). Lo que la Capa 1 no cubre: los estados interactivos con la app abierta (reposo, tabla llena, analizando, watcher). Se engancha al proceso vivo y muestrea `cpu_percent()` + RSS cada 0.5s durante N segundos → media/mediana/pico, atribuido **solo a ese proceso** (al contrario que `ps`/`powermetrics`, que miden todo el sistema). `psutil` entra como dependencia **solo de dev** (nuevo `requirements-dev.txt`; no se empaqueta, respeta el peso del bundle). **No** hace gating con código 1 (los estados en vivo son demasiado ruidosos para umbrales automáticos): mide, imprime y anexa a `benchmark_live_history.jsonl` etiquetado por estado, mostrando el delta contra el run anterior del mismo estado para ver la deriva. **Detalle de implementación**: la autodetección de PID exige `name=python` además de `src/main.py` en el cmdline, porque el wrapper de shell que lanza la app también tiene `src/main.py` en su cmdline (falso positivo: lo destapó la prueba real, salían 2 candidatos = zsh wrapper de 2 MB + Python de 216 MB). **Validación**: contra un proceso que quema CPU da ~100% (1 core) limpio; contra la app real en reposo da ~3.4% CPU / ~220 MB RSS — el 3.4% **coincide con el `powermetrics`** documentado, confirmando paridad. Documentado en [decisiones/medicion-cpu.md](decisiones/medicion-cpu.md). Pendiente: Capa 3 (perfilado puntual memray/py-spy), solo reactiva.

## [2026-06-05] rendimiento | Capa 3 del benchmarking documentada (perfilado reactivo, sin instalar)
Cerrado el plan de 3 capas de medición. La Capa 3 (`memray` para RAM, `py-spy` para CPU) queda **documentada pero no instalada**: es reactiva, no periódica — las Capas 1/2 detectan *que* hay regresión, la 3 diagnostica *dónde*. Comandos de referencia en [decisiones/medicion-cpu.md](decisiones/medicion-cpu.md): `memray run --native` + `flamegraph` para perfilar el batch (el `--native` es clave porque la RAM vive en numpy/scipy C, no en Python puro) o `memray attach <PID>` a la app viva; `py-spy top/record/dump --pid <PID>` enganchado al proceso sin reiniciar (mismo PID que la Capa 2). Ambas siguen comentadas en `requirements-dev.txt` (se activan con un `pip install` el día que hagan falta); no se empaquetan. Sistema de benchmarking completo: 1 batch determinista (regresiones, CI), 2 muestreo en vivo de la GUI, 3 perfilado puntual de diagnóstico.
