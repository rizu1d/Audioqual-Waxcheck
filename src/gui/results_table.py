"""Results table for displaying analysis results with quality level badges."""

import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

try:
    from tkinterdnd2 import DND_FILES, COPY
    HAS_DND = True
except ImportError:
    HAS_DND = False

from ..core.analyzer import AnalysisResult
from ..utils.constants import (
    STATUS_COLORS, THEME_COLORS, FONT_FAMILY, FONT_FAMILY_MONO, FONT_SIZES,
    QUALITY_LEVELS, get_quality_level,
    STATUS_PENDING, STATUS_ANALYZING, STATUS_ERROR,
)
from ..utils.file_utils import format_duration
from .icons import icon_search, icon_close, icon_quality_dot
from .quality_popup import QualityPopup
from ..utils.i18n import t, t_status, t_quality_level


SelectionCallback = Callable[[Optional[AnalysisResult]], None]

# Columns that use monospace font (numeric data)
_MONO_COLUMNS = {"duration", "declared_bitrate", "cutoff_frequency", "detected_quality"}


def _placeholder_result() -> AnalysisResult:
    """Empty result used to construct recycled pool rows before they are bound."""
    return AnalysisResult(
        filepath="", filename="", format="", duration=0.0,
        declared_bitrate=None, detected_quality="", cutoff_frequency_khz=0.0,
        status=STATUS_PENDING, confidence=0.0, details="",
    )


class QualityBadge(ctk.CTkFrame):
    """Pill-shaped quality badge with colored dot, text, and semi-transparent bg."""

    def __init__(self, master, cutoff_khz: float, status: str = "",
                 on_badge_click: Optional[Callable] = None, **kwargs):
        level = get_quality_level(cutoff_khz, status)
        colors = QUALITY_LEVELS[level]

        super().__init__(
            master,
            fg_color=colors["bg"],
            border_color=colors["border"],
            border_width=1,
            corner_radius=12,
            height=24,
            cursor="hand2",
            **kwargs
        )

        self.pack_propagate(False)
        self._level = level
        self._colors = colors
        self._on_badge_click = on_badge_click

        display_text = t_quality_level(level)
        self.configure(width=self._calculate_width(display_text))

        # Compound label anchored left so dots align vertically across all rows
        self._label = ctk.CTkLabel(
            self,
            text=f"  {display_text}",
            image=icon_quality_dot(7, colors["dot"]),
            compound="left",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=colors["text"],
            fg_color="transparent",
            cursor="hand2",
        )
        self._label.place(x=10, rely=0.5, anchor="w")

        # Badge click bindings (add="+" so row click also fires)
        if on_badge_click:
            self.bind("<Button-1>", self._fire_badge_click, add="+")
            self._label.bind("<Button-1>", self._fire_badge_click, add="+")

        # Hover glow
        self.bind("<Enter>", self._on_hover_enter)
        self.bind("<Leave>", self._on_hover_leave)
        self._label.bind("<Enter>", self._on_hover_enter)
        self._label.bind("<Leave>", self._on_hover_leave)

    def _on_hover_enter(self, event):
        self.configure(
            fg_color=self._colors["bg_hover"],
            border_color=self._colors["border_hover"],
        )

    def _on_hover_leave(self, event):
        self.configure(
            fg_color=self._colors["bg"],
            border_color=self._colors["border"],
        )

    def _fire_badge_click(self, event):
        """Fire the badge click callback."""
        if self._on_badge_click:
            self._on_badge_click(event)

    def _calculate_width(self, text: str) -> int:
        # 10px left + dot(7) + gap(~6) + text + 12px right
        return len(text) * 6 + 35

    def update_quality(self, cutoff_khz: float, status: str = ""):
        """Update badge for new cutoff frequency."""
        level = get_quality_level(cutoff_khz, status)
        if level == self._level:
            return

        colors = QUALITY_LEVELS[level]
        self._level = level
        self._colors = colors
        display_text = t_quality_level(level)

        self.configure(
            fg_color=colors["bg"],
            border_color=colors["border"],
            width=self._calculate_width(display_text),
        )
        self._label.configure(
            text=f"  {display_text}",
            image=icon_quality_dot(7, colors["dot"]),
            text_color=colors["text"],
        )


