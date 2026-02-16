"""Audio player controls widget."""

import os
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

from .audio_player import AudioPlayer, PlayerState
from .waveform_display import WaveformDisplay
from ..utils.constants import THEME_COLORS, FONT_FAMILY, FONT_SIZES, SAMPLE_RATE


def format_time(seconds: float) -> str:
    """Format seconds as MM:SS."""
    if seconds < 0:
        seconds = 0
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


class PlayerControls(ctk.CTkFrame):
    """
    Audio player controls widget with transport buttons, progress bar, and volume.

    Layout:
    [Prev] [Play/Pause] [Next] | 0:00 / 3:25 | [========o-----------] | Vol [===]
    """

    def __init__(
        self,
        master,
        audio_player: AudioPlayer,
        on_prev: Optional[Callable[[], None]] = None,
        on_next: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color=THEME_COLORS["primary_dark"], **kwargs)

        self._player = audio_player
        self._on_prev = on_prev
        self._on_next = on_next
        self._duration = 0.0
        self._is_seeking = False
        self._update_timer = None
        self._current_track_name: Optional[str] = None

        # Configure player callbacks
        self._player.set_callbacks(
            on_position_changed=self._on_position_changed,
            on_state_changed=self._on_state_changed,
            on_track_ended=self._on_track_ended,
            on_track_loaded=self._on_track_loaded,
        )

        self._setup_ui()
        self._start_position_updates()

    def _setup_ui(self):
        """Set up the controls UI."""
        self.grid_columnconfigure(3, weight=1)  # Progress bar expands

        # Icon sizes
        ICON_SIZE = 20
        BUTTON_SIZE = 36

        # Load icons
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")

        # Create simple text-based buttons if icons aren't available
        self._play_icon = None
        self._pause_icon = None
        self._prev_icon = None
        self._next_icon = None

        # Try to load icons, fall back to text
        try:
            play_path = os.path.join(assets_dir, "play.png")
            pause_path = os.path.join(assets_dir, "pause.png")
            prev_path = os.path.join(assets_dir, "prev.png")
            next_path = os.path.join(assets_dir, "next.png")

            if os.path.exists(play_path):
                self._play_icon = ctk.CTkImage(
                    light_image=Image.open(play_path),
                    dark_image=Image.open(play_path),
                    size=(ICON_SIZE, ICON_SIZE)
                )
            if os.path.exists(pause_path):
                self._pause_icon = ctk.CTkImage(
                    light_image=Image.open(pause_path),
                    dark_image=Image.open(pause_path),
                    size=(ICON_SIZE, ICON_SIZE)
                )
            if os.path.exists(prev_path):
                self._prev_icon = ctk.CTkImage(
                    light_image=Image.open(prev_path),
                    dark_image=Image.open(prev_path),
                    size=(ICON_SIZE, ICON_SIZE)
                )
            if os.path.exists(next_path):
                self._next_icon = ctk.CTkImage(
                    light_image=Image.open(next_path),
                    dark_image=Image.open(next_path),
                    size=(ICON_SIZE, ICON_SIZE)
                )
        except Exception:
            pass

        # Transport controls frame
        transport_frame = ctk.CTkFrame(self, fg_color="transparent")
        transport_frame.grid(row=0, column=0, padx=(12, 8), pady=8)

        # Previous button
        self._prev_btn = ctk.CTkButton(
            transport_frame,
            text="" if self._prev_icon else "⏮",
            image=self._prev_icon,
            command=self._on_prev_click,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            corner_radius=8,
            fg_color="transparent",
            hover_color=THEME_COLORS["bg_elevated"],
            text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(size=16),
        )
        self._prev_btn._canvas.configure(takefocus=False)
        self._prev_btn.grid(row=0, column=0, padx=2)

        # Play/Pause button
        self._play_btn = ctk.CTkButton(
            transport_frame,
            text="" if self._play_icon else "▶",
            image=self._play_icon,
            command=self._on_play_click,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            corner_radius=8,
            fg_color=THEME_COLORS["bg_elevated"],
            hover_color=THEME_COLORS["primary"],
            text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(size=16),
        )
        self._play_btn._canvas.configure(takefocus=False)
        self._play_btn.grid(row=0, column=1, padx=2)

        # Next button
        self._next_btn = ctk.CTkButton(
            transport_frame,
            text="" if self._next_icon else "⏭",
            image=self._next_icon,
            command=self._on_next_click,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            corner_radius=8,
            fg_color="transparent",
            hover_color=THEME_COLORS["bg_elevated"],
            text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(size=16),
        )
        self._next_btn._canvas.configure(takefocus=False)
        self._next_btn.grid(row=0, column=2, padx=2)

        # Time display
        self._time_label = ctk.CTkLabel(
            self,
            text="0:00 / 0:00",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_primary"],
            width=90,
        )
        self._time_label.grid(row=0, column=1, padx=8, pady=8)

        # Waveform display (replaces progress bar)
        self._waveform = WaveformDisplay(
            self,
            on_seek=self._on_waveform_seek,
        )
        self._waveform.grid(row=0, column=3, sticky="ew", padx=8, pady=8)

        # Volume controls
        volume_frame = ctk.CTkFrame(self, fg_color="transparent")
        volume_frame.grid(row=0, column=4, padx=(8, 12), pady=8)

        # Volume icons (programmatic)
        from .icons import icon_volume_high, icon_volume_low, icon_volume_mute
        self._vol_high_icon = icon_volume_high(14)
        self._vol_low_icon = icon_volume_low(14)
        self._vol_mute_icon = icon_volume_mute(14)

        # Volume icon label
        self._volume_label = ctk.CTkLabel(
            volume_frame,
            text="",
            image=self._vol_high_icon,
            width=24,
        )
        self._volume_label.grid(row=0, column=0, padx=(0, 4))

        # Volume slider
        self._volume_slider = ctk.CTkSlider(
            volume_frame,
            from_=0,
            to=1,
            width=80,
            height=16,
            button_color=THEME_COLORS["text_primary"],
            button_hover_color=THEME_COLORS["accent"],
            progress_color=THEME_COLORS["accent"],
            fg_color=THEME_COLORS["primary_muted"],
            command=self._on_volume_change,
        )
        self._volume_slider._canvas.configure(takefocus=False)
        self._volume_slider.grid(row=0, column=1)
        self._volume_slider.set(1.0)

    def _on_prev_click(self):
        """Handle previous button click."""
        if self._on_prev:
            self._on_prev()

    def _on_play_click(self):
        """Handle play/pause button click."""
        self._player.toggle_play_pause()

    def _on_next_click(self):
        """Handle next button click."""
        if self._on_next:
            self._on_next()

    def _on_volume_change(self, value: float):
        """Handle volume slider change."""
        self._player.set_volume(value)
        # Update volume icon
        if value == 0:
            self._volume_label.configure(image=self._vol_mute_icon)
        elif value < 0.5:
            self._volume_label.configure(image=self._vol_low_icon)
        else:
            self._volume_label.configure(image=self._vol_high_icon)

    def _on_waveform_seek(self, position_seconds: float):
        """Handle seek from waveform display."""
        if self._duration <= 0:
            return

        self._is_seeking = True

        # Seek in player
        self._player.seek(position_seconds)

        # Update time display
        self._update_time_display(position_seconds)

        self._is_seeking = False

    def _on_position_changed(self, position: float):
        """Handle position change from player."""
        if not self._is_seeking:
            self._update_time_display(position)
            if self._duration > 0:
                self._waveform.set_position(position / self._duration)

    def _on_state_changed(self, state: PlayerState):
        """Handle state change from player."""
        if state == PlayerState.PLAYING:
            if self._pause_icon:
                self._play_btn.configure(image=self._pause_icon, text="")
            else:
                self._play_btn.configure(text="⏸")
            # Restart position update timer when playback starts
            if self._update_timer is None:
                self._update_position()
        else:
            if self._play_icon:
                self._play_btn.configure(image=self._play_icon, text="")
            else:
                self._play_btn.configure(text="▶")

        # Update button state based on loading
        if state == PlayerState.LOADING:
            self._play_btn.configure(state="disabled")
        else:
            self._play_btn.configure(state="normal")

    def _on_track_ended(self):
        """Handle track end - auto-advance to next."""
        if self._on_next:
            self._on_next()

    def _on_track_loaded(self, duration: float):
        """Handle track loaded."""
        self._duration = duration
        self._update_time_display(0)

        # Pass audio samples to waveform display
        samples = self._player.get_samples()
        if samples is not None:
            self._waveform.set_audio_data(samples, SAMPLE_RATE)

    def _update_time_display(self, position: float):
        """Update the time display label."""
        current = format_time(position)
        total = format_time(self._duration)
        self._time_label.configure(text=f"{current} / {total}")

    def _start_position_updates(self):
        """Start periodic position updates while playing."""
        self._update_position()

    def _update_position(self):
        """Periodically update position display."""
        state = self._player.get_state()

        if state == PlayerState.PLAYING and not self._is_seeking:
            position = self._player.get_position()
            self._update_time_display(position)
            if self._duration > 0:
                self._waveform.set_position(position / self._duration)

            # Only schedule next update while playing (100ms = 10 updates/second)
            self._update_timer = self.after(100, self._update_position)
        else:
            # Stop scheduling updates when not playing - saves CPU
            self._update_timer = None

    def update_track_info(self, filepath: str, filename: str):
        """Update the displayed track information."""
        self._current_track_name = filename

    def reset(self):
        """Reset the controls to initial state."""
        self._duration = 0.0
        self._waveform.clear()
        self._update_time_display(0)
        self._on_state_changed(PlayerState.STOPPED)

    def cleanup(self):
        """Clean up resources."""
        if self._update_timer:
            self.after_cancel(self._update_timer)
            self._update_timer = None
        self._waveform.cleanup()
