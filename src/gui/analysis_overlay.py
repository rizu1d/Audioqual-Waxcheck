"""Full-screen overlay shown during batch analysis."""

import time
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image, ImageTk

from ..utils.i18n import t
from ..utils.constants import (
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    OVERLAY_COLORS,
    OVERLAY_SPINNER_SIZE,
    OVERLAY_SPINNER_WIDTH,
    OVERLAY_BAR_WIDTH,
    OVERLAY_BAR_HEIGHT,
)


class AnalysisOverlay(ctk.CTkFrame):
    """Overlay that blocks interaction and shows analysis progress."""

    def __init__(self, master, on_cancel: Optional[Callable] = None, **kwargs):
        super().__init__(master, fg_color=OVERLAY_COLORS["bg"], **kwargs)
        self._on_cancel = on_cancel
        self._spinner_start_time = 0.0
        self._spinner_after_id: Optional[str] = None
        self._total_files = 0

        # Build gradient image once (purple → gold)
        self._gradient_img = self._build_gradient(OVERLAY_BAR_WIDTH, OVERLAY_BAR_HEIGHT)

        self._build_ui()

    def _build_gradient(self, width: int, height: int) -> Image.Image:
        """Pre-compute a horizontal gradient image (bar_start → bar_end)."""
        r1, g1, b1 = self._hex_to_rgb(OVERLAY_COLORS["bar_start"])
        r2, g2, b2 = self._hex_to_rgb(OVERLAY_COLORS["bar_end"])
        img = Image.new("RGB", (width, height))
        pixels = img.load()
        for x in range(width):
            t = x / max(width - 1, 1)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            for y in range(height):
                pixels[x, y] = (r, g, b)
        return img

    @staticmethod
    def _hex_to_rgb(hex_color: str):
        h = hex_color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _build_ui(self):
        """Create all child widgets (centered)."""
        # Center container
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        # Spinner canvas — arcs created once, updated via itemconfigure
        size = OVERLAY_SPINNER_SIZE
        self._spinner_canvas = tk.Canvas(
            center,
            width=size,
            height=size,
            bg=OVERLAY_COLORS["bg"],
            highlightthickness=0,
        )
        self._spinner_canvas.pack(pady=(0, 20))
        pad = OVERLAY_SPINNER_WIDTH + 2
        self._spinner_canvas.create_arc(
            pad, pad, size - pad, size - pad,
            start=0, extent=359.9, style="arc",
            outline=OVERLAY_COLORS["spinner_track"],
            width=OVERLAY_SPINNER_WIDTH,
        )
        self._spinner_active_arc = self._spinner_canvas.create_arc(
            pad, pad, size - pad, size - pad,
            start=0, extent=90, style="arc",
            outline=OVERLAY_COLORS["spinner_active"],
            width=OVERLAY_SPINNER_WIDTH,
        )

        # Title
        self._title_label = ctk.CTkLabel(
            center,
            text=t("overlay.title"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=16),
            text_color=OVERLAY_COLORS["text_title"],
        )
        self._title_label.pack(pady=(0, 16))

        # Progress bar canvas
        self._bar_canvas = tk.Canvas(
            center,
            width=OVERLAY_BAR_WIDTH,
            height=OVERLAY_BAR_HEIGHT,
            bg=OVERLAY_COLORS["bg"],
            highlightthickness=0,
        )
        self._bar_canvas.pack(pady=(0, 12))
        # Draw empty track
        self._bar_canvas.create_rectangle(
            0, 0, OVERLAY_BAR_WIDTH, OVERLAY_BAR_HEIGHT,
            fill=OVERLAY_COLORS["bar_track"], outline="",
        )
        self._bar_photo = None  # Keep reference to prevent GC

        # Counter label
        self._counter_label = ctk.CTkLabel(
            center,
            text=t("overlay.counter", completed=0, total=0),
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12),
            text_color=OVERLAY_COLORS["text_counter"],
        )
        self._counter_label.pack(pady=(0, 4))

        # Filename label
        self._filename_label = ctk.CTkLabel(
            center,
            text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=OVERLAY_COLORS["text_filename"],
            wraplength=300,
        )
        self._filename_label.pack(pady=(0, 20))

        # Cancel button
        self._cancel_btn = ctk.CTkButton(
            center,
            text=t("button.cancel"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            width=100,
            height=32,
            corner_radius=6,
            fg_color="transparent",
            hover_color=OVERLAY_COLORS["bar_track"],
            border_width=1,
            border_color=OVERLAY_COLORS["cancel_border"],
            text_color=OVERLAY_COLORS["cancel_text"],
            command=self._on_cancel_click,
        )
        self._cancel_btn.pack()

    def _on_cancel_click(self):
        if self._on_cancel:
            self._on_cancel()

    # ─── Public API ───────────────────────────────────────────────────

    def show(self, total_files: int):
        """Show the overlay and start the spinner."""
        self._total_files = total_files
        self._counter_label.configure(text=t("overlay.counter", completed=0, total=total_files))
        self._filename_label.configure(text="")
        self._draw_progress(0)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self._start_spinner()

    def hide(self):
        """Hide the overlay and stop the spinner."""
        self._stop_spinner()
        self.place_forget()

    def update_progress(self, completed: int, total: int, current_file: str):
        """Update the progress bar, counter, and filename."""
        self._total_files = total
        fraction = completed / total if total > 0 else 0
        self._draw_progress(fraction)
        self._counter_label.configure(text=t("overlay.counter", completed=completed, total=total))
        # Show just filename, not full path
        import os
        self._filename_label.configure(text=os.path.basename(current_file))

    # ─── Spinner ──────────────────────────────────────────────────────

    def _start_spinner(self):
        self._spinner_start_time = time.monotonic()
        self._animate_spinner()

    def _stop_spinner(self):
        if self._spinner_after_id:
            self.after_cancel(self._spinner_after_id)
            self._spinner_after_id = None

    def _animate_spinner(self):
        # Time-based interpolation: 300°/s ≈ 1.2s per revolution
        elapsed = time.monotonic() - self._spinner_start_time
        angle = -(elapsed * 300) % 360
        self._spinner_canvas.itemconfigure(self._spinner_active_arc, start=angle)
        self._spinner_after_id = self.after(16, self._animate_spinner)

    # ─── Progress bar ─────────────────────────────────────────────────

    def _draw_progress(self, fraction: float):
        """Draw the progress bar by cropping the pre-built gradient."""
        c = self._bar_canvas
        c.delete("all")

        # Track background
        c.create_rectangle(
            0, 0, OVERLAY_BAR_WIDTH, OVERLAY_BAR_HEIGHT,
            fill=OVERLAY_COLORS["bar_track"], outline="",
        )

        if fraction <= 0:
            return

        fill_width = max(1, int(OVERLAY_BAR_WIDTH * min(fraction, 1.0)))
        cropped = self._gradient_img.crop((0, 0, fill_width, OVERLAY_BAR_HEIGHT))
        self._bar_photo = ImageTk.PhotoImage(cropped)
        c.create_image(0, 0, anchor="nw", image=self._bar_photo)
