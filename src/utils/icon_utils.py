"""SVG icon loading utilities using cairosvg."""

import io
import os
import sys

import customtkinter as ctk
from PIL import Image

# Ensure Homebrew's libcairo is discoverable on macOS (Anaconda doesn't include it).
if sys.platform == "darwin":
    _brew_lib = "/opt/homebrew/lib"
    _fallback = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    if _brew_lib not in _fallback:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = (
            f"{_brew_lib}:{_fallback}" if _fallback else _brew_lib
        )

import cairosvg  # noqa: E402  (must come after env setup)

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")


def load_svg_icon(svg_filename: str, size: int) -> ctk.CTkImage:
    """Load an SVG file from src/assets/ and return a CTkImage at the given size.

    Renders at 2x resolution for Retina displays; CTkImage handles scaling.
    """
    svg_path = os.path.join(_ASSETS_DIR, svg_filename)
    png_bytes = cairosvg.svg2png(
        url=svg_path, output_width=size * 2, output_height=size * 2
    )
    image = Image.open(io.BytesIO(png_bytes))
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
