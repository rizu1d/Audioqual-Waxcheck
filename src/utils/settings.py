"""Application settings with JSON persistence."""

import json
import os
from pathlib import Path
from typing import Any, Dict

# Settings file location: ~/.audioqual/settings.json
_SETTINGS_DIR = os.path.join(Path.home(), ".audioqual")
_SETTINGS_FILE = os.path.join(_SETTINGS_DIR, "settings.json")

# Default values for all settings
_DEFAULTS: Dict[str, Any] = {
    "rename_on_save": False,
    "watcher_folder": "",
    "watcher_auto_start": False,
    "output_device": "",
    "language": "es",
}


class AppSettings:
    """Persistent application settings backed by a JSON file."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data: Dict[str, Any] = dict(_DEFAULTS)
            cls._instance._load()
        return cls._instance

    # ─── Public API ──────────────────────────────────────────────────

    @property
    def rename_on_save(self) -> bool:
        return self._data.get("rename_on_save", False)

    @rename_on_save.setter
    def rename_on_save(self, value: bool):
        self._data["rename_on_save"] = value
        self._save()

    @property
    def watcher_folder(self) -> str:
        return self._data.get("watcher_folder", "")

    @watcher_folder.setter
    def watcher_folder(self, value: str):
        self._data["watcher_folder"] = value
        self._save()

    @property
    def watcher_auto_start(self) -> bool:
        return self._data.get("watcher_auto_start", False)

    @watcher_auto_start.setter
    def watcher_auto_start(self, value: bool):
        self._data["watcher_auto_start"] = value
        self._save()

    @property
    def output_device(self) -> str:
        return self._data.get("output_device", "")

    @output_device.setter
    def output_device(self, value: str):
        self._data["output_device"] = value
        self._save()

    @property
    def language(self) -> str:
        return self._data.get("language", "es")

    @language.setter
    def language(self, value: str):
        self._data["language"] = value
        self._save()

    # ─── Persistence ─────────────────────────────────────────────────

    def _load(self):
        """Load settings from disk, merging with defaults."""
        try:
            if os.path.exists(_SETTINGS_FILE):
                with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                if isinstance(stored, dict):
                    for key in _DEFAULTS:
                        if key in stored:
                            self._data[key] = stored[key]
        except Exception:
            pass

    def _save(self):
        """Write current settings to disk."""
        try:
            os.makedirs(_SETTINGS_DIR, exist_ok=True)
            with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass
