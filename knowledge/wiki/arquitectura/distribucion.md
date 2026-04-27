---
title: Distribución y empaquetado
created: 2026-04-27
updated: 2026-04-27
sources: [DISTRIBUCION-15march.txt]
tags: [distribucion, arquitectura]
---

# Distribución y empaquetado

## PyInstaller

La app se empaqueta con PyInstaller para distribución standalone. Specs en `build/`:
- `waxcheck_macos.spec` — macOS (Intel + Apple Silicon)
- `waxcheck_windows.spec` — Windows 64-bit

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
4. **Sin build Linux**: habría que crear .spec o usar AppImage/Flatpak

## Requisitos mínimos

- CPU: dual-core x86_64 o ARM64 (2 GHz+), sin GPU
- RAM: 4 GB mínimo, 8 GB recomendado
- Disco: ~400-500 MB + ~4.5 MB por archivo en caché
- Pantalla: 1280×720 mínimo, soporta HiDPI/Retina
