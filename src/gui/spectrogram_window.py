"""Spectrogram visualization in a separate window."""

import threading
import tkinter as tk
from typing import Optional

import customtkinter as ctk
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MultipleLocator
import numpy as np
from PIL import Image

from ..core.frequency_detector import FrequencyAnalysis
from ..utils.constants import (
    THEME_COLORS, FONT_FAMILY, FONT_SIZES, RELIABILITY_COLORS,
    HOP_LENGTH, SAMPLE_RATE,
)

# ── Spek-matching colormap ──────────────────────────────────────────────
# Palette extracted from Spek's source (spek-palette.cc):
# black → dark navy → purple → magenta → red → orange → yellow → white
_SPEK_COLORS_RGB = [
    (0x00, 0x00, 0x00), (0x0c, 0x00, 0x24), (0x1a, 0x00, 0x4a), (0x34, 0x00, 0x72),
    (0x4c, 0x00, 0x96), (0x64, 0x00, 0xaa), (0x7c, 0x00, 0xb2), (0x90, 0x00, 0xb2),
    (0xa0, 0x00, 0xa0), (0xb0, 0x00, 0x80), (0xc0, 0x00, 0x60), (0xd0, 0x00, 0x40),
    (0xe0, 0x00, 0x20), (0xf4, 0x00, 0x00), (0xff, 0x1c, 0x00), (0xff, 0x40, 0x00),
    (0xff, 0x60, 0x00), (0xff, 0x80, 0x00), (0xff, 0xa0, 0x00), (0xff, 0xc0, 0x00),
    (0xff, 0xe0, 0x00), (0xff, 0xff, 0x00), (0xff, 0xff, 0x40), (0xff, 0xff, 0x80),
    (0xff, 0xff, 0xc0), (0xff, 0xff, 0xff),
]
SPEK_CMAP = LinearSegmentedColormap.from_list(
    'spek',
    [(r / 255, g / 255, b / 255) for r, g, b in _SPEK_COLORS_RGB],
    N=256,
)

