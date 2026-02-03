"""Spectrogram visualization panel with background threading."""

import io
import os
import threading
from typing import Optional

import customtkinter as ctk
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np
from PIL import Image

from ..core.frequency_detector import FrequencyAnalysis
from ..utils.constants import THEME_COLORS, FONT_FAMILY, FONT_SIZES


class SpectrogramPanel(ctk.CTkFrame):
    """
    Panel for displaying audio spectrograms with frequency cutoff visualization.
    Uses background threading for responsive UI during rendering.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self._current_analysis: Optional[FrequencyAnalysis] = None
        self._current_filename: Optional[str] = None
        self._current_cutoff_khz: Optional[float] = None
        self._render_thread: Optional[threading.Thread] = None
        self._render_cancelled = threading.Event()
        self._render_id = 0  # Incremental ID for tracking renders
        self._photo_image = None  # Keep reference to prevent garbage collection
        self._resize_timer = None  # For debounced resize handling
        self._last_render_size = (0, 0)  # Track last render dimensions
        self._resize_paused = False  # Pause resize handling during drag operations

        self._setup_ui()

    def _setup_ui(self):
        """Set up the panel UI."""
        self.configure(fg_color=THEME_COLORS["bg_primary"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Title bar
        self.title_frame = ctk.CTkFrame(self, height=48, fg_color=THEME_COLORS["bg_frame"], corner_radius=8)
        self.title_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        self.title_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.title_frame,
            text="Espectrograma",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["heading"], weight="bold"),
            text_color=THEME_COLORS["text_primary"],
        )
        self.title_label.grid(row=0, column=0, padx=16, pady=10, sticky="w")

        self.file_label = ctk.CTkLabel(
            self.title_frame,
            text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_secondary"],
        )
        self.file_label.grid(row=0, column=1, padx=16, pady=10, sticky="e")

        # Figure container frame
        self.figure_frame = ctk.CTkFrame(self, fg_color=THEME_COLORS["bg_frame"], corner_radius=8)
        self.figure_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)
        self.figure_frame.grid_columnconfigure(0, weight=1)
        self.figure_frame.grid_rowconfigure(0, weight=1)

        # Image label for displaying rendered spectrogram
        self._image_label = ctk.CTkLabel(
            self.figure_frame,
            text="",
            image=None,
        )
        self._image_label.grid(row=0, column=0, sticky="nsew")
        self._image_label.grid_remove()  # Initially hidden

        # Info panel with elevated background
        self.info_frame = ctk.CTkFrame(
            self,
            height=60,
            fg_color=THEME_COLORS["bg_elevated"],
            corner_radius=8,
        )
        self.info_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 12))
        self.info_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Cutoff frequency info
        self.cutoff_label = ctk.CTkLabel(
            self.info_frame,
            text="Frec. de corte: -",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=THEME_COLORS["text_primary"],
        )
        self.cutoff_label.grid(row=0, column=0, padx=16, pady=14)

        # Max frequency info
        self.max_freq_label = ctk.CTkLabel(
            self.info_frame,
            text="Frec. max: -",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=THEME_COLORS["text_primary"],
        )
        self.max_freq_label.grid(row=0, column=1, padx=16, pady=14)

        # Confidence info
        self.confidence_label = ctk.CTkLabel(
            self.info_frame,
            text="Confianza: -",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=THEME_COLORS["text_primary"],
        )
        self.confidence_label.grid(row=0, column=2, padx=16, pady=14)

        # Empty state container (centered in figure_frame)
        self.empty_container = ctk.CTkFrame(
            self.figure_frame,
            fg_color="transparent",
        )
        self.empty_container.place(relx=0.5, rely=0.5, anchor="center")

        # Load wave icon
        self._wave_icon = None
        wave_icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "wave-icon.png")
        if os.path.exists(wave_icon_path):
            wave_icon_image = Image.open(wave_icon_path)
            self._wave_icon = ctk.CTkImage(
                light_image=wave_icon_image,
                dark_image=wave_icon_image,
                size=(80, 80)
            )

        # Empty state icon (wave icon or fallback emoji)
        self.empty_icon = ctk.CTkLabel(
            self.empty_container,
            text="" if self._wave_icon else "〰️",
            image=self._wave_icon,
            font=ctk.CTkFont(size=64),
            text_color=THEME_COLORS["text_muted"],
        )
        self.empty_icon.grid(row=0, column=0, pady=(0, 12))

        # Empty state message
        self.empty_label = ctk.CTkLabel(
            self.empty_container,
            text="Selecciona un archivo\npara ver el espectrograma",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=THEME_COLORS["text_muted"],
            justify="center",
        )
        self.empty_label.grid(row=1, column=0)

        # Loading indicator
        self._loading_label = ctk.CTkLabel(
            self.figure_frame,
            text="Cargando espectrograma...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=THEME_COLORS["text_secondary"],
        )

        # Bind resize event for responsive spectrogram
        self.figure_frame.bind("<Configure>", self._on_resize)

    def show_spectrogram(
        self,
        analysis: FrequencyAnalysis,
        filename: str,
        cutoff_khz: float,
    ):
        """
        Display the spectrogram and energy spectrum for an analysis.
        Uses background threading for responsive UI.

        Args:
            analysis: FrequencyAnalysis object with spectral data
            filename: Name of the file being displayed
            cutoff_khz: Detected cutoff frequency in kHz
        """
        # Store current analysis data for re-renders on resize
        self._current_analysis = analysis
        self._current_filename = filename
        self._current_cutoff_khz = cutoff_khz

        # 1. Cancel any in-progress render
        self._render_cancelled.set()
        self._render_id += 1
        current_render_id = self._render_id

        # 2. Show loading state immediately
        self._show_loading(filename)

        # 3. Get dimensions for rendering
        self.update_idletasks()
        width = max(self.figure_frame.winfo_width(), 300)
        height = max(self.figure_frame.winfo_height(), 200)
        self._last_render_size = (width, height)

        # 4. Reset cancellation flag for new render
        self._render_cancelled.clear()

        # 5. Start background render thread
        self._render_thread = threading.Thread(
            target=self._render_in_background,
            args=(current_render_id, analysis, filename, cutoff_khz, width, height),
            daemon=True,
        )
        self._render_thread.start()

    def _show_loading(self, filename: str):
        """Show loading indicator immediately."""
        # Hide empty state container and image
        self.empty_container.place_forget()
        self._image_label.grid_remove()

        # Show loading label
        self._loading_label.place(relx=0.5, rely=0.5, anchor="center")

        # Update file label
        self.file_label.configure(text=filename)
        self.cutoff_label.configure(text="Cargando...")
        self.max_freq_label.configure(text="Frec. max: -")
        self.confidence_label.configure(text="Confianza: -")

        # Force visual update
        self.update_idletasks()

    def _on_resize(self, event):
        """Handle container resize with debouncing."""
        # Skip if resize is paused (during drag operations)
        if self._resize_paused:
            return

        # Only re-render if we have an analysis to display
        if self._current_analysis is None:
            return

        # Cancel previous resize timer
        if self._resize_timer:
            self.after_cancel(self._resize_timer)

        # Set new timer (debounce 200ms)
        self._resize_timer = self.after(200, self._handle_resize)

    def pause_resize(self):
        """Pause resize handling during divider drag."""
        self._resize_paused = True
        # Cancel any pending resize timer
        if self._resize_timer:
            self.after_cancel(self._resize_timer)
            self._resize_timer = None
        # Unbind Configure event to prevent event cascade during drag
        self.figure_frame.unbind("<Configure>")

    def resume_resize(self):
        """Resume resize handling after divider drag."""
        self._resize_paused = False
        # Rebind Configure event
        self.figure_frame.bind("<Configure>", self._on_resize)
        # Trigger resize to update spectrogram to new size
        self._handle_resize()

    def _handle_resize(self):
        """Re-render spectrogram at new size."""
        self._resize_timer = None

        if self._current_analysis is None:
            return

        # Get new dimensions
        new_width = self.figure_frame.winfo_width()
        new_height = self.figure_frame.winfo_height()

        # Only re-render if size changed significantly (>20px difference)
        old_width, old_height = self._last_render_size
        if abs(new_width - old_width) < 20 and abs(new_height - old_height) < 20:
            return

        # Re-render with current analysis data
        self.show_spectrogram(
            self._current_analysis,
            self._current_filename,
            self._current_cutoff_khz,
        )

    def _render_in_background(
        self,
        render_id: int,
        analysis: FrequencyAnalysis,
        filename: str,
        cutoff_khz: float,
        width: int,
        height: int,
    ):
        """Render spectrogram in background thread using Agg backend."""
        # Check for cancellation
        if self._render_cancelled.is_set() or render_id != self._render_id:
            return

        try:
            # Use non-interactive backend (thread-safe)
            matplotlib.use('Agg')
            plt.style.use('dark_background')

            # Create new figure (don't reuse to avoid state issues)
            dpi = 100
            fig = Figure(
                figsize=(width / dpi, height / dpi),
                dpi=dpi,
                facecolor=THEME_COLORS["bg_primary"]
            )
            ax_spectrogram = fig.add_subplot(211)
            ax_energy = fig.add_subplot(212)

            # Check for cancellation
            if self._render_cancelled.is_set() or render_id != self._render_id:
                plt.close(fig)
                return

            # Plot spectrogram
            self._plot_spectrogram_on_axes(ax_spectrogram, analysis)

            # Plot energy spectrum
            self._plot_energy_on_axes(ax_energy, analysis, cutoff_khz)

            fig.tight_layout(pad=2.0)

            # Check for cancellation after plotting
            if self._render_cancelled.is_set() or render_id != self._render_id:
                plt.close(fig)
                return

            # Render to PIL image
            buf = io.BytesIO()
            fig.savefig(buf, format='png', facecolor=THEME_COLORS["bg_primary"], bbox_inches='tight')
            buf.seek(0)
            image = Image.open(buf)
            # Make a copy since we're closing the buffer
            image = image.copy()
            buf.close()

            plt.close(fig)  # Free memory

            # Send result to main thread
            self.after(0, lambda: self._on_render_complete(
                render_id, image, filename, cutoff_khz, analysis
            ))

        except Exception as e:
            # Log error but don't crash
            print(f"Error rendering spectrogram: {e}")
            plt.close('all')

    def _plot_spectrogram_on_axes(self, ax, analysis: FrequencyAnalysis):
        """Plot the spectrogram on given axes."""
        # Get data
        spectrogram_db = analysis.spectrogram_db
        frequencies = analysis.frequencies

        # Create time axis (simplified)
        n_frames = spectrogram_db.shape[1]

        # Set axes background
        ax.set_facecolor(THEME_COLORS["bg_primary"])

        # Plot spectrogram
        ax.imshow(
            spectrogram_db,
            aspect='auto',
            origin='lower',
            cmap='magma',
            extent=[0, n_frames, frequencies[0] / 1000, frequencies[-1] / 1000],
            vmin=-80,
            vmax=0,
        )

        # Add cutoff line - golden color
        cutoff_khz = analysis.cutoff_frequency_khz
        ax.axhline(y=cutoff_khz, color=THEME_COLORS["accent"], linestyle='--', linewidth=1.5, alpha=0.8)

        # Labels - cream color
        ax.set_xlabel('Tiempo (frames)', fontsize=10, color=THEME_COLORS["text_primary"])
        ax.set_ylabel('Frecuencia (kHz)', fontsize=10, color=THEME_COLORS["text_primary"])
        ax.set_title('Espectrograma', fontsize=12, color=THEME_COLORS["text_primary"])

        # Limit y-axis to relevant range
        ax.set_ylim(0, min(24, frequencies[-1] / 1000))

        ax.tick_params(colors=THEME_COLORS["text_primary"], labelsize=8)

    def _plot_energy_on_axes(
        self, ax, analysis: FrequencyAnalysis, cutoff_khz: float
    ):
        """Plot the average energy spectrum with cutoff indicator on given axes."""
        # Get data
        energy = analysis.energy_spectrum
        frequencies = analysis.frequencies / 1000  # Convert to kHz

        # Set axes background
        ax.set_facecolor(THEME_COLORS["bg_primary"])

        # Plot energy curve - purple color
        ax.fill_between(frequencies, energy, -80, alpha=0.3, color=THEME_COLORS["primary"])
        ax.plot(frequencies, energy, color=THEME_COLORS["primary"], linewidth=1.5)

        # Add cutoff line - golden color
        ax.axvline(x=cutoff_khz, color=THEME_COLORS["accent"], linestyle='--', linewidth=2, alpha=0.8)

        # Add noise floor line
        ax.axhline(y=-60, color='gray', linestyle=':', linewidth=1, alpha=0.5)

        # Add cutoff annotation - golden color
        ax.annotate(
            f'{cutoff_khz:.1f} kHz',
            xy=(cutoff_khz, -30),
            xytext=(cutoff_khz + 1, -20),
            fontsize=10,
            color=THEME_COLORS["accent"],
            arrowprops=dict(arrowstyle='->', color=THEME_COLORS["accent"], alpha=0.7),
        )

        # Labels - cream color
        ax.set_xlabel('Frecuencia (kHz)', fontsize=10, color=THEME_COLORS["text_primary"])
        ax.set_ylabel('Energia (dB)', fontsize=10, color=THEME_COLORS["text_primary"])
        ax.set_title('Espectro de Energia Promedio', fontsize=12, color=THEME_COLORS["text_primary"])

        # Set limits
        ax.set_xlim(0, min(24, frequencies[-1]))
        ax.set_ylim(-80, 0)

        ax.tick_params(colors=THEME_COLORS["text_primary"], labelsize=8)
        ax.grid(True, alpha=0.2)

    def _on_render_complete(
        self,
        render_id: int,
        image: Image.Image,
        filename: str,
        cutoff_khz: float,
        analysis: FrequencyAnalysis,
    ):
        """Handle render completion in main thread."""
        # Verify this is still the expected render
        if render_id != self._render_id:
            return  # Obsolete render, discard

        # Convert to CTkImage (handles HighDPI scaling)
        self._photo_image = ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=(image.width, image.height)
        )

        # Hide loading, show image
        self._loading_label.place_forget()
        self._image_label.configure(image=self._photo_image, text="")
        self._image_label.grid()

        # Update info labels
        self.cutoff_label.configure(text=f"Frec. de corte: {cutoff_khz:.1f} kHz")
        self.max_freq_label.configure(
            text=f"Frec. max: {analysis.max_frequency_hz / 1000:.1f} kHz"
        )
        self.confidence_label.configure(
            text=f"Confianza: {analysis.confidence * 100:.0f}%"
        )

    def clear(self):
        """Clear the spectrogram display."""
        # Cancel any in-progress render
        self._render_cancelled.set()
        self._render_id += 1

        self._current_analysis = None
        self._current_filename = None
        self._current_cutoff_khz = None
        self._photo_image = None
        self._last_render_size = (0, 0)

        # Hide image and loading
        self._image_label.grid_remove()
        self._loading_label.place_forget()

        # Show empty state container
        self.empty_container.place(relx=0.5, rely=0.5, anchor="center")

        # Reset labels
        self.file_label.configure(text="")
        self.cutoff_label.configure(text="Frec. de corte: -")
        self.max_freq_label.configure(text="Frec. max: -")
        self.confidence_label.configure(text="Confianza: -")

    def get_current_analysis(self) -> Optional[FrequencyAnalysis]:
        """Get the currently displayed analysis."""
        return self._current_analysis
