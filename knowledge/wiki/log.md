---
title: Cronología del proyecto AudioQual
created: 2026-04-27
updated: 2026-06-01
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
