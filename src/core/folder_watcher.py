"""Folder monitoring with watchdog for automatic file detection."""

import os
import sys
import threading
import time
from typing import Callable, List, Optional, Set

from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

from ..utils.file_utils import is_supported_audio_file

# macOS FSEventsObserver has a bug with Unicode paths (e.g. "Música").
# PollingObserver works universally, with a 3-second polling interval
# that is perfectly acceptable for a file-download monitoring use case
# (the stability loop already waits ~2s of constant size before dispatch).
_POLLING_INTERVAL = 3  # seconds

# Temporary file extensions to ignore (downloads in progress)
_TEMP_EXTENSIONS = {
    ".crdownload", ".part", ".tmp", ".download",
    ".partial", ".temp", ".incomplete",
}

# How often to check file size stability (seconds)
_STABILITY_CHECK_INTERVAL = 1.0
# File must be stable for this many consecutive checks (2 checks * 1s = 2s)
_STABILITY_REQUIRED_CHECKS = 2
# Maximum time to wait for a file to stabilize (seconds)
_STABILITY_TIMEOUT = 120


class _AudioFileHandler(FileSystemEventHandler):
    """Watchdog handler that filters for supported audio files."""

    def __init__(self, on_file_detected: Callable[[str], None]):
        super().__init__()
        self._on_file_detected = on_file_detected

    def on_created(self, event):
        if event.is_directory:
            return
        self._check_file(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        # Handles renames like .crdownload -> .mp3
        self._check_file(event.dest_path)

    def _check_file(self, filepath: str):
        ext = os.path.splitext(filepath)[1].lower()
        if ext in _TEMP_EXTENSIONS:
            return
        if is_supported_audio_file(filepath):
            self._on_file_detected(filepath)


class FolderWatcher:
    """Monitors a folder for new audio files and dispatches them when stable."""

    def __init__(self, on_files_ready: Optional[Callable[[List[str]], None]] = None):
        self.on_files_ready = on_files_ready
        self._observer: Optional[PollingObserver] = None
        self._stability_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._watch_path: Optional[str] = None
        # Files waiting for stability check: filepath -> (last_size, stable_count)
        self._pending_files: dict = {}
        self._pending_lock = threading.Lock()
        # Already dispatched files (avoid re-dispatching)
        self._dispatched_files: Set[str] = set()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._observer is not None and self._observer.is_alive()

    @property
    def watch_path(self) -> Optional[str]:
        with self._lock:
            return self._watch_path

    def start(self, folder_path: str) -> bool:
        """Start monitoring a folder. Returns True on success."""
        if not os.path.isdir(folder_path):
            return False

        # Stop any existing watcher first (outside _lock to avoid deadlock)
        if self._observer and self._observer.is_alive():
            self.stop()

        with self._lock:
            self._stop_event.clear()
            self._watch_path = folder_path
            self._dispatched_files.clear()

            handler = _AudioFileHandler(on_file_detected=self._on_file_detected)

            self._observer = PollingObserver(timeout=_POLLING_INTERVAL)
            self._observer.daemon = True
            self._observer.schedule(handler, folder_path, recursive=True)

            try:
                self._observer.start()
            except Exception:
                self._observer = None
                self._watch_path = None
                return False

            self._stability_thread = threading.Thread(
                target=self._stability_loop, daemon=True
            )
            self._stability_thread.start()

        return True

    def stop(self):
        """Stop monitoring."""
        with self._lock:
            self._stop_event.set()

            observer = self._observer
            self._observer = None
            self._watch_path = None

        # Stop observer outside lock to avoid deadlock with watchdog internals
        if observer:
            observer.stop()
            observer.join(timeout=3)

        # Wait for stability thread outside lock
        if self._stability_thread and self._stability_thread.is_alive():
            self._stability_thread.join(timeout=3)
        self._stability_thread = None

        with self._pending_lock:
            self._pending_files.clear()

    def cleanup(self):
        """Alias for stop(), used during application shutdown."""
        self.stop()

    def _on_file_detected(self, filepath: str):
        """Called from watchdog thread when a new audio file appears."""
        with self._pending_lock:
            if filepath in self._dispatched_files:
                return
            if filepath not in self._pending_files:
                self._pending_files[filepath] = {
                    "last_size": -1,
                    "stable_count": 0,
                    "first_seen": time.time(),
                }

    def _stability_loop(self):
        """Background loop that checks pending files for size stability."""
        while not self._stop_event.is_set():
            self._stop_event.wait(_STABILITY_CHECK_INTERVAL)
            if self._stop_event.is_set():
                break

            ready_files = []
            expired_files = []

            with self._pending_lock:
                for filepath, info in list(self._pending_files.items()):
                    if not os.path.exists(filepath):
                        expired_files.append(filepath)
                        continue

                    # Check timeout
                    if time.time() - info["first_seen"] > _STABILITY_TIMEOUT:
                        expired_files.append(filepath)
                        continue

                    try:
                        current_size = os.path.getsize(filepath)
                    except OSError:
                        expired_files.append(filepath)
                        continue

                    if current_size == info["last_size"] and current_size > 0:
                        info["stable_count"] += 1
                    else:
                        info["stable_count"] = 0
                    info["last_size"] = current_size

                    if info["stable_count"] >= _STABILITY_REQUIRED_CHECKS:
                        ready_files.append(filepath)

                # Clean up
                for fp in ready_files + expired_files:
                    self._pending_files.pop(fp, None)
                for fp in ready_files:
                    self._dispatched_files.add(fp)

            # Dispatch ready files
            if ready_files and self.on_files_ready:
                self.on_files_ready(ready_files)
