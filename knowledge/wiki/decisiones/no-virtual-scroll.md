---
title: "Decisión: Por qué no virtual scroll"
created: 2026-04-27
updated: 2026-04-27
sources: [VIRTUAL_SCROLL_INTENTO_FALLIDO.txt]
tags: [decision, gui, rendimiento]
---

# Decisión: Por qué no virtual scroll

## Contexto

Con 300+ archivos, la tabla de resultados iba lenta al hacer scroll. Cada fila = ~15 widgets CTk. Con 300 archivos = ~4500 widgets en un CTkScrollableFrame, y Tkinter reposiciona TODOS en cada evento de scroll.

## Lo que se intentó

Reemplazo de CTkScrollableFrame por un `tk.Canvas` + pool de ~25 ResultRow reutilizables. Solo se renderizan las filas visibles, reciclando widgets al scrollear (virtual scrolling clásico).

Se implementó completamente (~600 líneas modificadas), los 82 tests pasaron, pero el **rendimiento visual fue peor** que la implementación original.

## Por qué falló

1. **customtkinter widgets son pesados**: doble canvas interno, esquinas redondeadas, scaling. `place()` y `place_forget()` son más lentos que en Tk puro.
2. **_render_visible() se llamaba demasiado**: cada mousewheel event en macOS (decenas por gesto de trackpad) sin throttling ni debouncing.
3. **Reciclaje costoso**: destruir badge/label antiguo y crear nuevo en cada reciclaje incluye crear CTkFrame, CTkLabel, bind recursivo.
4. **CTkScrollableFrame ya optimiza internamente** para widgets CTk de formas que el canvas crudo no replica.

## Alternativas identificadas (no implementadas)

1. `ttk.Treeview` (widget nativo) — renunciar a customtkinter para la tabla
2. Lazy loading con CTkScrollableFrame — crear/destruir widgets bajo demanda con debouncing
3. Canvas items nativos (text, rectangle) — mucho más ligeros que widgets embebidos

## Lección

- Los tests de CI no detectan problemas de rendimiento — se necesita testing manual con volumen real
- Un approach incremental (solo debouncing al scroll) habría sido más seguro que una reescritura completa
- customtkinter widgets ≠ tk widgets estándar para operaciones de pool/reciclaje
