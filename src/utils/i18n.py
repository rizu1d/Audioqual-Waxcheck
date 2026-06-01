"""Internationalization (i18n) module.

Simple dictionary-based translation system. Translations live in
``src/locales/<lang>.json``.  The active language is read from
``AppSettings().language`` (defaults to ``"es"``).

Usage::

    from ..utils.i18n import t, t_status, t_quality_level
    label = t("status.ready")                       # "Listo" / "Ready"
    label = t("overlay.counter", completed=3, total=10)  # "3 / 10 archivos"
    display = t_status("Transcode detectado")       # translated status
    display = t_quality_level("bajo")               # "Bajo" / "Low"
"""

import json
import os
import sys
from typing import Any, Dict


def _locales_dir() -> str:
    """Resolve the locales directory in both development and frozen mode."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller extracts datas under sys._MEIPASS (mapped to src/locales)
        return os.path.join(sys._MEIPASS, "src", "locales")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "locales")


_LOCALES_DIR = _locales_dir()

# Maps internal STATUS_* constant values → translation keys
_STATUS_KEY_MAP = {
    "OK": "status.ok",
    "Transcode detectado": "status.transcode_detected",
    "Lossless": "status.lossless",
    "Baja calidad": "status.low_quality",
    "Error": "status.error",
    "Pendiente": "status.pending",
    "Analizando...": "status.analyzing",
    "Incierto": "status.uncertain",
    "Calidad variable": "status.variable_quality",
}

_strings: Dict[str, Any] = {}
_current_lang: str = ""


def _load_language(lang: str):
    """Load a language file into the module-level cache."""
    global _strings, _current_lang
    path = os.path.join(_LOCALES_DIR, f"{lang}.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            _strings = json.load(f)
    except FileNotFoundError:
        # Fallback to Spanish
        fallback = os.path.join(_LOCALES_DIR, "es.json")
        with open(fallback, "r", encoding="utf-8") as f:
            _strings = json.load(f)
        lang = "es"
    _current_lang = lang


def init(lang: str = ""):
    """Initialize or switch the active language.

    If *lang* is empty, reads from AppSettings.
    """
    if not lang:
        from .settings import AppSettings
        lang = AppSettings().language
    _load_language(lang)


def get_language() -> str:
    """Return the currently active language code."""
    return _current_lang


def t(key: str, **kwargs) -> str:
    """Translate *key*, formatting with *kwargs* if provided.

    Returns the key itself if no translation is found (graceful fallback).
    """
    if not _strings:
        init()

    value = _strings.get(key, key)

    # Some keys store lists (e.g. verified messages) — return as-is
    if isinstance(value, list):
        return value

    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError):
            return value
    return value


def t_status(internal_status: str) -> str:
    """Translate an internal STATUS_* value for display."""
    if not _strings:
        init()
    key = _STATUS_KEY_MAP.get(internal_status)
    if key:
        return _strings.get(key, internal_status)
    return internal_status


def t_quality_level(level: str) -> str:
    """Translate a quality level key ('bajo', 'medio', etc.) for display."""
    if not _strings:
        init()
    key = f"quality_level.{level}"
    return _strings.get(key, level.capitalize())
