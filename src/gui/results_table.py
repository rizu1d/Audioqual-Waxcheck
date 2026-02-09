"""Results table for displaying analysis results with pill-style status badges."""

import tkinter as tk
from pathlib import Path
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
        # Store as mutable list of lists so widths can be updated
        self._columns = [list(col) for col in columns]
        self._cells: Dict[str, ctk.CTkLabel] = {}
        self._cell_frames: Dict[str, ctk.CTkFrame] = {}
        self._badge: Optional[StatusBadge] = None
        self._hover_state = False  # Track current hover state to avoid redundant configure calls

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
                # Badge for status
                self._badge = StatusBadge(cell_frame, result.status)
                self._badge.place(x=8, rely=0.5, anchor="w")
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

        # Configure column weights - all fixed width
        for i, (col_id, _, width) in enumerate(self._columns):
            self.grid_columnconfigure(i, weight=0, minsize=width)

        # Bind click/hover events to the row
        self.bind("<Button-1>", self._handle_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

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
        """Bind click events to all descendants of the widget."""
        for child in widget.winfo_children():
            child.bind("<Button-1>", self._handle_click)
            self._bind_click_recursive(child)

    def _handle_click(self, event):
        """Handle click on row or its children."""
        if self.on_click:
            self.on_click(self)
        return "break"  # Prevent event from bubbling to other handlers

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
        ("detected_quality", "Calidad Det.", 100),
        ("status", "Estado", 170),
    ]

    MIN_WIDTHS = [100, 50, 60, 60, 70, 70, 90]

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

        # Mutable column widths (source of truth for current widths)
        self._column_widths: List[int] = [w for _, _, w in self.COLUMNS]

        # Resize state
        self._header_cells: List[ctk.CTkFrame] = []
        self._grips: List[tk.Frame] = []
        self._resize_col: int = -1
        self._resize_start_x: int = 0
        self._resize_start_width: int = 0
        self._resize_throttle_id = None

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
            fg_color=THEME_COLORS["bg_frame"],
            corner_radius=0,
            height=36,
        )
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.pack_propagate(False)
        self.header_frame.grid_propagate(False)

        # Create header labels with fixed-width containers
        self._header_cells = []
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
            self._header_cells.append(header_cell)

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

        # Create resize grips between header cells
        self._create_grips()

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

    def _create_grips(self):
        """Create drag handles between header cells for column resizing."""
        self._grips = []
        for i in range(len(self.COLUMNS) - 1):
            # Use plain tk.Frame for reliable event capture
            grip = tk.Frame(
                self.header_frame,
                width=8,
                cursor="sb_h_double_arrow",
                bg=THEME_COLORS["bg_frame"],
                bd=0,
                highlightthickness=0,
            )

            # Position at the border between column i and i+1
            x = sum(self._column_widths[:i + 1]) - 4
            grip.place(x=x, y=0, width=8, relheight=1.0)

            # Bind drag events
            col_index = i  # capture in closure
            grip.bind("<ButtonPress-1>", lambda e, c=col_index: self._on_grip_press(e, c))
            grip.bind("<B1-Motion>", lambda e, c=col_index: self._on_grip_drag(e, c))
            grip.bind("<ButtonRelease-1>", lambda e, c=col_index: self._on_grip_release(e, c))

            self._grips.append(grip)

    def _reposition_grips(self):
        """Reposition all grip handles based on current column widths."""
        for i, grip in enumerate(self._grips):
            x = sum(self._column_widths[:i + 1]) - 4
            grip.place_configure(x=x)

    def _on_grip_press(self, event, col_index: int):
        """Start column resize drag."""
        self._resize_col = col_index
        self._resize_start_x = event.x_root
        self._resize_start_width = self._column_widths[col_index]

    def _on_grip_drag(self, event, col_index: int):
        """Handle column resize drag motion (throttled)."""
        if self._resize_col < 0:
            return

        dx = event.x_root - self._resize_start_x
        new_width = max(self.MIN_WIDTHS[col_index], self._resize_start_width + dx)
        self._column_widths[col_index] = new_width

        # Throttle UI updates to ~30ms
        if self._resize_throttle_id is None:
            self._resize_throttle_id = self.after(30, self._apply_resize)

    def _on_grip_release(self, event, col_index: int):
        """End column resize drag."""
        if self._resize_col < 0:
            return

        # Cancel pending throttled update
        if self._resize_throttle_id is not None:
            self.after_cancel(self._resize_throttle_id)
            self._resize_throttle_id = None

        # Final width update
        dx = event.x_root - self._resize_start_x
        self._column_widths[col_index] = max(
            self.MIN_WIDTHS[col_index], self._resize_start_width + dx
        )

        self._resize_col = -1
        self._apply_column_widths()
        self._reposition_grips()
        self._refresh_all_text()

    def _apply_resize(self):
        """Apply column width change during drag (called by throttle timer)."""
        self._resize_throttle_id = None
        self._apply_column_widths()
        self._reposition_grips()

    def _apply_column_widths(self):
        """Propagate current column widths to header and all rows."""
        for i, (col_id, _, _) in enumerate(self.COLUMNS):
            width = self._column_widths[i]

            # Update header
            self._header_cells[i].configure(width=width)
            self.header_frame.grid_columnconfigure(i, minsize=width)

            # Update all rows
            for row in self._rows.values():
                cell_frame = row._cell_frames.get(col_id)
                if cell_frame:
                    cell_frame.configure(width=width)
                row.grid_columnconfigure(i, minsize=width)
                # Keep row's _columns in sync
                row._columns[i][2] = width

    def _refresh_all_text(self):
        """Re-truncate text in all rows based on current column widths."""
        for row in self._rows.values():
            row.refresh_text()

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
            # Create new row with current column widths
            row = ResultRow(
                self.scroll_frame,
                result,
                self._current_columns(),
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
        # Get all rows to destroy
        rows_to_destroy = list(self._rows.values())

        # Clear data structures immediately for responsiveness
        self._rows.clear()
        self._results.clear()
        self._selected_row = None

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

    def select_next(self) -> Optional[AnalysisResult]:
        """
        Select the next item in the table.

        Returns:
            The newly selected result, or None if at end or no items.
        """
        if not self._rows:
            return None

        rows_list = list(self._rows.values())

        if self._selected_row is None:
            # Nothing selected, select first
            self._on_row_click(rows_list[0])
            self.scroll_to_row(rows_list[0])
            return rows_list[0].result

        # Find current index
        try:
            current_index = rows_list.index(self._selected_row)
        except ValueError:
            return None

        # Select next if available
        next_index = current_index + 1
        if next_index < len(rows_list):
            self._on_row_click(rows_list[next_index])
            self.scroll_to_row(rows_list[next_index])
            return rows_list[next_index].result

        return None  # At end of list

    def select_previous(self) -> Optional[AnalysisResult]:
        """
        Select the previous item in the table.

        Returns:
            The newly selected result, or None if at start or no items.
        """
        if not self._rows:
            return None

        rows_list = list(self._rows.values())

        if self._selected_row is None:
            # Nothing selected, select last
            self._on_row_click(rows_list[-1])
            self.scroll_to_row(rows_list[-1])
            return rows_list[-1].result

        # Find current index
        try:
            current_index = rows_list.index(self._selected_row)
        except ValueError:
            return None

        # Select previous if available
        prev_index = current_index - 1
        if prev_index >= 0:
            self._on_row_click(rows_list[prev_index])
            self.scroll_to_row(rows_list[prev_index])
            return rows_list[prev_index].result

        return None  # At start of list

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
        rows_list = list(self._rows.values())
        was_selected = self._selected_row == row

        # Find index before removing
        try:
            index = rows_list.index(row)
        except ValueError:
            index = -1

        # Remove from data structures
        del self._rows[filepath]
        del self._results[filepath]
        row.destroy()

        if not was_selected:
            # Selection unchanged, return current selection
            return self._selected_row.result if self._selected_row else None

        # Was selected — pick new selection
        self._selected_row = None
        remaining = list(self._rows.values())
        if not remaining:
            if self.on_selection_changed:
                self.on_selection_changed(None)
            return None

        # Prefer same index (next item), fall back to last
        new_index = min(index, len(remaining) - 1)
        new_row = remaining[new_index]
        self._on_row_click(new_row)
        self.scroll_to_row(new_row)
        return new_row.result

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

        # Update the dataclass fields
        result.filepath = new_filepath
        result.filename = Path(new_filepath).name

        # Re-insert under new key
        self._results[new_filepath] = result
        self._rows[new_filepath] = row

        # Refresh the row display
        row.update_result(result)

    def get_ordered_filepaths(self) -> List[str]:
        """
        Get all filepaths in display order.

        Returns:
            List of filepaths in the order they appear in the table.
        """
        return [row.result.filepath for row in self._rows.values()]
