---
title: "Decisión: Virtual scroll en la tabla (intento fallido y solución)"
created: 2026-04-27
updated: 2026-06-02
sources: [VIRTUAL_SCROLL_INTENTO_FALLIDO.txt]
tags: [decision, gui, rendimiento]
---

# Decisión: Virtual scroll en la tabla (intento fallido y solución)

## Contexto

Con 100+ archivos la tabla de resultados va lenta al hacer scroll, y con ~400 se vuelve muy pesada. Cada fila (`ResultRow`) ≈ 17 widgets CTk; con 400 archivos ≈ 6800 widgets vivos en un `CTkScrollableFrame`. El cuello de botella es **mantener miles de widgets vivos** en el Canvas de Tk (la rueda en sí usa un único `bind_all` global, no un binding por fila).

## Primer intento (2026-04-27) — FALLÓ

Reemplazo de `CTkScrollableFrame` por un `tk.Canvas` crudo + pool de ~25 `ResultRow`. Se implementó completo (~600 líneas), los 82 tests pasaron, pero el rendimiento visual fue **peor** que el original. Causas:

1. **Canvas crudo**: al sustituir `CTkScrollableFrame` se perdieron las optimizaciones internas que CTk hace para sus widgets.
2. **Sin throttle**: `_render_visible()` se llamaba en cada evento de mousewheel (decenas por gesto de trackpad en macOS), sin debouncing.
3. **Reciclaje destructivo**: cada reciclaje destruía el badge/label y creaba uno nuevo (CTkFrame + CTkLabel + bind recursivo) → carísimo.

## Segundo intento (2026-06-02) — FUNCIONÓ

Misma idea (pool de filas recicladas, solo se renderiza la ventana visible) pero corrigiendo las tres causas del fallo. Implementado solo en `src/gui/results_table.py`, preservando el aspecto y toda la funcionalidad (badges, multi-selección, drag-out, sort, search, resize). Diferencias clave frente al intento fallido:

1. **Se mantiene `CTkScrollableFrame`**: se reusa su canvas y su `scrollregion`. Un único *spacer* empacado de altura `N·ROW_HEIGHT` (hijo del inner frame) hace crecer el `bbox("all")` → el scrollbar refleja la lista completa mientras solo hay ~27 filas vivas. Las filas se posicionan con `place(y=índice·ROW_HEIGHT)` absoluto encima del spacer.
2. **Debounce + caché de ventana**: el `yscrollcommand` del canvas se envuelve en un proxy que reenvía al scrollbar y programa un `_refresh_viewport` con debounce de ~16 ms. Si la ventana `(first, last)` no cambió, no se hace nada.
3. **Reciclaje no destructivo**: `ResultRow.rebind()` reconfigura los widgets existentes *in situ* (sin crear/destruir). Además, el reciclaje "inteligente" reusa las filas que ya muestran un filepath aún visible, y guarda llamadas con guards (`_cur_y`, `_selected`): en un scroll de 1 fila solo se reconfigura **1** fila.

**Separación modelo/vista**: la selección, el orden y el filtro viven en el modelo (listas de filepaths: `_order`, `_visible`, `_selected_fps`), no en los widgets. Así la selección **persiste** aunque la fila salga y vuelva a entrar del viewport.

### Resultado medido

- Widgets vivos: ~6800 → **~28** (27 filas del pool + spacer), independiente de N.
- `add_result` de 400 resultados: **2 ms** (solo modelo, sin crear widgets).
- Refresh de scroll incremental (caso real de la rueda) con 800 archivos: **~1,6 ms** mediana, 3 ms máx (antes el render de Tk gestionaba miles de widgets por gesto).
- 83/93 tests OK (10 known bugs preexistentes), `verify_ui` 15/15.

## Lecciones

- Los tests de CI no detectan regresiones de rendimiento: hace falta medición con volumen real (aquí, instrumentar `_refresh_viewport` con `perf_counter` y contar `winfo_children`).
- La virtualización con customtkinter **es viable** si (a) no se tira `CTkScrollableFrame`, (b) se hace debounce del refresh, y (c) el reciclaje reconfigura en vez de destruir/crear. El intento fallido erró en las tres.