class ResultRow(ctk.CTkFrame):
    """Single row in the results table."""

    def __init__(
        self,
        master,
        result: AnalysisResult,
        columns: list,
        on_click: Optional[Callable] = None,
        on_release: Optional[Callable] = None,
        on_right_click: Optional[Callable] = None,
        on_badge_click: Optional[Callable] = None,
        on_drag_files: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(
            master,
            fg_color="transparent",
            height=40,
            corner_radius=0,
            **kwargs
        )

        self.result = result
        self.on_click = on_click
        self.on_release = on_release
        self.on_right_click = on_right_click
        self._on_badge_click = on_badge_click
        self._on_drag_files = on_drag_files
        self._selected = False
        # Deduplication: prevent multiple firings per physical click.
        # Separate timestamps because both handlers should fire once per click
        # (badge click should both open popup AND select the row).
        self._last_row_click_time = 0
        self._last_row_release_time = 0
        self._last_badge_click_time = 0
        # Store as mutable list of lists so widths can be updated
        self._columns = [list(col) for col in columns]
        self._cells: Dict[str, ctk.CTkLabel] = {}
        self._cell_frames: Dict[str, ctk.CTkFrame] = {}
        self._badge: Optional[QualityBadge] = None
        self._hover_state = False  # Track current hover state to avoid redundant configure calls

        # Barra lateral de acento (selección)
        self._accent_bar = ctk.CTkFrame(
            self,
            fg_color=THEME_COLORS["row_accent"],
            width=3,
            corner_radius=0,
        )

        # Prevent frame from shrinking
        self.pack_propagate(False)
        self.grid_propagate(False)

        # Create cells for each column with fixed-width container frames
        for i, (col_id, _, width) in enumerate(self._columns):
            # Create container frame with fixed width to clip content
            cell_frame = ctk.CTkFrame(
                self,
                fg_color="transparent",
                width=width,
                height=40,
                corner_radius=0,
            )
            cell_frame.grid(row=0, column=i, sticky="nsew")
            cell_frame.grid_propagate(False)
            cell_frame.pack_propagate(False)
            self._cell_frames[col_id] = cell_frame

            if col_id == "status":
                # Quality badge or text label depending on analysis state
                if result.status in (STATUS_PENDING, STATUS_ANALYZING, STATUS_ERROR):
                    cell = ctk.CTkLabel(
                        cell_frame,
                        text=t_status(result.status),
                        anchor="w",
                        font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["small"]),
                        text_color=STATUS_COLORS.get(result.status, THEME_COLORS["text_muted"]),
                        fg_color="transparent",
                    )
                    cell.place(x=8, rely=0.5, anchor="w")
                    self._cells[col_id] = cell
                    self._badge = None
                else:
                    self._badge = QualityBadge(
                        cell_frame, result.cutoff_frequency_khz, result.status,
                        on_badge_click=self._handle_badge_click,
                    )
                    self._badge.place(x=8, rely=0.5, anchor="w")
            else:
                # Determine font: monospace for numeric data
                if col_id in _MONO_COLUMNS:
                    font = ctk.CTkFont(family=FONT_FAMILY_MONO, size=FONT_SIZES["small"])
                else:
                    font = ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"] - 1)

                # Frequency column gets lavender color
                if col_id == "cutoff_frequency":
                    text_color = THEME_COLORS["freq_glow"]
                else:
                    text_color = THEME_COLORS["text_primary"]

                cell = ctk.CTkLabel(
                    cell_frame,
                    text=self._get_value(col_id, width),
                    anchor="w",
                    font=font,
                    text_color=text_color,
                    fg_color="transparent",
                )
                cell.place(x=8, rely=0.5, anchor="w")
                self._cells[col_id] = cell

        # Configure column weights - filename stretches, rest fixed
        for i, (col_id, _, width) in enumerate(self._columns):
            w = 1 if i == 0 else 0
            self.grid_columnconfigure(i, weight=w, minsize=width)

        # Bind click/hover events to the row
        self.bind("<Button-1>", self._handle_click, add="+")
        self.bind("<ButtonRelease-1>", self._handle_release, add="+")
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        # Right-click binding (Button-2 on macOS, Button-3 on others)
        if sys.platform == "darwin":
            self.bind("<Button-2>", self._handle_right_click, add="+")
        else:
            self.bind("<Button-3>", self._handle_right_click, add="+")

        # Bind click events to all descendants (needed for CTk widgets with internal structure)
        self._bind_click_recursive(self)

        # Register drag-out (export files to Finder/other apps) if tkinterdnd2 is available
        if HAS_DND and self._on_drag_files is not None:
            self._register_drag_source(self)

    def _register_drag_source(self, widget):
        """Register widget and all descendants as a drag source exporting files."""
        try:
            widget.drag_source_register(1, DND_FILES)
            widget.dnd_bind("<<DragInitCmd>>", self._handle_drag_init)
        except Exception:
            return
        for child in widget.winfo_children():
            self._register_drag_source(child)

    def _handle_drag_init(self, event):
        """Provide the file paths to export when a drag-out gesture starts."""
        paths = self._on_drag_files(self) if self._on_drag_files else []
        # Only export files that still exist on disk
        paths = [p for p in paths if p and Path(p).exists()]
        if not paths:
            return None
        return (COPY, DND_FILES, tuple(paths))

    def _get_value(self, col_id: str, width: int) -> str:
        """Get the display value for a column, truncated if necessary."""
        result = self.result
        value = "-"

        if col_id == "filename":
            value = result.filename
        elif col_id == "format":
            value = result.format
        elif col_id == "duration":
            value = format_duration(result.duration) if result.duration > 0 else "-"
        elif col_id == "declared_bitrate":
            value = f"{result.declared_bitrate} kbps" if result.declared_bitrate else "-"
        elif col_id == "cutoff_frequency":
            if result.display_cutoff_override:
                value = result.display_cutoff_override
            elif result.cutoff_frequency_khz > 0:
                value = f"{result.cutoff_frequency_khz:.1f} kHz"
        elif col_id == "detected_quality":
            quality = result.detected_quality if result.detected_quality else "-"
            if result.is_uncertain and result.detected_quality:
                quality = f"{result.detected_quality} (?)"
            value = quality

        # Truncate text if too long for column (approx 7px per char + padding)
        max_chars = max((width - 16) // 7, 10)
        if len(value) > max_chars:
            value = value[:max_chars - 2] + "..."

        return value

    def _bind_click_recursive(self, widget):
        """Bind click and right-click events to all descendants of the widget."""
        for child in widget.winfo_children():
            child.bind("<Button-1>", self._handle_click, add="+")
            child.bind("<ButtonRelease-1>", self._handle_release, add="+")
            if sys.platform == "darwin":
                child.bind("<Button-2>", self._handle_right_click, add="+")
            else:
                child.bind("<Button-3>", self._handle_right_click, add="+")
            self._bind_click_recursive(child)

    def _handle_click(self, event):
        """Handle click on row or its children.

        Uses event.time deduplication because _bind_click_recursive binds
        this handler to every descendant widget — a single physical click
        would otherwise fire it ~15 times (once per widget in the row).
        """
        if event.time == self._last_row_click_time:
            return
        self._last_row_click_time = event.time
        # macOS Ctrl+click = right-click
        if sys.platform == "darwin" and (event.state & 0x4):
            if self.on_right_click:
                self.on_right_click(self, event)
            return
        if self.on_click:
            self.on_click(self, event)

    def _handle_release(self, event):
        """Handle button-1 release (used to finalize a deferred single-select)."""
        if event.time == self._last_row_release_time:
            return
        self._last_row_release_time = event.time
        # Skip on macOS Ctrl+click (treated as right-click on press)
        if sys.platform == "darwin" and (event.state & 0x4):
            return
        if self.on_release:
            self.on_release(self, event)

    def _handle_right_click(self, event):
        """Handle right-click on row or its children."""
        if event.time == self._last_row_click_time:
            return
        self._last_row_click_time = event.time
        if self.on_right_click:
            self.on_right_click(self, event)

    def _handle_badge_click(self, event):
        """Handle click specifically on the quality badge."""
        if event.time == self._last_badge_click_time:
            return
        self._last_badge_click_time = event.time
        if self._on_badge_click and self._badge:
            self._on_badge_click(self.result, self._badge)

    def _on_enter(self, event):
        """Handle mouse enter (hover)."""
        if not self._selected and not self._hover_state:
            self._hover_state = True
            self.configure(fg_color=THEME_COLORS["row_hover"])

    def _on_leave(self, event):
        """Handle mouse leave."""
        if not self._selected and self._hover_state:
            self._hover_state = False
            self.configure(fg_color="transparent")

    def set_selected(self, selected: bool):
        """Set the selection state of the row."""
        self._selected = selected
        self._hover_state = False  # Reset hover state on selection change
        if selected:
            self.configure(fg_color=THEME_COLORS["row_selected"])
            self._accent_bar.place(x=0, y=0, relheight=1.0)
            self._accent_bar.lift()
        else:
            self.configure(fg_color="transparent")
            self._accent_bar.place_forget()

    def update_result(self, result: AnalysisResult):
        """Update the row with new result data."""
        self.result = result

        # Update all non-status cells
        for col_id, cell in list(self._cells.items()):
            if col_id == "status":
                continue
            width = 100
            for cid, _, w in self._columns:
                if cid == col_id:
                    width = w
                    break
            cell.configure(text=self._get_value(col_id, width))

        # Handle status column: transition between text label and quality badge
        is_final = result.status not in (STATUS_PENDING, STATUS_ANALYZING, STATUS_ERROR)
        status_frame = self._cell_frames.get("status")

        if is_final and self._badge:
            # Already has a badge — just update it
            self._badge.update_quality(result.cutoff_frequency_khz, result.status)
        elif is_final and not self._badge:
            # Transition: text → badge (analysis completed)
            if "status" in self._cells:
                self._cells["status"].destroy()
                del self._cells["status"]
            if status_frame:
                self._badge = QualityBadge(
                    status_frame, result.cutoff_frequency_khz, result.status,
                    on_badge_click=self._handle_badge_click,
                )
                self._badge.place(x=8, rely=0.5, anchor="w")
        elif not is_final:
            # Still pending/analyzing/error — update text label
            if self._badge:
                self._badge.destroy()
                self._badge = None
            if "status" in self._cells:
                self._cells["status"].configure(
                    text=t_status(result.status),
                    text_color=STATUS_COLORS.get(result.status, THEME_COLORS["text_muted"]),
                )
            elif status_frame:
                cell = ctk.CTkLabel(
                    status_frame,
                    text=t_status(result.status),
                    anchor="w",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["small"]),
                    text_color=STATUS_COLORS.get(result.status, THEME_COLORS["text_muted"]),
                    fg_color="transparent",
                )
                cell.place(x=8, rely=0.5, anchor="w")
                self._cells["status"] = cell

    def refresh_text(self):
        """Re-truncate all cell text based on current column widths."""
        for col_id, cell in self._cells.items():
            width = 100
            for cid, _, w in self._columns:
                if cid == col_id:
                    width = w
                    break
            cell.configure(text=self._get_value(col_id, width))

    def rebind(self, result: AnalysisResult, selected: bool):
        """Re-point this recycled row to a different result.

        Used by the virtualized table to reuse a small pool of row widgets
        instead of creating one widget per file.  Reconfigures the existing
        cells/badge in place (no widget creation/destruction).
        """
        self.update_result(result)        # sets self.result + refreshes cells/badge
        self.set_selected(selected)       # selection state comes from the model
        self._hover_state = False
        self._reset_dedup()

    def _reset_dedup(self):
        """Reset per-click dedup timestamps.

        A recycled widget could otherwise inherit a stale event.time and drop
        a legitimate click whose timestamp happens to collide.
        """
        self._last_row_click_time = 0
        self._last_row_release_time = 0
        self._last_badge_click_time = 0


