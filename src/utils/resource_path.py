"""Resource path resolution for both development and PyInstaller frozen mode.

When running from source, assets live at src/assets/ relative to __file__.
When frozen by PyInstaller, they live in sys._MEIPASS (the temp extraction dir).
"""

import os
import sys


def is_frozen() -> bool:
    """True if running inside a PyInstaller bundle."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_assets_dir() -> str:
    """Return the absolute path to the assets directory."""
    if is_frozen():
        # PyInstaller extracts to sys._MEIPASS; datas are mapped there
        return os.path.join(sys._MEIPASS, "src", "assets")
    else:
        # Development: resolve relative to this file
        return os.path.join(os.path.dirname(__file__), "..", "assets")


def get_resource(relative_path: str) -> str:
    """Return absolute path for a resource relative to assets/.

    Example: get_resource("fonts/Outfit-Regular.ttf")
    """
    return os.path.join(get_assets_dir(), relative_path)
