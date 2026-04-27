---
title: Sistema de verificación y testing
created: 2026-04-27
updated: 2026-04-27
sources: [VERIFICACION.txt]
tags: [testing, arquitectura, tfg]
---

# Sistema de verificación y testing

## Problema que resuelve

Antes de este sistema, no había forma automatizada de verificar que la app seguía funcionando después de cada cambio. Esto causaba regresiones no detectadas y múltiples rondas de corrección.

## Arquitectura de 3 capas

### Capa 1: Verificadores

- **verify_ui.py**: 15 checks de interfaz gráfica (VUI_001 a VUI_015). Crea una instancia real de la app, inspecciona widgets, destruye la app.
- **run_tests.py**: tests de algoritmo con 32 archivos de audio reales. 4 suites: detection, classification, UI básica, UI verification.

### Capa 2: Orquestador

- **verify_implementation.py**: combina verificadores en dos modos:
  - `--quick` (~15s): boot + análisis de 2 archivos
  - `--full` (~2-3 min): boot + UI verification + algorithm tests completos

### Capa 3: Scripts de conveniencia

- `quick_check.sh` (~30s): quick verification + full test suite
- `full_check.sh` (~2-3 min): verificación completa

## Decisiones técnicas clave

- Las suites de UI verification se ejecutan en **subprocess** para evitar conflictos de Tkinter (CTkImage/PhotoImage queda inválido entre roots)
- `tests.json` es **append-only**: nunca se editan ni eliminan tests existentes
- Los checks de UI **nunca** invocan botones que abren diálogos (bloquearían el thread)
- ExceptionCapture sobreescribe `sys.excepthook` para capturar excepciones que Tkinter traga silenciosamente

## Protocolo de verificación

| Tipo de cambio | Comando | Tiempo |
|---------------|---------|--------|
| UI | `bash tests/quick_check.sh` | ~30s |
| Algoritmo/constantes | `bash tests/full_check.sh` | ~2-3 min |
| Bugfix simple | `python3 tests/verify_implementation.py --quick` | ~15s |
| Refactor grande | `bash tests/full_check.sh` | ~2-3 min |

Regla: nunca reportar una tarea como completada sin ejecutar la verificación correspondiente.

## Relevancia para el TFG

El sistema de verificación es un ejemplo de **testing con datos reales** (32 archivos de audio) frente al testing unitario con mocks. La decisión de usar archivos reales, con sus implicaciones en tiempo de ejecución (~42s vs ~2s), es una decisión de diseño documentable.