class ResultsTable(ctk.CTkFrame):
    """
    A scrollable table for displaying audio analysis results with pill-style status badges.
    Columns are resizable by dragging the border between header cells.
    """

    @staticmethod
    def _get_columns():
        return [
            ("filename", t("column.filename"), 250),
            ("format", t("column.format"), 70),
            ("duration", t("column.duration"), 80),
            ("declared_bitrate", t("column.declared_bitrate"), 80),
            ("cutoff_frequency", t("column.cutoff_frequency"), 100),
            ("detected_quality", t("column.detected_quality"), 100),
            ("status", t("column.status"), 130),
        ]

    COLUMNS = None  # Initialized in __init__

    MIN_WIDTHS = [100, 50, 60, 60, 70, 70, 90]

    # Virtualization geometry
    ROW_HEIGHT = 41   # 40px row + 1px gap (matches former pady=(0, 1))
    BUFFER = 8        # extra rows rendered above/below the viewport

    def __init__(
        self,
        master,
        on_selection_changed: Optional[SelectionCallback] = None,
        on_context_menu: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        # Initialize translated columns
        if ResultsTable.COLUMNS is None:
            ResultsTable.COLUMNS = self._get_columns()

        self.on_selection_changed = on_selection_changed
        self.on_context_menu = on_context_menu

        # ── Model (source of truth — independent of which rows are rendered) ──
        self._results: Dict[str, AnalysisResult] = {}   # filepath -> data
        self._order: List[str] = []                      # filepaths in insertion/sort order (unfiltered)
        self._visible: List[str] = []                    # filepaths after filter, in display order

        # Selection lives in the MODEL (filepaths), so it survives a row leaving
        # and re-entering the viewport during scroll.
        self._selected_fps: List[str] = []
        self._anchor_fp: Optional[str] = None
        # Filepath whose collapse-to-single was deferred from press to release,
        # so a drag-out can keep the full multi-selection (Finder-style).
        self._pending_collapse_fp: Optional[str] = None
        self._quality_popup: Optional[QualityPopup] = None

        # ── View (recycled pool of ~K row widgets) ──
        self._pool: List[ResultRow] = []                 # reusable ResultRow widgets
        self._row_for_fp: Dict[str, ResultRow] = {}      # filepath -> widget, only for mounted rows
        self._last_first: int = 0                        # cached rendered window (avoids redundant re-render)
        self._last_last: int = 0
        self._last_total_h: int = -1                     # cached content height (avoids redundant spacer resize)
        self._viewport_timer = None                      # debounce for viewport refresh

        # Mutable column widths (source of truth for current widths)
        self._column_widths: List[int] = [w for _, _, w in self.COLUMNS]

        # Resize state
        self._header_cells: List[ctk.CTkFrame] = []
        self._header_labels: Dict[str, ctk.CTkLabel] = {}
        self._resize_col: int = -1
        self._resize_start_x: int = 0
        self._resize_start_left: int = 0
        self._resize_start_right: int = 0
        self._resize_throttle_id = None

        # Sort state
        self._sort_column: Optional[str] = None
        self._sort_ascending: bool = True

        # Debounce timer for reorder during batch analysis
        self._reorder_timer = None

        # Auto-resize state (distribute extra width to filename column)
        self._resize_table_timer = None
        self._last_table_width = 0

        # Search/filter state
        self._filter_text: str = ""
        self._filter_active: bool = False

        self._setup_ui()

    def _current_columns(self) -> List[tuple]:
        """Return COLUMNS definition with current widths."""
        return [
            (col_id, col_name, self._column_widths[i])
            for i, (col_id, col_name, _) in enumerate(self.COLUMNS)
        ]

    def _setup_ui(self):
        """Set up the table UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header row
        self.header_frame = ctk.CTkFrame(
            self,
            fg_color=THEME_COLORS["bg_secondary"],
            corner_radius=0,
            height=36,
        )
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.pack_propagate(False)
        self.header_frame.grid_propagate(False)

        # Create header labels with fixed-width containers
        self._header_cells = []
        self._header_labels = {}
        for i, (col_id, col_name, width) in enumerate(self.COLUMNS):
            # Container frame with fixed width
            header_cell = ctk.CTkFrame(
                self.header_frame,
                fg_color="transparent",
                width=width,
                height=36,
                corner_radius=0,
                cursor="hand2",
            )
            header_cell.grid(row=0, column=i, sticky="nsew")
            header_cell.grid_propagate(False)
            header_cell.pack_propagate(False)
            self._header_cells.append(header_cell)

            header_label = ctk.CTkLabel(
                header_cell,
                text=col_name.upper(),
                anchor="w",
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["header"], weight="bold"),
                text_color=THEME_COLORS["primary"],
                fg_color="transparent",
                cursor="hand2",
            )
            header_label.place(x=8, rely=0.5, anchor="w")
            self._header_labels[col_id] = header_label

            # Bind events for sorting and column resize
            for widget in (header_cell, header_label):
                widget.bind("<Motion>", self._on_header_motion)
                widget.bind("<ButtonPress-1>", self._on_header_press)
                widget.bind("<B1-Motion>", self._on_header_b1_drag)
                widget.bind("<ButtonRelease-1>", self._on_header_b1_release)

        # Configure header column weights - filename stretches, rest fixed
        for i, (col_id, _, width) in enumerate(self.COLUMNS):
            w = 1 if i == 0 else 0
            self.header_frame.grid_columnconfigure(i, weight=w, minsize=width)

        # Scrollable content frame
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=THEME_COLORS["bg_secondary"],
            corner_radius=0,
            scrollbar_button_color=THEME_COLORS["scrollbar_thumb"],
            scrollbar_button_hover_color=THEME_COLORS["scrollbar_thumb_hover"],
        )
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")

        # ── Virtualization ──
        # A single packed spacer drives the inner frame's height (and therefore
        # the canvas scrollregion via CTk's bbox("all") binding), so the
        # scrollbar reflects the full list while only ~K rows are actually
        # rendered.  Rows are positioned with absolute place() over the spacer.
        self._spacer = ctk.CTkFrame(
            self.scroll_frame, fg_color="transparent", corner_radius=0, height=1
        )
        self._spacer.pack(fill="x")
        self._spacer.lower()

        self._canvas_fit_timer = None
        canvas = self.scroll_frame._parent_canvas
        window_id = self.scroll_frame._create_window_id

        # Wrap the canvas yscrollcommand so every scroll source (wheel, scrollbar
        # drag, yview_moveto, keyboard) triggers a viewport recompute, while
        # still forwarding to the scrollbar so the thumb stays in sync.
        self._scrollbar_set = self.scroll_frame._scrollbar.set
        canvas.configure(yscrollcommand=self._on_canvas_yscroll)

        # Throttle canvas width propagation during continuous resize; also
        # recompute the visible window when the viewport height changes.
        def _throttled_canvas_fit(event):
            self._schedule_viewport_update()
            if self._canvas_fit_timer is not None:
                self.after_cancel(self._canvas_fit_timer)
            self._canvas_fit_timer = self.after(
                100, lambda: self._apply_canvas_width(canvas, window_id)
            )

        canvas.bind("<Configure>", _throttled_canvas_fit)

        self._setup_search_widget()

        # Auto-distribute width on resize
        self.bind("<Configure>", self._on_table_configure)

    # ─── Virtualization engine ───────────────────────────────────────

    def _on_canvas_yscroll(self, lo, hi):
        """Proxy for the canvas yscrollcommand: keep the thumb in sync and
        recompute the visible window on every scroll."""
        self._scrollbar_set(lo, hi)
        self._schedule_viewport_update()

    def _schedule_viewport_update(self):
        """Debounce viewport recomputation (~1 frame) to coalesce bursts."""
        if self._viewport_timer is not None:
            return
        self._viewport_timer = self.after(16, self._refresh_viewport)

    def _rebuild_visible(self):
        """Recompute the visible (filtered) filepath list from the current order."""
        if self._filter_text:
            self._visible = [
                fp for fp in self._order
                if self._matches_filter(self._results[fp].filename)
            ]
        else:
            self._visible = list(self._order)

    def _ensure_pool(self, needed: int):
        """Grow the recycled row pool to at least `needed` widgets (never shrinks)."""
        while len(self._pool) < needed:
            row = ResultRow(
                self.scroll_frame,
                _placeholder_result(),
                self._current_columns(),
                on_click=self._on_row_click,
                on_release=self._on_row_release,
                on_right_click=self._on_row_right_click,
                on_badge_click=self._on_badge_click,
                on_drag_files=self._get_drag_filepaths,
            )
            row._mounted = False
            row._fp = None
            row._cur_y = None
            row.place_forget()
            self._pool.append(row)

    def _refresh_viewport(self, force: bool = False):
        """Render only the rows inside the current viewport (+ buffer)."""
        if self._viewport_timer is not None:
            try:
                self.after_cancel(self._viewport_timer)
            except Exception:
                pass
            self._viewport_timer = None
        canvas = self.scroll_frame._parent_canvas

        n = len(self._visible)
        total_h = n * self.ROW_HEIGHT

        # Resize the spacer (drives scrollregion) only when the count changes.
        if total_h != self._last_total_h:
            self._spacer.configure(height=max(total_h, 1))
            self._last_total_h = total_h
            # Settle the scrollregion so canvasy() reads the new geometry.
            try:
                canvas.update_idletasks()
            except Exception:
                pass

        if n == 0:
            for row in self._pool:
                if getattr(row, "_mounted", False):
                    row.place_forget()
                    row._mounted = False
                    row._fp = None
            self._row_for_fp = {}
            self._last_first = self._last_last = 0
            return

        viewport_h = canvas.winfo_height()
        if viewport_h <= 1:
            # Canvas not realized yet — retry shortly.
            self._schedule_viewport_update()
            return

        top_px = max(0.0, canvas.canvasy(0))
        first = max(0, int(top_px // self.ROW_HEIGHT) - self.BUFFER)
        count = int(viewport_h // self.ROW_HEIGHT) + 2 * self.BUFFER + 2
        last = min(n, first + count)

        if not force and first == self._last_first and last == self._last_last:
            return
        self._last_first, self._last_last = first, last

        self._mount_range(first, last)

    def _mount_range(self, first: int, last: int):
        """Bind pool rows to the visible slice, recycling rows that already
        show a still-visible filepath to minimize reconfigure work."""
        desired = self._visible[first:last]
        desired_set = set(desired)
        selected_set = set(self._selected_fps)

        self._ensure_pool(len(desired))

        # Keep rows already showing a desired filepath; free the rest.
        reuse: Dict[str, ResultRow] = {}
        free: List[ResultRow] = []
        for row in self._pool:
            fp = getattr(row, "_fp", None)
            if getattr(row, "_mounted", False) and fp in desired_set and fp not in reuse:
                reuse[fp] = row
            else:
                free.append(row)

        new_map: Dict[str, ResultRow] = {}
        fi = 0
        for offset, fp in enumerate(desired):
            y = (first + offset) * self.ROW_HEIGHT
            want_sel = fp in selected_set
            row = reuse.get(fp)
            if row is not None:
                # Data is kept fresh by add_result/update_filepath.  Only touch
                # geometry/appearance when something actually changed — during a
                # plain scroll a reused row keeps its absolute y and state, so
                # this loop becomes nearly free.
                if row._selected != want_sel:
                    row.set_selected(want_sel)
                if row._cur_y != y:
                    row.place_configure(y=y)
                    row._cur_y = y
            else:
                row = free[fi]
                fi += 1
                row.rebind(self._results[fp], want_sel)
                # Height comes from the constructor (40px, propagation off); CTk
                # forbids passing width/height to place().
                row.place(x=0, y=y, relwidth=1.0)
                row._cur_y = y
                row._mounted = True
            row._fp = fp
            new_map[fp] = row

        # Hide any leftover free rows.
        for k in range(fi, len(free)):
            row = free[k]
            if getattr(row, "_mounted", False):
                row.place_forget()
                row._mounted = False
                row._fp = None

        self._row_for_fp = new_map

    def _apply_selection_to_pool(self):
        """Reflect the model's selection on the currently mounted rows."""
        sel = set(self._selected_fps)
        for fp, row in self._row_for_fp.items():
            row.set_selected(fp in sel)

    def _sync_row_widths(self, row: ResultRow):
        """Apply the current column widths to a single (pool) row."""
        for i, (col_id, _, _) in enumerate(self.COLUMNS):
            width = self._column_widths[i]
            w = 1 if i == 0 else 0
            cell_frame = row._cell_frames.get(col_id)
            if cell_frame:
                cell_frame.configure(width=width)
            row.grid_columnconfigure(i, weight=w, minsize=width)
            row._columns[i][2] = width

    # ─── Auto-resize ─────────────────────────────────────────────────

    def _apply_canvas_width(self, canvas, window_id):
        """Deferred: propagate canvas width to the inner frame."""
        self._canvas_fit_timer = None
        try:
            canvas.itemconfigure(window_id, width=canvas.winfo_width())
        except Exception:
            pass

    def _on_table_configure(self, event):
        """Expand filename column to fill available width on resize (debounced).

        With virtualization only ~K rows are ever rendered, so there is no need
        to detach the scroll frame during resize — a simple debounce suffices.
        """
        # Don't interfere with manual column drag
        if self._resize_col >= 0:
            return
        if self._resize_table_timer is not None:
            self.after_cancel(self._resize_table_timer)
        self._resize_table_timer = self.after(150, self._finish_resize)

    def _finish_resize(self):
        """Sync widths and re-render the viewport after resize ends."""
        self._resize_table_timer = None
        self._check_and_distribute_width()
        self._refresh_viewport(force=True)

    def _check_and_distribute_width(self):
        """Check actual width and redistribute space to filename column."""
        try:
            new_width = self.winfo_width()
        except Exception:
            return
        if new_width <= 1 or new_width == self._last_table_width:
            return
        self._last_table_width = new_width
        # Sum of all columns except filename (index 0)
        fixed_total = sum(self._column_widths[1:])
        ideal_filename = new_width - fixed_total
        new_filename_width = max(ideal_filename, self.MIN_WIDTHS[0])
        # Avoid unnecessary updates
        if abs(new_filename_width - self._column_widths[0]) < 3:
            return
        self._column_widths[0] = new_filename_width
        self._apply_filename_width()
        self._refresh_filename_text()

    # ─── Search / Filter ────────────────────────────────────────────

    def _setup_search_widget(self):
        """Create search button and floating search bar in the header."""
        # Magnifying glass button in the header (top-right)
        self._search_btn = ctk.CTkButton(
            self.header_frame,
            text="",
            image=icon_search(16, THEME_COLORS["text_muted"]),
            width=28, height=28,
            fg_color="transparent",
            hover_color=THEME_COLORS["bg_elevated"],
            corner_radius=6,
            command=self.toggle_search,
        )
        self._search_btn.place(relx=1.0, rely=0.5, anchor="e", x=-8)
        self._search_btn.lift()

        # Floating search bar (hidden by default, fixed size so place() works)
        self._search_bar = ctk.CTkFrame(
            self.header_frame,
            fg_color=THEME_COLORS["bg_elevated"],
            corner_radius=8,
            height=30,
            width=260,
        )
        self._search_bar.pack_propagate(False)

        # Close button
        self._search_close_btn = ctk.CTkButton(
            self._search_bar,
            text="",
            image=icon_close(10, THEME_COLORS["text_muted"]),
            width=22, height=22,
            fg_color="transparent",
            hover_color=THEME_COLORS["bg_frame"],
            corner_radius=4,
            command=self.close_search,
        )
        self._search_close_btn.pack(side="left", padx=(4, 0), pady=3)

        # Search entry
        self._search_entry = ctk.CTkEntry(
            self._search_bar,
            placeholder_text=t("search.placeholder"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            fg_color="transparent",
            border_width=0,
            height=24,
            text_color=THEME_COLORS["text_primary"],
        )
        self._search_entry.pack(side="left", fill="x", expand=True, padx=(2, 8), pady=3)

        # Bind events
        self._search_entry.bind("<KeyRelease>", lambda e: self._on_search_changed())
        self._search_entry.bind("<Escape>", lambda e: self.close_search())

    def toggle_search(self):
        """Toggle the search bar visibility."""
        if self._filter_active:
            self.close_search()
        else:
            self.open_search()

    def open_search(self):
        """Show the search bar and focus the entry."""
        if self._filter_active:
            self._search_entry.focus_set()
            return
        self._filter_active = True
        self._search_btn.place_forget()
        self._search_bar.place(relx=1.0, rely=0.5, anchor="e", x=-4)
        self._search_bar.lift()
        self._search_entry.focus_set()

    def close_search(self):
        """Hide the search bar, clear filter, restore all rows."""
        if not self._filter_active:
            return
        self._filter_active = False
        self._search_bar.place_forget()
        self._search_btn.place(relx=1.0, rely=0.5, anchor="e", x=-8)
        self._search_btn.lift()
        self._search_entry.delete(0, "end")
        self._filter_text = ""
        self._show_all_rows()

    def is_search_active(self) -> bool:
        """Return whether the search bar is currently visible."""
        return self._filter_active

    @staticmethod
    def _normalize(text: str) -> str:
        """Strip non-alphanumeric chars for fuzzy matching.

        E.g. "C.R.E.A.M.mp3" → "creammp3", so query "cream" matches.
        """
        return "".join(c for c in text.lower() if c.isalnum())

    def _matches_filter(self, filename: str) -> bool:
        """Check if filename matches the current filter (exact or fuzzy)."""
        name = filename.lower()
        if self._filter_text in name:
            return True
        return self._normalize(self._filter_text) in self._normalize(name)

    def _on_search_changed(self):
        """Handle typing in the search entry."""
        text = self._search_entry.get().strip().lower()
        if text == self._filter_text:
            return
        self._filter_text = text
        self._apply_filter()

    def _apply_filter(self):
        """Recompute the visible list from the current filter text and re-render."""
        self._rebuild_visible()
        self._refresh_viewport(force=True)

    def _show_all_rows(self):
        """Restore all rows (filter cleared)."""
        self._rebuild_visible()
        self._refresh_viewport(force=True)

    # ─── Column resize (boundary-based, no grip widgets) ────────────

    _RESIZE_GRAB_ZONE = 6  # px from column boundary to trigger resize

    def _find_resize_boundary(self, event):
        """Return column index if event is near a column boundary, else -1."""
        try:
            hx = event.x_root - self.header_frame.winfo_rootx()
        except Exception:
            return -1
        cumulative = 0
        for i in range(len(self._column_widths) - 1):
            cumulative += self._column_widths[i]
            if abs(hx - cumulative) <= self._RESIZE_GRAB_ZONE:
                return i
        return -1

    def _find_header_column(self, event):
        """Return the col_id at the event's x position."""
        try:
            hx = event.x_root - self.header_frame.winfo_rootx()
        except Exception:
            return None
        cumulative = 0
        for i, (col_id, _, _) in enumerate(self.COLUMNS):
            cumulative += self._column_widths[i]
            if hx < cumulative:
                return col_id
        return self.COLUMNS[-1][0] if self.COLUMNS else None

    def _on_header_motion(self, event):
        """Change cursor when near column boundary."""
        if self._resize_col >= 0:
            return
        col = self._find_resize_boundary(event)
        new_cursor = "sb_h_double_arrow" if col >= 0 else "hand2"
        if getattr(self, '_header_cursor', None) != new_cursor:
            self._header_cursor = new_cursor
            for cell in self._header_cells:
                cell.configure(cursor=new_cursor)
            for label in self._header_labels.values():
                label.configure(cursor=new_cursor)

    def _on_header_press(self, event):
        """Start column resize if near boundary, otherwise trigger sort."""
        col = self._find_resize_boundary(event)
        if col >= 0:
            self._resize_col = col
            self._resize_start_x = event.x_root
            self._resize_start_left = self._column_widths[col]
            self._resize_start_right = self._column_widths[col + 1]
        else:
            col_id = self._find_header_column(event)
            if col_id:
                self._on_header_click(col_id)

    def _compute_resize(self, dx):
        """Compute new column widths for a drag of dx pixels.

        Trades space between the two columns adjacent to the boundary,
        keeping all other columns (and the total) unchanged.
        """
        col = self._resize_col

        if col == 0:
            # Boundary col0/col1: only adjust col1 (col0 auto-fills via weight=1)
            # Drag right → col1 shrinks; drag left → col1 grows
            new_right = self._resize_start_right - dx
            new_right = max(self.MIN_WIDTHS[1], new_right)
            # Prevent col0 from going below its minimum
            try:
                tw = self.winfo_width()
                if tw > 1:
                    others = sum(self._column_widths[j] for j in range(2, len(self._column_widths)))
                    max_col1 = tw - others - self.MIN_WIDTHS[0]
                    new_right = min(new_right, max(max_col1, self.MIN_WIDTHS[1]))
            except Exception:
                pass
            self._column_widths[1] = new_right
        else:
            # Trade space between col and col+1
            # Clamp dx so neither side goes below its minimum
            max_dx_right = self._resize_start_right - self.MIN_WIDTHS[col + 1]
            max_dx_left = self._resize_start_left - self.MIN_WIDTHS[col]
            dx = max(-max_dx_left, min(dx, max_dx_right))

            self._column_widths[col] = self._resize_start_left + dx
            self._column_widths[col + 1] = self._resize_start_right - dx

    def _on_header_b1_drag(self, event):
        """Handle column resize drag motion (throttled)."""
        if self._resize_col < 0:
            return
        dx = event.x_root - self._resize_start_x
        self._compute_resize(dx)
        if self._resize_throttle_id is None:
            self._resize_throttle_id = self.after(30, self._apply_resize)

    def _on_header_b1_release(self, event):
        """End column resize drag."""
        if self._resize_col < 0:
            return
        if self._resize_throttle_id is not None:
            self.after_cancel(self._resize_throttle_id)
            self._resize_throttle_id = None
        dx = event.x_root - self._resize_start_x
        self._compute_resize(dx)
        self._resize_col = -1
        self._sync_filename_width()
        self._apply_column_widths()
        self._refresh_all_text()

    def _apply_resize(self):
        """Apply column width change during drag (called by throttle timer)."""
        self._resize_throttle_id = None
        self._sync_filename_width()
        self._apply_column_widths()

    def _sync_filename_width(self):
        """Keep filename column width in sync with actual rendered width.

        Column 0 has grid weight=1, so it always fills remaining space.
        After resizing any other column, _column_widths[0] must be updated
        to match reality, otherwise boundary detection drifts.
        """
        try:
            table_width = self.winfo_width()
        except Exception:
            return
        if table_width <= 1:
            return
        fixed_total = sum(self._column_widths[1:])
        self._column_widths[0] = max(table_width - fixed_total, self.MIN_WIDTHS[0])
        self._last_table_width = table_width

    def _apply_column_widths(self):
        """Propagate current column widths to header and the row pool."""
        for i, (col_id, _, _) in enumerate(self.COLUMNS):
            width = self._column_widths[i]
            w = 1 if i == 0 else 0  # filename column stretches
            # Update header
            self._header_cells[i].configure(width=width)
            self.header_frame.grid_columnconfigure(i, weight=w, minsize=width)
        # Update the pool (only ~K widgets, not one per file)
        for row in self._pool:
            self._sync_row_widths(row)

    def _refresh_all_text(self):
        """Re-truncate text in pool rows based on current column widths."""
        for row in self._pool:
            row.refresh_text()

    def _apply_filename_width(self):
        """Update only the filename column width (column 0) in header and pool rows."""
        width = self._column_widths[0]
        col_id = self.COLUMNS[0][0]
        self._header_cells[0].configure(width=width)
        self.header_frame.grid_columnconfigure(0, weight=1, minsize=width)
        for row in self._pool:
            cell_frame = row._cell_frames.get(col_id)
            if cell_frame:
                cell_frame.configure(width=width)
            row.grid_columnconfigure(0, weight=1, minsize=width)
            row._columns[0][2] = width

    def _refresh_filename_text(self):
        """Re-truncate only filename text in pool rows."""
        width = self._column_widths[0]
        for row in self._pool:
            cell = row._cells.get("filename")
            if cell:
                cell.configure(text=row._get_value("filename", width))

    def _get_drag_filepaths(self, row: ResultRow) -> List[str]:
        """Return file paths to export on drag-out.

        If the dragged row is part of the current multi-selection, export all
        selected files; otherwise export just the dragged row (Finder-style).
        """
        # A drag is starting: cancel any deferred collapse so the release does
        # not shrink the multi-selection after the files have been exported.
        self._pending_collapse_fp = None
        fp = row.result.filepath
        if fp in self._selected_fps and len(self._selected_fps) > 1:
            return list(self._selected_fps)
        return [fp]

    def _on_row_click(self, row: ResultRow, event=None):
        """Handle row click for selection with modifier key support."""
        fp = row.result.filepath
        cmd_held = False
        shift_held = False
        if event:
            if sys.platform == "darwin":
                cmd_held = bool(event.state & 0x8)   # Command
            else:
                cmd_held = bool(event.state & 0x4)   # Control
            shift_held = bool(event.state & 0x1)     # Shift

        if cmd_held:
            self._pending_collapse_fp = None
            self._toggle_selection(fp)
        elif shift_held:
            self._pending_collapse_fp = None
            self._extend_selection(fp)
        elif fp in self._selected_fps and len(self._selected_fps) > 1:
            # Pressing on an already multi-selected row: defer collapsing to a
            # single selection until release, so a drag-out can export them all.
            self._pending_collapse_fp = fp
        else:
            self._pending_collapse_fp = None
            self._select_single(fp)

    def _on_row_release(self, row: ResultRow, event=None):
        """Finalize a deferred single-select if the press did not start a drag."""
        fp = row.result.filepath
        if self._pending_collapse_fp == fp:
            self._pending_collapse_fp = None
            self._select_single(fp)

    def _select_single(self, fp: str):
        """Select a single filepath, deselecting all others."""
        self._selected_fps = [fp]
        self._anchor_fp = fp
        self._apply_selection_to_pool()
        if self.on_selection_changed:
            self.on_selection_changed(self._results.get(fp))

    def _toggle_selection(self, fp: str):
        """Toggle selection of a filepath (Cmd/Ctrl+click)."""
        if fp in self._selected_fps:
            self._selected_fps.remove(fp)
            if self._anchor_fp == fp:
                self._anchor_fp = self._selected_fps[-1] if self._selected_fps else None
        else:
            self._selected_fps.append(fp)
            self._anchor_fp = fp
        self._apply_selection_to_pool()
        if self.on_selection_changed:
            result = self._results.get(self._selected_fps[-1]) if self._selected_fps else None
            self.on_selection_changed(result)

    def _extend_selection(self, fp: str):
        """Extend selection from anchor to filepath (Shift+click)."""
        if not self._anchor_fp:
            self._select_single(fp)
            return

        try:
            anchor_idx = self._visible.index(self._anchor_fp)
            target_idx = self._visible.index(fp)
        except ValueError:
            self._select_single(fp)
            return

        start = min(anchor_idx, target_idx)
        end = max(anchor_idx, target_idx)
        self._selected_fps = self._visible[start:end + 1]
        self._apply_selection_to_pool()
        # Don't change anchor on Shift+click
        if self.on_selection_changed:
            self.on_selection_changed(self._results.get(fp))

    def _on_row_right_click(self, row: ResultRow, event):
        """Handle right-click on a row."""
        fp = row.result.filepath
        # If the row is not in the current selection, select it (single)
        if fp not in self._selected_fps:
            self._select_single(fp)
        if self.on_context_menu:
            self.on_context_menu(event)

    def _on_badge_click(self, result: AnalysisResult, badge_widget):
        """Handle click on a quality badge — show explanation popup."""
        self._close_quality_popup()
        self._quality_popup = QualityPopup(
            self.winfo_toplevel(),
            result,
            badge_widget,
            on_close=self._on_popup_closed,
        )

    def _close_quality_popup(self):
        """Close the quality popup if open."""
        if self._quality_popup:
            try:
                self._quality_popup.close()
            except Exception:
                pass
            self._quality_popup = None

    def _on_popup_closed(self):
        """Callback when popup closes itself."""
        self._quality_popup = None

    # ─── Column sorting ──────────────────────────────────────────────

    # Severity ordering for status column (higher = more problematic)
    _STATUS_SEVERITY = {
        "Transcode detectado": 8,
        "Baja calidad": 7,
        "Calidad variable": 6,
        "Incierto": 5,
        "Error": 4,
        "OK": 3,
        "Lossless": 2,
        "Pendiente": 1,
        "Analizando...": 0,
    }

    # Quality ordering (higher = worse quality, so descending shows problems first)
    _QUALITY_ORDER = {
        "Lossless": 0,
        "320kbps": 1,
        "256kbps": 2,
        "192kbps": 3,
        "160kbps": 4,
        "128kbps": 5,
        "96kbps": 6,
        "Baja calidad": 7,
    }

    def _on_header_click(self, col_id: str):
        """Handle header click for column sorting."""
        if self._sort_column == col_id:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = col_id
            self._sort_ascending = False  # First click = descending
        self._update_header_indicators()
        self._reorder_rows()

    def _update_header_indicators(self):
        """Update sort direction arrows in header labels."""
        for col_id, label in self._header_labels.items():
            orig_name = None
            for cid, cname, _ in self.COLUMNS:
                if cid == col_id:
                    orig_name = cname
                    break
            header_text = orig_name.upper()
            if col_id == self._sort_column:
                arrow = "\u25B2" if self._sort_ascending else "\u25BC"
                label.configure(text=header_text + arrow)
            else:
                label.configure(text=header_text)

    def _get_sort_key(self, result: AnalysisResult):
        """Get sort key for a result based on current sort column."""
        col = self._sort_column
        if col == "filename":
            return result.filename.lower()
        elif col == "format":
            return result.format.lower()
        elif col == "duration":
            return result.duration
        elif col == "declared_bitrate":
            return result.declared_bitrate or 0
        elif col == "cutoff_frequency":
            return result.cutoff_frequency_khz
        elif col == "detected_quality":
            return self._QUALITY_ORDER.get(result.detected_quality, 99)
        elif col == "status":
            return self._STATUS_SEVERITY.get(result.status, 99)
        return ""

    def _schedule_reorder(self):
        """Schedule a debounced reorder (used during batch analysis)."""
        if self._reorder_timer is not None:
            self.after_cancel(self._reorder_timer)
        self._reorder_timer = self.after(50, self._reorder_rows)

    def _reorder_rows(self):
        """Reorder the model based on current sort, then re-render the viewport."""
        self._reorder_timer = None

        if not self._sort_column or not self._order:
            return

        self._order.sort(
            key=lambda fp: self._get_sort_key(self._results[fp]),
            reverse=not self._sort_ascending,
        )
        self._rebuild_visible()
        self._refresh_viewport(force=True)

    def add_result(self, result: AnalysisResult):
        """Add or update a result in the table."""
        fp = result.filepath
        existing = fp in self._results
        self._results[fp] = result

        if existing:
            # Live update: if the row is currently mounted, refresh it in place.
            row = self._row_for_fp.get(fp)
            if row is not None:
                row.rebind(result, fp in set(self._selected_fps))
        else:
            self._order.append(fp)

        self._rebuild_visible()

        # Maintain sort order if sorting is active (debounced during batch)
        if self._sort_column:
            self._schedule_reorder()

        self._schedule_viewport_update()

    def clear(self):
        """Clear all results from the table."""
        self._close_quality_popup()
        # Reset search/filter state
        self._filter_text = ""
        if self._filter_active:
            self.close_search()

        # Cancel any pending timers
        if self._reorder_timer is not None:
            self.after_cancel(self._reorder_timer)
            self._reorder_timer = None
        if self._viewport_timer is not None:
            self.after_cancel(self._viewport_timer)
            self._viewport_timer = None

        # Clear the model
        self._results.clear()
        self._order.clear()
        self._visible.clear()
        self._selected_fps.clear()
        self._anchor_fp = None
        self._pending_collapse_fp = None

        # Recycle (don't destroy) the pool: just unmount every row.
        self._row_for_fp.clear()
        for row in self._pool:
            if getattr(row, "_mounted", False):
                row.place_forget()
                row._mounted = False
                row._fp = None

        self._last_first = self._last_last = 0
        self._last_total_h = -1
        self._spacer.configure(height=1)
        try:
            self.scroll_frame._parent_canvas.yview_moveto(0.0)
        except Exception:
            pass

    def get_selected_result(self) -> Optional[AnalysisResult]:
        """Get the currently selected result (last clicked if multi-selected)."""
        if self._selected_fps:
            return self._results.get(self._selected_fps[-1])
        return None

    def get_selected_results(self) -> List[AnalysisResult]:
        """Get all selected results."""
        return [self._results[fp] for fp in self._selected_fps if fp in self._results]

    def get_results_count(self) -> int:
        """Get the number of results."""
        return len(self._results)

    def select_next(self) -> Optional[AnalysisResult]:
        """
        Select the next visible item in the table (collapses multi-selection).

        Returns:
            The newly selected result, or None if at end or no items.
        """
        if not self._visible:
            return None

        if not self._selected_fps:
            return self._select_at_index(0)

        # Use last selected filepath as reference point
        try:
            current_index = self._visible.index(self._selected_fps[-1])
        except ValueError:
            return None

        next_index = current_index + 1
        if next_index < len(self._visible):
            return self._select_at_index(next_index)
        return None

    def select_previous(self) -> Optional[AnalysisResult]:
        """
        Select the previous visible item in the table (collapses multi-selection).

        Returns:
            The newly selected result, or None if at start or no items.
        """
        if not self._visible:
            return None

        if not self._selected_fps:
            return self._select_at_index(len(self._visible) - 1)

        # Use first selected filepath as reference point
        try:
            current_index = self._visible.index(self._selected_fps[0])
        except ValueError:
            return None

        prev_index = current_index - 1
        if prev_index >= 0:
            return self._select_at_index(prev_index)
        return None

    def _select_at_index(self, idx: int) -> Optional[AnalysisResult]:
        """Select the visible item at `idx`, scroll it into view, return its result."""
        fp = self._visible[idx]
        self._select_single(fp)
        self.scroll_to_index(idx)
        return self._results.get(fp)

    def remove_results(self, filepaths: List[str]) -> Optional[AnalysisResult]:
        """
        Remove multiple results from the table.

        Returns:
            The newly selected result, or None if the table is now empty.
        """
        if not filepaths:
            return self.get_selected_result()

        for filepath in filepaths:
            if filepath not in self._results:
                continue
            if filepath in self._order:
                self._order.remove(filepath)
            del self._results[filepath]
            if filepath in self._selected_fps:
                self._selected_fps.remove(filepath)
            if self._anchor_fp == filepath:
                self._anchor_fp = None
            if self._pending_collapse_fp == filepath:
                self._pending_collapse_fp = None

        self._rebuild_visible()
        self._refresh_viewport(force=True)

        # Auto-select if nothing is selected
        if not self._selected_fps:
            self._anchor_fp = None
            if self._visible:
                fp = self._visible[0]
                self._select_single(fp)
                return self._results[fp]
            if self.on_selection_changed:
                self.on_selection_changed(None)
            return None

        return self._results[self._selected_fps[-1]]

    def scroll_to_index(self, idx: int):
        """Scroll so that the visible item at `idx` is shown, then render it."""
        try:
            canvas = self.scroll_frame._parent_canvas
            n = len(self._visible)
            if n == 0:
                return
            total_height = n * self.ROW_HEIGHT
            viewport_h = canvas.winfo_height()
            if viewport_h > 1 and total_height > viewport_h:
                target_top = idx * self.ROW_HEIGHT
                view_top = max(0.0, canvas.canvasy(0))
                view_bottom = view_top + viewport_h
                if target_top < view_top:
                    canvas.yview_moveto(target_top / total_height)
                elif target_top + self.ROW_HEIGHT > view_bottom:
                    canvas.yview_moveto(
                        (target_top + self.ROW_HEIGHT - viewport_h) / total_height
                    )
        except Exception:
            pass  # Scroll is best-effort
        # Ensure the target row is mounted (selection must be visible immediately).
        self._refresh_viewport(force=True)

    def update_filepath(self, old_filepath: str, new_filepath: str):
        """Re-key a result when its file has been renamed on disk.

        Updates internal dicts, the AnalysisResult, and the displayed row.
        """
        if old_filepath not in self._results:
            return

        result = self._results.pop(old_filepath)
        # Update the dataclass fields
        result.filepath = new_filepath
        result.filename = Path(new_filepath).name
        self._results[new_filepath] = result

        # Re-key the order and selection state
        try:
            self._order[self._order.index(old_filepath)] = new_filepath
        except ValueError:
            self._order.append(new_filepath)
        self._selected_fps = [
            new_filepath if fp == old_filepath else fp for fp in self._selected_fps
        ]
        if self._anchor_fp == old_filepath:
            self._anchor_fp = new_filepath
        if self._pending_collapse_fp == old_filepath:
            self._pending_collapse_fp = new_filepath

        self._rebuild_visible()
        self._refresh_viewport(force=True)

    def get_ordered_filepaths(self) -> List[str]:
        """
        Get all filepaths in display order.

        Returns:
            List of filepaths in the order they appear in the table.
        """
        return list(self._order)
