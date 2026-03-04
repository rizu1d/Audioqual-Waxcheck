"""Audio playback engine with threading pattern for responsive UI."""

import threading
from enum import Enum
from typing import Callable, Optional

import numpy as np

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False

from scipy import signal

from ..utils.constants import SAMPLE_RATE
from ..utils.settings import AppSettings


class PlayerState(Enum):
    """Audio player state."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    LOADING = "loading"


class AudioPlayer:
    """
    Audio playback engine using sounddevice + librosa.

    Uses a callback-based streaming approach for precise position tracking
    and non-blocking playback.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self._sample_rate = sample_rate
        self._samples: Optional[np.ndarray] = None
        self._position = 0  # Current position in samples
        self._volume = 1.0
        self._state = PlayerState.STOPPED
        self._current_filepath: Optional[str] = None
        self._duration_samples = 0

        # Threading
        self._lock = threading.Lock()
        self._load_thread: Optional[threading.Thread] = None
        self._stream: Optional[sd.OutputStream] = None
        self._stream_generation = 0  # Incremented on each stream create/destroy

        # Callbacks for UI updates (called from main thread via after())
        self._on_position_changed: Optional[Callable[[float], None]] = None
        self._on_state_changed: Optional[Callable[[PlayerState], None]] = None
        self._on_track_ended: Optional[Callable[[], None]] = None
        self._on_track_loaded: Optional[Callable[[float], None]] = None  # duration in seconds
        self._on_load_error: Optional[Callable[[str], None]] = None

        # Reference to tk root for after() scheduling
        self._tk_root = None

    def set_tk_root(self, root):
        """Set the Tk root for scheduling callbacks on the main thread."""
        self._tk_root = root

    def set_callbacks(
        self,
        on_position_changed: Optional[Callable[[float], None]] = None,
        on_state_changed: Optional[Callable[[PlayerState], None]] = None,
        on_track_ended: Optional[Callable[[], None]] = None,
        on_track_loaded: Optional[Callable[[float], None]] = None,
        on_load_error: Optional[Callable[[str], None]] = None,
    ):
        """Set UI callbacks."""
        self._on_position_changed = on_position_changed
        self._on_state_changed = on_state_changed
        self._on_track_ended = on_track_ended
        self._on_track_loaded = on_track_loaded
        self._on_load_error = on_load_error

    def _schedule_callback(self, callback: Callable, *args):
        """Schedule a callback to run on the main thread."""
        if callback and self._tk_root:
            from ..utils.tk_utils import schedule_callback_from_thread
            schedule_callback_from_thread(self._tk_root, callback, *args)

    def _set_state(self, state: PlayerState):
        """Update state and notify callback."""
        self._state = state
        self._schedule_callback(self._on_state_changed, state)

    def load(self, filepath: str):
        """
        Load an audio file asynchronously.

        Args:
            filepath: Path to the audio file
        """
        if not HAS_SOUNDDEVICE:
            self._schedule_callback(self._on_load_error, "sounddevice no instalado")
            return

        # Stop any current playback
        self.stop()

        # Cancel any in-progress load
        if self._load_thread and self._load_thread.is_alive():
            # We can't really cancel librosa.load, but we can ignore its result
            pass

        self._current_filepath = filepath
        self._set_state(PlayerState.LOADING)

        # Load in background thread
        self._load_thread = threading.Thread(
            target=self._load_in_background,
            args=(filepath,),
            daemon=True,
        )
        self._load_thread.start()

    def _load_in_background(self, filepath: str):
        """Load audio file in background thread using soundfile (low GIL contention)."""
        try:
            # Check if this is still the file we want
            if filepath != self._current_filepath:
                return

            # Determine file extension for format-specific handling
            ext = filepath.lower().rsplit('.', 1)[-1] if '.' in filepath else ''

            # Formats supported by soundfile (libsndfile)
            soundfile_formats = {'wav', 'flac', 'ogg', 'aiff', 'aif'}

            if HAS_SOUNDFILE and ext in soundfile_formats:
                # Use soundfile - releases GIL during I/O, much faster
                samples, file_sr = sf.read(filepath, dtype='float32', always_2d=True)

                # Convert to mono if stereo (average channels)
                if samples.shape[1] > 1:
                    samples = np.mean(samples, axis=1)
                else:
                    samples = samples[:, 0]

                # Resample if needed
                if file_sr != self._sample_rate:
                    # Use scipy's resample_poly for efficient resampling
                    from math import gcd
                    g = gcd(self._sample_rate, file_sr)
                    up = self._sample_rate // g
                    down = file_sr // g
                    samples = signal.resample_poly(samples, up, down).astype(np.float32)
            else:
                # Fallback to librosa for MP3, M4A, AAC, WMA and other formats
                import librosa
                samples, _ = librosa.load(filepath, sr=self._sample_rate, mono=True)

            # Check again if this is still the file we want
            if filepath != self._current_filepath:
                return

            with self._lock:
                self._samples = samples.astype(np.float32)
                self._duration_samples = len(samples)
                self._position = 0

            duration_seconds = len(samples) / self._sample_rate
            self._set_state(PlayerState.STOPPED)
            self._schedule_callback(self._on_track_loaded, duration_seconds)

        except Exception as e:
            self._set_state(PlayerState.STOPPED)
            self._schedule_callback(self._on_load_error, str(e))

    def play(self):
        """Start or resume playback."""
        if not HAS_SOUNDDEVICE:
            return

        if self._samples is None:
            return

        if self._state == PlayerState.PLAYING:
            return

        self._set_state(PlayerState.PLAYING)
        self._start_stream()

    def pause(self):
        """Pause playback."""
        if self._state != PlayerState.PLAYING:
            return

        self._stop_stream()
        self._set_state(PlayerState.PAUSED)

    def stop(self):
        """Stop playback and reset position."""
        self._stop_stream()
        with self._lock:
            self._position = 0
        self._set_state(PlayerState.STOPPED)
        self._schedule_callback(self._on_position_changed, 0.0)

    def toggle_play_pause(self):
        """Toggle between play and pause."""
        if self._state == PlayerState.PLAYING:
            self.pause()
        elif self._samples is not None:
            self.play()

    def seek(self, position_seconds: float):
        """
        Seek to a position in the track.

        Args:
            position_seconds: Position in seconds
        """
        if self._samples is None:
            return

        new_position = int(position_seconds * self._sample_rate)
        new_position = max(0, min(new_position, self._duration_samples - 1))

        with self._lock:
            self._position = new_position

        self._schedule_callback(self._on_position_changed, position_seconds)

        # No stream restart needed: the audio callback reads self._position
        # under lock on each invocation and picks up the new position seamlessly.
        # Restarting caused ~10ms blocking per seek (system audio API calls),
        # which made drag-seeking stutter at 60+ events/sec.

    def set_volume(self, volume: float):
        """
        Set playback volume.

        Args:
            volume: Volume level (0.0 to 1.0)
        """
        self._volume = max(0.0, min(1.0, volume))

    def get_volume(self) -> float:
        """Get current volume level."""
        return self._volume

    def get_position(self) -> float:
        """Get current position in seconds."""
        with self._lock:
            return self._position / self._sample_rate if self._sample_rate > 0 else 0.0

    def get_duration(self) -> float:
        """Get track duration in seconds."""
        return self._duration_samples / self._sample_rate if self._sample_rate > 0 else 0.0

    def get_state(self) -> PlayerState:
        """Get current player state."""
        return self._state

    def is_loaded(self) -> bool:
        """Check if a track is loaded."""
        return self._samples is not None

    def get_samples(self) -> Optional[np.ndarray]:
        """Get loaded audio samples for visualization."""
        return self._samples

    def _get_output_device(self):
        """Resolve the configured output device name to a sounddevice index.

        Returns None (system default) if the setting is empty or the device
        is no longer connected.
        """
        name = AppSettings().output_device
        if not name:
            return None
        try:
            for dev in sd.query_devices():
                if dev["name"] == name and dev["max_output_channels"] > 0:
                    return dev["index"]
        except Exception:
            pass
        # Device not found — reset setting and fall back to system default
        AppSettings().output_device = ""
        return None

    def _start_stream(self):
        """Start the audio output stream."""
        with self._lock:
            if self._stream is not None:
                return
            self._stream_generation += 1
            gen = self._stream_generation

        device = self._get_output_device()

        try:
            stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype='float32',
                callback=self._audio_callback,
                finished_callback=lambda: self._on_stream_finished(gen),
                device=device,
            )
            stream.start()
            with self._lock:
                self._stream = stream
        except Exception as e:
            # If a custom device failed, retry with system default
            if device is not None:
                print(f"Error opening device {device}, falling back to default: {e}")
                AppSettings().output_device = ""
                try:
                    stream = sd.OutputStream(
                        samplerate=self._sample_rate,
                        channels=1,
                        dtype='float32',
                        callback=self._audio_callback,
                        finished_callback=lambda: self._on_stream_finished(gen),
                    )
                    stream.start()
                    with self._lock:
                        self._stream = stream
                    return
                except Exception:
                    pass
            print(f"Error starting audio stream: {e}")
            self._set_state(PlayerState.STOPPED)

    def _stop_stream(self):
        """Stop the audio output stream."""
        with self._lock:
            stream = self._stream
            self._stream = None
            self._stream_generation += 1  # Invalidate pending finished_callbacks
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    def _audio_callback(self, outdata: np.ndarray, frames: int, time_info, status):
        """
        Audio callback called by sounddevice to fill the output buffer.

        This runs in a separate audio thread - must be fast and non-blocking.
        """
        if self._samples is None or self._state != PlayerState.PLAYING:
            outdata.fill(0)
            return

        with self._lock:
            start = self._position
            end = min(start + frames, self._duration_samples)
            actual_frames = end - start

            if actual_frames <= 0:
                # End of track
                outdata.fill(0)
                self._position = self._duration_samples
                return

            # Copy samples with volume
            outdata[:actual_frames, 0] = self._samples[start:end] * self._volume

            # Zero-pad if needed (shouldn't happen in normal playback)
            if actual_frames < frames:
                outdata[actual_frames:, 0] = 0

            self._position = end

        # Check if we've reached the end
        if end >= self._duration_samples:
            # Signal end of track (will be handled in finished_callback)
            pass

    def _on_stream_finished(self, generation: int):
        """Called when the audio stream finishes."""
        with self._lock:
            # Ignore callback from a replaced/stopped stream
            if generation != self._stream_generation:
                return
            at_end = self._position >= self._duration_samples - self._sample_rate // 10  # ~100ms tolerance
            self._stream = None

        if at_end and self._state == PlayerState.PLAYING:
            self._set_state(PlayerState.STOPPED)
            with self._lock:
                self._position = 0
            self._schedule_callback(self._on_track_ended)
            self._schedule_callback(self._on_position_changed, 0.0)

    def cleanup(self):
        """Clean up resources. Call before closing the application."""
        self.stop()
        self._samples = None
        self._current_filepath = None
