"""Audio file loading and metadata extraction."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import librosa
import numpy as np
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.wave import WAVE

from ..utils.constants import SAMPLE_RATE
from ..utils.file_utils import get_file_extension, get_file_size_mb


@dataclass
class AudioMetadata:
    """Audio file metadata."""
    filepath: str
    filename: str
    format: str
    duration: float
    sample_rate: int
    channels: int
    bitrate: Optional[int]  # in kbps
    file_size_mb: float
    bit_depth: Optional[int]


@dataclass
class AudioData:
    """Loaded audio data with metadata."""
    metadata: AudioMetadata
    samples: np.ndarray
    sample_rate: int


def get_audio_metadata(filepath: str) -> AudioMetadata:
    """Extract metadata from an audio file using mutagen."""
    path = Path(filepath)
    ext = get_file_extension(filepath)
    file_size = get_file_size_mb(filepath)

    # Default values
    duration = 0.0
    sample_rate = 0
    channels = 0
    bitrate = None
    bit_depth = None

    try:
        audio_file = MutagenFile(filepath)

        if audio_file is not None:
            # Get duration
            if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'length'):
                duration = audio_file.info.length

            # Get sample rate
            if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'sample_rate'):
                sample_rate = audio_file.info.sample_rate

            # Get channels
            if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'channels'):
                channels = audio_file.info.channels

            # Get bitrate (for compressed formats)
            if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'bitrate'):
                bitrate = int(audio_file.info.bitrate / 1000) if audio_file.info.bitrate else None

            # Get bit depth (for lossless formats)
            if ext == 'flac' and isinstance(audio_file, FLAC):
                if hasattr(audio_file.info, 'bits_per_sample'):
                    bit_depth = audio_file.info.bits_per_sample
            elif ext == 'wav' and isinstance(audio_file, WAVE):
                if hasattr(audio_file.info, 'bits_per_sample'):
                    bit_depth = audio_file.info.bits_per_sample

    except Exception:
        pass

    return AudioMetadata(
        filepath=filepath,
        filename=path.name,
        format=ext.upper(),
        duration=duration,
        sample_rate=sample_rate,
        channels=channels,
        bitrate=bitrate,
        file_size_mb=file_size,
        bit_depth=bit_depth,
    )


def load_audio(filepath: str, target_sr: int = SAMPLE_RATE) -> AudioData:
    """
    Load an audio file and return audio data with metadata.

    Args:
        filepath: Path to the audio file
        target_sr: Target sample rate for resampling

    Returns:
        AudioData object containing samples and metadata
    """
    # Get metadata first
    metadata = get_audio_metadata(filepath)

    # Load audio with librosa
    samples, sr = librosa.load(filepath, sr=target_sr, mono=True)

    # Update metadata with actual loaded values if they were missing
    if metadata.duration == 0:
        metadata.duration = len(samples) / sr
    if metadata.sample_rate == 0:
        metadata.sample_rate = sr

    return AudioData(
        metadata=metadata,
        samples=samples,
        sample_rate=sr,
    )


def load_audio_segment(
    filepath: str,
    start_time: float = 0,
    duration: Optional[float] = None,
    target_sr: int = SAMPLE_RATE,
) -> Tuple[np.ndarray, int]:
    """
    Load a segment of an audio file.

    Args:
        filepath: Path to the audio file
        start_time: Start time in seconds
        duration: Duration in seconds (None for entire file from start)
        target_sr: Target sample rate

    Returns:
        Tuple of (samples, sample_rate)
    """
    samples, sr = librosa.load(
        filepath,
        sr=target_sr,
        mono=True,
        offset=start_time,
        duration=duration,
    )
    return samples, sr
