"""Main application window."""

import os
import threading
import time
import tkinter as tk
from tkinter import filedialog
from typing import List, Optional

import customtkinter as ctk
from PIL import Image

try:
    from tkinterdnd2 import DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

from .results_table import ResultsTable
from .audio_player import AudioPlayer
from .player_controls import PlayerControls
from ..core.analyzer import AnalysisResult, AudioAnalyzer, create_pending_result
from ..utils.constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    THEME_COLORS,
    FONT_FAMILY,
    FONT_SIZES,
    SUPPORTED_FORMATS,
)
from ..utils.file_utils import get_audio_files_from_path


class MainWindow(ctk.CTkFrame):
    """
    Main application window containing all UI components.
    """

    def __init__(
        self,
        master,
        analyzer: AudioAnalyzer,
        audio_player: Optional[AudioPlayer] = None,
        on_result_selected=None,
        on_show_spectrogram=None,
        on_clear=None,
        **kwargs
    ):
        super().__init__(master, fg_color=THEME_COLORS["bg_primary"], **kwargs)

        self.analyzer = analyzer
        self._audio_player = audio_player
        self.on_result_selected = on_result_selected
        self.on_show_spectrogram = on_show_spectrogram
        self.on_clear = on_clear
        self._analysis_thread: Optional[threading.Thread] = None
        # Rate limiting for progress updates (100ms minimum between updates)
        self._last_progress_update = 0
        self._pending_progress_update = None  # Store pending update for final flush

        self._setup_ui()

    def _setup_ui(self):
        """Set up the main window UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top bar with title and controls
        self._setup_top_bar()

        # Main content area
        self._setup_content_area()

        # Player controls (above status bar)
        self._setup_player_controls()

        # Bottom status bar
        self._setup_status_bar()

    def _setup_top_bar(self):
        """Set up the top bar with title and controls."""
        self.top_bar = ctk.CTkFrame(self, height=60, fg_color=THEME_COLORS["bg_primary"])
        self.top_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 0))
        self.top_bar.grid_columnconfigure(1, weight=1)

        # Title
        self.title_label = ctk.CTkLabel(
            self.top_bar,
            text="AudioQual",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["title"], weight="bold"),
            text_color=THEME_COLORS["text_primary"],
        )
        self.title_label.grid(row=0, column=0, padx=16, pady=12)

        # Controls frame (aligned right)
        self.controls_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.controls_frame.grid(row=0, column=2, padx=16, pady=12, sticky="e")

        # Unified button/icon sizes
        ICON_SIZE = 28
        BUTTON_SIZE = 48

        # Load add files icon (using drop-icon.png)
        add_icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "drop-icon.png")
        add_icon_image = Image.open(add_icon_path)
        self._add_icon = ctk.CTkImage(
            light_image=add_icon_image,
            dark_image=add_icon_image,
            size=(ICON_SIZE, ICON_SIZE)
        )

        # Add files button (always visible)
        self.add_files_btn = ctk.CTkButton(
            self.controls_frame,
            text="",
            image=self._add_icon,
            command=self._on_add_files_click,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            corner_radius=12,
            fg_color=THEME_COLORS["bg_elevated"],
            hover_color=THEME_COLORS["primary_dark"],
        )
        self.add_files_btn.grid(row=0, column=0, padx=6)

        # Load clean icon
        clean_icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "clean.jpg")
        clean_icon_image = Image.open(clean_icon_path)
        self._clean_icon = ctk.CTkImage(
            light_image=clean_icon_image,
            dark_image=clean_icon_image,
            size=(ICON_SIZE, ICON_SIZE)
        )

        # Clear button with elevated background
        self.clear_btn = ctk.CTkButton(
            self.controls_frame,
            text="",
            image=self._clean_icon,
            command=self._on_clear,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            corner_radius=12,
            fg_color=THEME_COLORS["bg_elevated"],
            hover_color=THEME_COLORS["primary_dark"],
        )
        self.clear_btn.grid(row=0, column=1, padx=6)

        # Load spectrogram icon
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "spectrum.jpg")
        icon_image = Image.open(icon_path)
        self._toggle_icon = ctk.CTkImage(
            light_image=icon_image,
            dark_image=icon_image,
            size=(ICON_SIZE, ICON_SIZE)
        )

        # Spectrogram window button with elevated background
        self.spectrogram_btn = ctk.CTkButton(
            self.controls_frame,
            text="",
            image=self._toggle_icon,
            command=self._on_show_spectrogram,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            corner_radius=12,
            fg_color=THEME_COLORS["bg_elevated"],
            hover_color=THEME_COLORS["primary_dark"],
        )
        self.spectrogram_btn.grid(row=0, column=2, padx=6)

    def _setup_content_area(self):
        """Set up the main content area."""
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Results table
        self.results_table = ResultsTable(
            self.content_frame,
            on_selection_changed=self._on_selection_changed,
        )
        self.results_table.grid(row=0, column=0, sticky="nsew")

        # Empty state overlay (shown when no files)
        self._setup_empty_state()

        # Set up drag-and-drop on content frame
        self._setup_dnd()

    def _setup_player_controls(self):
        """Set up the audio player controls."""
        if self._audio_player:
            self._player_controls = PlayerControls(
                self,
                audio_player=self._audio_player,
                on_prev=self._on_player_prev,
                on_next=self._on_player_next,
                height=50,
                corner_radius=8,
            )
            self._player_controls.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
        else:
            self._player_controls = None

    def _on_player_prev(self):
        """Handle previous track button."""
        result = self.results_table.select_previous()
        if result:
            self._play_track(result)

    def _on_player_next(self):
        """Handle next track button."""
        result = self.results_table.select_next()
        if result:
            self._play_track(result)

    def _play_track(self, result: AnalysisResult):
        """Load and play a track."""
        print(f"[PERF] {time.time():.3f} | {threading.current_thread().name} | _play_track inicio: {result.filename}")
        if self._audio_player and result:
            self._audio_player.load(result.filepath)
            # Auto-play after a brief delay to allow loading
            self.after(100, self._audio_player.play)
        print(f"[PERF] {time.time():.3f} | {threading.current_thread().name} | _play_track fin")

    def _setup_status_bar(self):
        """Set up the bottom status bar."""
        self.status_bar = ctk.CTkFrame(
            self,
            height=36,
            fg_color=THEME_COLORS["primary_dark"],
            corner_radius=0,
        )
        # Adjust row number since player controls is now row 2
        status_row = 3 if self._audio_player else 2
        self.status_bar.grid(row=status_row, column=0, sticky="ew", padx=16, pady=(0, 16))
        self.status_bar.grid_columnconfigure(1, weight=1)

        # Status label
        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="Listo",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_primary"],
        )
        self.status_label.grid(row=0, column=0, padx=16, pady=8)

        # Progress bar (hidden by default)
        self.progress_bar = ctk.CTkProgressBar(
            self.status_bar,
            width=200,
            height=6,
            corner_radius=3,
            progress_color=THEME_COLORS["accent"],
        )
        self.progress_bar.grid(row=0, column=1, padx=16, pady=8, sticky="e")
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()

        # File count label
        self.count_label = ctk.CTkLabel(
            self.status_bar,
            text="0 archivos",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_primary"],
        )
        self.count_label.grid(row=0, column=2, padx=16, pady=8)

    def _setup_empty_state(self):
        """Set up the empty state overlay shown when no files are loaded."""
        # Load drop icon
        self._drop_icon = None
        drop_icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "drop-icon.png")
        if os.path.exists(drop_icon_path):
            drop_icon_image = Image.open(drop_icon_path)
            self._drop_icon = ctk.CTkImage(
                light_image=drop_icon_image,
                dark_image=drop_icon_image,
                size=(64, 64)
            )

        # Empty state frame - overlays the results table area
        self.empty_state = ctk.CTkFrame(
            self.content_frame,
            fg_color=THEME_COLORS["bg_secondary"],
            corner_radius=0,
        )
        self.empty_state.grid(row=0, column=0, sticky="nsew")
        self.empty_state.grid_columnconfigure(0, weight=1)
        self.empty_state.grid_rowconfigure(0, weight=1)

        # Center content
        center_frame = ctk.CTkFrame(self.empty_state, fg_color="transparent")
        center_frame.grid(row=0, column=0)

        # Icon
        icon_label = ctk.CTkLabel(
            center_frame,
            text="" if self._drop_icon else "",
            image=self._drop_icon,
            font=ctk.CTkFont(size=56),
        )
        icon_label.grid(row=0, column=0, pady=(0, 16))

        # Main text
        main_label = ctk.CTkLabel(
            center_frame,
            text="Arrastra archivos de audio aquí",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["heading"], weight="bold"),
            text_color=THEME_COLORS["text_primary"],
        )
        main_label.grid(row=1, column=0, pady=(0, 8))

        # Formats text
        formats_list = ["MP3", "WAV", "FLAC", "M4A", "AAC", "OGG"]
        formats_str = ", ".join(formats_list)
        sub_label = ctk.CTkLabel(
            center_frame,
            text=formats_str,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_muted"],
        )
        sub_label.grid(row=2, column=0)

    def _setup_dnd(self):
        """Set up drag-and-drop on content frame."""
        if not HAS_DND:
            return

        try:
            self.content_frame.drop_target_register(DND_FILES)
            self.content_frame.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass

    def _on_drop(self, event):
        """Handle file drop on content frame."""
        data = event.data

        # Parse dropped files (format varies by platform)
        if data.startswith("{"):
            # Windows format with braces
            files = []
            in_brace = False
            current = ""
            for char in data:
                if char == "{":
                    in_brace = True
                elif char == "}":
                    in_brace = False
                    if current:
                        files.append(current)
                    current = ""
                elif in_brace:
                    current += char
                elif char == " " and not in_brace:
                    if current:
                        files.append(current)
                    current = ""
                else:
                    current += char
            if current:
                files.append(current)
        else:
            # Unix format - space separated
            files = data.split()

        # Process files in background thread to avoid UI blocking
        self._process_paths_async(files)

    def _on_add_files_click(self):
        """Handle add files button click - show menu."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Archivos", command=self._on_select_files)
        menu.add_command(label="Carpeta", command=self._on_select_folder)

        x = self.add_files_btn.winfo_rootx()
        y = self.add_files_btn.winfo_rooty() + self.add_files_btn.winfo_height()
        menu.tk_popup(x, y)

    def _on_select_files(self):
        """Open file selection dialog."""
        filetypes = [
            ("Audio files", " ".join(f"*{ext}" for ext in SUPPORTED_FORMATS)),
            ("All files", "*.*"),
        ]

        files = filedialog.askopenfilenames(
            title="Seleccionar archivos de audio",
            filetypes=filetypes,
        )

        if files:
            self._process_paths(list(files))

    def _on_select_folder(self):
        """Open folder selection dialog."""
        folder = filedialog.askdirectory(
            title="Seleccionar carpeta con archivos de audio",
        )

        if folder:
            self._process_paths([folder])

    def _process_paths(self, paths: List[str]):
        """Process a list of file/folder paths (sync version for file dialog)."""
        self._process_paths_async(paths)

    def _process_paths_async(self, paths: List[str]):
        """Process paths in background thread to avoid UI blocking."""
        # Show loading status
        self.status_label.configure(text="Escaneando archivos...")

        def scan_files():
            all_files = []
            for path in paths:
                files = get_audio_files_from_path(path)
                all_files.extend(files)

            # Remove duplicates while preserving order
            seen = set()
            unique_files = []
            for f in all_files:
                if f not in seen:
                    seen.add(f)
                    unique_files.append(f)

            # Return to main thread
            self.after(0, lambda: self._on_files_scanned(unique_files))

        threading.Thread(target=scan_files, daemon=True).start()

    def _on_files_scanned(self, files: List[str]):
        """Handle completion of file scanning (main thread)."""
        self.status_label.configure(text="Listo")
        if files:
            self._on_files_added(files)

    def _on_files_added(self, files: List[str]):
        """Handle files being added via drop or selection."""
        # Add pending results to table
        for filepath in files:
            self.results_table.add_result(create_pending_result(filepath))

        self._update_count()
        self._update_empty_state_visibility()
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
        """Handle analysis progress updates (called from worker thread).

        Rate-limited to max 1 UI update per 100ms to prevent event loop saturation.
        """
        print(f"[PERF] {time.time():.3f} | {threading.current_thread().name} | Callback recibido: {current_file}")
        current_time = time.time() * 1000  # ms
        is_final = completed >= total

        def update_ui():
            print(f"[PERF] {time.time():.3f} | {threading.current_thread().name} | Actualizando tabla: {current_file}")
            if result:
                self.results_table.add_result(result)

            progress = completed / total if total > 0 else 0
            self.progress_bar.set(progress)
            self.status_label.configure(
                text=f"Analizando: {current_file} ({completed}/{total})"
            )
            self._update_count()
            self._last_progress_update = time.time() * 1000

        # Always process the final update immediately
        if is_final:
            self.after(0, update_ui)
            return

        # Rate limit: only update UI if 100ms has passed since last update
        if current_time - self._last_progress_update >= 100:
            self.after(0, update_ui)
        else:
            # Store pending update - will be flushed on final or next allowed update
            # Still add result to table immediately to not lose data
            if result:
                self.after(0, lambda r=result: self.results_table.add_result(r))

    def _set_analyzing_state(self, is_analyzing: bool):
        """Set UI state for analyzing/ready."""
        if is_analyzing:
            self.progress_bar.grid()
            self.progress_bar.set(0)
            self.add_files_btn.configure(state="disabled")
        else:
            self.progress_bar.grid_remove()
            self.status_label.configure(text="Listo")
            self.add_files_btn.configure(state="normal")
            # Force event loop to process pending events (fixes macOS tkinter freeze)
            # Schedule multiple update_idletasks to ensure event loop wakes up
            print(f"[PERF] {time.time():.3f} | {threading.current_thread().name} | Análisis completado, forzando wakeup del event loop")
            root = self.winfo_toplevel()
            root.update_idletasks()
            # Schedule additional wakeups to ensure event loop stays active
            for i in range(5):
                self.after(100 * (i + 1), root.update_idletasks)

    def _on_selection_changed(self, result: Optional[AnalysisResult]):
        """Handle result selection change."""
        print(f"[PERF] {time.time():.3f} | {threading.current_thread().name} | _on_selection_changed inicio: {result.filename if result else 'None'}")
        if self.on_result_selected:
            self.on_result_selected(result)

        # Load and play the selected track
        if result and self._audio_player:
            print(f"[PERF] {time.time():.3f} | {threading.current_thread().name} | _on_selection_changed -> _play_track")
            self._play_track(result)
        print(f"[PERF] {time.time():.3f} | {threading.current_thread().name} | _on_selection_changed fin")

    def _on_clear(self):
        """Handle clear button click."""
        if self.analyzer.is_running():
            self.analyzer.cancel()

        # Stop playback and reset player
        if self._audio_player:
            self._audio_player.stop()
        if self._player_controls:
            self._player_controls.reset()

        self.results_table.clear()
        self._update_count()
        self._update_empty_state_visibility()

        if self.on_result_selected:
            self.on_result_selected(None)

        if self.on_clear:
            self.on_clear()

    def _update_empty_state_visibility(self):
        """Update empty state visibility based on file count."""
        count = self.results_table.get_results_count()
        if count > 0:
            # Files loaded: hide empty state, show results table
            self.empty_state.grid_remove()
            self.results_table.grid()
        else:
            # No files: show empty state over results table
            self.results_table.grid()
            self.empty_state.grid(row=0, column=0, sticky="nsew")

    def _update_count(self):
        """Update the file count label."""
        count = self.results_table.get_results_count()
        text = f"{count} archivo{'s' if count != 1 else ''}"
        self.count_label.configure(text=text)

    def _on_show_spectrogram(self):
        """Handle spectrogram button click."""
        if self.on_show_spectrogram:
            self.on_show_spectrogram()
