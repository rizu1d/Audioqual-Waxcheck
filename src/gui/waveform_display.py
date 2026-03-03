"""DJ-style waveform display with playhead and seeking."""

import threading
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk
import numpy as np
from PIL import Image, ImageDraw

from ..utils.constants import THEME_COLORS, SAMPLE_RATE


class WaveformDisplay(ctk.CTkFrame):
    """
    DJ-style waveform display showing amplitude bars.

    Features:
    - Amplitude bars above/below center line
    - Played portion in light color, unplayed in dark
    - Gold playhead indicator
    - Click/drag to seek
    """

    # Display dimensions
    HEIGHT = 50
    BAR_WIDTH = 1

    # Colors — matched to player bar background
    COLOR_BG = THEME_COLORS["purple_deep"]
    COLOR_UNPLAYED = "#32294c"                    # rgba(121,105,168,0.18) on purple_deep
    COLOR_PLAYED = THEME_COLORS["primary"]        # Purple (#7969A8)
    COLOR_PLAYHEAD = THEME_COLORS["text_primary"] # Cream (#F3F1E5)

    def __init__(
        self,
        master,
        on_seek: Optional[Callable[[float], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", height=self.HEIGHT, **kwargs)

        self._on_seek = on_seek
        self._samples: Optional[np.ndarray] = None
        self._peaks: Optional[np.ndarray] = None
        self._unplayed_image: Optional[Image.Image] = None
        self._played_image: Optional[Image.Image] = None
        self._current_position: float = 0.0
        self._duration: float = 0.0
        self._sample_rate: int = SAMPLE_RATE

        # Threading
        self._render_id: int = 0
        self._render_thread: Optional[threading.Thread] = None
        self._resize_timer = None
        self._last_width: int = 0

        # UI state
        self._is_seeking: bool = False
        self._photo_image = None
        self._last_playhead_x: int = 0  # Track last playhead position for skip optimization

        self._setup_ui()

    def _setup_ui(self):
        """Set up the display UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Image label for waveform display
        self._image_label = ctk.CTkLabel(
            self,
            text="",
            image=None,
            fg_color=self.COLOR_BG,
            corner_radius=0,
            height=self.HEIGHT,
        )
        self._image_label.grid(row=0, column=0, sticky="ew")

        # Bind mouse events for seeking
        self._image_label.bind("<Button-1>", self._on_click)
        self._image_label.bind("<B1-Motion>", self._on_drag)
        self._image_label.bind("<ButtonRelease-1>", self._on_release)

        # Bind resize
        self._image_label.bind("<Configure>", self._on_resize)

    def set_audio_data(self, samples: np.ndarray, sample_rate: int):
        """
        Set the audio data to visualize.

        Args:
            samples: Audio samples (1D numpy array)
            sample_rate: Sample rate in Hz
        """
        self._samples = samples
        self._sample_rate = sample_rate
        self._duration = len(samples) / sample_rate if sample_rate > 0 else 0.0
        self._current_position = 0.0
        self._peaks = None
        self._unplayed_image = None
        self._played_image = None

        # Start rendering
        self._start_render()

    def set_position(self, ratio: float):
        """
        Update the playhead position.

        Args:
            ratio: Position ratio (0.0 to 1.0)
        """
        self._current_position = max(0.0, min(1.0, ratio))

        # Update display if we have pre-rendered images
        if self._unplayed_image is not None and not self._is_seeking:
            # Skip update if playhead moved less than 2 pixels (reduces ~10 updates/s to ~2-3/s)
            if self._last_width > 0:
                new_x = int(self._current_position * self._last_width)
                if abs(new_x - self._last_playhead_x) < 2:
                    return
            self._update_display()

    def clear(self):
        """Clear the waveform display."""
        self._samples = None
        self._peaks = None
        self._unplayed_image = None
        self._played_image = None
        self._current_position = 0.0
        self._duration = 0.0
        self._photo_image = None

        # Show empty state
        self._image_label.configure(image=None)

    def _on_resize(self, event):
        """Handle widget resize with debouncing."""
        if self._samples is None:
            return

        new_width = event.width

        # Ignore small changes
        if abs(new_width - self._last_width) < 20:
            return

        # Cancel previous timer
        if self._resize_timer:
            self.after_cancel(self._resize_timer)

        # Debounce: wait 400ms before re-rendering
        self._resize_timer = self.after(400, self._handle_resize)

    def _handle_resize(self):
        """Re-render waveform at new size."""
        self._resize_timer = None

        if self._samples is None:
            return

        # Clear cached data to force re-render
        self._peaks = None
        self._unplayed_image = None
        self._played_image = None
        self._start_render()

    def _start_render(self):
        """Start background render of waveform."""
        if self._samples is None:
            return

        # Get current width
        width = self._image_label.winfo_width()
        if width < 10:
            # Widget not yet sized, retry later
            self.after(50, self._start_render)
            return

        self._last_width = width

        # Increment render ID to cancel stale renders
        self._render_id += 1
        current_render_id = self._render_id

        # Start background thread
        self._render_thread = threading.Thread(
            target=self._render_in_background,
            args=(current_render_id, width, self.HEIGHT),
            daemon=True,
        )
        self._render_thread.start()

    def _render_in_background(self, render_id: int, width: int, height: int):
        """Render waveform in background thread."""
        if render_id != self._render_id or self._samples is None:
            return

        try:
            # Compute peaks
            num_bars = width // self.BAR_WIDTH
            peaks = self._compute_peaks(self._samples, num_bars)

            if render_id != self._render_id:
                return

            # Pre-render both unplayed and played images
            unplayed_image = self._create_waveform_image(peaks, width, height, self.COLOR_UNPLAYED)

            if render_id != self._render_id:
                return

            played_image = self._create_waveform_image(peaks, width, height, self.COLOR_PLAYED)

            if render_id != self._render_id:
                return

            # Store results and update display on main thread
            from ..utils.tk_utils import schedule_callback_from_thread
            schedule_callback_from_thread(self, self._on_render_complete, render_id, peaks, unplayed_image, played_image)

        except Exception as e:
            print(f"Error rendering waveform: {e}")

    def _compute_peaks(self, samples: np.ndarray, num_points: int) -> np.ndarray:
        """
        Downsample audio to RMS values for visualization.

        Args:
            samples: Audio samples
            num_points: Number of peak values to compute

        Returns:
            Normalized peak array (0.0 to 1.0) with power curve applied
        """
        if num_points <= 0:
            return np.array([])

        # Ensure we have at least one sample per point
        num_points = min(num_points, len(samples))
        chunk_size = len(samples) // num_points

        if chunk_size <= 0:
            return np.zeros(num_points)

        # Vectorized RMS computation
        trimmed = samples[:num_points * chunk_size]
        chunks = trimmed.reshape(num_points, chunk_size)
        peaks = np.sqrt(np.mean(chunks ** 2, axis=1))

        # Normalize to 0-1
        max_peak = np.max(peaks)
        if max_peak > 0:
            peaks = peaks / max_peak

        # Power curve for dynamic range expansion
        peaks = peaks ** 1.5

        return peaks

    def _create_waveform_image(self, peaks: np.ndarray, width: int, height: int, color: str) -> Image.Image:
        """
        Create a full waveform image in a single color.

        Args:
            peaks: Normalized peak array
            width: Image width
            height: Image height
            color: Bar color

        Returns:
            PIL Image with waveform
        """
        image = Image.new('RGB', (width, height), self.COLOR_BG)
        draw = ImageDraw.Draw(image)

        center_y = height // 2
        max_bar_height = int(height * 0.45)  # 45% of half-height on each side

        for i in range(min(len(peaks), width)):
            bar_h = max(1, int(peaks[i] * max_bar_height))
            # With BAR_WIDTH=1, draw vertical lines
            draw.line(
                [(i, center_y - bar_h), (i, center_y + bar_h)],
                fill=color,
            )

        return image

    def _on_render_complete(self, render_id: int, peaks: np.ndarray, unplayed_image: Image.Image, played_image: Image.Image):
        """Handle render completion on main thread."""
        if render_id != self._render_id:
            return

        self._peaks = peaks
        self._unplayed_image = unplayed_image
        self._played_image = played_image
        self._update_display()

    def _update_display(self):
        """Update the display with current position using pre-rendered images."""
        if self._unplayed_image is None or self._played_image is None:
            return

        try:
            width = self._unplayed_image.width
            height = self._unplayed_image.height

            # Calculate playhead position
            playhead_x = int(self._current_position * width)

            # Store for skip optimization
            self._last_playhead_x = playhead_x

            # Composite: start with unplayed, paste played portion
            display = self._unplayed_image.copy()

            if playhead_x > 0:
                played_strip = self._played_image.crop((0, 0, playhead_x, height))
                display.paste(played_strip, (0, 0))

            # Draw playhead line
            if 0 <= playhead_x < width:
                draw = ImageDraw.Draw(display)
                draw.line(
                    [(playhead_x, 0), (playhead_x, height - 1)],
                    fill=self.COLOR_PLAYHEAD,
                    width=2,
                )

            # Update CTkImage (release old one first to reduce peak memory)
            old = self._photo_image
            self._photo_image = ctk.CTkImage(
                light_image=display,
                dark_image=display,
                size=(display.width, display.height),
            )
            self._image_label.configure(image=self._photo_image)
            del old

        except tk.TclError:
            # Widget was destroyed
            pass

    def _on_click(self, event):
        """Handle mouse click for seeking."""
        self._is_seeking = True
        self._seek_to_event(event)

    def _on_drag(self, event):
        """Handle mouse drag for seeking."""
        if self._is_seeking:
            self._seek_to_event(event)

    def _on_release(self, event):
        """Handle mouse release after seeking."""
        if self._is_seeking:
            self._seek_to_event(event)
            self._is_seeking = False

    def _seek_to_event(self, event):
        """Seek to position based on mouse event."""
        if self._duration <= 0:
            return

        width = self._image_label.winfo_width()
        if width <= 0:
            return

        # Calculate ratio from click position
        x = max(0, min(event.x, width))
        ratio = x / width

        # Update position immediately for responsiveness
        self._current_position = ratio
        self._update_display()

        # Call seek callback
        if self._on_seek:
            position_seconds = ratio * self._duration
            self._on_seek(position_seconds)

    def cleanup(self):
        """Clean up resources."""
        if self._resize_timer:
            self.after_cancel(self._resize_timer)
            self._resize_timer = None
