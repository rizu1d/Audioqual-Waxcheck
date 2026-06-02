"""Spectrogram visualization in a separate window.

Uses a Canvas-based renderer inspired by Spek:
- Spectrogram bitmap rendered via numpy + colormap LUT (no matplotlib)
- Axes drawn natively on canvas (always crisp at any size)
- On resize: only the bitmap scales, axes redraw at native resolution
"""

import threading
import tkinter as tk
from typing import Optional

import customtkinter as ctk
import numpy as np
from PIL import Image, ImageTk

from ..core.frequency_detector import FrequencyAnalysis
from ..utils.constants import (
    THEME_COLORS, FONT_FAMILY, FONT_FAMILY_MONO, FONT_SIZES,
    RELIABILITY_COLORS, HOP_LENGTH, SAMPLE_RATE,
)
from ..utils.i18n import t

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
# Spectrogram dB range (matching Spek's sensitivity)
_SPEC_DB_MIN = -80
_SPEC_DB_MAX = 0


# ── Pre-build 256-entry RGB lookup table from the palette (once at import) ──
def _build_colormap_lut() -> np.ndarray:
    """256-entry RGB LUT linearly interpolating the Spek anchor palette.

    Reproduces, bit-for-bit, what a matplotlib ``LinearSegmentedColormap``
    built from the same anchors and sampled at ``i/255`` used to give — but
    with plain numpy, so the app carries no matplotlib dependency. The anchors
    are spread evenly over [0, 1]; ``internal`` mirrors matplotlib's N=256
    lookup table and ``xa`` mirrors its ``int(x * N)`` index mapping.
    """
    anchors = np.array(_SPEK_COLORS_RGB, dtype=np.float64)
    anchor_pos = np.linspace(0.0, 1.0, len(anchors))
    internal = np.linspace(0.0, 1.0, 256)
    channels = [np.interp(internal, anchor_pos, anchors[:, c]) for c in range(3)]
    lut = np.empty((256, 3), dtype=np.uint8)
    for i in range(256):
        xa = min(int(i / 255.0 * 256), 255)
        lut[i] = [int(channels[c][xa]) for c in range(3)]
    return lut


_COLORMAP_LUT = _build_colormap_lut()


