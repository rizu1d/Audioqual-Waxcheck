# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for macOS build."""

import sys
from pathlib import Path

block_cipher = None

# Get the project root
project_root = Path(SPECPATH).parent

# Analysis
a = Analysis(
    [str(project_root / 'src' / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        'customtkinter',
        'tkinterdnd2',
        'librosa',
        'soundfile',
        'numpy',
        'matplotlib',
        'matplotlib.backends.backend_tkagg',
        'mutagen',
        'mutagen.mp3',
        'mutagen.flac',
        'mutagen.wave',
        'PIL',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'sphinx',
        'setuptools',
        'wheel',
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
    argv_emulation=True,
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

app = BUNDLE(
    coll,
    name='AudioQual.app',
    icon=None,  # Add icon path here if available: 'assets/icon.icns'
    bundle_identifier='com.audioqual.app',
    info_plist={
        'CFBundleName': 'AudioQual',
        'CFBundleDisplayName': 'AudioQual',
        'CFBundleGetInfoString': 'Audio Quality Analyzer',
        'CFBundleIdentifier': 'com.audioqual.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': 'True',
        'NSRequiresAquaSystemAppearance': 'False',
    },
)
