"""Main application class integrating core and GUI."""

from typing import List, Optional

import customtkinter as ctk

try:
    from tkinterdnd2 import TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from .core.analyzer import AnalysisResult, AudioAnalyzer
from .gui.main_window import MainWindow
from .gui.spectrogram_panel import SpectrogramPanel
from .gui.export_dialog import ExportDialog
from .utils.constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
)


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
        ctk.set_default_color_theme("blue")

        # Configure grid
        self.root.grid_columnconfigure(0, weight=3)
        self.root.grid_columnconfigure(1, weight=2)
        self.root.grid_rowconfigure(0, weight=1)

    def _setup_components(self):
        """Create application components."""
        # Create analyzer
        self.analyzer = AudioAnalyzer()

        # Create main window (left panel)
        self.main_window = MainWindow(
            self.root,
            analyzer=self.analyzer,
            on_result_selected=self._on_result_selected,
            on_export_requested=self._on_export_requested,
        )

        # Create spectrogram panel (right panel)
        self.spectrogram_panel = SpectrogramPanel(self.root)

    def _setup_layout(self):
        """Set up the main layout."""
        self.main_window.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        self.spectrogram_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)

    def _on_result_selected(self, result: Optional[AnalysisResult]):
        """Handle result selection from the table."""
        if result and result.frequency_analysis:
            self.spectrogram_panel.show_spectrogram(
                result.frequency_analysis,
                result.filename,
                result.cutoff_frequency_khz,
            )
        else:
            self.spectrogram_panel.clear()

    def _on_export_requested(self, results: List[AnalysisResult]):
        """Handle export request."""
        dialog = ExportDialog(self.root, results)
        dialog.grab_set()

    def run(self):
        """Start the application main loop."""
        self.root.mainloop()


def create_app() -> AudioQualApp:
    """Create and return a new application instance."""
    return AudioQualApp()