# Spectrogram dB range (matching Spek's sensitivity)
_SPEC_DB_MIN = -80
_SPEC_DB_MAX = 0


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

        self.withdraw()  # Hide until positioned

        self._setup_window()
        self._setup_ui()

        self.deiconify()  # Show at correct position
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
        self._loading_label.place(relx=0.5, rely=0.45, anchor="center")

        # Progress bar for loading animation
        self._progress_bar = ctk.CTkProgressBar(
            self.figure_frame,
            width=200,
            height=4,
            progress_color=THEME_COLORS["accent"],
            fg_color=THEME_COLORS["bg_elevated"],
            mode="indeterminate",
        )
        self._progress_bar.place(relx=0.5, rely=0.55, anchor="center")
        self._progress_bar.start()

        # Info panel at the bottom
        self.info_frame = ctk.CTkFrame(
            self,
            height=50,
            fg_color=THEME_COLORS["bg_elevated"],
            corner_radius=8,
        )
        self.info_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.info_frame.grid_columnconfigure((0, 1), weight=1)

        # Cutoff frequency info
        self.cutoff_label = ctk.CTkLabel(
            self.info_frame,
            text=f"Frec. de corte: {self._current_cutoff_khz:.1f} kHz",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=THEME_COLORS["text_primary"],
        )
        self.cutoff_label.grid(row=0, column=0, padx=16, pady=12)

        # Reliability info
        rel_text, rel_color = self._get_reliability_label(self._current_analysis.confidence)
        self.confidence_label = ctk.CTkLabel(
            self.info_frame,
            text=rel_text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
            text_color=rel_color,
        )
        self.confidence_label.grid(row=0, column=1, padx=16, pady=12)

        # Bind resize event
        self.figure_frame.bind("<Configure>", self._on_resize)

    @staticmethod
    def _get_reliability_label(confidence: float) -> tuple[str, str]:
        """Return (text, color) for a confidence value."""
        if confidence >= 0.7:
            return "Fiabilidad: Alta", RELIABILITY_COLORS["high"]
        elif confidence >= 0.5:
            return "Fiabilidad: Media", RELIABILITY_COLORS["medium"]
        else:
            return "Fiabilidad: Baja", RELIABILITY_COLORS["low"]

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
        rel_text, rel_color = self._get_reliability_label(analysis.confidence)
        self.confidence_label.configure(text=rel_text, text_color=rel_color)

        # Cancel any pending render timer
        if self._render_timer:
            self.after_cancel(self._render_timer)
            self._render_timer = None

        # Cancel any in-progress render
        self._render_cancelled.set()

        # Show loading state with progress bar
        self._image_label.grid_remove()
        self._loading_label.place(relx=0.5, rely=0.45, anchor="center")
        self._progress_bar.place(relx=0.5, rely=0.55, anchor="center")
        self._progress_bar.start()

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
        import time as time_module
        self._resize_timer = None

        if self._current_analysis is None:
            return

        # Skip if render just completed
        if time_module.time() - self._last_render_time < 0.5:
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

        fig = None
        try:
            bg_color = THEME_COLORS["bg_primary"]
            text_color = THEME_COLORS["text_primary"]
            dpi = 100

            fig = Figure(
                figsize=(width / dpi, height / dpi),
                dpi=dpi,
                facecolor=bg_color,
            )

            # Layout: main spectrogram + narrow colorbar on the right
            gs = fig.add_gridspec(
                1, 2,
                width_ratios=[40, 1],
                wspace=0.05,
            )
            ax = fig.add_subplot(gs[0])
            cbar_ax = fig.add_subplot(gs[1])

            if self._render_cancelled.is_set() or render_id != self._render_id:
                return

            # Plot spectrogram (returns the AxesImage for colorbar)
            im = self._plot_spectrogram(ax, self._current_analysis)

            # ── Colorbar (dB legend) ──
            cbar = fig.colorbar(im, cax=cbar_ax)
            cbar.set_label(
                'dB', color=text_color, fontsize=9,
                rotation=0, labelpad=12, va='center',
            )
            cbar.ax.tick_params(colors=text_color, labelsize=7, length=3)
            cbar.ax.yaxis.set_major_locator(MultipleLocator(20))
            cbar_ax.set_facecolor(bg_color)

            fig.tight_layout(pad=0.8)

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
            from ..utils.tk_utils import schedule_callback_from_thread
            schedule_callback_from_thread(self, self._on_render_complete, render_id, image)

        except Exception as e:
            print(f"Error rendering spectrogram: {e}")
        finally:
            if fig is not None:
                fig.clear()
                import matplotlib.pyplot as plt
                plt.close(fig)

    def _plot_spectrogram(self, ax, analysis: FrequencyAnalysis):
        """Plot the spectrogram on given axes. Returns the AxesImage for colorbar."""
        spectrogram_db = analysis.spectrogram_db
        frequencies = analysis.frequencies
        n_frames = spectrogram_db.shape[1]

        # Calculate time extent from STFT parameters
        duration_sec = n_frames * HOP_LENGTH / SAMPLE_RATE

        bg_color = THEME_COLORS["bg_primary"]
        text_color = THEME_COLORS["text_primary"]

        ax.set_facecolor(bg_color)

        # Plot with Spek colormap and matching dB range
        im = ax.imshow(
            spectrogram_db,
            aspect='auto',
            origin='lower',
            cmap=SPEK_CMAP,
            extent=[0, duration_sec, frequencies[0] / 1000, frequencies[-1] / 1000],
            vmin=_SPEC_DB_MIN,
            vmax=_SPEC_DB_MAX,
            interpolation='bilinear',
        )

        # ── X-axis: time as m:ss ──
        def _format_time(x, _pos):
            minutes = int(x // 60)
            seconds = int(x % 60)
            return f"{minutes}:{seconds:02d}"

        ax.xaxis.set_major_formatter(FuncFormatter(_format_time))

        # ── Y-axis: frequency in kHz ──
        max_khz = min(24, frequencies[-1] / 1000)
        ax.set_ylim(0, max_khz)
        ax.yaxis.set_major_locator(MultipleLocator(2))

        # ── Styling ──
        ax.tick_params(colors=text_color, labelsize=8, length=3)
        for spine in ax.spines.values():
            spine.set_edgecolor(text_color)
            spine.set_alpha(0.2)

        return im

    def _on_render_complete(self, render_id: int, image: Image.Image):
        """Handle render completion in main thread."""
        if render_id != self._render_id:
            return

        try:
            # Stop and hide progress bar
            self._progress_bar.stop()
            self._progress_bar.place_forget()
            self._loading_label.place_forget()

            # Start progressive reveal
            self._reveal_progressive(image, render_id)

        except tk.TclError:
            # Widget was destroyed during render
            pass

    def _reveal_progressive(self, full_image: Image.Image, render_id: int):
        """Reveal image progressively from left to right."""
        import time as time_module
        n_steps = 12
        step_delay = 25  # ms between steps

        def update_reveal(step: int):
            if render_id != self._render_id:
                return  # Cancelled

            try:
                # Calculate visible width
                visible_width = int(full_image.width * step / n_steps)

                # Create cropped image
                cropped = full_image.crop((0, 0, visible_width, full_image.height))

                # Create padded image (full size, black on right)
                revealed = Image.new('RGBA', full_image.size, (26, 26, 31, 255))  # bg_primary color
                revealed.paste(cropped, (0, 0))

                # Update display
                self._photo_image = ctk.CTkImage(
                    light_image=revealed,
                    dark_image=revealed,
                    size=(revealed.width, revealed.height),
                )
                self._image_label.configure(image=self._photo_image, text="")
                self._image_label.grid(row=0, column=0, sticky="nsew")
                self._image_label.lift()

                # Schedule next step
                if step < n_steps:
                    self.after(step_delay, lambda: update_reveal(step + 1))
                else:
                    # Final step: show complete image
                    self._photo_image = ctk.CTkImage(
                        light_image=full_image,
                        dark_image=full_image,
                        size=(full_image.width, full_image.height),
                    )
                    self._image_label.configure(image=self._photo_image, text="")
                    self._last_render_time = time_module.time()

            except tk.TclError:
                # Widget was destroyed
                pass

        # Start reveal animation
        update_reveal(1)

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
        self.master.focus_force()

    def is_open(self) -> bool:
        """Check if the window is still open."""
        try:
            return self.winfo_exists()
        except tk.TclError:
            return False
