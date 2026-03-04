"""Disk cache for downsampled spectrogram data.

Saves lightweight versions of spectrogram data to ~/.audioqual/cache/
so spectrograms can be displayed without re-analyzing audio files.
"""

import hashlib
import os
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from ..core.frequency_detector import FrequencyAnalysis

_CACHE_DIR = os.path.join(Path.home(), ".audioqual", "cache")

# Downsample target: 1024 freq bins × 4096 time frames
# Stored as uint8 (1 byte) instead of float32 (4 bytes) = ~4MB per file
_TARGET_FREQ_BINS = 1024
_TARGET_TIME_FRAMES = 4096

# dB range matching spectrogram_window.py display normalization
_DB_MIN = -80.0
_DB_MAX = 0.0


def _cache_path(filepath: str) -> str:
    """Get cache file path for an audio file."""
    h = hashlib.sha256(filepath.encode()).hexdigest()[:16]
    return os.path.join(_CACHE_DIR, f"{h}.npz")


def save_to_cache(filepath: str, analysis: FrequencyAnalysis, cutoff_khz: float) -> None:
    """Downsample spectrogram, quantize to uint8, and save to disk cache."""
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)

        spec = analysis.spectrogram_db
        n_freq, n_time = spec.shape

        # Downsample by slicing (fast, no interpolation needed for display)
        freq_step = max(1, n_freq // _TARGET_FREQ_BINS)
        time_step = max(1, n_time // _TARGET_TIME_FRAMES)
        downsampled = spec[::freq_step, ::time_step]

        # Quantize float32 dB → uint8 (same normalization as spectrogram_window.py)
        quantized = np.clip(downsampled, _DB_MIN, _DB_MAX)
        quantized = ((quantized - _DB_MIN) * (255.0 / (_DB_MAX - _DB_MIN))).astype(np.uint8)

        np.savez(
            _cache_path(filepath),
            spec_uint8=quantized,
            max_freq_hz=np.float64(analysis.frequencies[-1]),
            confidence=np.float64(analysis.confidence),
            cutoff_khz=np.float64(cutoff_khz),
        )
    except Exception:
        pass


def load_from_cache(filepath: str) -> Optional[Tuple[FrequencyAnalysis, float]]:
    """Load cached spectrogram from disk. Returns (FrequencyAnalysis, cutoff_khz) or None."""
    cache_file = _cache_path(filepath)
    if not os.path.exists(cache_file):
        return None

    try:
        data = np.load(cache_file)
        max_freq_hz = float(data["max_freq_hz"])
        confidence = float(data["confidence"])
        cutoff_khz = float(data["cutoff_khz"])

        # Dequantize uint8 → float32 dB
        spec_uint8 = data["spec_uint8"]
        spec_db = spec_uint8.astype(np.float32) * ((_DB_MAX - _DB_MIN) / 255.0) + _DB_MIN

        # Reconstruct minimal FrequencyAnalysis for spectrogram display
        n_freq = spec_db.shape[0]
        frequencies = np.linspace(0, max_freq_hz, n_freq)

        analysis = FrequencyAnalysis(
            cutoff_frequency_hz=cutoff_khz * 1000,
            cutoff_frequency_khz=cutoff_khz,
            max_frequency_hz=max_freq_hz,
            energy_spectrum=np.array([]),  # Not needed for display
            frequencies=frequencies,
            spectrogram_db=spec_db,
            confidence=confidence,
        )
        return (analysis, cutoff_khz)
    except Exception:
        # Corrupted cache file — remove it
        try:
            os.remove(cache_file)
        except OSError:
            pass
        return None


def clear_cache() -> None:
    """Remove all cache files."""
    if not os.path.isdir(_CACHE_DIR):
        return
    try:
        for entry in os.scandir(_CACHE_DIR):
            if entry.name.endswith(".npz"):
                os.remove(entry.path)
    except Exception:
        pass
