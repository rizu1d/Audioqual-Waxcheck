---
title: "Decisión: drag-out de archivos desde la tabla de resultados"
created: 2026-06-01
updated: 2026-06-01
sources: []
tags: [decision, gui]
---

# Decisión: drag-out de archivos desde la tabla de resultados

## Contexto

La tabla de resultados (`ResultRow` / `ResultsTable` en `src/gui/results_table.py`) ya recibía archivos por arrastre (drag-in, vía `tkinterdnd2`). Se quería poder arrastrar archivos **hacia fuera** de la app (a Finder u otras apps), como en un explorador de archivos.

## Decisión

Cada `ResultRow` se registra como `drag_source_register(1, DND_FILES)` (recursivamente sobre la fila y sus descendientes) y responde a `<<DragInitCmd>>` devolviendo `(COPY, DND_FILES, rutas)`. Las rutas a exportar las decide `ResultsTable._get_drag_filepaths()`:

- Si la fila arrastrada forma parte de una multi-selección, se exportan **todas** las seleccionadas.
- Si no, solo la fila arrastrada (estilo Finder).

Solo se exportan rutas que sigan existiendo en disco.

## Conflicto click vs. arrastre (colapso diferido)

El `<Button-1>` de la fila dispara `_select_single()`, que colapsa la multi-selección a una sola fila. Como el press para iniciar un arrastre también es un `<Button-1>`, la selección se colapsaba **antes** de que el drag leyera las filas, exportando un solo archivo.

Solución (patrón estándar de gestores de archivos): al pulsar sobre una fila **ya** multi-seleccionada sin modificadores, el colapso a selección única se **difiere** del press al release (`_pending_collapse_row`). Si en medio arranca un arrastre, `_get_drag_filepaths()` cancela ese pendiente, conservando la multi-selección. Un click sin arrastre colapsa normalmente al soltar.

## Trade-off: mueve en vez de copiar (macOS)

En macOS, arrastrar dentro del mismo volumen **mueve** el archivo; a otro volumen lo copia. El `COPY` que devolvemos es solo una sugerencia de acción: `tkdnd` en macOS no fuerza de forma fiable el operation mask, así que Finder aplica su comportamiento por defecto (mover).

Se decidió **dejarlo así**: forzar copia desde código no es trivial con `tkinterdnd2` en Mac, y mover es razonable. El usuario puede mantener **⌥ Option** durante el arrastre para forzar copia (comportamiento nativo de Finder).

## Degradación

Si `tkinterdnd2` no está instalado (`HAS_DND = False`), el drag-out simplemente no se registra; el resto de la tabla funciona igual.
