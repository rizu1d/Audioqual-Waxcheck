---
title: Cronología del proyecto AudioQual
created: 2026-04-27
updated: 2026-04-27
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
