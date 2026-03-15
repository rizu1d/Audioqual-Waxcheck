"""Results table for displaying analysis results with quality level badges."""

import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from ..core.analyzer import AnalysisResult
from ..utils.constants import (
    STATUS_COLORS, THEME_COLORS, FONT_FAMILY, FONT_FAMILY_MONO, FONT_SIZES,
    QUALITY_LEVELS, get_quality_level,
    STATUS_PENDING, STATUS_ANALYZING, STATUS_ERROR,
)
from ..utils.file_utils import format_duration
from .icons import icon_search, icon_close, icon_quality_dot
from .quality_popup import QualityPopup


SelectionCallback = Callable[[Optional[AnalysisResult]], None]

# Columns that use monospace font (numeric data)
_MONO_COLUMNS = {"duration", "declared_bitrate", "cutoff_frequency", "detected_quality"}


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

        display_text = level.capitalize()
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
        display_text = level.capitalize()

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
        on_right_click: Optional[Callable] = None,
        on_badge_click: Optional[Callable] = None,
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
        self.on_right_click = on_right_click
        self._on_badge_click = on_badge_click
        self._selected = False
        # Deduplication: prevent multiple firings per physical click.
        # Separate timestamps because both handlers should fire once per click
        # (badge click should both open popup AND select the row).
        self._last_row_click_time = 0
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
                        text=result.status,
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
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        # Right-click binding (Button-2 on macOS, Button-3 on others)
        if sys.platform == "darwin":
            self.bind("<Button-2>", self._handle_right_click, add="+")
        else:
            self.bind("<Button-3>", self._handle_right_click, add="+")

        # Bind click events to all descendants (needed for CTk widgets with internal structure)
        self._bind_click_recursive(self)

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
                    text=result.status,
                    text_color=STATUS_COLORS.get(result.status, THEME_COLORS["text_muted"]),
                )
            elif status_frame:
                cell = ctk.CTkLabel(
                    status_frame,
                    text=result.status,
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


class ResultsTable(ctk.CTkFrame):
    """
    A scrollable table for displaying audio analysis results with pill-style status badges.
    Columns are resizable by dragging the border between header cells.
    """

    COLUMNS = [
        ("filename", "Archivo", 250),
        ("format", "Formato", 70),
        ("duration", "Duración", 80),
        ("declared_bitrate", "Bitrate", 80),
        ("cutoff_frequency", "Frec. Corte", 100),
        ("detected_quality", "Bitrate Real", 100),
        ("status", "Calidad", 130),
    ]

    MIN_WIDTHS = [100, 50, 60, 60, 70, 70, 90]

    def __init__(
        self,
        master,
        on_selection_changed: Optional[SelectionCallback] = None,
        on_context_menu: Optional[Callable] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_selection_changed = on_selection_changed
        self.on_context_menu = on_context_menu
        self._results: Dict[str, AnalysisResult] = {}
        self._rows: Dict[str, ResultRow] = {}
        self._selected_rows: List[ResultRow] = []
        self._anchor_row: Optional[ResultRow] = None
        self._quality_popup: Optional[QualityPopup] = None

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
        self._hidden_rows: set = set()

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

        # Configure scroll frame columns to match header
        for i in range(len(self.COLUMNS)):
            self.scroll_frame.grid_columnconfigure(i, weight=0)

        self._setup_search_widget()

        # Auto-distribute width on resize
        self.bind("<Configure>", self._on_table_configure)

    # ─── Auto-resize ─────────────────────────────────────────────────

    def _on_table_configure(self, event):
        """Expand filename column to fill available width on resize."""
        # Don't interfere with manual column drag
        if self._resize_col >= 0:
            return
        # Debounce all Configure events into a single check
        if self._resize_table_timer is not None:
            self.after_cancel(self._resize_table_timer)
        self._resize_table_timer = self.after(50, self._check_and_distribute_width)

    def _check_and_distribute_width(self):
        """Check actual width and redistribute space to filename column."""
        self._resize_table_timer = None
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
        self._apply_column_widths()
        self._refresh_all_text()

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
            placeholder_text="Buscar archivo...",
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
        """Show/hide rows based on the current filter text."""
        if not self._filter_text:
            self._show_all_rows()
            return

        newly_hidden = set()
        for filepath, row in self._rows.items():
            if self._matches_filter(row.result.filename):
                if filepath in self._hidden_rows:
                    self._hidden_rows.discard(filepath)
                    row.pack(fill="x", pady=(0, 1))
            else:
                if filepath not in self._hidden_rows:
                    row.pack_forget()
                newly_hidden.add(filepath)

        self._hidden_rows = newly_hidden

    def _show_all_rows(self):
        """Restore all hidden rows."""
        if not self._hidden_rows:
            return
        for filepath in list(self._hidden_rows):
            row = self._rows.get(filepath)
            if row:
                row.pack(fill="x", pady=(0, 1))
        self._hidden_rows.clear()
        # Re-apply sort order if active
        if self._sort_column:
            self._reorder_rows()

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
        """Propagate current column widths to header and all rows."""
        for i, (col_id, _, _) in enumerate(self.COLUMNS):
            width = self._column_widths[i]
            w = 1 if i == 0 else 0  # filename column stretches

            # Update header
            self._header_cells[i].configure(width=width)
            self.header_frame.grid_columnconfigure(i, weight=w, minsize=width)

            # Update all rows
            for row in self._rows.values():
                cell_frame = row._cell_frames.get(col_id)
                if cell_frame:
                    cell_frame.configure(width=width)
                row.grid_columnconfigure(i, weight=w, minsize=width)
                # Keep row's _columns in sync
                row._columns[i][2] = width

    def _refresh_all_text(self):
        """Re-truncate text in all rows based on current column widths."""
        for row in self._rows.values():
            row.refresh_text()

    def _on_row_click(self, row: ResultRow, event=None):
        """Handle row click for selection with modifier key support."""
        cmd_held = False
        shift_held = False
        if event:
            if sys.platform == "darwin":
                cmd_held = bool(event.state & 0x8)   # Command
            else:
                cmd_held = bool(event.state & 0x4)   # Control
            shift_held = bool(event.state & 0x1)     # Shift

        if cmd_held:
            self._toggle_selection(row)
        elif shift_held:
            self._extend_selection(row)
        else:
            self._select_single(row)

    def _select_single(self, row: ResultRow):
        """Select a single row, deselecting all others."""
        for r in self._selected_rows:
            if r != row:
                r.set_selected(False)
        row.set_selected(True)
        self._selected_rows = [row]
        self._anchor_row = row
        if self.on_selection_changed:
            self.on_selection_changed(row.result)

    def _toggle_selection(self, row: ResultRow):
        """Toggle selection of a row (Cmd/Ctrl+click)."""
        if row in self._selected_rows:
            row.set_selected(False)
            self._selected_rows.remove(row)
            if self._anchor_row == row:
                self._anchor_row = self._selected_rows[-1] if self._selected_rows else None
        else:
            row.set_selected(True)
            self._selected_rows.append(row)
            self._anchor_row = row
        if self.on_selection_changed:
            result = self._selected_rows[-1].result if self._selected_rows else None
            self.on_selection_changed(result)

    def _extend_selection(self, row: ResultRow):
        """Extend selection from anchor to row (Shift+click)."""
        if not self._anchor_row:
            self._select_single(row)
            return

        visible = [r for fp, r in self._rows.items() if fp not in self._hidden_rows]
        try:
            anchor_idx = visible.index(self._anchor_row)
            target_idx = visible.index(row)
        except ValueError:
            self._select_single(row)
            return

        start = min(anchor_idx, target_idx)
        end = max(anchor_idx, target_idx)

        for r in self._selected_rows:
            r.set_selected(False)

        self._selected_rows = visible[start:end + 1]
        for r in self._selected_rows:
            r.set_selected(True)
        # Don't change anchor on Shift+click
        if self.on_selection_changed:
            self.on_selection_changed(row.result)

    def _on_row_right_click(self, row: ResultRow, event):
        """Handle right-click on a row."""
        # If the row is not in the current selection, select it (single)
        if row not in self._selected_rows:
            self._select_single(row)
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
        """Reorder all rows in the scroll frame based on current sort."""
        self._reorder_timer = None

        if not self._sort_column or not self._rows:
            return

        # Sort rows
        sorted_items = sorted(
            self._rows.items(),
            key=lambda item: self._get_sort_key(item[1].result),
            reverse=not self._sort_ascending,
        )

        # Rebuild _rows dict in sorted order
        self._rows = dict(sorted_items)

        # Re-pack only visible rows using pack(after=...) to avoid flickering
        visible = [
            row for fp, row in self._rows.items()
            if fp not in self._hidden_rows
        ]
        if not visible:
            return
        visible[0].pack(fill="x", pady=(0, 1))
        for i in range(1, len(visible)):
            visible[i].pack(fill="x", pady=(0, 1), after=visible[i - 1])

    def add_result(self, result: AnalysisResult):
        """Add or update a result in the table."""
        self._results[result.filepath] = result

        # Check if row exists
        if result.filepath in self._rows:
            # Update existing row
            self._rows[result.filepath].update_result(result)
        else:
            # Create new row with current column widths
            row = ResultRow(
                self.scroll_frame,
                result,
                self._current_columns(),
                on_click=self._on_row_click,
                on_right_click=self._on_row_right_click,
                on_badge_click=self._on_badge_click,
            )
            row.pack(fill="x", pady=(0, 1))
            self._rows[result.filepath] = row

            # If filter is active and new file doesn't match, hide it
            if self._filter_text and not self._matches_filter(result.filename):
                row.pack_forget()
                self._hidden_rows.add(result.filepath)

        # Maintain sort order if sorting is active (debounced during batch)
        if self._sort_column:
            self._schedule_reorder()

    def add_results(self, results: List[AnalysisResult]):
        """Add multiple results to the table."""
        for result in results:
            self.add_result(result)

    def clear(self):
        """Clear all results from the table."""
        self._close_quality_popup()
        # Reset search/filter state
        self._hidden_rows.clear()
        self._filter_text = ""
        if self._filter_active:
            self.close_search()

        # Cancel any pending reorder timer
        if self._reorder_timer is not None:
            self.after_cancel(self._reorder_timer)
            self._reorder_timer = None

        # Get all rows to destroy
        rows_to_destroy = list(self._rows.values())

        # Clear data structures immediately for responsiveness
        self._rows.clear()
        self._results.clear()
        self._selected_rows.clear()
        self._anchor_row = None

        # Batch destroy widgets - do it in chunks to avoid long UI freeze
        if len(rows_to_destroy) <= 50:
            # Small batch: destroy all at once
            for row in rows_to_destroy:
                row.destroy()
        else:
            # Large batch: destroy in chunks using after() to keep UI responsive
            self._destroy_rows_batched(rows_to_destroy, 0)

    def _destroy_rows_batched(self, rows: list, index: int, batch_size: int = 20):
        """Destroy rows in batches to keep UI responsive."""
        end_index = min(index + batch_size, len(rows))
        for i in range(index, end_index):
            rows[i].destroy()

        if end_index < len(rows):
            # Schedule next batch
            self.after(1, lambda: self._destroy_rows_batched(rows, end_index, batch_size))

    def get_selected_result(self) -> Optional[AnalysisResult]:
        """Get the currently selected result (last clicked if multi-selected)."""
        if self._selected_rows:
            return self._selected_rows[-1].result
        return None

    def get_selected_results(self) -> List[AnalysisResult]:
        """Get all selected results."""
        return [r.result for r in self._selected_rows]

    def get_all_results(self) -> List[AnalysisResult]:
        """Get all results in the table."""
        return list(self._results.values())

    def get_results_count(self) -> int:
        """Get the number of results."""
        return len(self._results)

    def select_first(self):
        """Select the first visible item in the table."""
        for fp, row in self._rows.items():
            if fp not in self._hidden_rows:
                self._select_single(row)
                return

    def select_next(self) -> Optional[AnalysisResult]:
        """
        Select the next visible item in the table (collapses multi-selection).

        Returns:
            The newly selected result, or None if at end or no items.
        """
        if not self._rows:
            return None

        visible = [
            row for fp, row in self._rows.items()
            if fp not in self._hidden_rows
        ]
        if not visible:
            return None

        if not self._selected_rows:
            self._select_single(visible[0])
            self.scroll_to_row(visible[0])
            return visible[0].result

        # Use last selected row as reference point
        current = self._selected_rows[-1]
        try:
            current_index = visible.index(current)
        except ValueError:
            return None

        next_index = current_index + 1
        if next_index < len(visible):
            self._select_single(visible[next_index])
            self.scroll_to_row(visible[next_index])
            return visible[next_index].result

        return None

    def select_previous(self) -> Optional[AnalysisResult]:
        """
        Select the previous visible item in the table (collapses multi-selection).

        Returns:
            The newly selected result, or None if at start or no items.
        """
        if not self._rows:
            return None

        visible = [
            row for fp, row in self._rows.items()
            if fp not in self._hidden_rows
        ]
        if not visible:
            return None

        if not self._selected_rows:
            self._select_single(visible[-1])
            self.scroll_to_row(visible[-1])
            return visible[-1].result

        # Use first selected row as reference point
        current = self._selected_rows[0]
        try:
            current_index = visible.index(current)
        except ValueError:
            return None

        prev_index = current_index - 1
        if prev_index >= 0:
            self._select_single(visible[prev_index])
            self.scroll_to_row(visible[prev_index])
            return visible[prev_index].result

        return None

    def remove_result(self, filepath: str) -> Optional[AnalysisResult]:
        """
        Remove a single result from the table.

        If the removed row was selected, auto-selects the next row (or previous if last).

        Returns:
            The newly selected result, or None if the table is now empty.
        """
        if filepath not in self._rows:
            return None

        row = self._rows[filepath]
        was_selected = row in self._selected_rows

        # Find index in visible rows before removing
        visible = [r for fp, r in self._rows.items() if fp not in self._hidden_rows]
        try:
            index = visible.index(row)
        except ValueError:
            index = -1

        # Remove from data structures
        del self._rows[filepath]
        del self._results[filepath]
        self._hidden_rows.discard(filepath)
        if was_selected:
            self._selected_rows.remove(row)
        if self._anchor_row == row:
            self._anchor_row = self._selected_rows[-1] if self._selected_rows else None
        row.destroy()

        if not was_selected:
            return self._selected_rows[-1].result if self._selected_rows else None

        # If other selections remain, use the last one
        if self._selected_rows:
            return self._selected_rows[-1].result

        # No selections remain — pick a new one
        remaining = list(self._rows.values())
        if not remaining:
            if self.on_selection_changed:
                self.on_selection_changed(None)
            return None

        new_index = min(index, len(remaining) - 1)
        new_row = remaining[new_index]
        self._select_single(new_row)
        self.scroll_to_row(new_row)
        return new_row.result

    def remove_results(self, filepaths: List[str]) -> Optional[AnalysisResult]:
        """
        Remove multiple results from the table.

        Returns:
            The newly selected result, or None if the table is now empty.
        """
        if not filepaths:
            return self.get_selected_result()

        for filepath in filepaths:
            if filepath not in self._rows:
                continue
            row = self._rows[filepath]
            if row in self._selected_rows:
                self._selected_rows.remove(row)
            if self._anchor_row == row:
                self._anchor_row = None
            del self._rows[filepath]
            del self._results[filepath]
            self._hidden_rows.discard(filepath)
            row.destroy()

        # Auto-select if nothing is selected
        if not self._selected_rows:
            self._anchor_row = None
            remaining = list(self._rows.values())
            if remaining:
                self._select_single(remaining[0])
                return remaining[0].result
            else:
                if self.on_selection_changed:
                    self.on_selection_changed(None)
                return None

        return self._selected_rows[-1].result

    def scroll_to_row(self, row: ResultRow):
        """Scroll the table so that the given row is visible."""
        try:
            canvas = self.scroll_frame._parent_canvas
            canvas.update_idletasks()

            # Get canvas viewport height
            canvas_height = canvas.winfo_height()
            if canvas_height <= 0:
                return

            # Get total scrollable height
            scroll_region = canvas.cget("scrollregion")
            if not scroll_region:
                return
            total_height = int(scroll_region.split()[-1])
            if total_height <= canvas_height:
                return  # Everything fits, no scroll needed

            # Get row position relative to the scroll frame inner widget
            row_y = row.winfo_y()
            row_height = row.winfo_height()

            # Current viewport top/bottom in content coordinates
            current_top = canvas.yview()[0] * total_height
            current_bottom = canvas.yview()[1] * total_height

            if row_y < current_top:
                # Row is above viewport — scroll up
                canvas.yview_moveto(row_y / total_height)
            elif row_y + row_height > current_bottom:
                # Row is below viewport — scroll down so row bottom aligns with viewport bottom
                canvas.yview_moveto((row_y + row_height - canvas_height) / total_height)
        except Exception:
            pass  # Scroll is best-effort

    def update_filepath(self, old_filepath: str, new_filepath: str):
        """Re-key a result when its file has been renamed on disk.

        Updates internal dicts, the AnalysisResult, and the displayed row.
        """
        if old_filepath not in self._rows:
            return

        row = self._rows.pop(old_filepath)
        result = self._results.pop(old_filepath)
        was_hidden = old_filepath in self._hidden_rows
        self._hidden_rows.discard(old_filepath)

        # Update the dataclass fields
        result.filepath = new_filepath
        result.filename = Path(new_filepath).name

        # Re-insert under new key
        self._results[new_filepath] = result
        self._rows[new_filepath] = row

        # Refresh the row display
        row.update_result(result)

        # Re-evaluate filter with new filename
        if self._filter_text:
            matches = self._matches_filter(result.filename)
            if not matches:
                row.pack_forget()
                self._hidden_rows.add(new_filepath)
            elif was_hidden:
                row.pack(fill="x", pady=(0, 1))

    def get_ordered_filepaths(self) -> List[str]:
        """
        Get all filepaths in display order.

        Returns:
            List of filepaths in the order they appear in the table.
        """
        return [row.result.filepath for row in self._rows.values()]
