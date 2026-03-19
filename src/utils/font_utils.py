"""Cross-platform custom font loading for Outfit and Space Mono.

Registers TTF files from src/assets/fonts/ with the OS font system.
Best-effort: silent failure falls back to system fonts via tkinter.
"""

import os
import sys
import ctypes
from pathlib import Path

from .resource_path import get_assets_dir

FONTS_DIR = Path(get_assets_dir()) / "fonts"


def load_custom_fonts():
    """Register all .ttf fonts in the assets/fonts directory with the OS."""
    if not FONTS_DIR.is_dir():
        return

    font_files = list(FONTS_DIR.glob("*.ttf"))
    if not font_files:
        return

    if sys.platform == "darwin":
        _load_fonts_macos(font_files)
    elif sys.platform == "win32":
        _load_fonts_windows(font_files)
    else:
        _load_fonts_linux(font_files)


def _load_fonts_macos(font_files):
    """Register fonts on macOS using CoreText (process-scoped)."""
    try:
        ct = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/CoreText.framework/CoreText"
        )
        cf = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )

        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32
        ]
        cf.CFURLCreateWithFileSystemPath.restype = ctypes.c_void_p
        cf.CFURLCreateWithFileSystemPath.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int32, ctypes.c_bool
        ]
        cf.CFRelease.argtypes = [ctypes.c_void_p]

        ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
        ct.CTFontManagerRegisterFontsForURL.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p
        ]

        kCFStringEncodingUTF8 = 0x08000100
        kCFURLPOSIXPathStyle = 0
        kCTFontManagerScopeProcess = 1

        for font_path in font_files:
            cf_str = cf.CFStringCreateWithCString(
                None, str(font_path).encode("utf-8"), kCFStringEncodingUTF8
            )
            if not cf_str:
                continue
            url = cf.CFURLCreateWithFileSystemPath(
                None, cf_str, kCFURLPOSIXPathStyle, False
            )
            cf.CFRelease(cf_str)
            if not url:
                continue
            ct.CTFontManagerRegisterFontsForURL(
                url, kCTFontManagerScopeProcess, None
            )
            cf.CFRelease(url)
    except Exception:
        pass


def _load_fonts_windows(font_files):
    """Register fonts on Windows using GDI32 (process-private)."""
    try:
        FR_PRIVATE = 0x10
        gdi32 = ctypes.windll.gdi32
        for font_path in font_files:
            gdi32.AddFontResourceExW(str(font_path), FR_PRIVATE, 0)
    except Exception:
        pass


def _load_fonts_linux(font_files):
    """Install fonts on Linux to the user font directory."""
    try:
        import shutil
        user_fonts = Path.home() / ".local" / "share" / "fonts"
        user_fonts.mkdir(parents=True, exist_ok=True)
        copied = False
        for font_path in font_files:
            dest = user_fonts / font_path.name
            if not dest.exists():
                shutil.copy2(font_path, dest)
                copied = True
        if copied:
            os.system("fc-cache -f 2>/dev/null &")
    except Exception:
        pass
