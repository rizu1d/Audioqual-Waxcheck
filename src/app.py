"""Main application class integrating core and GUI."""

import time
import threading
from collections import OrderedDict
from typing import Optional

import customtkinter as ctk

# Configure matplotlib ONCE at module load, before any imports that might use it
# This avoids the overhead of calling matplotlib.use('Agg') and plt.style.use() on every render
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend (thread-safe)
import matplotlib.pyplot as plt
plt.style.use('dark_background')

try:
    from tkinterdnd2 import TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from .core.analyzer import AnalysisResult, AudioAnalyzer
from .core.frequency_detector import FrequencyAnalysis
from .gui.main_window import MainWindow
from .gui.spectrogram_window import SpectrogramWindow
from .gui.audio_player import AudioPlayer
from .utils.constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    THEME_COLORS,
)

# Maximum number of spectrograms to cache in memory (LRU)
MAX_SPECTROGRAM_CACHE = 10


class AudioQualApp:
    """
    Main application class that creates and manages the application window.
    """

    def __init__(self):
        # Create root window with drag-and-drop support if available
        if HAS_DND:
            self.root = TkinterDnD.Tk()
        else:
            self.root = ctk.CTk()

        # LRU cache for frequency analysis data (filepath -> FrequencyAnalysis)
        # This keeps the last N spectrograms in memory for quick re-display
        self._spectrogram_cache: OrderedDict[str, tuple] = OrderedDict()
        # Reference to the spectrogram window (None if closed)
        self._spectrogram_window: Optional[SpectrogramWindow] = None
        # Currently selected result (for spectrogram display)
        self._selected_result: Optional[AnalysisResult] = None

        self._setup_window()
        self._setup_components()
        self._setup_layout()

    def _setup_window(self):
        """Configure the main window."""
        self.root.title("AudioQual - Analizador de Calidad de Audio")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

        # Set appearance mode
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")  # More neutral, will be overridden by custom colors

        # Configure grid - single column layout
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # === DIAGNOSTIC: Click monitor ===
        self._last_click_time = time.time()

        def _on_global_click(event):
            now = time.time()
            delta = now - self._last_click_time
            print(f"[CLICK] {now:.3f} | pos=({event.x},{event.y}) | delta={delta:.3f}s | widget={event.widget}")
            self._last_click_time = now

        self.root.bind_all("<Button-1>", _on_global_click, add="+")

        # === DIAGNOSTIC: Heartbeat monitor (detects main thread blocks) ===
        self._last_heartbeat = time.time()

        def _heartbeat():
            now = time.time()
            delta = now - self._last_heartbeat
            if delta > 0.2:  # >200ms = bloqueo
                print(f"[BLOCK] {now:.3f} | Main thread bloqueado {delta:.3f}s")
            self._last_heartbeat = now
            self.root.after(100, _heartbeat)

        _heartbeat()

    def _setup_components(self):
        """Create application components."""
        # Create analyzer
        self.analyzer = AudioAnalyzer()

        # Create audio player
        self.audio_player = AudioPlayer()
        self.audio_player.set_tk_root(self.root)

        # Create main window
        self.main_window = MainWindow(
            self.root,
            analyzer=self.analyzer,
            audio_player=self.audio_player,
            on_result_selected=self._on_result_selected,
            on_show_spectrogram=self._show_spectrogram_window,
            on_clear=self._on_clear,
        )

    def _setup_layout(self):
        """Set up the main layout."""
        self.main_window.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def _on_result_selected(self, result: Optional[AnalysisResult]):
        """Handle result selection from the table."""
        print(f"[PERF] {time.time():.3f} | {threading.current_thread().name} | _on_result_selected inicio: {result.filename if result else 'None'}")
        self._selected_result = result

        if not result:
            return

        # Check if result has frequency_analysis (fresh result)
        if result.frequency_analysis:
            # Cache the frequency analysis for later re-selection
            self._cache_spectrogram(
                result.filepath,
                result.frequency_analysis,
                result.filename,
                result.cutoff_frequency_khz,
            )

        # If spectrogram window is open, update it
        if self._spectrogram_window and self._spectrogram_window.is_open():
            print(f"[PERF] {time.time():.3f} | {threading.current_thread().name} | _update_spectrogram_window llamado")
            self._update_spectrogram_window()
        print(f"[PERF] {time.time():.3f} | {threading.current_thread().name} | _on_result_selected fin")

    def _show_spectrogram_window(self):
        """Show or update the spectrogram window."""
        if not self._selected_result:
            return

        # Get frequency analysis data
        freq_analysis, filename, cutoff_khz = self._get_analysis_data(
            self._selected_result
        )

        if not freq_analysis:
            return

        # Check if window exists and is open
        if self._spectrogram_window and self._spectrogram_window.is_open():
            # Update existing window
            self._spectrogram_window.update_spectrogram(
                freq_analysis, filename, cutoff_khz
            )
            self._spectrogram_window.focus()
        else:
            # Create new window
            self._spectrogram_window = SpectrogramWindow(
                self.root,
                freq_analysis,
                filename,
                cutoff_khz,
            )

    def _update_spectrogram_window(self):
        """Update spectrogram window with currently selected result."""
        if not self._selected_result:
            return

        freq_analysis, filename, cutoff_khz = self._get_analysis_data(
            self._selected_result
        )

        if freq_analysis and self._spectrogram_window:
            self._spectrogram_window.update_spectrogram(
                freq_analysis, filename, cutoff_khz
            )

    def _get_analysis_data(self, result: AnalysisResult):
        """Get frequency analysis data from result or cache."""
        if result.frequency_analysis:
            return (
                result.frequency_analysis,
                result.filename,
                result.cutoff_frequency_khz,
            )

        # Try cache
        cached = self._spectrogram_cache.get(result.filepath)
        if cached:
            # Move to end (most recently used)
            self._spectrogram_cache.move_to_end(result.filepath)
            return cached

        return (None, None, None)

    def _cache_spectrogram(
        self,
        filepath: str,
        analysis: FrequencyAnalysis,
        filename: str,
        cutoff_khz: float,
    ):
        """Cache spectrogram data with LRU eviction."""
        # Remove oldest if at capacity
        while len(self._spectrogram_cache) >= MAX_SPECTROGRAM_CACHE:
            self._spectrogram_cache.popitem(last=False)

        # Add/update cache entry
        self._spectrogram_cache[filepath] = (analysis, filename, cutoff_khz)

    def _on_clear(self):
        """Handle clear action - clear cache."""
        self._spectrogram_cache.clear()
        self._selected_result = None
        # Stop audio playback
        if self.audio_player:
            self.audio_player.stop()

    def _cleanup(self):
        """Clean up resources before closing."""
        if self.audio_player:
            self.audio_player.cleanup()

    def run(self):
        """Start the application main loop."""
        # Set up cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        """Handle application close."""
        self._cleanup()
        self.root.destroy()


def create_app() -> AudioQualApp:
    """Create and return a new application instance."""
    return AudioQualApp()
