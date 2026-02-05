"""Spectrogram visualization in a separate window."""

import threading
import time
import tkinter as tk
from typing import Optional

import customtkinter as ctk
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np
from PIL import Image

from ..core.frequency_detector import FrequencyAnalysis
from ..utils.constants import THEME_COLORS, FONT_FAMILY, FONT_SIZES


class SpectrogramWindow(ctk.CTkToplevel):
    """
    Separate window for displaying audio spectrograms with frequency cutoff visualization.
    Uses background threading for responsive UI during rendering.
    """

    def __init__(
        self,
        master,
        analysis: FrequencyAnalysis,
        filename: str,
        cutoff_khz: float,
    ):
        super().__init__(master)

        self._current_analysis: FrequencyAnalysis = analysis
        self._current_filename: str = filename
        self._current_cutoff_khz: float = cutoff_khz
        self._render_thread: Optional[threading.Thread] = None
        self._render_cancelled = threading.Event()
        self._render_id = 0
        self._photo_image = None
        self._resize_timer = None
        self._render_timer = None
        self._last_render_size = (0, 0)
        self._last_render_time = 0

        self._setup_window()
        self._setup_ui()

        # Schedule initial render after window is mapped
        self.after(100, self._start_render)

    def _setup_window(self):
        """Configure the window."""
        self.title(f"Espectrograma - {self._current_filename}")
        self.geometry("800x500")
        self.minsize(400, 300)

        # Dark background
        self.configure(fg_color=THEME_COLORS["bg_primary"])

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_ui(self):
        """Set up the window UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # Figure container frame
        self.figure_frame = ctk.CTkFrame(
            self,
            fg_color=THEME_COLORS["bg_frame"],
            corner_radius=8,
        )
        self.figure_frame.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.figure_frame.grid_columnconfigure(0, weight=1)
        self.figure_frame.grid_rowconfigure(0, weight=1)

        # Image label for displaying rendered spectrogram
        self._image_label = ctk.CTkLabel(
            self.figure_frame,
            text="",
            image=None,
        )
        self._image_label.grid(row=0, column=0, sticky="nsew")
        self._image_label.grid_remove()

        # Loading indicator
        self._loading_label = ctk.CTkLabel(
            self.figure_frame,
            text="Cargando espectrograma...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=THEME_COLORS["text_secondary"],
        )
        self._loading_label.place(relx=0.5, rely=0.5, anchor="center")

        # Info panel at the bottom
        self.info_frame = ctk.CTkFrame(
            self,
            height=50,
            fg_color=THEME_COLORS["bg_elevated"],
            corner_radius=8,
        )
        self.info_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.info_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Cutoff frequency info
        self.cutoff_label = ctk.CTkLabel(
            self.info_frame,
            text=f"Frec. de corte: {self._current_cutoff_khz:.1f} kHz",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=THEME_COLORS["text_primary"],
        )
        self.cutoff_label.grid(row=0, column=0, padx=16, pady=12)

        # Max frequency info
        self.max_freq_label = ctk.CTkLabel(
            self.info_frame,
            text=f"Frec. max: {self._current_analysis.max_frequency_hz / 1000:.1f} kHz",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=THEME_COLORS["text_primary"],
        )
        self.max_freq_label.grid(row=0, column=1, padx=16, pady=12)

        # Confidence info
        self.confidence_label = ctk.CTkLabel(
            self.info_frame,
            text=f"Confianza: {self._current_analysis.confidence * 100:.0f}%",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=THEME_COLORS["text_primary"],
        )
        self.confidence_label.grid(row=0, column=2, padx=16, pady=12)

        # Bind resize event
        self.figure_frame.bind("<Configure>", self._on_resize)

    def update_spectrogram(
        self,
        analysis: FrequencyAnalysis,
        filename: str,
        cutoff_khz: float,
    ):
        """
        Update the window with a new spectrogram.

        Args:
            analysis: FrequencyAnalysis object with spectral data
            filename: Name of the file being displayed
            cutoff_khz: Detected cutoff frequency in kHz
        """
        self._current_analysis = analysis
        self._current_filename = filename
        self._current_cutoff_khz = cutoff_khz

        # Update window title
        self.title(f"Espectrograma - {filename}")

        # Update info labels
        self.cutoff_label.configure(text=f"Frec. de corte: {cutoff_khz:.1f} kHz")
        self.max_freq_label.configure(
            text=f"Frec. max: {analysis.max_frequency_hz / 1000:.1f} kHz"
        )
        self.confidence_label.configure(
            text=f"Confianza: {analysis.confidence * 100:.0f}%"
        )

        # Cancel any pending render timer
        if self._render_timer:
            self.after_cancel(self._render_timer)
            self._render_timer = None

        # Cancel any in-progress render
        self._render_cancelled.set()

        # Show loading state
        self._image_label.grid_remove()
        self._loading_label.place(relx=0.5, rely=0.5, anchor="center")

        # Schedule render after a brief delay
        self._render_timer = self.after(100, self._start_render)

    def _on_resize(self, event):
        """Handle window resize with debouncing."""
        if self._current_analysis is None:
            return

        # Cancel previous resize timer
        if self._resize_timer:
            self.after_cancel(self._resize_timer)

        # Set new timer (debounce 400ms)
        self._resize_timer = self.after(400, self._handle_resize)

    def _handle_resize(self):
        """Re-render spectrogram at new size."""
        self._resize_timer = None

        if self._current_analysis is None:
            return

        # Skip if render just completed
        if time.time() - self._last_render_time < 0.5:
            return

        # Skip if render timer is pending
        if self._render_timer is not None:
            return

        # Skip if render is in progress
        if self._render_thread is not None and self._render_thread.is_alive():
            self._resize_timer = self.after(500, self._handle_resize)
            return

        # Get new dimensions
        new_width = self.figure_frame.winfo_width()
        new_height = self.figure_frame.winfo_height()

        # Only re-render if size changed significantly (>50px)
        old_width, old_height = self._last_render_size
        if abs(new_width - old_width) < 50 and abs(new_height - old_height) < 50:
            return

        self._start_render()

    def _start_render(self):
        """Start the background render."""
        self._render_timer = None

        if self._current_analysis is None:
            return

        self._render_id += 1
        current_render_id = self._render_id

        # Get dimensions
        width = self.figure_frame.winfo_width()
        height = self.figure_frame.winfo_height()
        width = max(width, 300) if width > 1 else 300
        height = max(height, 200) if height > 1 else 200
        self._last_render_size = (width, height)

        # Reset cancellation flag and start background render
        self._render_cancelled.clear()
        self._render_thread = threading.Thread(
            target=self._render_in_background,
            args=(current_render_id, width, height),
            daemon=True,
        )
        self._render_thread.start()

    def _render_in_background(self, render_id: int, width: int, height: int):
        """Render spectrogram in background thread."""
        if self._render_cancelled.is_set() or render_id != self._render_id:
            return

        try:
            dpi = 100
            fig = Figure(
                figsize=(width / dpi, height / dpi),
                dpi=dpi,
                facecolor=THEME_COLORS["bg_primary"],
            )
            ax = fig.add_subplot(111)

            if self._render_cancelled.is_set() or render_id != self._render_id:
                return

            # Plot spectrogram
            self._plot_spectrogram(ax, self._current_analysis)

            fig.tight_layout(pad=1.0)

            if self._render_cancelled.is_set() or render_id != self._render_id:
                return

            # Render to PIL image
            canvas = FigureCanvasAgg(fig)
            canvas.draw()

            buf = canvas.buffer_rgba()
            image = Image.frombuffer(
                'RGBA',
                (int(fig.get_figwidth() * dpi), int(fig.get_figheight() * dpi)),
                buf,
                'raw',
                'RGBA',
                0,
                1,
            )
            image = image.copy()

            # Send result to main thread
            self.after(0, lambda: self._on_render_complete(render_id, image))

        except Exception as e:
            print(f"Error rendering spectrogram: {e}")

    def _plot_spectrogram(self, ax, analysis: FrequencyAnalysis):
        """Plot the spectrogram on given axes."""
        spectrogram_db = analysis.spectrogram_db
        frequencies = analysis.frequencies

        n_frames = spectrogram_db.shape[1]

        ax.set_facecolor(THEME_COLORS["bg_primary"])

        ax.imshow(
            spectrogram_db,
            aspect='auto',
            origin='lower',
            cmap='magma',
            extent=[0, n_frames, frequencies[0] / 1000, frequencies[-1] / 1000],
            vmin=-80,
            vmax=0,
        )

        # Add cutoff line
        cutoff_khz = analysis.cutoff_frequency_khz
        ax.axhline(
            y=cutoff_khz,
            color=THEME_COLORS["accent"],
            linestyle='--',
            linewidth=1.5,
            alpha=0.8,
        )

        # Labels
        ax.set_xlabel('Tiempo (frames)', fontsize=10, color=THEME_COLORS["text_primary"])
        ax.set_ylabel('Frecuencia (kHz)', fontsize=10, color=THEME_COLORS["text_primary"])
        ax.set_title('Espectrograma', fontsize=12, color=THEME_COLORS["text_primary"])

        # Limit y-axis
        ax.set_ylim(0, min(24, frequencies[-1] / 1000))

        ax.tick_params(colors=THEME_COLORS["text_primary"], labelsize=8)

    def _on_render_complete(self, render_id: int, image: Image.Image):
        """Handle render completion in main thread."""
        if render_id != self._render_id:
            return

        try:
            self._photo_image = ctk.CTkImage(
                light_image=image,
                dark_image=image,
                size=(image.width, image.height),
            )

            # Hide loading, show image
            self._loading_label.place_forget()

            self._image_label.configure(image=self._photo_image, text="")
            self._image_label.grid(row=0, column=0, sticky="nsew")
            self._image_label.lift()

            self._last_render_time = time.time()

        except tk.TclError:
            # Widget was destroyed during render
            pass

    def _on_close(self):
        """Handle window close."""
        # Cancel any in-progress render
        self._render_cancelled.set()
        self._render_id += 1

        # Cancel timers
        if self._render_timer:
            self.after_cancel(self._render_timer)
        if self._resize_timer:
            self.after_cancel(self._resize_timer)

        self.destroy()

    def is_open(self) -> bool:
        """Check if the window is still open."""
        try:
            return self.winfo_exists()
        except tk.TclError:
            return False
