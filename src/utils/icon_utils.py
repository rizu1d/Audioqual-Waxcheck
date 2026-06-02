"""Icon loading utilities.

Icons ship as pre-rendered 256x256 PNGs in src/assets/. The SVG sources are
kept in the repo and can be re-rendered with scripts/render_icons.py, but they
are not needed at runtime (so the app has no cairosvg/libcairo dependency).
"""

import os

import customtkinter as ctk
from PIL import Image

from .resource_path import get_assets_dir

_ASSETS_DIR = get_assets_dir()


def load_svg_icon(icon_name: str, size: int) -> ctk.CTkImage:
    """Load the PNG icon matching *icon_name* and return a CTkImage at *size*.

    Icons are stored as 256x256 PNGs alongside their SVG sources. The PNG is
    downscaled to 2x the requested size (for Retina sharpness); CTkImage handles
    display scaling. Accepts either a ``.svg`` or ``.png`` name (the extension is
    ignored) so existing call sites keep working unchanged.
    """
    base_name = os.path.splitext(icon_name)[0]
    png_path = os.path.join(_ASSETS_DIR, f"{base_name}.png")
    if os.path.isfile(png_path):
        image = Image.open(png_path).convert("RGBA")
        image = image.resize((size * 2, size * 2), Image.LANCZOS)
        return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))

    # Last resort: transparent placeholder
    image = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
