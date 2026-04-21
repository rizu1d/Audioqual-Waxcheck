"""Audio file loading and metadata extraction."""

import struct
from dataclasses import dataclass
from math import gcd
from pathlib import Path
from typing import Optional, Tuple

import librosa
import numpy as np
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3, HeaderNotFoundError
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

# Valid MPEG audio version/layer combinations for sync word validation
_MPEG_SYNC_MASK = 0xFFE00000  # 11 sync bits


def _validate_mp3_file(filepath: str) -> None:
    """Pre-validate MP3 file to avoid C-level crashes (SIGBUS) in libmpg123.

    Checks:
    1. Mutagen can parse the MP3 headers (catches HeaderNotFoundError)
    2. File has valid MPEG sync words (not just null bytes)

    Raises:
        ValueError: If the file is corrupted or invalid.
    """
    # Check 1: mutagen strict parse
    try:
        mp3 = MP3(filepath)
        if mp3.info.length <= 0:
            raise ValueError(f"Archivo MP3 corrupto: duración inválida")
    except HeaderNotFoundError:
        raise ValueError(f"Archivo MP3 corrupto: no se encontró header MPEG válido")
    except Exception as e:
        raise ValueError(f"Archivo MP3 corrupto: {e}")

    # Check 2: scan for null-header pattern that causes SIGBUS
    # Read chunks and look for large runs of null bytes in audio data
    try:
        file_size = Path(filepath).stat().st_size
        # Sample 3 positions: start (after ID3), middle, near end
        with open(filepath, 'rb') as f:
            # Skip ID3v2 tag if present
            header = f.read(10)
            offset = 0
            if header[:3] == b'ID3':
                tag_size = (header[6] << 21 | header[7] << 14 |
                            header[8] << 7 | header[9])
                offset = tag_size + 10

            # Check a few positions for null-filled regions
            check_size = 4096
            positions = [offset, file_size // 2, max(0, file_size - check_size)]
            for pos in positions:
                f.seek(pos)
                chunk = f.read(check_size)
                if len(chunk) >= 2048 and chunk.count(b'\x00') > len(chunk) * 0.95:
                    raise ValueError(
                        f"Archivo MP3 corrupto: región de bytes nulos detectada"
                    )
    except ValueError:
        raise
    except Exception:
        pass  # File read issues will be caught by librosa anyway


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

    # Pre-validate MP3 files to prevent C-level crashes (SIGBUS)
    if ext == 'mp3':
        _validate_mp3_file(filepath)

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
