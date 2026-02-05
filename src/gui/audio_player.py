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

import librosa

from ..utils.constants import SAMPLE_RATE


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
            self._tk_root.after(0, lambda: callback(*args))

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
        """Load audio file in background thread."""
        try:
            # Check if this is still the file we want
            if filepath != self._current_filepath:
                return

            # Load with librosa (handles all formats)
            samples, sr = librosa.load(filepath, sr=self._sample_rate, mono=True)

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

        # If playing, restart stream from new position
        if self._state == PlayerState.PLAYING:
            self._stop_stream()
            self._start_stream()

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

    def _start_stream(self):
        """Start the audio output stream."""
        if self._stream is not None:
            return

        try:
            self._stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype='float32',
                callback=self._audio_callback,
                finished_callback=self._on_stream_finished,
            )
            self._stream.start()
        except Exception as e:
            print(f"Error starting audio stream: {e}")
            self._set_state(PlayerState.STOPPED)

    def _stop_stream(self):
        """Stop the audio output stream."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

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

    def _on_stream_finished(self):
        """Called when the audio stream finishes."""
        # Check if we reached the end naturally
        with self._lock:
            at_end = self._position >= self._duration_samples - self._sample_rate // 10  # ~100ms tolerance

        if at_end and self._state == PlayerState.PLAYING:
            self._stream = None
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
