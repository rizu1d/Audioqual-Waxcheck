---
title: "Decisión: Desarrollo asistido por LLM (Claude Code)"
created: 2026-04-27
updated: 2026-04-27
sources: []
tags: [decision, tfg]
---

# Decisión: Desarrollo asistido por LLM (Claude Code)

## Contexto

AudioQual se ha desarrollado desde el inicio (28 enero 2026) con asistencia de Claude Code como copiloto de programación. Este hecho es central para el TFG y merece documentación.

## Modelo de trabajo

- **El usuario** (Alexandre) define la visión, toma decisiones de diseño, valida resultados con herramientas externas (MusicScope, Spek), y dirige la calibración del algoritmo
- **Claude Code** implementa código, propone soluciones técnicas, ejecuta tests, mantiene consistencia del codebase, y documenta conocimiento

## Artefactos de gobierno

- **CLAUDE.md**: instrucciones de alto nivel para el LLM (comandos, arquitectura, reglas)
- **.claude/rules/**: reglas operativas (thread-safety, testing, i18n, memory management)
- **knowledge/**: documentación generada por el LLM y curada por el usuario
- **memory/**: persistencia cross-conversación del LLM
- **tests/tests.json**: append-only, garantiza zero-regression

## Patrones que funcionaron

1. **Cluster-by-cluster**: resolver un grupo de problemas relacionados antes de pasar al siguiente
2. **Zero-regression obligatorio**: nunca reportar completado sin pasar tests
3. **Conocimiento acumulativo**: documentar en knowledge/ lo aprendido, no solo el código
4. **Verificación cruzada**: LLM analiza datos, humano valida con herramientas externas

## Patrones que no funcionaron

1. **Confianza ciega en herramientas visuales**: Spek nos llevó a conclusiones erróneas hasta que se contrastó con MusicScope
2. **Reescrituras grandes sin validación incremental**: virtual scroll (600 líneas) falló; enfoques incrementales habrían sido más seguros

## Relevancia para el TFG

Este modelo de trabajo es documentable como metodología: un humano con conocimiento de dominio + un LLM con capacidad de implementación y memoria persistente. Las ventajas (velocidad de iteración, consistencia) y limitaciones (el LLM no puede validar visualmente, no tiene contexto de audio real) son materia de análisis.