class SpectrogramWindow(ctk.CTkToplevel):
    """
    Separate window for displaying audio spectrograms with frequency cutoff visualization.

    Architecture (inspired by Spek):
    - Spectrogram bitmap: numpy array → colormap LUT → PIL Image (fast, ~50ms)
    - Axes/labels: drawn natively on tk.Canvas (always crisp at any resolution)
    - Resize: only bitmap scales via PIL.resize (~5ms), axes redraw natively
    - Progressive reveal: axes visible from start, bitmap fills left-to-right
    """

    # Layout padding (pixels) — similar to Spek's DIP constants
    LPAD = 52    # Left (frequency labels)
    TPAD = 14    # Top
    RPAD = 62    # Right (colorbar + dB labels)
    BPAD = 32    # Bottom (time labels)
    CBAR_W = 10  # Colorbar strip width
    CBAR_GAP = 8 # Gap between spectrogram and colorbar

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

        # Spectrogram image data
        self._raw_spectrogram: Optional[Image.Image] = None
        self._colorbar_strip: Optional[Image.Image] = None
        self._spec_photo = None   # Keep reference alive for tk
        self._cbar_photo = None

        # Axis metadata (set after computation)
        self._duration_sec: float = 0.0
        self._max_khz: float = 0.0

        # Rendering state
        self._render_thread: Optional[threading.Thread] = None
        self._render_cancelled = threading.Event()
        self._render_id: int = 0
        self._reveal_timer = None
        self._is_revealing: bool = False
        self._scaled_for_reveal: Optional[Image.Image] = None

        self.withdraw()  # Hide until positioned

        self._setup_window()
        self._setup_ui()

        self.deiconify()  # Show at correct position
        # Schedule render after window is mapped
        self.after(50, self._start_render)

    def _setup_window(self):
        """Configure the window."""
        self.title(t("spectrogram.window_title", filename=self._current_filename))
        self.geometry("800x500")
        self.minsize(400, 300)
        self.configure(fg_color=THEME_COLORS["bg_primary"])
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

        # Canvas for spectrogram + native axes
        self._canvas = tk.Canvas(
            self.figure_frame,
            bg=THEME_COLORS["bg_frame"],
            highlightthickness=0,
        )
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Loading indicator
        self._loading_label = ctk.CTkLabel(
            self.figure_frame,
            text=t("spectrogram.loading"),
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
            text=t("spectrogram.cutoff_label", cutoff=f"{self._current_cutoff_khz:.1f}"),
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

    @staticmethod
    def _get_reliability_label(confidence: float) -> tuple[str, str]:
        """Return (text, color) for a confidence value."""
        if confidence >= 0.7:
            return t("reliability.high"), RELIABILITY_COLORS["high"]
        elif confidence >= 0.5:
            return t("reliability.medium"), RELIABILITY_COLORS["medium"]
        else:
            return t("reliability.low"), RELIABILITY_COLORS["low"]

    # ── Public API ──────────────────────────────────────────────────────

    def update_spectrogram(
        self,
        analysis: FrequencyAnalysis,
        filename: str,
        cutoff_khz: float,
    ):
        """Update the window with a new spectrogram."""
        self._current_analysis = analysis
        self._current_filename = filename
        self._current_cutoff_khz = cutoff_khz

        # Update window title and info labels
        self.title(t("spectrogram.window_title", filename=filename))
        self.cutoff_label.configure(text=t("spectrogram.cutoff_label", cutoff=f"{cutoff_khz:.1f}"))
        rel_text, rel_color = self._get_reliability_label(analysis.confidence)
        self.confidence_label.configure(text=rel_text, text_color=rel_color)

        # Cancel ongoing work
        self._cancel_reveal()
        self._render_cancelled.set()

        # Clear old data
        self._raw_spectrogram = None
        self._canvas.delete("all")

        # Show loading
        self._loading_label.place(relx=0.5, rely=0.45, anchor="center")
        self._progress_bar.place(relx=0.5, rely=0.55, anchor="center")
        self._progress_bar.start()

        # Start render after brief delay for UI update
        self.after(50, self._start_render)

    def is_open(self) -> bool:
        """Check if the window is still open."""
        try:
            return self.winfo_exists()
        except tk.TclError:
            return False

    # ── Background computation ──────────────────────────────────────────

    def _start_render(self):
        """Start background computation of spectrogram image."""
        if self._current_analysis is None:
            return

        self._render_id += 1
        current_id = self._render_id
        self._render_cancelled.clear()

        self._render_thread = threading.Thread(
            target=self._compute_in_background,
            args=(current_id,),
            daemon=True,
        )
        self._render_thread.start()

    def _compute_in_background(self, render_id: int):
        """Compute spectrogram PIL image from analysis data (no matplotlib)."""
        if self._render_cancelled.is_set() or render_id != self._render_id:
            return

        try:
            analysis = self._current_analysis
            spec_db = analysis.spectrogram_db

            # Normalize spectrogram to 0-255 uint8 indices
            db_range = float(_SPEC_DB_MAX - _SPEC_DB_MIN)
            spec = np.array(spec_db, dtype=np.float32)
            np.clip(spec, _SPEC_DB_MIN, _SPEC_DB_MAX, out=spec)
            spec -= _SPEC_DB_MIN
            spec *= (255.0 / db_range)
            indices = spec.astype(np.uint8)
            del spec

            if self._render_cancelled.is_set() or render_id != self._render_id:
                return

            # Flip vertically (low frequencies at bottom in display)
            indices = indices[::-1]

            # Apply colormap via pre-built LUT
            rgb = _COLORMAP_LUT[indices]
            del indices

            # Create PIL image
            img = Image.fromarray(rgb, 'RGB')
            del rgb

            # Downsample if very large (keeps memory reasonable)
            max_w, max_h = 2048, 1024
            if img.width > max_w or img.height > max_h:
                ratio = min(max_w / img.width, max_h / img.height)
                img = img.resize(
                    (max(1, int(img.width * ratio)), max(1, int(img.height * ratio))),
                    Image.LANCZOS,
                )

            if self._render_cancelled.is_set() or render_id != self._render_id:
                return

            # Build colorbar gradient strip
            gradient = np.arange(255, -1, -1, dtype=np.uint8).reshape(256, 1)
            cbar_rgb = _COLORMAP_LUT[gradient.flatten()].reshape(256, 1, 3)
            cbar_img = Image.fromarray(cbar_rgb, 'RGB')

            # Compute metadata
            n_frames = spec_db.shape[1]
            duration = n_frames * HOP_LENGTH / SAMPLE_RATE
            max_khz = min(24.0, analysis.frequencies[-1] / 1000)

            from ..utils.tk_utils import schedule_callback_from_thread
            schedule_callback_from_thread(
                self, self._on_compute_complete,
                render_id, img, cbar_img, duration, max_khz,
            )
        except Exception as e:
            print(f"Error computing spectrogram: {e}")

    def _on_compute_complete(
        self, render_id: int, spec_img: Image.Image,
        cbar_img: Image.Image, duration: float, max_khz: float,
    ):
        """Handle computation completion in main thread."""
        if render_id != self._render_id:
            return

        self._raw_spectrogram = spec_img
        self._colorbar_strip = cbar_img
        self._duration_sec = duration
        self._max_khz = max_khz

        try:
            self._progress_bar.stop()
            self._progress_bar.place_forget()
            self._loading_label.place_forget()
            self._start_reveal()
        except tk.TclError:
            pass

    # ── Progressive reveal animation ────────────────────────────────────

    def _start_reveal(self):
        """Progressive left-to-right reveal: axes visible from start, bitmap fills in."""
        self._is_revealing = True
        self._canvas.delete("all")

        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        spec_w = cw - self.LPAD - self.RPAD
        spec_h = ch - self.TPAD - self.BPAD

        if spec_w < 10 or spec_h < 10:
            self._is_revealing = False
            self._redraw()
            return

        # Pre-scale spectrogram to target size once
        self._scaled_for_reveal = self._raw_spectrogram.resize(
            (spec_w, spec_h), Image.LANCZOS,
        )

        # Draw axes and colorbar first (always visible from start, like Spek)
        self._draw_colorbar(cw, ch)
        self._draw_axes(cw, ch)

        # Start progressive bitmap reveal
        self._reveal_step_fn(1, 12, spec_w, spec_h, self._render_id)

    def _reveal_step_fn(
        self, step: int, total: int, spec_w: int, spec_h: int, render_id: int,
    ):
        """Single step of the progressive reveal animation."""
        if render_id != self._render_id:
            self._is_revealing = False
            return

        try:
            visible_w = max(1, int(spec_w * step / total))

            # Crop from pre-scaled image (essentially free — no pixel computation)
            cropped = self._scaled_for_reveal.crop((0, 0, visible_w, spec_h))
            self._spec_photo = ImageTk.PhotoImage(cropped)

            self._canvas.delete("spectrogram")
            self._canvas.create_image(
                self.LPAD, self.TPAD,
                image=self._spec_photo, anchor="nw", tags="spectrogram",
            )

            if step < total:
                self._reveal_timer = self.after(
                    25,
                    lambda: self._reveal_step_fn(step + 1, total, spec_w, spec_h, render_id),
                )
            else:
                # Reveal complete
                self._is_revealing = False
                self._scaled_for_reveal = None

        except tk.TclError:
            self._is_revealing = False

    def _cancel_reveal(self):
        """Cancel any in-progress reveal animation."""
        if self._reveal_timer:
            self.after_cancel(self._reveal_timer)
            self._reveal_timer = None
        self._is_revealing = False
        self._scaled_for_reveal = None

    # ── Canvas resize & redraw ──────────────────────────────────────────

    def _on_canvas_configure(self, event):
        """Handle canvas resize: scale bitmap instantly, redraw native axes."""
        if self._raw_spectrogram is None:
            return
        if self._is_revealing:
            # User resizing during reveal — skip to full display
            self._cancel_reveal()
        self._redraw()

    def _redraw(self):
        """Full redraw: scale spectrogram bitmap + draw native axes."""
        self._canvas.delete("all")

        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 50 or ch < 50:
            return

        spec_w = cw - self.LPAD - self.RPAD
        spec_h = ch - self.TPAD - self.BPAD
        if spec_w < 10 or spec_h < 10:
            return

        # Scale spectrogram bitmap to fit (~5ms with LANCZOS)
        scaled = self._raw_spectrogram.resize((spec_w, spec_h), Image.LANCZOS)
        self._spec_photo = ImageTk.PhotoImage(scaled)
        self._canvas.create_image(
            self.LPAD, self.TPAD,
            image=self._spec_photo, anchor="nw", tags="spectrogram",
        )

        # Draw colorbar and axes at native resolution (always crisp)
        self._draw_colorbar(cw, ch)
        self._draw_axes(cw, ch)

    # ── Native axis drawing ─────────────────────────────────────────────

    def _draw_colorbar(self, cw: int, ch: int):
        """Draw the colorbar gradient strip."""
        spec_h = ch - self.TPAD - self.BPAD
        if spec_h < 10 or self._colorbar_strip is None:
            return

        cbar_x = cw - self.RPAD + self.CBAR_GAP
        cbar_scaled = self._colorbar_strip.resize((self.CBAR_W, spec_h), Image.NEAREST)
        self._cbar_photo = ImageTk.PhotoImage(cbar_scaled)
        self._canvas.create_image(
            cbar_x, self.TPAD,
            image=self._cbar_photo, anchor="nw", tags="colorbar",
        )

    def _draw_axes(self, cw: int, ch: int):
        """Draw axes labels and ticks natively on the canvas (always crisp)."""
        if self._duration_sec <= 0 or self._max_khz <= 0:
            return

        text_color = THEME_COLORS["text_primary"]
        border_color = "#3a3a3e"
        font_tick = (FONT_FAMILY_MONO, 8)
        font_label = (FONT_FAMILY_MONO, 9)

        spec_x = self.LPAD
        spec_y = self.TPAD
        spec_w = cw - self.LPAD - self.RPAD
        spec_h = ch - self.TPAD - self.BPAD

        if spec_w < 10 or spec_h < 10:
            return

        # Spectrogram border
        self._canvas.create_rectangle(
            spec_x, spec_y, spec_x + spec_w, spec_y + spec_h,
            outline=border_color, width=1, tags="axes",
        )

        # ── Time axis (bottom) ──
        time_ticks = self._compute_time_ticks()
        for t_sec, label in time_ticks:
            frac = t_sec / self._duration_sec
            x = spec_x + frac * spec_w
            y = spec_y + spec_h
            self._canvas.create_line(x, y, x, y + 4, fill=text_color, tags="axes")
            self._canvas.create_text(
                x, y + 6, text=label, fill=text_color,
                font=font_tick, anchor="n", tags="axes",
            )
        # "min" axis label
        self._canvas.create_text(
            spec_x + spec_w / 2, ch - 2, text="min",
            fill=text_color, font=font_label, anchor="s", tags="axes",
        )

        # ── Frequency axis (left) ──
        freq_step = 2.0  # kHz
        f = 0.0
        while f <= self._max_khz + 0.01:
            frac = f / self._max_khz
            y = spec_y + spec_h - frac * spec_h
            self._canvas.create_line(spec_x - 4, y, spec_x, y, fill=text_color, tags="axes")
            self._canvas.create_text(
                spec_x - 6, y, text=str(int(f)),
                fill=text_color, font=font_tick, anchor="e", tags="axes",
            )
            f += freq_step
        # "kHz" axis label
        self._canvas.create_text(
            spec_x - 6, spec_y - 4, text="kHz",
            fill=text_color, font=font_label, anchor="se", tags="axes",
        )

        # ── dB axis (right of colorbar) ──
        cbar_x = cw - self.RPAD + self.CBAR_GAP
        db_x = cbar_x + self.CBAR_W + 4
        for db_val in [0, -20, -40, -60, -80]:
            frac = -db_val / (-_SPEC_DB_MIN)  # 0 dB at top, -80 dB at bottom
            y = spec_y + frac * spec_h
            self._canvas.create_text(
                db_x, y, text=str(db_val),
                fill=text_color, font=font_tick, anchor="w", tags="axes",
            )
        # "dB" label
        self._canvas.create_text(
            db_x, spec_y - 4, text="dB",
            fill=text_color, font=font_label, anchor="sw", tags="axes",
        )

    def _compute_time_ticks(self) -> list[tuple[float, str]]:
        """Compute nice time axis tick positions and labels."""
        duration = self._duration_sec
        if duration <= 0:
            return []

        # Choose a nice interval aiming for ~8 ticks
        nice_intervals = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600]
        raw_interval = duration / 8
        interval = nice_intervals[-1]
        for ni in nice_intervals:
            if ni >= raw_interval:
                interval = ni
                break

        ticks = []
        t = 0.0
        while t <= duration + 0.01:
            mins = int(t // 60)
            secs = int(t % 60)
            ticks.append((t, f"{mins}:{secs:02d}"))
            t += interval
        return ticks

    # ── Window lifecycle ────────────────────────────────────────────────

    def _on_close(self):
        """Handle window close."""
        self._render_cancelled.set()
        self._render_id += 1
        self._cancel_reveal()
        self.destroy()
        self.master.focus_force()
