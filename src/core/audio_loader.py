"""Audio file loading and metadata extraction."""

from dataclasses import dataclass
from math import gcd
from pathlib import Path
from typing import Optional, Tuple

import librosa
import numpy as np
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.wave import WAVE
from mutagen.aiff import AIFF

from ..utils.constants import SAMPLE_RATE
from ..utils.file_utils import get_file_extension, get_file_size_mb

# Try importing soundfile for fast loading of lossless formats
try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False

# Formats that soundfile (libsndfile) can read natively
_SOUNDFILE_FORMATS = {'wav', 'flac', 'ogg', 'aiff', 'aif'}


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
            elif ext in ('aiff', 'aif') and isinstance(audio_file, AIFF):
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


def _load_with_soundfile(filepath: str, target_sr: int) -> Tuple[np.ndarray, int]:
    """Load audio using soundfile (libsndfile). Fast, releases GIL during I/O."""
    samples, file_sr = sf.read(filepath, dtype='float32', always_2d=True)

    # Convert to mono if multichannel
    if samples.shape[1] > 1:
        samples = np.mean(samples, axis=1)
    else:
        samples = samples[:, 0]

    # Resample only if needed (most files are already 44100Hz)
    if file_sr != target_sr:
        from scipy.signal import resample_poly
        g = gcd(target_sr, file_sr)
        up = target_sr // g
        down = file_sr // g
        samples = resample_poly(samples, up, down).astype(np.float32)

    return samples, target_sr


def load_audio(filepath: str, target_sr: int = SAMPLE_RATE) -> AudioData:
    """
    Load an audio file and return audio data with metadata.

    Uses soundfile (libsndfile) for WAV/FLAC/OGG/AIFF (3-5x faster),
    falls back to librosa for MP3/M4A/AAC/WMA.

    Args:
        filepath: Path to the audio file
        target_sr: Target sample rate for resampling

    Returns:
        AudioData object containing samples and metadata
    """
    # Get metadata first
    metadata = get_audio_metadata(filepath)

    ext = get_file_extension(filepath)

    # Fast path: soundfile for lossless/native formats
    if HAS_SOUNDFILE and ext in _SOUNDFILE_FORMATS:
        try:
            samples, sr = _load_with_soundfile(filepath, target_sr)
        except Exception:
            samples, sr = librosa.load(filepath, sr=target_sr, mono=True)
    else:
        # Slow path: librosa for MP3, M4A, AAC, WMA
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
