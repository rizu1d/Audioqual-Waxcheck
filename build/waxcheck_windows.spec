# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for WaxCheck Windows build.

Usage:
    cd <project_root>
    pyinstaller build/waxcheck_windows.spec
"""

import os
import sys
from pathlib import Path

block_cipher = None

# Get the project root (parent of build/)
project_root = Path(SPECPATH).parent

# ── Collect customtkinter and tkinterdnd2 data files ──
import customtkinter
import tkinterdnd2

ctk_path = Path(customtkinter.__file__).parent
dnd_path = Path(tkinterdnd2.__file__).parent

# ── Data files to bundle ──
datas = [
    # App assets (fonts, icons, images)
    (str(project_root / 'src' / 'assets'), os.path.join('src', 'assets')),
    # customtkinter theme files (required for CTk widgets)
    (str(ctk_path), 'customtkinter'),
    # tkinterdnd2 platform libraries
    (str(dnd_path), 'tkinterdnd2'),
]

# ── Analysis ──
a = Analysis(
    [str(project_root / 'src' / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # UI frameworks
        'customtkinter',
        'tkinterdnd2',
        # Audio analysis
        'librosa',
        'librosa.core',
        'librosa.feature',
        'librosa.util',
        'soundfile',
        'sounddevice',
        'audioread',
        # Scientific
        'numpy',
        'scipy',
        'scipy.signal',
        'scipy.fft',
        # Visualization
        'matplotlib',
        'matplotlib.backends.backend_agg',
        'matplotlib.backends.backend_tkagg',
        # Image / SVG
        'PIL',
        'PIL._tkinter_finder',
        'cairosvg',
        'cairocffi',
        # Audio metadata
        'mutagen',
        'mutagen.mp3',
        'mutagen.flac',
        'mutagen.wave',
        'mutagen.aiff',
        'mutagen.mp4',
        'mutagen.oggvorbis',
        # File watching
        'watchdog',
        'watchdog.observers',
        'watchdog.events',
        # App modules
        'src.utils.resource_path',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ── Testing / dev tools ──
        'pytest', 'sphinx', 'setuptools', 'wheel', 'pip',
        'IPython', 'jupyter', 'notebook', 'tkinter.test',
        # ── GUI frameworks we don't use (Anaconda drags these in) ──
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
        # ── Data science stack (not needed for audio analysis) ──
        'pandas', 'sklearn', 'scikit-learn', 'skimage', 'scikit-image',
        'statsmodels', 'astropy', 'h5py', 'tables',
        # ── Arrow / Parquet / gRPC (Anaconda transitive deps) ──
        'pyarrow', 'grpc', 'grpcio', 'google.protobuf',
        'google.cloud', 'google.auth',
        # ── AWS SDK (Anaconda bundles this) ──
        'boto3', 'botocore', 's3transfer',
        # ── Other heavy unused packages ──
        'lxml', 'sqlalchemy', 'zmq', 'tornado',
        'numba', 'llvmlite', 'dask', 'bokeh', 'plotly',
        'sympy', 'networkx', 'nltk', 'spacy',
        'cv2', 'opencv',
        'cryptography',
        # ── Matplotlib backends we don't need ──
        'matplotlib.backends.backend_qt5agg',
        'matplotlib.backends.backend_qt5',
        'matplotlib.backends.backend_wxagg',
        'matplotlib.backends.backend_gtk3agg',
        'matplotlib.backends.backend_gtk4agg',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── Strip bloated binaries that Anaconda drags in ──
# These are native libs (.dll/.so) that excludes= doesn't always catch
_bloat_prefixes = (
    'libLLVM', 'Qt5', 'Qt6', 'libarrow', 'arrow', 'libgrpc', 'grpc',
    'libprotobuf', 'protobuf', 'libhdf5', 'hdf5', 'libaws', 'aws-',
    'libgoogle', 'libicu', 'icu',
)
a.binaries = [b for b in a.binaries if not any(
    b[0].startswith(p) or b[0].split('/')[-1].startswith(p)
    for p in _bloat_prefixes
)]

# ── Build ──
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WaxCheck',
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
    icon=str(project_root / 'build' / 'icons' / 'waxcheck.ico'),
    version_info=None,  # Can add a version .rc file later
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WaxCheck',
)
