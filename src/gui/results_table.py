"""Results table for displaying analysis results with pill-style status badges."""

from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from ..core.analyzer import AnalysisResult
from ..utils.constants import STATUS_COLORS, THEME_COLORS, FONT_FAMILY, FONT_SIZES
from ..utils.file_utils import format_duration


SelectionCallback = Callable[[Optional[AnalysisResult]], None]


class StatusBadge(ctk.CTkFrame):
    """Pill-shaped status badge with colored background."""

    def __init__(self, master, status: str, **kwargs):
        # Get color for status
        bg_color = STATUS_COLORS.get(status, THEME_COLORS["text_muted"])

        super().__init__(
            master,
            fg_color=bg_color,
            corner_radius=12,
            height=24,
            **kwargs
        )

        # Prevent frame from shrinking
        self.pack_propagate(False)
        self.configure(width=self._calculate_width(status))

        # Label with status text
        self.label = ctk.CTkLabel(
            self,
            text=status,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        self.label.place(relx=0.5, rely=0.5, anchor="center")

    def _calculate_width(self, text: str) -> int:
        """Calculate badge width based on text length."""
        # Approximate width: ~7px per character + padding
        return max(len(text) * 7 + 24, 70)

    def update_status(self, status: str):
        """Update the badge status and color."""
        bg_color = STATUS_COLORS.get(status, THEME_COLORS["text_muted"])
        self.configure(fg_color=bg_color, width=self._calculate_width(status))
        self.label.configure(text=status)


class ResultRow(ctk.CTkFrame):
    """Single row in the results table."""

    def __init__(
        self,
        master,
        result: AnalysisResult,
        columns: list,
        on_click: Optional[Callable] = None,
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
        self._selected = False
        self._columns = columns
        self._cells: Dict[str, ctk.CTkLabel] = {}
        self._cell_frames: Dict[str, ctk.CTkFrame] = {}
        self._badge: Optional[StatusBadge] = None

        # Prevent frame from shrinking
        self.pack_propagate(False)
        self.grid_propagate(False)

        # Create cells for each column with fixed-width container frames
        for i, (col_id, _, width) in enumerate(columns):
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
                # Badge for status
                self._badge = StatusBadge(cell_frame, result.status)
                self._badge.place(x=8, rely=0.5, anchor="w")
                # Bind click to badge and its children
                self._badge.bind("<Button-1>", self._handle_click)
                self._badge.label.bind("<Button-1>", self._handle_click)
            else:
                # Normal label for other columns
                cell = ctk.CTkLabel(
                    cell_frame,
                    text=self._get_value(col_id, width),
                    anchor="w",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"] - 1),
                    text_color=THEME_COLORS["text_primary"],
                    fg_color="transparent",
                )
                cell.place(x=8, rely=0.5, anchor="w")
                self._cells[col_id] = cell
                # Bind click to cell
                cell.bind("<Button-1>", self._handle_click)

            # Bind click to cell frame
            cell_frame.bind("<Button-1>", self._handle_click)

        # Configure column weights - all fixed width
        for i, (col_id, _, width) in enumerate(columns):
            self.grid_columnconfigure(i, weight=0, minsize=width)

        # Bind click and hover events to row
        self.bind("<Button-1>", self._handle_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

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

    def _handle_click(self, event):
        """Handle click on row or its children."""
        if self.on_click:
            self.on_click(self)

    def _on_enter(self, event):
        """Handle mouse enter (hover)."""
        if not self._selected:
            self.configure(fg_color=THEME_COLORS["row_hover"])

    def _on_leave(self, event):
        """Handle mouse leave."""
        if not self._selected:
            self.configure(fg_color="transparent")

    def set_selected(self, selected: bool):
        """Set the selection state of the row."""
        self._selected = selected
        if selected:
            self.configure(fg_color=THEME_COLORS["row_selected"])
        else:
            self.configure(fg_color="transparent")

    def update_result(self, result: AnalysisResult):
        """Update the row with new result data."""
        self.result = result

        # Update all cells with proper width for truncation
        for col_id, cell in self._cells.items():
            # Find width for this column
            width = 100  # default
            for cid, _, w in self._columns:
                if cid == col_id:
                    width = w
                    break
            cell.configure(text=self._get_value(col_id, width))

        # Update badge
        if self._badge:
            self._badge.update_status(result.status)


class ResultsTable(ctk.CTkFrame):
    """
    A scrollable table for displaying audio analysis results with pill-style status badges.
    """

    COLUMNS = [
        ("filename", "Archivo", 250),
        ("format", "Formato", 70),
        ("duration", "Duración", 80),
        ("declared_bitrate", "Bitrate", 80),
        ("cutoff_frequency", "Frec. Corte", 100),
        ("detected_quality", "Calidad Det.", 100),
        ("status", "Estado", 150),
    ]

    def __init__(
        self,
        master,
        on_selection_changed: Optional[SelectionCallback] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_selection_changed = on_selection_changed
        self._results: Dict[str, AnalysisResult] = {}
        self._rows: Dict[str, ResultRow] = {}
        self._selected_row: Optional[ResultRow] = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the table UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header row
        self.header_frame = ctk.CTkFrame(
            self,
            fg_color=THEME_COLORS["bg_frame"],
            corner_radius=0,
            height=36,
        )
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.pack_propagate(False)
        self.header_frame.grid_propagate(False)

        # Create header labels with fixed-width containers
        for i, (col_id, col_name, width) in enumerate(self.COLUMNS):
            # Container frame with fixed width
            header_cell = ctk.CTkFrame(
                self.header_frame,
                fg_color="transparent",
                width=width,
                height=36,
                corner_radius=0,
            )
            header_cell.grid(row=0, column=i, sticky="nsew")
            header_cell.grid_propagate(False)
            header_cell.pack_propagate(False)

            header_label = ctk.CTkLabel(
                header_cell,
                text=col_name,
                anchor="w",
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
                text_color=THEME_COLORS["text_muted"],
                fg_color="transparent",
            )
            header_label.place(x=8, rely=0.5, anchor="w")

        # Configure header column weights - all fixed
        for i, (col_id, _, width) in enumerate(self.COLUMNS):
            self.header_frame.grid_columnconfigure(i, weight=0, minsize=width)

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

    def _on_row_click(self, row: ResultRow):
        """Handle row click for selection."""
        # Deselect previous row
        if self._selected_row and self._selected_row != row:
            self._selected_row.set_selected(False)

        # Select new row
        row.set_selected(True)
        self._selected_row = row

        # Notify callback
        if self.on_selection_changed:
            self.on_selection_changed(row.result)

    def add_result(self, result: AnalysisResult):
        """Add or update a result in the table."""
        self._results[result.filepath] = result

        # Check if row exists
        if result.filepath in self._rows:
            # Update existing row
            self._rows[result.filepath].update_result(result)
        else:
            # Create new row
            row = ResultRow(
                self.scroll_frame,
                result,
                self.COLUMNS,
                on_click=self._on_row_click,
            )
            row.pack(fill="x", pady=(0, 1))
            self._rows[result.filepath] = row

    def add_results(self, results: List[AnalysisResult]):
        """Add multiple results to the table."""
        for result in results:
            self.add_result(result)

    def clear(self):
        """Clear all results from the table."""
        # Destroy all row widgets
        for row in self._rows.values():
            row.destroy()

        self._rows.clear()
        self._results.clear()
        self._selected_row = None

    def get_selected_result(self) -> Optional[AnalysisResult]:
        """Get the currently selected result."""
        if self._selected_row:
            return self._selected_row.result
        return None

    def get_all_results(self) -> List[AnalysisResult]:
        """Get all results in the table."""
        return list(self._results.values())

    def get_results_count(self) -> int:
        """Get the number of results."""
        return len(self._results)

    def select_first(self):
        """Select the first item in the table."""
        if self._rows:
            first_row = list(self._rows.values())[0]
            self._on_row_click(first_row)
