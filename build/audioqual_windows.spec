# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Windows build."""

import os
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
        'soundfile',
        'audioread',
        'audioread.macca',
        'audioread.ffdec',
        'audioread.gstdec',
        'audioread.rawread',
        'soxr',
        'numpy',
        'scipy',
        'scipy.signal',
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
        # librosa: eliminada. Sus 3 usos espectrales son ahora numpy/scipy y la
        # decodificación va por soundfile + audioread. numba/llvmlite solo
        # entraban a través de librosa (0 usos directos), así que se excluye
        # toda la cadena — era ~110 MB de llvmlite, el mayor objetivo de peso.
        'librosa',
        'numba',
        'llvmlite',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# --- Trim unused Pillow native libraries ---
# The app only decodes PNG and JPEG (toolbar/logo icons + APIC/FLAC cover
# art); the spectrogram is built from an in-memory RGB array, and ImageDraw
# is used only for shapes (no truetype text). The core extension (_imaging)
# hard-links libtiff/libjpeg/libopenjp2/libz/libxcb, so those MUST stay. Only
# the libraries reached exclusively through lazily-imported plugins are
# removable: AVIF (_avif), WebP (_webp), the font stack (_imagingft →
# freetype/harfbuzz/brotli) and the ICC color engine (_imagingcms → lcms).
# We drop both those plugin extensions and their private dylibs. PIL.init()
# imports the WebP/AVIF plugins inside try/except, so their absence degrades
# gracefully; ImageFont/ImageCms are never imported by the app. Saves ~7.5 MB.
_PIL_DROP_TOKENS = (
    # private dylibs reached only via the plugins below
    'libavif', 'libwebp', 'libsharpyuv',
    'libfreetype', 'libharfbuzz', 'libbrotli', 'liblcms',
    # the plugin C-extensions themselves
    '_webp.', '_avif.', '_imagingft.', '_imagingcms.',
)


def _is_unused_pil_binary(dest, source):
    src = (source or '').replace('\\', '/').lower()
    if '/pil/' not in src and '/pil.libs/' not in src:
        return False
    name = os.path.basename(dest).lower()
    return any(tok in name for tok in _PIL_DROP_TOKENS)


a.binaries = [b for b in a.binaries if not _is_unused_pil_binary(b[0], b[1])]

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
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if available: 'assets/icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name='AudioQual',
)
