"""Main application class integrating core and GUI."""

import os
import sys
from collections import OrderedDict
from tkinter import filedialog
from typing import Optional

import customtkinter as ctk

# Configure matplotlib ONCE at module load, before any imports that might use it
# This avoids the overhead of calling matplotlib.use('Agg') and plt.style.use() on every render
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend (thread-safe)
import matplotlib.pyplot as plt
plt.style.use('dark_background')

try:
    from tkinterdnd2 import TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from .core.analyzer import AnalysisResult, AudioAnalyzer
from .core.frequency_detector import FrequencyAnalysis
from .gui.main_window import MainWindow
from .gui.spectrogram_window import SpectrogramWindow
from .gui.audio_player import AudioPlayer, PlayerState
from .utils.settings import AppSettings
from .utils.tk_utils import (
    init_thread_scheduler,
    cleanup_thread_scheduler,
    schedule_callback_from_thread,
)

try:
    from .core.folder_watcher import FolderWatcher
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

from .utils.constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    THEME_COLORS,
)

# Maximum number of spectrograms to cache in memory (LRU)
MAX_SPECTROGRAM_CACHE = 10


class AudioQualApp:
    """
    Main application class that creates and manages the application window.
    """

    def __init__(self):
        # Load custom fonts before creating any UI
        from .utils.font_utils import load_custom_fonts
        load_custom_fonts()

        # Create root window with drag-and-drop support if available
        if HAS_DND:
            self.root = TkinterDnD.Tk()
        else:
            self.root = ctk.CTk()

        # LRU cache for frequency analysis data (filepath -> FrequencyAnalysis)
        # This keeps the last N spectrograms in memory for quick re-display
        self._spectrogram_cache: OrderedDict[str, tuple] = OrderedDict()
        # Reference to the spectrogram window (None if closed)
        self._spectrogram_window: Optional[SpectrogramWindow] = None
        # Currently selected result (for spectrogram display)
        self._selected_result: Optional[AnalysisResult] = None
        # Filepath currently being re-analyzed for spectrogram (dedup guard)
        self._spectrogram_reanalyze_pending: Optional[str] = None

        init_thread_scheduler(self.root)

        self._setup_window()
        self._setup_components()
        self._setup_layout()
        self._setup_keyboard_bindings()

        if sys.platform == "darwin":
            self._setup_macos_click_fix()

    def _setup_macos_click_fix(self):
        """Workaround for macOS Cocoa backend focus issues.

        On macOS, the Cocoa backend may not deliver click events to widgets
        when the app window doesn't have keyboard focus. This ensures the
        root window is always properly focused for click processing.
        """
        import tkinter as tk

        def _on_any_click(event):
            try:
                # If no widget in the app has focus, force it to root.
                # This handles the case where focus was lost (e.g. after
                # closing a dialog, switching apps, or Cocoa focus quirks).
                if self.root.focus_get() is None:
                    self.root.focus_force()
            except tk.TclError:
                pass

        self.root.bind_all("<Button-1>", _on_any_click, add="+")

    def _setup_window(self):
        """Configure the main window."""
        self.root.title("WaxCheck")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

        # Set app icon (dock/taskbar)
        try:
            from .utils.icon_utils import load_svg_icon
            import cairosvg
            from PIL import Image, ImageTk
            import io
            svg_path = os.path.join(os.path.dirname(__file__), "assets", "logo-waxcheckV2.svg")
            png_bytes = cairosvg.svg2png(url=svg_path, output_width=256, output_height=256)
            icon_img = Image.open(io.BytesIO(png_bytes))
            self._app_icon = ImageTk.PhotoImage(icon_img)
            self.root.iconphoto(True, self._app_icon)
        except Exception:
            pass

        # Set appearance mode
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")  # More neutral, will be overridden by custom colors

        # Configure grid - single column layout
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

    def _setup_components(self):
        """Create application components."""
        # Create analyzer
        self.analyzer = AudioAnalyzer()

        # Create audio player
        self.audio_player = AudioPlayer()
        self.audio_player.set_tk_root(self.root)

        # Settings and folder watcher
        self._settings = AppSettings()
        if HAS_WATCHDOG:
            self._folder_watcher = FolderWatcher(
                on_files_ready=self._on_watcher_files_ready
            )
        else:
            self._folder_watcher = None

        # Create main window
        self.main_window = MainWindow(
            self.root,
            analyzer=self.analyzer,
            audio_player=self.audio_player,
            on_result_selected=self._on_result_selected,
            on_show_spectrogram=self._show_spectrogram_window,
            on_clear=self._on_clear,
            on_metadata_saved=self._on_metadata_saved,
            on_toggle_watcher=self._on_toggle_watcher,
        )

        # Auto-start watcher if configured
        if (self._folder_watcher
                and self._settings.watcher_auto_start
                and self._settings.watcher_folder
                and os.path.isdir(self._settings.watcher_folder)):
            self._start_watcher(self._settings.watcher_folder)

    def _setup_layout(self):
        """Set up the main layout."""
        self.main_window.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def _setup_keyboard_bindings(self):
        """Set up global keyboard shortcuts on the root window."""
        mod = "Command" if sys.platform == "darwin" else "Control"

        self.root.bind("<space>", self._handle_space)
        self.root.bind("<Delete>", self._handle_delete)
        self.root.bind("<BackSpace>", self._handle_delete)
        self.root.bind("<Up>", self._handle_up)
        self.root.bind("<Down>", self._handle_down)
        self.root.bind("<Return>", self._handle_return)
        self.root.bind("<Left>", self._handle_seek_back)
        self.root.bind("<Right>", self._handle_seek_forward)
        self.root.bind(f"<{mod}-o>", self._handle_open)
        self.root.bind(f"<{mod}-O>", self._handle_open)
        self.root.bind(f"<{mod}-e>", self._handle_edit_metadata)
        self.root.bind(f"<{mod}-E>", self._handle_edit_metadata)
        self.root.bind(f"<{mod}-i>", self._handle_edit_metadata)
        self.root.bind(f"<{mod}-I>", self._handle_edit_metadata)
        self.root.bind(f"<{mod}-f>", self._handle_search)
        self.root.bind(f"<{mod}-F>", self._handle_search)
        self.root.bind("<Escape>", self._handle_stop)

    def _is_text_entry(self, event) -> bool:
        """Return True if the event originated from a text entry widget."""
        try:
            return event.widget.winfo_class() in ("Entry", "TEntry")
        except Exception:
            return False

    def _handle_search(self, event):
        """Toggle the search bar in the results table."""
        self.main_window.results_table.toggle_search()
        return "break"

    def _handle_space(self, event):
        """Toggle play/pause for the selected file."""
        if self._is_text_entry(event):
            return
        if self.audio_player.get_state() == PlayerState.STOPPED:
            selected = self.main_window.results_table.get_selected_result()
            if selected:
                if self.audio_player._current_filepath == selected.filepath:
                    # File already loaded — play directly
                    self.audio_player.play()
                else:
                    # Different file — load and play
                    self.audio_player.load(selected.filepath)
                    self.root.after(100, self.audio_player.play)
        else:
            self.audio_player.toggle_play_pause()
        return "break"

    def _handle_delete(self, event):
        """Remove the selected file from the list."""
        if self._is_text_entry(event):
            return
        self.main_window.remove_selected_file()
        return "break"

    def _handle_up(self, event):
        """Select the previous file in the list."""
        if self._is_text_entry(event):
            return
        result = self.main_window.results_table.select_previous()
        if result:
            self._on_result_selected(result)
            # Load into player without auto-play
            self.audio_player.stop()
            self.audio_player.load(result.filepath)
        return "break"

    def _handle_down(self, event):
        """Select the next file in the list."""
        if self._is_text_entry(event):
            return
        result = self.main_window.results_table.select_next()
        if result:
            self._on_result_selected(result)
            # Load into player without auto-play
            self.audio_player.stop()
            self.audio_player.load(result.filepath)
        return "break"

    def _handle_return(self, event):
        """Load and play the selected file."""
        if self._is_text_entry(event):
            return
        selected = self.main_window.results_table.get_selected_result()
        if not selected:
            return "break"

        state = self.audio_player.get_state()

        if self.audio_player._current_filepath == selected.filepath:
            # Same file already loaded — play/resume if not already playing
            if state != PlayerState.PLAYING:
                self.audio_player.play()
        else:
            # Different file — load and play
            self.audio_player.load(selected.filepath)
            self.root.after(100, self.audio_player.play)
        return "break"

    def _handle_seek_back(self, event):
        """Seek backward 5 seconds (only while playing/paused)."""
        if self._is_text_entry(event):
            return
        state = self.audio_player.get_state()
        if state in (PlayerState.PLAYING, PlayerState.PAUSED):
            pos = self.audio_player.get_position()
            self.audio_player.seek(max(0, pos - 5))
        return "break"

    def _handle_seek_forward(self, event):
        """Seek forward 5 seconds (only while playing/paused)."""
        if self._is_text_entry(event):
            return
        state = self.audio_player.get_state()
        if state in (PlayerState.PLAYING, PlayerState.PAUSED):
            pos = self.audio_player.get_position()
            self.audio_player.seek(pos + 5)
        return "break"

    def _handle_open(self, event):
        """Open the file selection dialog."""
        self.main_window._on_add_files_click()
        return "break"

    def _handle_stop(self, event):
        """Stop playback, or close search bar if active."""
        if self.main_window.results_table.is_search_active():
            self.main_window.results_table.close_search()
            return "break"
        self.audio_player.stop()
        return "break"

    def _handle_edit_metadata(self, event):
        """Open the metadata editor for the selected file."""
        self.main_window.open_metadata_editor()
        return "break"

    def _on_metadata_saved(self, old_filepath: str, new_filepath=None):
        """Handle metadata saved callback. Updates table and cache on rename."""
        if new_filepath and new_filepath != old_filepath:
            # Update results table
            self.main_window.results_table.update_filepath(old_filepath, new_filepath)

            # Update spectrogram cache key
            cached = self._spectrogram_cache.pop(old_filepath, None)
            if cached:
                self._spectrogram_cache[new_filepath] = cached

            # Reload into player if this file was loaded
            if self.audio_player._current_filepath == old_filepath:
                self.audio_player.stop()
                self.audio_player.load(new_filepath)

    def _on_result_selected(self, result: Optional[AnalysisResult]):
        """Handle result selection from the table."""
        self._selected_result = result

        if not result:
            return

        # Check if result has frequency_analysis (fresh result)
        if result.frequency_analysis:
            # Cache the frequency analysis for later re-selection
            self._cache_spectrogram(
                result.filepath,
                result.frequency_analysis,
                result.filename,
                result.cutoff_frequency_khz,
            )

        # If spectrogram window is open, update it
        if self._spectrogram_window and self._spectrogram_window.is_open():
            self._update_spectrogram_window()

    def _show_spectrogram_window(self):
        """Show or update the spectrogram window."""
        if not self._selected_result:
            return

        # Get frequency analysis data
        freq_analysis, filename, cutoff_khz = self._get_analysis_data(
            self._selected_result
        )

        if not freq_analysis:
            # Data not in cache - re-analyze in background, open window when ready
            self._reanalyze_for_spectrogram_async(self._selected_result, open_window=True)
            return

        # Check if window exists and is open
        if self._spectrogram_window and self._spectrogram_window.is_open():
            # Update existing window
            self._spectrogram_window.update_spectrogram(
                freq_analysis, filename, cutoff_khz
            )
            self._spectrogram_window.focus()
        else:
            # Create new window
            self._spectrogram_window = SpectrogramWindow(
                self.root,
                freq_analysis,
                filename,
                cutoff_khz,
            )

    def _update_spectrogram_window(self):
        """Update spectrogram window with currently selected result."""
        if not self._selected_result:
            return

        freq_analysis, filename, cutoff_khz = self._get_analysis_data(
            self._selected_result
        )

        if freq_analysis and self._spectrogram_window:
            self._spectrogram_window.update_spectrogram(
                freq_analysis, filename, cutoff_khz
            )
        elif self._spectrogram_window and self._spectrogram_window.is_open():
            # Data not in cache - re-analyze in background
            self._reanalyze_for_spectrogram_async(self._selected_result)

    def _get_analysis_data(self, result: AnalysisResult):
        """Get frequency analysis data from result or cache.

        Returns (None, None, None) if not available. Caller should use
        _reanalyze_for_spectrogram_async() to fetch data in background.
        """
        if result.frequency_analysis:
            return (
                result.frequency_analysis,
                result.filename,
                result.cutoff_frequency_khz,
            )

        # Try cache
        cached = self._spectrogram_cache.get(result.filepath)
        if cached:
            # Move to end (most recently used)
            self._spectrogram_cache.move_to_end(result.filepath)
            return cached

        return (None, None, None)

    def _reanalyze_for_spectrogram_async(self, result: AnalysisResult, open_window: bool = False):
        """Re-analyze a single file in background thread to get spectrogram data.

        Args:
            result: The analysis result to re-analyze
            open_window: If True, create/open the spectrogram window when done
        """
        import threading

        filepath = result.filepath

        # Skip if already re-analyzing this exact file
        if self._spectrogram_reanalyze_pending == filepath:
            return

        self._spectrogram_reanalyze_pending = filepath
        self.main_window.status_label.configure(
            text=f"Cargando espectrograma..."
        )

        def _do_reanalyze():
            try:
                fresh = self.analyzer.analyze_file(filepath)
                if fresh.frequency_analysis:
                    def _on_done():
                        self._spectrogram_reanalyze_pending = None
                        self.main_window.status_label.configure(text="Listo")

                        self._cache_spectrogram(
                            filepath,
                            fresh.frequency_analysis,
                            fresh.filename,
                            fresh.cutoff_frequency_khz,
                        )
                        # Only show if this file is still selected
                        if (self._selected_result
                                and self._selected_result.filepath == filepath):
                            if (self._spectrogram_window
                                    and self._spectrogram_window.is_open()):
                                self._spectrogram_window.update_spectrogram(
                                    fresh.frequency_analysis,
                                    fresh.filename,
                                    fresh.cutoff_frequency_khz,
                                )
                            elif open_window:
                                self._spectrogram_window = SpectrogramWindow(
                                    self.root,
                                    fresh.frequency_analysis,
                                    fresh.filename,
                                    fresh.cutoff_frequency_khz,
                                )
                    schedule_callback_from_thread(self.root, _on_done)
                else:
                    def _on_fail():
                        self._spectrogram_reanalyze_pending = None
                        self.main_window.status_label.configure(text="Listo")
                    schedule_callback_from_thread(self.root, _on_fail)
            except Exception:
                def _on_error():
                    self._spectrogram_reanalyze_pending = None
                    self.main_window.status_label.configure(text="Listo")
                schedule_callback_from_thread(self.root, _on_error)

        threading.Thread(target=_do_reanalyze, daemon=True).start()

    def _cache_spectrogram(
        self,
        filepath: str,
        analysis: FrequencyAnalysis,
        filename: str,
        cutoff_khz: float,
    ):
        """Cache spectrogram data with LRU eviction."""
        # Remove oldest if at capacity
        while len(self._spectrogram_cache) >= MAX_SPECTROGRAM_CACHE:
            self._spectrogram_cache.popitem(last=False)

        # Add/update cache entry
        self._spectrogram_cache[filepath] = (analysis, filename, cutoff_khz)

    # ─── Folder Watcher ────────────────────────────────────────────────

    def _on_toggle_watcher(self):
        """Handle watcher button click — show context menu with options."""
        if not self._folder_watcher:
            return

        import tkinter as tk
        menu = tk.Menu(self.root, tearoff=0)

        if self._folder_watcher.is_running:
            current = os.path.basename(self._folder_watcher.watch_path or "")
            menu.add_command(
                label=f"Monitorizando: {current}",
                state="disabled",
            )
            menu.add_separator()
            menu.add_command(
                label="Cambiar carpeta...",
                command=self._change_watcher_folder,
            )
            menu.add_command(
                label="Detener monitorización",
                command=self._stop_watcher,
            )
        else:
            saved = self._settings.watcher_folder
            if saved and os.path.isdir(saved):
                menu.add_command(
                    label=f"Monitorizar: {os.path.basename(saved)}",
                    command=lambda: self._start_watcher(saved),
                )
                menu.add_separator()
            menu.add_command(
                label="Seleccionar carpeta...",
                command=self._change_watcher_folder,
            )

        btn = self.main_window.watcher_btn
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        menu.tk_popup(x, y)

    def _change_watcher_folder(self):
        """Ask for a new folder and start watching it."""
        folder = filedialog.askdirectory(
            title="Seleccionar carpeta a monitorizar",
            parent=self.root,
        )
        if folder:
            self._start_watcher(folder)

    def _start_watcher(self, folder: str):
        """Start monitoring a folder."""
        if not self._folder_watcher:
            return
        if self._folder_watcher.start(folder):
            self._settings.watcher_folder = folder
            basename = os.path.basename(folder)
            self.main_window.set_watcher_active(True, basename)
            self.main_window.status_label.configure(
                text=f"Monitorizando: {basename}"
            )

    def _stop_watcher(self):
        """Stop folder monitoring."""
        if not self._folder_watcher:
            return
        self._folder_watcher.stop()
        self.main_window.set_watcher_active(False)
        self.main_window.status_label.configure(text="Listo")

    def _on_watcher_files_ready(self, files):
        """Called from watcher thread when files are stable and ready."""
        schedule_callback_from_thread(
            self.root, self.main_window.add_files_from_watcher, files
        )

    def _on_clear(self):
        """Handle clear action - clear cache."""
        self._spectrogram_cache.clear()
        self._selected_result = None
        self._spectrogram_reanalyze_pending = None
        # Stop audio playback
        if self.audio_player:
            self.audio_player.stop()

    def _cleanup(self):
        """Clean up resources before closing."""
        if self.audio_player:
            self.audio_player.cleanup()

    def _heartbeat(self):
        """Keep the macOS event loop alive and drain pending callbacks.

        Three independent mechanisms process callbacks:
          1. pipe+createfilehandler in tk_utils (primary, macOS)
          2. after()-based 50ms poller in tk_utils (secondary, all platforms)
          3. This heartbeat (tertiary safety net)

        Even if mechanisms 1 and 2 both fail, this ensures callbacks
        are processed within 100ms.
        """
        from .utils.tk_utils import process_pending_callbacks
        process_pending_callbacks()
        self.root.after(100, self._heartbeat)

    def run(self):
        """Start the application main loop."""
        # Set up cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # Start heartbeat to prevent macOS event loop dormancy
        self._heartbeat()
        self.root.mainloop()

    def _on_close(self):
        """Handle application close."""
        # Hide window immediately so the user perceives instant close
        self.root.withdraw()

        if self._folder_watcher:
            self._folder_watcher.cleanup()
        self._cleanup()
        cleanup_thread_scheduler()

        # Destroy toplevel children first (spectrogram, metadata, settings)
        for child in list(self.root.winfo_children()):
            try:
                if isinstance(child, ctk.CTkToplevel):
                    child.destroy()
            except Exception:
                pass

        # Cancel all pending after callbacks to avoid TclError on destroyed window
        # (customtkinter's scaling_tracker fires periodic checks that can race with destroy)
        try:
            for after_id in self.root.tk.call('after', 'info'):
                self.root.after_cancel(after_id)
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass


def create_app() -> AudioQualApp:
    """Create and return a new application instance."""
    return AudioQualApp()
