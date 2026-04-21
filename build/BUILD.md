# WaxCheck — Guía de Build y Distribución

## Requisitos previos

```bash
# Python 3.9+ con pip
python3 --version   # >= 3.9

# Instalar dependencias del proyecto + PyInstaller
python3 -m pip install -r requirements.txt
python3 -m pip install pyinstaller
```

## Build macOS

### Generar WaxCheck.app

```bash
cd <carpeta_del_proyecto>
bash build/build_macos.sh
```

El resultado estará en `dist/WaxCheck.app`.

### Generar .dmg instalador (para compartir)

```bash
bash build/build_macos.sh --dmg
```

Genera `dist/WaxCheck-0.1.0-beta-macOS.dmg` (~100-130 MB).
El DMG incluye un atajo a Applications para arrastrar e instalar.

### Nota sobre apps sin firmar

Al no tener Apple Developer ID, macOS bloqueará la app la primera vez.
Instrucciones para los testers:

1. Intentar abrir WaxCheck normalmente (aparecerá un aviso de seguridad)
2. Ir a **Ajustes del Sistema → Privacidad y Seguridad**
3. Bajo "Seguridad", verán un mensaje sobre WaxCheck — pulsar **Abrir igualmente**
4. Alternativamente: click derecho sobre WaxCheck.app → **Abrir** → **Abrir** en el diálogo

Solo hay que hacerlo una vez; después se abre normalmente.

## Build Windows

### Generar carpeta portable

```cmd
cd <carpeta_del_proyecto>
build\build_windows.bat
```

El resultado estará en `dist\WaxCheck\WaxCheck.exe`.

### Generar .zip para compartir

```cmd
build\build_windows.bat --zip
```

Genera `dist\WaxCheck-0.1.0-beta-Windows.zip` (~110-140 MB).

### Nota sobre antivirus

Windows Defender y otros antivirus pueden marcar ejecutables de PyInstaller como sospechosos (falso positivo). Sin un certificado de code signing, esto es normal. Los testers pueden:

1. Cuando aparezca el aviso de SmartScreen, pulsar **Más información** → **Ejecutar de todos modos**
2. Si el antivirus lo bloquea, añadir una excepción para la carpeta `WaxCheck`

## Estructura generada

```
dist/
├── WaxCheck.app/                    (macOS)
│   └── Contents/
│       ├── MacOS/WaxCheck           Ejecutable
│       ├── Resources/               Icono, assets
│       └── Info.plist               Metadatos de la app
│
├── WaxCheck/                        (Windows)
│   ├── WaxCheck.exe                 Ejecutable principal
│   ├── src/assets/                  Iconos, fuentes, imágenes
│   └── *.dll, *.pyd                 Dependencias
│
├── WaxCheck-0.1.0-beta-macOS.dmg    (si se usó --dmg)
└── WaxCheck-0.1.0-beta-Windows.zip  (si se usó --zip)
```

## Archivos de build

| Archivo | Descripción |
|---------|-------------|
| `build/waxcheck_macos.spec` | Spec PyInstaller para macOS |
| `build/waxcheck_windows.spec` | Spec PyInstaller para Windows |
| `build/build_macos.sh` | Script de build macOS (bash) |
| `build/build_windows.bat` | Script de build Windows (cmd) |
| `build/icons/waxcheck.icns` | Icono macOS (generado del SVG) |
| `build/icons/waxcheck.ico` | Icono Windows (generado del SVG) |

## Troubleshooting

**"No module named customtkinter"** al ejecutar la app buildeada:
Asegúrate de que `customtkinter` está instalado en el mismo entorno Python donde ejecutas PyInstaller. El spec necesita importar el módulo para localizar sus archivos.

**La app se abre pero no muestra iconos SVG:**
Verifica que `cairosvg` y sus dependencias nativas (libcairo) están instaladas. En macOS: `brew install cairo`. En Windows: cairo se incluye con el paquete pip de `cairocffi`.

**Error "tkdnd" en Windows:**
`tkinterdnd2` necesita la DLL de tkdnd. El spec ya incluye todo el directorio de tkinterdnd2, pero si falla, verifica que la DLL está en la carpeta de salida.
