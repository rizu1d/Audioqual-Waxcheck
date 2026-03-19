"""SVG icon loading utilities using cairosvg, with PNG fallback.

If cairosvg/cairo is not available (common on Windows without GTK),
falls back to loading a PNG version of the icon from src/assets/.
"""

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

try:
    import cairosvg  # noqa: E402  (must come after env setup)
    HAS_CAIRO = True
except (ImportError, OSError):
    HAS_CAIRO = False

from .resource_path import get_assets_dir

_ASSETS_DIR = get_assets_dir()


def load_svg_icon(svg_filename: str, size: int) -> ctk.CTkImage:
    """Load an SVG file from src/assets/ and return a CTkImage at the given size.

    Renders at 2x resolution for Retina displays; CTkImage handles scaling.
    If cairosvg is not available, attempts to load a PNG fallback with the
    same base name (e.g., "logo-waxcheckV2.svg" → "logo-waxcheckV2.png"
    or "logo-WaxCheck.png").
    """
    # Try SVG rendering first
    if HAS_CAIRO:
        try:
            svg_path = os.path.join(_ASSETS_DIR, svg_filename)
            png_bytes = cairosvg.svg2png(
                url=svg_path, output_width=size * 2, output_height=size * 2
            )
            image = Image.open(io.BytesIO(png_bytes))
            return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
        except Exception:
            pass

    # Fallback: try PNG with same base name
    base_name = os.path.splitext(svg_filename)[0]
    for png_name in [f"{base_name}.png", svg_filename.replace(".svg", ".png")]:
        png_path = os.path.join(_ASSETS_DIR, png_name)
        if os.path.isfile(png_path):
            image = Image.open(png_path).convert("RGBA")
            image = image.resize((size * 2, size * 2), Image.LANCZOS)
            return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))

    # Last resort: transparent placeholder
    image = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
