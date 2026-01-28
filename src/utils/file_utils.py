"""File handling utilities."""

import os
from pathlib import Path
from typing import List

from .constants import SUPPORTED_FORMATS


def is_supported_audio_file(filepath: str) -> bool:
    """Check if a file has a supported audio format."""
    ext = Path(filepath).suffix.lower()
    return ext in SUPPORTED_FORMATS


def get_audio_files_from_path(path: str) -> List[str]:
    """Get all supported audio files from a path (file or directory)."""
    path = Path(path)
    files = []

    if path.is_file():
        if is_supported_audio_file(str(path)):
            files.append(str(path))
    elif path.is_dir():
        for root, _, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                if is_supported_audio_file(filepath):
                    files.append(filepath)

    return sorted(files)


def get_file_size_mb(filepath: str) -> float:
    """Get file size in megabytes."""
    try:
        size_bytes = os.path.getsize(filepath)
        return size_bytes / (1024 * 1024)
    except OSError:
        return 0.0


def get_filename(filepath: str) -> str:
    """Get filename without path."""
    return Path(filepath).name


def get_file_extension(filepath: str) -> str:
    """Get file extension in lowercase without dot."""
    return Path(filepath).suffix.lower().lstrip(".")


def format_duration(seconds: float) -> str:
    """Format duration in seconds to MM:SS or HH:MM:SS."""
    if seconds < 0:
        return "00:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
