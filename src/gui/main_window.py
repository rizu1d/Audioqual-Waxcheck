"""Main application window."""

import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Optional

import customtkinter as ctk

try:
    from tkinterdnd2 import DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

from .results_table import ResultsTable
from .audio_player import AudioPlayer
from .player_controls import PlayerControls
from .metadata_editor import MetadataEditor
from .settings_window import SettingsWindow
from ..core.analyzer import AnalysisResult, AudioAnalyzer, create_pending_result
from ..utils.constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    THEME_COLORS,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    FONT_SIZES,
    SUPPORTED_FORMATS,
)
from ..utils.file_utils import get_audio_files_from_path
from ..utils.icon_utils import load_svg_icon
from ..utils.tk_utils import schedule_callback_from_thread


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
        on_metadata_saved=None,
        on_toggle_watcher=None,
        **kwargs
    ):
        super().__init__(master, fg_color=THEME_COLORS["bg_primary"], **kwargs)

        self.analyzer = analyzer
        self._audio_player = audio_player
        self.on_result_selected = on_result_selected
        self.on_show_spectrogram = on_show_spectrogram
        self.on_clear = on_clear
        self.on_metadata_saved = on_metadata_saved
        self.on_toggle_watcher = on_toggle_watcher
        self._analysis_thread: Optional[threading.Thread] = None
        # Rate limiting for progress updates (100ms minimum between updates)
        self._last_progress_update = 0
        self._pending_progress_update = None  # Store pending update for final flush
        self._pending_analysis_queue: List[str] = []
        self._pulse_active = False

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

        # Logo
        self._logo_icon = load_svg_icon("logo-waxcheckV2.svg", 64)
        self.title_label = ctk.CTkLabel(
            self.top_bar,
            text="",
            image=self._logo_icon,
        )
        self.title_label.grid(row=0, column=0, padx=0, pady=12)

        # Controls frame (aligned right)
        self.controls_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.controls_frame.grid(row=0, column=2, padx=0, pady=12, sticky="e")

        # Unified button/icon sizes
        ICON_SIZE = 44
        BUTTON_SIZE = 48

        # Load add files icon
        self._add_icon = load_svg_icon("drop-iconV2.svg", ICON_SIZE)

        # Add files button (always visible)
        self.add_files_btn = ctk.CTkButton(
            self.controls_frame,
            text="",
            image=self._add_icon,
            command=self._on_add_files_click,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            corner_radius=9,
            fg_color=THEME_COLORS["toolbar_btn"],
            hover_color=THEME_COLORS["toolbar_btn_hover"],
        )
        self.add_files_btn._canvas.configure(takefocus=False)
        self.add_files_btn.grid(row=0, column=0, padx=(0, 6))

        # Load watcher icons (OFF = initial state, ON = when active)
        self._watcher_icon_off = load_svg_icon("watcher-icon-OFF.svg", ICON_SIZE)
        self._watcher_icon_on = load_svg_icon("watcher-iconV3.svg", ICON_SIZE)
        self._watcher_icon = self._watcher_icon_off

        # Watcher button
        self.watcher_btn = ctk.CTkButton(
            self.controls_frame,
            text="",
            image=self._watcher_icon,
            command=self._on_toggle_watcher,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            corner_radius=9,
            fg_color=THEME_COLORS["toolbar_btn"],
            hover_color=THEME_COLORS["toolbar_btn_hover"],
        )
        self.watcher_btn._canvas.configure(takefocus=False)
        self.watcher_btn.grid(row=0, column=1, padx=6)

        # Load clean icon
        self._clean_icon = load_svg_icon("clean-iconV2.svg", ICON_SIZE)

        # Clear button
        self.clear_btn = ctk.CTkButton(
            self.controls_frame,
            text="",
            image=self._clean_icon,
            command=self._on_clear,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            corner_radius=9,
            fg_color=THEME_COLORS["toolbar_btn"],
            hover_color=THEME_COLORS["toolbar_btn_hover"],
        )
        self.clear_btn._canvas.configure(takefocus=False)
        self.clear_btn.grid(row=0, column=2, padx=6)

        # Load spectrogram icon
        self._toggle_icon = load_svg_icon("spectrum-iconV2.svg", ICON_SIZE)

        # Spectrogram window button
        self.spectrogram_btn = ctk.CTkButton(
            self.controls_frame,
            text="",
            image=self._toggle_icon,
            command=self._on_show_spectrogram,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            corner_radius=9,
            fg_color=THEME_COLORS["toolbar_btn"],
            hover_color=THEME_COLORS["toolbar_btn_hover"],
        )
        self.spectrogram_btn._canvas.configure(takefocus=False)
        self.spectrogram_btn.grid(row=0, column=3, padx=6)

        # Load metadata icon
        self._meta_icon = load_svg_icon("Metadata-iconV3.svg", ICON_SIZE)

        # Metadata editor button
        self.metadata_btn = ctk.CTkButton(
            self.controls_frame,
            text="",
            image=self._meta_icon,
            command=self._on_edit_metadata,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            corner_radius=9,
            fg_color=THEME_COLORS["toolbar_btn"],
            hover_color=THEME_COLORS["toolbar_btn_hover"],
        )
        self.metadata_btn._canvas.configure(takefocus=False)
        self.metadata_btn.grid(row=0, column=4, padx=6)

        # Settings icon
        self._settings_icon = load_svg_icon("settings-iconV3.svg", ICON_SIZE)

        # Settings button
        self.settings_btn = ctk.CTkButton(
            self.controls_frame,
            text="",
            image=self._settings_icon,
            command=self._on_open_settings,
            width=BUTTON_SIZE,
            height=BUTTON_SIZE,
            corner_radius=9,
            fg_color=THEME_COLORS["toolbar_btn"],
            hover_color=THEME_COLORS["toolbar_btn_hover"],
        )
        self.settings_btn._canvas.configure(takefocus=False)
        self.settings_btn.grid(row=0, column=5, padx=(6, 0))

    def _setup_content_area(self):
        """Set up the main content area."""
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(4, 16))
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Results table
        self.results_table = ResultsTable(
            self.content_frame,
            on_selection_changed=self._on_selection_changed,
            on_context_menu=self._show_context_menu,
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
        """Load and play a track (explicit play from prev/next buttons)."""
        if self._audio_player and result:
            self._audio_player.load(result.filepath)
            self.after(100, self._audio_player.play)

    def _setup_status_bar(self):
        """Set up the bottom status bar."""
        self.status_bar = ctk.CTkFrame(
            self,
            height=36,
            fg_color=THEME_COLORS["bg_secondary"],
            corner_radius=0,
            border_width=1,
            border_color=THEME_COLORS["border"],
        )
        # Adjust row number since player controls is now row 2
        status_row = 3 if self._audio_player else 2
        self.status_bar.grid(row=status_row, column=0, sticky="ew", padx=16, pady=(0, 16))
        self.status_bar.grid_columnconfigure(2, weight=1)

        # Green status dot (always visible)
        self._status_dot = ctk.CTkLabel(
            self.status_bar,
            text="\u25CF",
            font=ctk.CTkFont(size=8),
            text_color="#6BCB77",
            width=12,
        )
        self._status_dot.grid(row=0, column=0, padx=(16, 0), pady=8)

        # Watcher indicator (hidden by default, appears after status dot)
        self._watcher_indicator = ctk.CTkLabel(
            self.status_bar,
            text="\u25CF",
            font=ctk.CTkFont(size=10),
            text_color="#5DB88C",
            width=16,
        )
        # Will be shown in column 0 when watcher active (replaces status dot)
        self._watcher_indicator.grid(row=0, column=0, padx=(16, 0), pady=8)
        self._watcher_indicator.grid_remove()

        # Status label — green for "Listo"
        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="Listo",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["small"]),
            text_color="#6BCB77",
        )
        self.status_label.grid(row=0, column=1, padx=(4, 16), pady=8)

        # Progress bar (hidden by default)
        self.progress_bar = ctk.CTkProgressBar(
            self.status_bar,
            width=200,
            height=6,
            corner_radius=3,
            progress_color=THEME_COLORS["accent"],
        )
        self.progress_bar.grid(row=0, column=2, padx=16, pady=8, sticky="e")
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()

        # File count label — Space Mono, muted color
        self.count_label = ctk.CTkLabel(
            self.status_bar,
            text="0 archivos",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11),
            text_color=THEME_COLORS["text_muted"],
        )
        self.count_label.grid(row=0, column=3, padx=16, pady=8)

    def _setup_empty_state(self):
        """Set up the empty state overlay shown when no files are loaded."""
        # Load drop icon
        self._drop_icon = load_svg_icon("drop-iconV2.svg", 64)

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
        """Set up drag-and-drop on content frame and results table."""
        if not HAS_DND:
            return

        try:
            # Register on content_frame (for empty state)
            self.content_frame.drop_target_register(DND_FILES)
            self.content_frame.dnd_bind("<<Drop>>", self._on_drop)

            # Register on results table scroll_frame (for when table has files)
            self.results_table.scroll_frame.drop_target_register(DND_FILES)
            self.results_table.scroll_frame.dnd_bind("<<Drop>>", self._on_drop)
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
        # Get existing filepaths to avoid duplicates
        existing_filepaths = set(self.results_table.get_ordered_filepaths())

        self.status_label.configure(text="Escaneando archivos...")

        def scan_files():
            all_files = []
            for path in paths:
                files = get_audio_files_from_path(path)
                all_files.extend(files)

            # Remove duplicates within batch AND against existing files
            seen = set(existing_filepaths)  # Start with existing
            unique_files = []
            for f in all_files:
                if f not in seen:
                    seen.add(f)
                    unique_files.append(f)

            # Return to main thread
            schedule_callback_from_thread(self, self._on_files_scanned, unique_files)

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
            self._pending_analysis_queue.extend(files)
            return

        self._set_analyzing_state(True)

        def run_analysis():
            self.analyzer.analyze_batch(
                files,
                progress_callback=self._on_analysis_progress,
            )
            schedule_callback_from_thread(self, self._on_analysis_complete)

        self._analysis_thread = threading.Thread(target=run_analysis, daemon=True)
        self._analysis_thread.start()

    def _on_analysis_complete(self):
        """Handle analysis batch completion. Drains pending queue if needed."""
        self._set_analyzing_state(False)
        if self._pending_analysis_queue:
            queued = self._pending_analysis_queue[:]
            self._pending_analysis_queue.clear()
            self._start_analysis(queued)

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
        import time
        current_time = time.time() * 1000  # ms
        is_final = completed >= total

        def update_ui():
            if result:
                self.results_table.add_result(result)
                # Free heavy spectrogram data after UI display (~100-200MB per file)
                result.frequency_analysis = None

            progress = completed / total if total > 0 else 0
            self.progress_bar.set(progress)
            self.status_label.configure(
                text=f"Analizando: {current_file} ({completed}/{total})"
            )
            self._update_count()
            self._last_progress_update = time.time() * 1000

        # Always process the final update immediately
        if is_final:
            schedule_callback_from_thread(self, update_ui)
            return

        # Rate limit: only update UI if 100ms has passed since last update
        if current_time - self._last_progress_update >= 100:
            schedule_callback_from_thread(self, update_ui)
        else:
            # Store pending update - will be flushed on final or next allowed update
            # Still add result to table immediately to not lose data
            if result:
                def _add_result_and_free(r):
                    self.results_table.add_result(r)
                    # Free heavy spectrogram data after UI display
                    r.frequency_analysis = None
                schedule_callback_from_thread(self, _add_result_and_free, result)

    def _set_analyzing_state(self, is_analyzing: bool):
        """Set UI state for analyzing/ready."""
        if is_analyzing:
            self.progress_bar.grid()
            self.progress_bar.set(0)
            self.add_files_btn.configure(state="disabled")
            self._status_dot.configure(text_color=THEME_COLORS["accent"])
            self.status_label.configure(text_color=THEME_COLORS["text_primary"])
        else:
            self.progress_bar.grid_remove()
            self.status_label.configure(text="Listo", text_color="#6BCB77")
            self._status_dot.configure(text_color="#6BCB77")
            self.add_files_btn.configure(state="normal")

    def _on_selection_changed(self, result: Optional[AnalysisResult]):
        """Handle result selection change."""
        if self.on_result_selected:
            self.on_result_selected(result)

        # Load track for playback (but don't auto-play)
        if result and self._audio_player:
            self._audio_player.load(result.filepath)

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

    def remove_selected_file(self):
        """Remove selected file(s) from the list (not from disk)."""
        selected = self.results_table.get_selected_results()
        if not selected:
            return
        self._remove_files_from_list([r.filepath for r in selected])

    # ─── Context menu ─────────────────────────────────────────────────

    def _show_context_menu(self, event):
        """Show context menu for selected files."""
        selected = self.results_table.get_selected_results()
        if not selected:
            return

        menu = tk.Menu(self, tearoff=0)

        if len(selected) == 1:
            result = selected[0]
            menu.add_command(
                label="Abrir espectrograma",
                command=self._on_show_spectrogram,
            )
            menu.add_command(
                label="Ver información",
                command=self._on_edit_metadata,
            )
            menu.add_command(
                label="Volver a analizar",
                command=lambda fp=result.filepath: self._reanalyze_files([fp]),
            )
            menu.add_command(
                label="Copiar ruta",
                command=lambda fp=result.filepath: self._copy_path_to_clipboard(fp),
            )
            finder_label = "Mostrar en Finder" if sys.platform == "darwin" else "Mostrar en Explorador"
            menu.add_command(
                label=finder_label,
                command=lambda fp=result.filepath: self._show_in_file_manager(fp),
            )
            menu.add_separator()
            menu.add_command(
                label="Quitar de la lista",
                command=lambda fp=result.filepath: self._remove_files_from_list([fp]),
            )
            menu.add_command(
                label="Mover a la papelera",
                command=lambda fp=result.filepath: self._move_to_trash([fp]),
            )
        else:
            filepaths = [r.filepath for r in selected]
            menu.add_command(
                label="Volver a analizar",
                command=lambda fps=filepaths: self._reanalyze_files(fps),
            )
            menu.add_separator()
            menu.add_command(
                label="Quitar de la lista",
                command=lambda fps=filepaths: self._remove_files_from_list(fps),
            )
            menu.add_command(
                label="Mover a la papelera",
                command=lambda fps=filepaths: self._move_to_trash(fps),
            )

        menu.tk_popup(event.x_root, event.y_root)

    def _reanalyze_files(self, filepaths: List[str]):
        """Re-analyze specific files."""
        for filepath in filepaths:
            self.results_table.add_result(create_pending_result(filepath))
        self._start_analysis(filepaths)

    def _copy_path_to_clipboard(self, filepath: str):
        """Copy file path to clipboard."""
        self.clipboard_clear()
        self.clipboard_append(filepath)

    def _show_in_file_manager(self, filepath: str):
        """Show file in system file manager."""
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", filepath])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", filepath])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(filepath)])

    def _remove_files_from_list(self, filepaths: List[str]):
        """Remove files from the list (not from disk)."""
        # Stop playback if any of these files is playing
        if self._audio_player:
            for fp in filepaths:
                if self._audio_player._current_filepath == fp:
                    self._audio_player.stop()
                    if self._player_controls:
                        self._player_controls.reset()
                    break

        new_selection = self.results_table.remove_results(filepaths)

        self._update_count()
        self._update_empty_state_visibility()

        if new_selection and self._audio_player:
            self._audio_player.load(new_selection.filepath)

        if self.on_result_selected:
            self.on_result_selected(new_selection)

    def _move_to_trash(self, filepaths: List[str]):
        """Move files to system trash with confirmation."""
        if len(filepaths) == 1:
            filename = os.path.basename(filepaths[0])
            msg = f"¿Mover «{filename}» a la papelera?"
        else:
            msg = f"¿Mover {len(filepaths)} archivos a la papelera?"

        confirmed = messagebox.askokcancel(
            title="Mover a la papelera",
            message=msg,
            parent=self.winfo_toplevel(),
        )
        if not confirmed:
            return

        success = []
        for fp in filepaths:
            if self._move_file_to_trash(fp):
                success.append(fp)

        if success:
            self._remove_files_from_list(success)

    @staticmethod
    def _move_file_to_trash(filepath: str) -> bool:
        """Move a single file to the system trash. Returns True on success."""
        try:
            if sys.platform == "darwin":
                escaped = filepath.replace("\\", "\\\\").replace('"', '\\"')
                result = subprocess.run(
                    ["osascript", "-e",
                     f'tell application "Finder" to delete POSIX file "{escaped}"'],
                    capture_output=True, text=True, timeout=10,
                )
                return result.returncode == 0
            elif sys.platform == "win32":
                try:
                    import send2trash
                    send2trash.send2trash(filepath)
                    return True
                except ImportError:
                    result = subprocess.run(
                        ["powershell", "-Command",
                         'Add-Type -AssemblyName Microsoft.VisualBasic; '
                         '[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('
                         f'"{filepath}", "OnlyErrorDialogs", "SendToRecycleBin")'],
                        capture_output=True, timeout=10,
                    )
                    return result.returncode == 0
            else:
                result = subprocess.run(
                    ["gio", "trash", filepath],
                    capture_output=True, timeout=10,
                )
                return result.returncode == 0
        except Exception:
            return False

    def _on_show_spectrogram(self):
        """Handle spectrogram button click."""
        if self.on_show_spectrogram:
            self.on_show_spectrogram()

    def _on_edit_metadata(self):
        """Handle metadata editor button click."""
        selected = self.results_table.get_selected_result()
        if not selected:
            return
        MetadataEditor(
            self.winfo_toplevel(),
            filepath=selected.filepath,
            on_save=self.on_metadata_saved,
            analysis_result=selected,
            on_navigate=self._navigate_metadata_editor,
        )

    def _navigate_metadata_editor(self, direction: int):
        """Navigate to prev/next file in the results table for the metadata editor.

        Returns the new AnalysisResult, or None if at boundary.
        """
        if direction < 0:
            return self.results_table.select_previous()
        else:
            return self.results_table.select_next()

    def open_metadata_editor(self):
        """Public method to open metadata editor (for keyboard shortcut)."""
        self._on_edit_metadata()

    def _on_open_settings(self):
        """Handle settings button click."""
        SettingsWindow(self.winfo_toplevel())

    # ─── Watcher ──────────────────────────────────────────────────────

    def _on_toggle_watcher(self):
        """Handle watcher button click."""
        if self.on_toggle_watcher:
            self.on_toggle_watcher()

    def set_watcher_active(self, active: bool, folder_name: str = ""):
        """Update UI to reflect watcher state."""
        if active:
            self.watcher_btn.configure(image=self._watcher_icon_on)
            self._watcher_indicator.grid()
            self._start_indicator_pulse()
        else:
            self.watcher_btn.configure(image=self._watcher_icon_off)
            self._watcher_indicator.grid_remove()
            self._stop_indicator_pulse()

    def _start_indicator_pulse(self):
        """Start pulsing the watcher indicator."""
        self._pulse_active = True
        self._pulse_step(True)

    def _stop_indicator_pulse(self):
        """Stop pulsing the watcher indicator."""
        self._pulse_active = False

    def _pulse_step(self, bright: bool):
        """Alternate indicator color for pulse effect."""
        if not self._pulse_active:
            return
        color = "#5DB88C" if bright else "#2D6B4A"
        self._watcher_indicator.configure(text_color=color)
        self.after(800, self._pulse_step, not bright)

    def add_files_from_watcher(self, files: List[str]):
        """Add files detected by the folder watcher (deduplicates first)."""
        existing = set(self.results_table.get_ordered_filepaths())
        new_files = [f for f in files if f not in existing]
        if new_files:
            self._on_files_added(new_files)
