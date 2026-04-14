"""Floating popup that explains why a file received its quality verdict."""

import tkinter as tk
from typing import Optional

import customtkinter as ctk

from ..core.analyzer import AnalysisResult
from ..utils.constants import (
    FONT_FAMILY, FONT_FAMILY_MONO, FONT_SIZES,
    THEME_COLORS, QUALITY_LEVELS, POPUP_WIDTH,
    STATUS_TRANSCODE, STATUS_LOSSLESS,
    get_quality_level,
)
from .icons import icon_quality_dot
from ..utils.i18n import t, t_quality_level


# ---------- singleton click-outside watcher ----------
# A single bind_all handler shared by ALL popup instances.
# Prevents handler accumulation (each popup open/close was adding
# a new bind_all that was never removed).
_active_popup = None
_click_watcher_installed = False


def _on_global_click(event):
    """Close the active popup if click is outside it."""
    if _active_popup is None or not _active_popup._listening:
        return
    try:
        top = event.widget.winfo_toplevel()
        if top != _active_popup:
            _active_popup.close()
    except (tk.TclError, AttributeError):
        if _active_popup:
            _active_popup.close()


# ---------- quality-to-numeric helpers ----------

_QUALITY_TO_BITRATE = {
    "lossless": 1411,
    "320kbps": 320,
    "256kbps": 256,
    "192kbps": 192,
    "160kbps": 160,
    "128kbps": 128,
    "96kbps": 96,
    "low": 64,
}

_LOSSLESS_FORMATS = {"FLAC", "WAV", "AIFF"}


def _detected_bitrate_int(detected_quality: str) -> int:
    """Convert a detected_quality string like '128kbps' to an integer."""
    return _QUALITY_TO_BITRATE.get(detected_quality, 0)


def _format_cutoff(cutoff_khz: float) -> str:
    """Format cutoff for display, removing trailing zeros."""
    if cutoff_khz == int(cutoff_khz):
        return f"{int(cutoff_khz)}.0 kHz"
    return f"{cutoff_khz:.1f} kHz"


# ---------- case determination ----------

def _determine_case(result: AnalysisResult) -> int:
    """Return case number (1-8) based on analysis result."""
    level = get_quality_level(result.cutoff_frequency_khz, result.status)
    is_lossless_fmt = result.format.upper() in _LOSSLESS_FORMATS
    is_transcode = result.status == STATUS_TRANSCODE

    if level == "bajo":
        if is_transcode or _has_bitrate_discrepancy(result):
            return 1  # Transcode severo
        return 2      # Baja calidad honesta

    if level == "medio":
        if is_transcode or _has_bitrate_discrepancy(result):
            return 3  # Transcode medio
        return 4      # Calidad media honesta

    if level == "bueno":
        if is_lossless_fmt:
            return 6  # Lossless con posible transcode
        cutoff = result.cutoff_frequency_khz
        # For 320 kbps declared, distinguish by cutoff range
        if result.declared_bitrate and result.declared_bitrate >= 320:
            if 19.0 <= cutoff < 20.0:
                return 10  # Bueno, casi 320 nativo (19-19.99 kHz)
            if cutoff < 19.0:
                return 9   # Bueno, calidad ~256 (18-18.99 kHz)
        # Other bitrate discrepancies
        detected_kbps = _detected_bitrate_int(result.detected_quality)
        if (result.declared_bitrate and detected_kbps
                and result.declared_bitrate > detected_kbps):
            return 9       # Bueno, bitrate real < declarado
        return 5      # Lossy verificado

    # excelente
    if is_lossless_fmt:
        return 7      # Lossless verificado
    return 8          # Lossy alta calidad (MP3 320)


def _has_bitrate_discrepancy(result: AnalysisResult) -> bool:
    """Check if declared bitrate is significantly higher than detected."""
    if result.declared_bitrate is None:
        return False
    detected_kbps = _detected_bitrate_int(result.detected_quality)
    if detected_kbps == 0:
        return False
    return result.declared_bitrate > detected_kbps * 1.5 + 40


# ---------- explanation text ----------

def _build_explanation(result: AnalysisResult, case: int) -> str:
    """Build explanation text for the given case."""
    fmt = result.format
    declared = f"{result.declared_bitrate} kbps" if result.declared_bitrate else t("popup.unknown_bitrate")
    cutoff = _format_cutoff(result.cutoff_frequency_khz)
    real_kbps = _detected_bitrate_int(result.detected_quality)
    real = f"{real_kbps} kbps" if real_kbps and real_kbps < 1411 else "Lossless"

    key = f"popup.explanation.{case}"
    return t(key, fmt=fmt, declared=declared, cutoff=cutoff, real=real)


