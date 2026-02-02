"""Drag and drop zone for audio files."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Callable, List, Optional

import customtkinter as ctk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from ..utils.file_utils import get_audio_files_from_path
from ..utils.constants import SUPPORTED_FORMATS, THEME_COLORS


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

        # Drop zone frame - dark with subtle purple border
        self.drop_frame = ctk.CTkFrame(
            self,
            fg_color=THEME_COLORS["bg_tertiary"],
            corner_radius=10,
            border_width=2,
            border_color=THEME_COLORS["primary_dark"],
        )
        self.drop_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.drop_frame.grid_columnconfigure(0, weight=1)
        self.drop_frame.grid_rowconfigure(0, weight=1)

        # Inner content frame
        self.content_frame = ctk.CTkFrame(
            self.drop_frame,
            fg_color="transparent",
        )
        self.content_frame.grid(row=0, column=0)

        # Icon/emoji label
        self.icon_label = ctk.CTkLabel(
            self.content_frame,
            text="",
            font=ctk.CTkFont(size=48),
        )
        self.icon_label.grid(row=0, column=0, pady=(0, 10))

        # Main instruction label
        self.main_label = ctk.CTkLabel(
            self.content_frame,
            text="Arrastra archivos de audio aqui",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=THEME_COLORS["text_primary"],
        )
        self.main_label.grid(row=1, column=0, pady=(0, 5))

        # Sub label
        formats_str = ", ".join(sorted(f.upper().lstrip(".") for f in SUPPORTED_FORMATS))
        self.sub_label = ctk.CTkLabel(
            self.content_frame,
            text=f"Formatos soportados: {formats_str}",
            font=ctk.CTkFont(size=12),
            text_color=THEME_COLORS["text_secondary"],
        )
        self.sub_label.grid(row=2, column=0, pady=(0, 15))

        # Buttons frame
        self.buttons_frame = ctk.CTkFrame(
            self.content_frame,
            fg_color="transparent",
        )
        self.buttons_frame.grid(row=3, column=0)

        # Select files button - purple style
        self.select_files_btn = ctk.CTkButton(
            self.buttons_frame,
            text="Seleccionar archivos",
            command=self._on_select_files,
            width=150,
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
            text_color=THEME_COLORS["text_primary"],
        )
        self.select_files_btn.grid(row=0, column=0, padx=5)

        # Select folder button - purple style
        self.select_folder_btn = ctk.CTkButton(
            self.buttons_frame,
            text="Seleccionar carpeta",
            command=self._on_select_folder,
            width=150,
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
            text_color=THEME_COLORS["text_primary"],
        )
        self.select_folder_btn.grid(row=0, column=1, padx=5)

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
        self.drop_frame.configure(border_color=THEME_COLORS["primary_dark"])

    def _on_select_files(self):
        """Handle select files button click."""
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
        """Handle select folder button click."""
        folder = filedialog.askdirectory(
            title="Seleccionar carpeta con archivos de audio",
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
        self.select_files_btn.configure(state=state)
        self.select_folder_btn.configure(state=state)
