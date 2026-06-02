# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Linux build."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs

block_cipher = None

# Get the project root
project_root = Path(SPECPATH).parent

# Bundle app data: fonts/icons (src/assets) and translations (src/locales).
# Destination paths match what resource_path.py / i18n.py expect under sys._MEIPASS.
datas = [
    (str(project_root / 'src' / 'assets'), 'src/assets'),
    (str(project_root / 'src' / 'locales'), 'src/locales'),
]

# Native audio libs: libsndfile (ships in _soundfile_data) and PortAudio
# (ships in _sounddevice_data). The official PyInstaller hooks already collect
# these, but we add them explicitly as a safety net across hook versions.
# If absent in the wheels, install system packages libsndfile1 / libportaudio2.
binaries = []
for _pkg in ('_soundfile_data', '_sounddevice_data'):
    try:
        binaries += collect_dynamic_libs(_pkg)
    except Exception:
        pass

# Analysis
a = Analysis(
    [str(project_root / 'src' / 'main.py')],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'customtkinter',
        'tkinterdnd2',
        'librosa',
        'soundfile',
        'numpy',
        'mutagen',
        'mutagen.mp3',
        'mutagen.flac',
        'mutagen.wave',
        'PIL',
        'PIL._tkinter_finder',
        'watchdog',
        'watchdog.observers',
        'watchdog.events',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'sphinx',
        'setuptools',
        'wheel',
        # scikit-learn: dependencia transitiva de librosa que el código nunca
        # alcanza (verificado: 0 imports en el repo y no se carga en runtime).
        # Excluida para reducir ~45 MB del paquete.
        'sklearn',
        # cairosvg/libcairo: solo se usaba para rasterizar iconos SVG en
        # runtime. Ahora los iconos se cargan como PNG pre-renderizados
        # (scripts/render_icons.py), así que cairo ya no hace falta.
        'cairosvg',
        'cairocffi',
        'cffi',
        # matplotlib: solo se usaba para una colormap (LinearSegmentedColormap),
        # ahora reconstruida como LUT numpy en spectrogram_window.py. Excluirla
        # quita matplotlib y sus backends/fonts del paquete.
        'matplotlib',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove duplicate binaries/datas
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AudioQual',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AudioQual',
)
