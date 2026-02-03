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
    PANEL_WIDTH,
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

        self._spectrum_panel_visible = False  # Hidden by default
        self._setup_window()
        self._setup_components()
        self._setup_layout()

    def _setup_window(self):
        """Configure the main window."""
        self.root.title("AudioQual - Analizador de Calidad de Audio")
        # Start with compact size (panel hidden)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

        # Set appearance mode
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")  # More neutral, will be overridden by custom colors

        # Configure grid - fixed column sizes, no weights
        self.root.grid_columnconfigure(0, weight=1)  # Main content expands to fill
        self.root.grid_columnconfigure(1, weight=0, minsize=0)  # Panel column (hidden initially)
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
            on_toggle_panel=self._toggle_spectrum_panel,
        )

        # Create spectrogram panel (right panel)
        self.spectrogram_panel = SpectrogramPanel(self.root)

    def _setup_layout(self):
        """Set up the main layout."""
        # Main window takes full width initially (panel hidden)
        self.main_window.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        # Spectrogram panel is NOT gridded initially (hidden by default)

    def _toggle_spectrum_panel(self):
        """Toggle the spectrogram panel visibility by resizing the window."""
        if self._spectrum_panel_visible:
            # Hide panel - shrink window
            self.spectrogram_panel.grid_remove()
            self.root.grid_columnconfigure(1, minsize=0)
            self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        else:
            # Show panel - expand window
            self.spectrogram_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
            self.root.grid_columnconfigure(1, weight=0, minsize=PANEL_WIDTH)
            new_width = WINDOW_WIDTH + PANEL_WIDTH
            self.root.geometry(f"{new_width}x{WINDOW_HEIGHT}")

        self._spectrum_panel_visible = not self._spectrum_panel_visible
        self.main_window.set_panel_visible(self._spectrum_panel_visible)

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
