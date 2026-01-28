"""Results table for displaying analysis results."""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from ..core.analyzer import AnalysisResult
from ..utils.constants import STATUS_COLORS
from ..utils.file_utils import format_duration


SelectionCallback = Callable[[Optional[AnalysisResult]], None]


class ResultsTable(ctk.CTkFrame):
    """
    A scrollable table for displaying audio analysis results.
    """

    COLUMNS = [
        ("filename", "Archivo", 250),
        ("format", "Formato", 70),
        ("duration", "Duracion", 80),
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
        super().__init__(master, **kwargs)

        self.on_selection_changed = on_selection_changed
        self._results: Dict[str, AnalysisResult] = {}
        self._selected_filepath: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the table UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create frame for treeview
        self.tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tree_frame.grid(row=0, column=0, sticky="nsew")
        self.tree_frame.grid_columnconfigure(0, weight=1)
        self.tree_frame.grid_rowconfigure(0, weight=1)

        # Style for treeview
        style = ttk.Style()
        style.theme_use("default")

        # Configure treeview colors
        style.configure(
            "Results.Treeview",
            background="#2b2b2b",
            foreground="white",
            fieldbackground="#2b2b2b",
            rowheight=28,
        )
        style.configure(
            "Results.Treeview.Heading",
            background="#1f1f1f",
            foreground="white",
            relief="flat",
        )
        style.map(
            "Results.Treeview",
            background=[("selected", "#3b3b3b")],
            foreground=[("selected", "white")],
        )

        # Create treeview
        columns = [col[0] for col in self.COLUMNS]
        self.tree = ttk.Treeview(
            self.tree_frame,
            columns=columns,
            show="headings",
            style="Results.Treeview",
            selectmode="browse",
        )

        # Configure columns
        for col_id, col_name, col_width in self.COLUMNS:
            self.tree.heading(col_id, text=col_name, anchor="w")
            self.tree.column(col_id, width=col_width, minwidth=50, anchor="w")

        # Scrollbars
        self.vsb = ttk.Scrollbar(
            self.tree_frame,
            orient="vertical",
            command=self.tree.yview,
        )
        self.hsb = ttk.Scrollbar(
            self.tree_frame,
            orient="horizontal",
            command=self.tree.xview,
        )

        self.tree.configure(
            yscrollcommand=self.vsb.set,
            xscrollcommand=self.hsb.set,
        )

        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb.grid(row=1, column=0, sticky="ew")

        # Bind selection event
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Create tags for status colors
        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(status, foreground=color)

    def _on_select(self, event):
        """Handle row selection."""
        selection = self.tree.selection()

        if not selection:
            self._selected_filepath = None
            if self.on_selection_changed:
                self.on_selection_changed(None)
            return

        item_id = selection[0]
        filepath = self.tree.item(item_id, "values")[0]  # filename is first, but we use item id

        # The item id is the filepath
        self._selected_filepath = item_id

        if self.on_selection_changed and item_id in self._results:
            self.on_selection_changed(self._results[item_id])

    def add_result(self, result: AnalysisResult):
        """Add or update a result in the table."""
        self._results[result.filepath] = result

        # Format quality display with uncertainty indicator
        quality_display = result.detected_quality if result.detected_quality else "-"
        if result.is_uncertain and result.detected_quality:
            quality_display = f"{result.detected_quality} (?)"

        # Format values
        values = (
            result.filename,
            result.format,
            format_duration(result.duration) if result.duration > 0 else "-",
            f"{result.declared_bitrate} kbps" if result.declared_bitrate else "-",
            f"{result.cutoff_frequency_khz:.1f} kHz" if result.cutoff_frequency_khz > 0 else "-",
            quality_display,
            result.status,
        )

        # Check if item exists
        if self.tree.exists(result.filepath):
            self.tree.item(result.filepath, values=values, tags=(result.status,))
        else:
            self.tree.insert(
                "",
                "end",
                iid=result.filepath,
                values=values,
                tags=(result.status,),
            )

    def add_results(self, results: List[AnalysisResult]):
        """Add multiple results to the table."""
        for result in results:
            self.add_result(result)

    def clear(self):
        """Clear all results from the table."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._results.clear()
        self._selected_filepath = None

    def get_selected_result(self) -> Optional[AnalysisResult]:
        """Get the currently selected result."""
        if self._selected_filepath and self._selected_filepath in self._results:
            return self._results[self._selected_filepath]
        return None

    def get_all_results(self) -> List[AnalysisResult]:
        """Get all results in the table."""
        return list(self._results.values())

    def get_results_count(self) -> int:
        """Get the number of results."""
        return len(self._results)

    def select_first(self):
        """Select the first item in the table."""
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])
