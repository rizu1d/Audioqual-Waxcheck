"""Main application class integrating core and GUI."""

from typing import Optional

import customtkinter as ctk

try:
    from tkinterdnd2 import TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from .core.analyzer import AnalysisResult, AudioAnalyzer
from .gui.main_window import MainWindow
from .gui.spectrogram_panel import SpectrogramPanel
from .utils.constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    PANEL_WIDTH,
    MIN_MAIN_WIDTH,
    MIN_SPECTRUM_WIDTH,
    DIVIDER_WIDTH,
    THEME_COLORS,
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
        self._current_panel_width = PANEL_WIDTH  # Track current panel width for resizing
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

        # Configure grid - 3 columns: main | divider | panel
        self.root.grid_columnconfigure(0, weight=1)  # Main content expands to fill
        self.root.grid_columnconfigure(1, weight=0, minsize=0)  # Divider column (hidden initially)
        self.root.grid_columnconfigure(2, weight=0, minsize=0)  # Panel column (hidden initially)
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
            on_toggle_panel=self._toggle_spectrum_panel,
        )

        # Create spectrogram panel (right panel)
        self.spectrogram_panel = SpectrogramPanel(self.root)

        # Create draggable divider
        self.divider = ctk.CTkFrame(
            self.root,
            width=DIVIDER_WIDTH,
            fg_color=THEME_COLORS["bg_frame"],
            corner_radius=0,
        )
        self._setup_divider_events()

    def _setup_divider_events(self):
        """Configure mouse events for the draggable divider."""
        self._drag_start_x = None
        self._drag_start_panel_width = None
        self._drag_update_scheduled = False  # Throttle flag
        self._pending_spectrum_width = None  # Pending width to apply

        # Cursor change on hover
        self.divider.bind("<Enter>", lambda e: self.divider.configure(cursor="sb_h_double_arrow"))
        self.divider.bind("<Leave>", lambda e: self.divider.configure(cursor=""))

        # Drag events
        self.divider.bind("<Button-1>", self._on_divider_press)
        self.divider.bind("<B1-Motion>", self._on_divider_drag)
        self.divider.bind("<ButtonRelease-1>", self._on_divider_release)

    def _on_divider_press(self, event):
        """Start divider drag."""
        self._drag_start_x = event.x_root
        self._drag_start_panel_width = self._current_panel_width
        # Pause spectrogram resize handling during drag
        self.spectrogram_panel.pause_resize()

    def _on_divider_drag(self, event):
        """Handle divider dragging - redistribute space between panels."""
        if self._drag_start_x is None:
            return

        # Calcular delta (positivo = arrastrar derecha, negativo = arrastrar izquierda)
        delta = event.x_root - self._drag_start_x

        # Calcular nuevo ancho del panel de espectros
        # Arrastrar derecha (delta positivo) = espectros se reducen
        # Arrastrar izquierda (delta negativo) = espectros crecen
        new_spectrum_width = self._drag_start_panel_width - delta

        # Calcular ancho disponible para el panel principal
        # Tamaño fijo de ventana expandida (padding: 10 izq + 10 der = 20)
        total_content_width = WINDOW_WIDTH + PANEL_WIDTH
        new_main_width = total_content_width - new_spectrum_width

        # Aplicar límites mínimos para ambos paneles
        if new_spectrum_width < MIN_SPECTRUM_WIDTH:
            new_spectrum_width = MIN_SPECTRUM_WIDTH
        if new_main_width < MIN_MAIN_WIDTH:
            new_spectrum_width = total_content_width - MIN_MAIN_WIDTH

        # Guardar valor pendiente
        self._pending_spectrum_width = new_spectrum_width

        # Throttle: solo programar actualización si no hay una pendiente
        if not self._drag_update_scheduled:
            self._drag_update_scheduled = True
            self.root.after(30, self._apply_drag_update)  # 30ms ≈ 33fps

    def _apply_drag_update(self):
        """Apply pending drag update (throttled)."""
        self._drag_update_scheduled = False

        if self._pending_spectrum_width is None:
            return

        # Aplicar el cambio de tamaño
        self._current_panel_width = self._pending_spectrum_width
        self.root.grid_columnconfigure(2, minsize=self._pending_spectrum_width)

    def _on_divider_release(self, event):
        """End divider drag."""
        # Aplicar cualquier actualización pendiente inmediatamente
        if self._pending_spectrum_width is not None:
            self._current_panel_width = self._pending_spectrum_width
            self.root.grid_columnconfigure(2, minsize=self._pending_spectrum_width)

        # Limpiar estado
        self._drag_start_x = None
        self._drag_start_panel_width = None
        self._pending_spectrum_width = None
        self._drag_update_scheduled = False

        # Resume spectrogram resize handling and trigger re-render
        self.spectrogram_panel.resume_resize()

    def _setup_layout(self):
        """Set up the main layout."""
        # Main window takes full width initially (panel hidden)
        self.main_window.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        # Divider and spectrogram panel are NOT gridded initially (hidden by default)

    def _toggle_spectrum_panel(self):
        """Toggle the spectrogram panel visibility."""
        if self._spectrum_panel_visible:
            # Hide panel and divider - shrink window
            self.divider.grid_remove()
            self.spectrogram_panel.grid_remove()
            self.root.grid_columnconfigure(1, minsize=0)
            self.root.grid_columnconfigure(2, minsize=0)
            self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        else:
            # Show divider and panel - expand window to fixed size
            self.divider.grid(row=0, column=1, sticky="ns", pady=10)
            self.spectrogram_panel.grid(row=0, column=2, sticky="nsew", padx=(0, 10), pady=10)
            self._current_panel_width = PANEL_WIDTH  # Reset a tamaño default
            self.root.grid_columnconfigure(1, minsize=DIVIDER_WIDTH)
            self.root.grid_columnconfigure(2, minsize=PANEL_WIDTH)
            expanded_width = WINDOW_WIDTH + DIVIDER_WIDTH + PANEL_WIDTH
            self.root.geometry(f"{expanded_width}x{WINDOW_HEIGHT}")

        self._spectrum_panel_visible = not self._spectrum_panel_visible
        self.main_window.set_panel_visible(self._spectrum_panel_visible)

    def _on_result_selected(self, result: Optional[AnalysisResult]):
        """Handle result selection from the table."""
        if result and result.frequency_analysis:
            # Auto-abrir panel si está cerrado
            if not self._spectrum_panel_visible:
                self._toggle_spectrum_panel()

            self.spectrogram_panel.show_spectrogram(
                result.frequency_analysis,
                result.filename,
                result.cutoff_frequency_khz,
            )
        else:
            self.spectrogram_panel.clear()

    def run(self):
        """Start the application main loop."""
        self.root.mainloop()


def create_app() -> AudioQualApp:
    """Create and return a new application instance."""
    return AudioQualApp()