# ---------- verified / comparison info ----------

_CASE_SHOWS_COMPARISON = {1, 3, 6}

def _get_verified_message(case: int) -> tuple:
    """Return (title, subtitle) for verified cases, translated."""
    msg = t(f"popup.verified.{case}")
    if isinstance(msg, list) and len(msg) == 2:
        return tuple(msg)
    default = t("popup.verified_default")
    return (default, "")


# ---------- popup widget ----------

class QualityPopup(ctk.CTkToplevel):
    """Floating popup that explains why a file received its quality level."""

    def __init__(
        self,
        master,
        result: AnalysisResult,
        anchor_widget,
        on_close=None,
    ):
        super().__init__(master)

        self._result = result
        self._on_close = on_close
        self._listening = False

        # Determine case and quality level
        self._case = _determine_case(result)
        self._level = get_quality_level(result.cutoff_frequency_khz, result.status)
        self._colors = QUALITY_LEVELS[self._level]

        # Animation
        self._fade_steps = 8
        self._fade_interval = 20  # ms per step
        self._fading_out = False

        # Window setup — borderless floating popup
        self.overrideredirect(True)
        self.configure(fg_color=THEME_COLORS["bg_secondary"])
        self.transient(master)  # Child of main window — prevents going behind on macOS
        self.resizable(False, False)
        self.attributes("-alpha", 0.0)  # Start invisible for fade-in

        self._build_ui()

        # Position near anchor widget
        self.update_idletasks()
        self._position_near(anchor_widget)

        # Fade in, then bind close handlers
        self._fade_in(step=1)

        # Close on Escape
        self.bind("<Escape>", lambda e: self.close())

    def _build_ui(self):
        """Build all popup widgets."""
        result = self._result
        level = self._level
        colors = self._colors

        # Container with border simulation (outer frame)
        border_frame = ctk.CTkFrame(
            self,
            fg_color="#1a172a",  # border color
            corner_radius=14,
        )
        border_frame.pack(fill="both", expand=True, padx=1, pady=1)

        inner = ctk.CTkFrame(
            border_frame,
            fg_color=THEME_COLORS["bg_secondary"],
            corner_radius=13,
        )
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        # 1. Top accent bar (3px)
        accent = ctk.CTkFrame(
            inner, fg_color=colors["text"], height=3, corner_radius=0,
        )
        accent.pack(fill="x", side="top")
        accent.pack_propagate(False)

        # Content area
        content = ctk.CTkFrame(inner, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=(16, 14))

        # 2. Header: badge + filename
        self._build_header(content, result, level, colors)

        # 3. Explanation text
        explanation = _build_explanation(result, self._case)
        exp_label = ctk.CTkLabel(
            content,
            text=explanation,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color="#b8b5a8",
            wraplength=POPUP_WIDTH - 48,
            justify="left",
            anchor="nw",
        )
        exp_label.pack(fill="x", pady=(0, 16))

        # 4. Data grid (2x2)
        self._build_data_grid(content, result, level, colors)

        # 5. Comparison bar or check
        if self._case in _CASE_SHOWS_COMPARISON:
            self._build_comparison(content, result, level, colors)
        else:
            self._build_verified(content, level, colors)

        # 6. Footer hint
        footer = ctk.CTkLabel(
            content,
            text=t("popup.close_hint"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color="#45454f",
        )
        footer.pack(pady=(6, 0))

    def _build_header(self, parent, result, level, colors):
        """Build header row with mini badge + filename."""
        header = ctk.CTkFrame(parent, fg_color="transparent", height=30)
        header.pack(fill="x", pady=(0, 14))
        header.pack_propagate(False)

        # Mini badge
        badge = ctk.CTkFrame(
            header,
            fg_color=colors["bg"],
            border_color=colors["border"],
            border_width=1,
            corner_radius=12,
            height=24,
        )
        badge.pack(side="left", padx=(0, 10))
        badge.pack_propagate(False)

        badge_text = t_quality_level(level)
        badge.configure(width=len(badge_text) * 6 + 35)

        badge_label = ctk.CTkLabel(
            badge,
            text=f"  {badge_text}",
            image=icon_quality_dot(7, colors["dot"]),
            compound="left",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=colors["text"],
            fg_color="transparent",
        )
        badge_label.place(x=10, rely=0.5, anchor="w")

        # Filename
        max_chars = 35
        name = result.filename
        if len(name) > max_chars:
            name = name[:max_chars - 3] + "..."
        fname = ctk.CTkLabel(
            header,
            text=name,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=THEME_COLORS["text_primary"],
            anchor="w",
        )
        fname.pack(side="left", fill="x", expand=True)

    def _build_data_grid(self, parent, result, level, colors):
        """Build 2x2 grid of technical data."""
        # Outer frame with gap-color background
        grid_bg = ctk.CTkFrame(
            parent, fg_color="#12101c", corner_radius=8,
        )
        grid_bg.pack(fill="x", pady=(0, 14))

        grid_bg.grid_columnconfigure(0, weight=1)
        grid_bg.grid_columnconfigure(1, weight=1)

        real_kbps = _detected_bitrate_int(result.detected_quality)
        is_lossless = result.detected_quality == "lossless"
        has_discrepancy = self._case in _CASE_SHOWS_COMPARISON

        cells = [
            (t("popup.grid.declared_bitrate"), f"{result.declared_bitrate} kbps" if result.declared_bitrate else "-", None),
            (t("popup.grid.actual_bitrate"), "Lossless" if is_lossless else f"{real_kbps} kbps",
             colors["text"] if is_lossless else ("#E85555" if has_discrepancy else "#6BCB77")),
            (t("popup.grid.cutoff_frequency"), _format_cutoff(result.cutoff_frequency_khz), None),
            (t("popup.grid.format"), result.format, None),
        ]

        for i, (label, value, value_color) in enumerate(cells):
            row, col = divmod(i, 2)
            cell = ctk.CTkFrame(
                grid_bg, fg_color=THEME_COLORS["bg_secondary"], corner_radius=0,
            )
            padx_l = 2 if col == 1 else 0
            padx_r = 0
            pady_t = 2 if row == 1 else 0
            pady_b = 0
            cell.grid(row=row, column=col, sticky="nsew", padx=(padx_l, padx_r), pady=(pady_t, pady_b))

            lbl = ctk.CTkLabel(
                cell,
                text=label,
                font=ctk.CTkFont(family=FONT_FAMILY, size=9, weight="bold"),
                text_color=THEME_COLORS["text_secondary"],
                anchor="w",
            )
            lbl.pack(anchor="w", padx=14, pady=(10, 2))

            val = ctk.CTkLabel(
                cell,
                text=value,
                font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=13),
                text_color=value_color or THEME_COLORS["text_primary"],
                anchor="w",
            )
            val.pack(anchor="w", padx=14, pady=(0, 10))

    def _build_comparison(self, parent, result, level, colors):
        """Build 'Declarado vs Real' comparison bars."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=(0, 4))

        is_lossless_fmt = result.format.upper() in _LOSSLESS_FORMATS

        # Label
        title_text = t("popup.comparison.expected_vs_actual") if is_lossless_fmt else t("popup.comparison.declared_vs_actual")
        title = ctk.CTkLabel(
            frame,
            text=title_text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=9, weight="bold"),
            text_color=THEME_COLORS["text_secondary"],
            anchor="w",
        )
        title.pack(anchor="w", pady=(0, 8))

        # Determine values
        if is_lossless_fmt:
            declared_val = result.declared_bitrate or 1411
            declared_label = t("popup.comparison.expected")
        else:
            declared_val = result.declared_bitrate or 320
            declared_label = t("popup.comparison.declared")

        real_kbps = _detected_bitrate_int(result.detected_quality)
        if real_kbps == 0:
            real_kbps = 64

        max_val = max(declared_val, real_kbps, 1)
        declared_pct = declared_val / max_val
        real_pct = real_kbps / max_val

        bar_width = POPUP_WIDTH - 48 - 60 - 65 - 20  # available track width

        # Declared row
        self._build_bar_row(
            frame, declared_label,
            f"{declared_val} kbps",
            declared_pct, bar_width,
            "#3d3a4a",  # muted cream-ish bar
        )

        # Real row
        self._build_bar_row(
            frame, t("popup.comparison.actual"),
            f"{real_kbps} kbps",
            real_pct, bar_width,
            colors["text"],
        )

    def _build_bar_row(self, parent, label, value_text, fill_pct, track_width, fill_color):
        """Build a single comparison bar row."""
        row = ctk.CTkFrame(parent, fg_color="transparent", height=20)
        row.pack(fill="x", pady=(0, 4))
        row.pack_propagate(False)

        # Row label (right-aligned)
        lbl = ctk.CTkLabel(
            row,
            text=label,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=THEME_COLORS["text_secondary"],
            width=60,
            anchor="e",
        )
        lbl.pack(side="left", padx=(0, 10))

        # Track container
        track = ctk.CTkFrame(
            row,
            fg_color="#15131f",
            corner_radius=3,
            height=6,
        )
        track.pack(side="left", fill="x", expand=True, pady=7)
        track.pack_propagate(False)

        # Fill bar
        fill_width = max(int(fill_pct * track_width), 4)
        fill = ctk.CTkFrame(
            track,
            fg_color=fill_color,
            corner_radius=3,
            height=6,
            width=fill_width,
        )
        fill.place(x=0, y=0, relheight=1.0)

        # Value text
        val = ctk.CTkLabel(
            row,
            text=value_text,
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=10),
            text_color=THEME_COLORS["text_secondary"],
            width=65,
            anchor="w",
        )
        val.pack(side="left", padx=(10, 0))

    def _build_verified(self, parent, level, colors):
        """Build verification check indicator."""
        msg = _get_verified_message(self._case)

        frame = ctk.CTkFrame(
            parent,
            fg_color="#0f0e18",
            border_color="#1a172a",
            border_width=1,
            corner_radius=8,
        )
        frame.pack(fill="x", pady=(0, 4))

        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        # Check circle
        circle = ctk.CTkFrame(
            inner,
            fg_color=colors["bg"],
            border_color=colors["border"],
            border_width=1,
            corner_radius=14,
            width=28,
            height=28,
        )
        circle.pack(side="left", padx=(0, 10))
        circle.pack_propagate(False)

        check_label = ctk.CTkLabel(
            circle,
            text="\u2713",  # Unicode checkmark
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color=colors["text"],
            fg_color="transparent",
        )
        check_label.place(relx=0.5, rely=0.5, anchor="center")

        # Text
        text = ctk.CTkLabel(
            inner,
            text=f"{msg[0]}  —  {msg[1]}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color="#9590a0",
            wraplength=POPUP_WIDTH - 120,
            justify="left",
            anchor="w",
        )
        text.pack(side="left", fill="x", expand=True)

    # ---------- positioning ----------

    def _position_near(self, anchor):
        """Position popup near the anchor widget."""
        try:
            ax = anchor.winfo_rootx()
            ay = anchor.winfo_rooty()
            ah = anchor.winfo_height()
        except tk.TclError:
            ax, ay, ah = 100, 100, 24

        popup_w = POPUP_WIDTH + 4  # +border
        popup_h = self.winfo_reqheight()

        # Screen dimensions
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        # Default: below the badge
        x = ax
        y = ay + ah + 8

        # If popup goes below screen, open above
        if y + popup_h > screen_h - 40:
            y = ay - popup_h - 8

        # If popup goes off right edge, shift left
        if x + popup_w > screen_w - 20:
            x = screen_w - popup_w - 20

        # Ensure not off-screen left
        x = max(x, 10)
        y = max(y, 10)

        self.geometry(f"{popup_w}x{popup_h}+{x}+{y}")

    # ---------- animation ----------

    def _fade_in(self, step: int):
        """Animate opacity from 0 to 1."""
        if step > self._fade_steps:
            self.attributes("-alpha", 1.0)
            # Bind close handlers after fade-in completes
            self.after(50, self._bind_click_outside)
            return
        try:
            self.attributes("-alpha", step / self._fade_steps)
            self.after(self._fade_interval, self._fade_in, step + 1)
        except tk.TclError:
            pass

    def _fade_out(self, step: int):
        """Animate opacity from 1 to 0, then destroy."""
        if step < 0:
            try:
                self.destroy()
            except tk.TclError:
                pass
            return
        try:
            self.attributes("-alpha", step / self._fade_steps)
            self.after(self._fade_interval, self._fade_out, step - 1)
        except tk.TclError:
            pass

    # ---------- close logic ----------

    def _bind_click_outside(self):
        """Bind mechanisms to detect clicks outside the popup."""
        global _active_popup, _click_watcher_installed
        self._listening = True
        _active_popup = self
        # Install the singleton click watcher once (never removed, near-zero
        # overhead when no popup is active — just checks _active_popup is None).
        if not _click_watcher_installed:
            self.master.bind_all("<Button-1>", _on_global_click, add="+")
            _click_watcher_installed = True
        # Fallback for macOS: close when this popup window is deactivated
        self.bind("<Deactivate>", lambda e: self.after(50, self.close))

    def close(self):
        """Close the popup and clean up."""
        global _active_popup
        if not self._listening or self._fading_out:
            return
        self._listening = False
        _active_popup = None
        self._fading_out = True

        if self._on_close:
            self._on_close()

        # Fade out then destroy
        self._fade_out(self._fade_steps - 1)
