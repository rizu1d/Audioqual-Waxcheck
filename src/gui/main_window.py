"""Main application window."""

import threading
from typing import List, Optional

import customtkinter as ctk

from .file_drop_zone import FileDropZone
from .results_table import ResultsTable
from ..core.analyzer import AnalysisResult, AudioAnalyzer, create_pending_result
from ..utils.constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
)


class MainWindow(ctk.CTkFrame):
    """
    Main application window containing all UI components.
    """

    def __init__(
        self,
        master,
        analyzer: AudioAnalyzer,
        on_result_selected=None,
        on_export_requested=None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.analyzer = analyzer
        self.on_result_selected = on_result_selected
        self.on_export_requested = on_export_requested
        self._analysis_thread: Optional[threading.Thread] = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the main window UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top bar with title and controls
        self._setup_top_bar()

        # Main content area
        self._setup_content_area()

        # Bottom status bar
        self._setup_status_bar()

    def _setup_top_bar(self):
        """Set up the top bar with title and controls."""
        self.top_bar = ctk.CTkFrame(self, height=50)
        self.top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        self.top_bar.grid_columnconfigure(1, weight=1)

        # Title
        self.title_label = ctk.CTkLabel(
            self.top_bar,
            text="AudioQual",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.title_label.grid(row=0, column=0, padx=10, pady=10)

        # Subtitle
        self.subtitle_label = ctk.CTkLabel(
            self.top_bar,
            text="Analizador de calidad de audio",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60"),
        )
        self.subtitle_label.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # Controls frame
        self.controls_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.controls_frame.grid(row=0, column=2, padx=10, pady=10)

        # Clear button
        self.clear_btn = ctk.CTkButton(
            self.controls_frame,
            text="Limpiar",
            command=self._on_clear,
            width=100,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
        )
        self.clear_btn.grid(row=0, column=0, padx=5)

        # Export button
        self.export_btn = ctk.CTkButton(
            self.controls_frame,
            text="Exportar",
            command=self._on_export,
            width=100,
        )
        self.export_btn.grid(row=0, column=1, padx=5)

    def _setup_content_area(self):
        """Set up the main content area."""
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=0)
        self.content_frame.grid_rowconfigure(1, weight=1)

        # Drop zone (collapsible when files are loaded)
        self.drop_zone = FileDropZone(
            self.content_frame,
            on_files_added=self._on_files_added,
            height=200,
        )
        self.drop_zone.grid(row=0, column=0, sticky="ew")

        # Results table
        self.results_table = ResultsTable(
            self.content_frame,
            on_selection_changed=self._on_selection_changed,
        )
        self.results_table.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

    def _setup_status_bar(self):
        """Set up the bottom status bar."""
        self.status_bar = ctk.CTkFrame(self, height=30)
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.status_bar.grid_columnconfigure(1, weight=1)

        # Status label
        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="Listo",
            font=ctk.CTkFont(size=12),
        )
        self.status_label.grid(row=0, column=0, padx=10, pady=5)

        # Progress bar (hidden by default)
        self.progress_bar = ctk.CTkProgressBar(self.status_bar, width=200)
        self.progress_bar.grid(row=0, column=1, padx=10, pady=5, sticky="e")
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()

        # File count label
        self.count_label = ctk.CTkLabel(
            self.status_bar,
            text="0 archivos",
            font=ctk.CTkFont(size=12),
        )
        self.count_label.grid(row=0, column=2, padx=10, pady=5)

    def _on_files_added(self, files: List[str]):
        """Handle files being added via drop or selection."""
        # Add pending results to table
        for filepath in files:
            self.results_table.add_result(create_pending_result(filepath))

        self._update_count()
        self._start_analysis(files)

    def _start_analysis(self, files: List[str]):
        """Start batch analysis in background thread."""
        if self._analysis_thread and self._analysis_thread.is_alive():
            return

        self._set_analyzing_state(True)

        def run_analysis():
            self.analyzer.analyze_batch(
                files,
                progress_callback=self._on_analysis_progress,
            )
            self.after(0, lambda: self._set_analyzing_state(False))

        self._analysis_thread = threading.Thread(target=run_analysis, daemon=True)
        self._analysis_thread.start()

    def _on_analysis_progress(
        self,
        completed: int,
        total: int,
        current_file: str,
        result: Optional[AnalysisResult],
    ):
        """Handle analysis progress updates (called from worker thread)."""
        def update_ui():
            if result:
                self.results_table.add_result(result)

            progress = completed / total if total > 0 else 0
            self.progress_bar.set(progress)
            self.status_label.configure(
                text=f"Analizando: {current_file} ({completed}/{total})"
            )
            self._update_count()

        self.after(0, update_ui)

    def _set_analyzing_state(self, is_analyzing: bool):
        """Set UI state for analyzing/ready."""
        if is_analyzing:
            self.progress_bar.grid()
            self.progress_bar.set(0)
            self.drop_zone.set_enabled(False)
            self.export_btn.configure(state="disabled")
        else:
            self.progress_bar.grid_remove()
            self.status_label.configure(text="Listo")
            self.drop_zone.set_enabled(True)
            self.export_btn.configure(state="normal")

    def _on_selection_changed(self, result: Optional[AnalysisResult]):
        """Handle result selection change."""
        if self.on_result_selected:
            self.on_result_selected(result)

    def _on_clear(self):
        """Handle clear button click."""
        if self.analyzer.is_running():
            self.analyzer.cancel()

        self.results_table.clear()
        self._update_count()

        if self.on_result_selected:
            self.on_result_selected(None)

    def _on_export(self):
        """Handle export button click."""
        results = self.results_table.get_all_results()
        if results and self.on_export_requested:
            self.on_export_requested(results)

    def _update_count(self):
        """Update the file count label."""
        count = self.results_table.get_results_count()
        text = f"{count} archivo{'s' if count != 1 else ''}"
        self.count_label.configure(text=text)
