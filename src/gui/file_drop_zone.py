"""Drag and drop zone for audio files."""

import tkinter as tk
from tkinter import filedialog
from typing import Callable, List, Optional

import customtkinter as ctk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from ..utils.file_utils import get_audio_files_from_path
from ..utils.i18n import t
from ..utils.icon_utils import load_svg_icon
from ..utils.constants import SUPPORTED_FORMATS, THEME_COLORS, FONT_FAMILY, FONT_SIZES


FileCallback = Callable[[List[str]], None]


class FileDropZone(ctk.CTkFrame):
    """
    A frame that accepts drag-and-drop files and provides file selection buttons.
    """

    def __init__(
        self,
        master,
        on_files_added: Optional[FileCallback] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.on_files_added = on_files_added

        self._setup_ui()
        self._setup_dnd()

    def _setup_ui(self):
        """Set up the UI components."""
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Drop zone frame - dark with subtle muted purple border, more rounded
        self.drop_frame = ctk.CTkFrame(
            self,
            fg_color=THEME_COLORS["bg_tertiary"],
            corner_radius=16,
            border_width=2,
            border_color=THEME_COLORS["primary_muted"],
        )
        self.drop_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.drop_frame.grid_columnconfigure(0, weight=1)
        self.drop_frame.grid_rowconfigure(0, weight=1)

        # Inner content frame with generous padding
        self.content_frame = ctk.CTkFrame(
            self.drop_frame,
            fg_color="transparent",
        )
        self.content_frame.grid(row=0, column=0, padx=32, pady=32)

        # Load drop icon
        self._drop_icon = load_svg_icon("drop-iconV2.svg", 64)

        # Icon label - use image or fallback to emoji
        self.icon_label = ctk.CTkLabel(
            self.content_frame,
            text="" if self._drop_icon else "📂",
            image=self._drop_icon,
            font=ctk.CTkFont(size=56),
        )
        self.icon_label.grid(row=0, column=0, pady=(0, 16))

        # Main instruction label - larger and bolder
        self.main_label = ctk.CTkLabel(
            self.content_frame,
            text=t("drop_zone.instruction"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["heading"], weight="bold"),
            text_color=THEME_COLORS["text_primary"],
        )
        self.main_label.grid(row=1, column=0, pady=(0, 8))

        # Sub label - more subtle with muted color
        formats_list = ["MP3", "WAV", "FLAC", "M4A", "AAC", "OGG"]
        formats_str = ", ".join(formats_list)
        self.sub_label = ctk.CTkLabel(
            self.content_frame,
            text=formats_str,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_muted"],
        )
        self.sub_label.grid(row=2, column=0, pady=(0, 20))

        # Select button - single button with dropdown menu
        self.select_btn = ctk.CTkButton(
            self.content_frame,
            text=t("drop_zone.select"),
            command=self._on_select_click,
            width=180,
            height=44,
            corner_radius=12,
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
            text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"], weight="bold"),
        )
        self.select_btn.grid(row=3, column=0)

    def _setup_dnd(self):
        """Set up drag and drop if available."""
        if not HAS_DND:
            return

        try:
            # Register drop target
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)
            self.drop_frame.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            self.drop_frame.dnd_bind("<<DragLeave>>", self._on_drag_leave)
        except Exception:
            pass

    def _on_drop(self, event):
        """Handle file drop event."""
        # Parse dropped files (format varies by platform)
        data = event.data

        # Handle different formats
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
            # Unix format - space separated, with potential escapes
            files = data.split()

        self._process_paths(files)
        self._reset_drop_style()

    def _on_drag_enter(self, event):
        """Handle drag enter event - golden border highlight."""
        self.drop_frame.configure(border_color=THEME_COLORS["accent"])

    def _on_drag_leave(self, event):
        """Handle drag leave event."""
        self._reset_drop_style()

    def _reset_drop_style(self):
        """Reset drop zone to default style."""
        self.drop_frame.configure(border_color=THEME_COLORS["primary_muted"])

    def _on_select_click(self, event=None):
        """Show context menu with selection options."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=t("menu.files"), command=self._on_select_files)
        menu.add_command(label=t("menu.folder"), command=self._on_select_folder)

        # Position menu below the button
        btn = self.select_btn
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        menu.tk_popup(x, y)

    def show_select_menu(self, button):
        """Show the select menu positioned below the given button."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=t("menu.files"), command=self._on_select_files)
        menu.add_command(label=t("menu.folder"), command=self._on_select_folder)

        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        menu.tk_popup(x, y)

    def select_files(self):
        """Public method to open file selection dialog."""
        self._on_select_files()

    def select_folder(self):
        """Public method to open folder selection dialog."""
        self._on_select_folder()

    def _on_select_files(self):
        """Handle select files button click."""
        filetypes = [
            ("Audio files", " ".join(f"*{ext}" for ext in SUPPORTED_FORMATS)),
            ("All files", "*.*"),
        ]

        files = filedialog.askopenfilenames(
            title=t("dialog.select_audio_files"),
            filetypes=filetypes,
        )

        if files:
            self._process_paths(list(files))

    def _on_select_folder(self):
        """Handle select folder button click."""
        folder = filedialog.askdirectory(
            title=t("dialog.select_audio_folder"),
        )

        if folder:
            self._process_paths([folder])

    def _process_paths(self, paths: List[str]):
        """Process a list of file/folder paths."""
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

        if unique_files and self.on_files_added:
            self.on_files_added(unique_files)

    def set_enabled(self, enabled: bool):
        """Enable or disable the drop zone."""
        state = "normal" if enabled else "disabled"
        self.select_btn.configure(state=state)
