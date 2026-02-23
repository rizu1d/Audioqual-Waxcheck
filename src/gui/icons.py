"""Programmatic icon generation using PIL.ImageDraw.

Icons are drawn at 2x resolution on transparent RGBA canvases,
then wrapped in CTkImage for HiDPI display. Cached at module level.
"""

import math
from typing import Tuple

import customtkinter as ctk
from PIL import Image, ImageDraw

_COLOR = "#F3F1E5"
_STROKE_RATIO = 0.036

_cache: dict = {}


def _get_cached(key, factory):
    if key not in _cache:
        _cache[key] = factory()
    return _cache[key]


def _canvas(size):
    cs = size * 2
    img = Image.new("RGBA", (cs, cs), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), cs


def _sw(cs):
    return max(2, round(cs * _STROKE_RATIO))


def _c(hex_color):
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def _wrap(img, size):
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


# ── Settings (gear) ───────────────────────────────────────────────


def icon_settings(size: int = 28, color: str = _COLOR) -> ctk.CTkImage:
    """Gear icon."""
    def factory():
        img, draw, cs = _canvas(size)
        sw = _sw(cs)
        c = _c(color)
        cx, cy = cs / 2, cs / 2
        outer_r = cs * 0.38
        inner_r = cs * 0.28
        teeth = 8
        points = []
        for i in range(teeth * 2):
            angle = math.pi * 2 * i / (teeth * 2) - math.pi / 2
            r = outer_r if i % 2 == 0 else inner_r
            points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
        draw.polygon(points, outline=c, width=sw)
        center_r = cs * 0.1
        draw.ellipse(
            [cx - center_r, cy - center_r, cx + center_r, cy + center_r],
            outline=c, width=sw,
        )
        return _wrap(img, size)

    return _get_cached(("settings", size, color), factory)


# ── Volume icons ──────────────────────────────────────────────────


def _draw_speaker(draw, cs, color):
    """Speaker cone shared by all volume icons."""
    bx0 = cs * 0.15
    by0 = cs * 0.38
    bx1 = cs * 0.30
    by1 = cs * 0.62
    draw.rectangle([bx0, by0, bx1, by1], fill=color)
    draw.polygon([(bx1, by0), (cs * 0.48, cs * 0.22),
                  (cs * 0.48, cs * 0.78), (bx1, by1)], fill=color)


def icon_volume_high(size: int = 14, color: str = _COLOR) -> ctk.CTkImage:
    """Speaker + 2 arcs."""
    def factory():
        img, draw, cs = _canvas(size)
        sw = _sw(cs)
        c = _c(color)
        _draw_speaker(draw, cs, c)
        cx, cy = cs * 0.52, cs / 2
        for r_frac in [0.18, 0.30]:
            r = cs * r_frac
            draw.arc([cx - r, cy - r, cx + r, cy + r],
                     start=-45, end=45, fill=c, width=sw)
        return _wrap(img, size)

    return _get_cached(("vol_high", size, color), factory)


def icon_volume_low(size: int = 14, color: str = _COLOR) -> ctk.CTkImage:
    """Speaker + 1 arc."""
    def factory():
        img, draw, cs = _canvas(size)
        sw = _sw(cs)
        c = _c(color)
        _draw_speaker(draw, cs, c)
        cx, cy = cs * 0.52, cs / 2
        r = cs * 0.18
        draw.arc([cx - r, cy - r, cx + r, cy + r],
                 start=-45, end=45, fill=c, width=sw)
        return _wrap(img, size)

    return _get_cached(("vol_low", size, color), factory)


def icon_volume_mute(size: int = 14, color: str = _COLOR) -> ctk.CTkImage:
    """Speaker + X."""
    def factory():
        img, draw, cs = _canvas(size)
        sw = _sw(cs)
        c = _c(color)
        _draw_speaker(draw, cs, c)
        xx, xy = cs * 0.62, cs / 2
        xr = cs * 0.12
        draw.line([(xx - xr, xy - xr), (xx + xr, xy + xr)], fill=c, width=sw)
        draw.line([(xx - xr, xy + xr), (xx + xr, xy - xr)], fill=c, width=sw)
        return _wrap(img, size)

    return _get_cached(("vol_mute", size, color), factory)


# ── Search (magnifying glass) ────────────────────────────────────


def icon_search(size: int = 16, color: str = _COLOR) -> ctk.CTkImage:
    """Magnifying glass icon."""
    def factory():
        img, draw, cs = _canvas(size)
        sw = _sw(cs)
        c = _c(color)
        # Lens circle (centered at 0.43 so visual weight sits at canvas center)
        cx, cy = cs * 0.43, cs * 0.43
        r = cs * 0.24
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c, width=sw)
        # Handle line (diagonal from bottom-right of circle)
        offset = r * 0.707  # cos(45°)
        draw.line(
            [(cx + offset, cy + offset), (cs * 0.80, cs * 0.80)],
            fill=c, width=sw,
        )
        return _wrap(img, size)

    return _get_cached(("search", size, color), factory)


# ── Quality dot (colored circle for badges) ──────────────────────


def icon_quality_dot(size: int = 7, color: str = "#E85555") -> ctk.CTkImage:
    """Small filled circle for quality level badges."""
    def factory():
        cs = size * 2  # Retina resolution
        img = Image.new("RGBA", (cs, cs), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        c = _c(color)
        margin = 1
        draw.ellipse([margin, margin, cs - margin - 1, cs - margin - 1], fill=c)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))

    return _get_cached(("quality_dot", size, color), factory)


# ── Close (X mark) ───────────────────────────────────────────────


def icon_close(size: int = 12, color: str = _COLOR) -> ctk.CTkImage:
    """X mark icon."""
    def factory():
        img, draw, cs = _canvas(size)
        sw = _sw(cs)
        c = _c(color)
        margin = cs * 0.25
        draw.line([(margin, margin), (cs - margin, cs - margin)], fill=c, width=sw)
        draw.line([(cs - margin, margin), (margin, cs - margin)], fill=c, width=sw)
        return _wrap(img, size)

    return _get_cached(("close", size, color), factory)
