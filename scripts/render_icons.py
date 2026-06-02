#!/usr/bin/env python3
"""Re-render the app's SVG icons to 256x256 PNGs in src/assets/.

This is a BUILD-TIME tool, not part of the runtime app. The app loads the
pre-rendered PNGs (see src/utils/icon_utils.py), so cairosvg/libcairo is only
needed here, not in requirements.txt.

Usage:
    pip install cairosvg          # build-time only
    python3 scripts/render_icons.py

Run it after editing any of the SVG sources below, then commit the updated PNGs.
"""

import os
import sys

# SVG sources actually loaded by the app (keep in sync with main_window.py /
# app.py). Each is rendered to "<name>.png" at RENDER_SIZE px.
ICONS = [
    "logo-waxcheckV2.svg",
    "drop-iconV2.svg",
    "watcher-icon-OFF.svg",
    "watcher-iconV3.svg",
    "clean-iconV2.svg",
    "spectrum-iconV2.svg",
    "Metadata-iconV3.svg",
    "settings-iconV3.svg",
]

RENDER_SIZE = 256  # matches the resolution icon_utils.py downscales from

ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "assets"
)


def main() -> int:
    try:
        import cairosvg
    except ImportError:
        print("cairosvg is required for this build tool: pip install cairosvg")
        return 1

    for svg_name in ICONS:
        svg_path = os.path.join(ASSETS_DIR, svg_name)
        if not os.path.isfile(svg_path):
            print(f"  SKIP (missing): {svg_name}")
            continue
        png_name = os.path.splitext(svg_name)[0] + ".png"
        png_path = os.path.join(ASSETS_DIR, png_name)
        cairosvg.svg2png(
            url=svg_path,
            write_to=png_path,
            output_width=RENDER_SIZE,
            output_height=RENDER_SIZE,
        )
        print(f"  rendered {svg_name} -> {png_name} ({RENDER_SIZE}px)")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
