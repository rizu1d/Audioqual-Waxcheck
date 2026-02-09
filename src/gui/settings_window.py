"""Settings window (configuration panel)."""

import customtkinter as ctk

from ..utils.constants import THEME_COLORS, FONT_FAMILY, FONT_SIZES
from ..utils.settings import AppSettings


class SettingsWindow(ctk.CTkToplevel):
    """Modal window for application settings."""

    def __init__(self, master):
        super().__init__(master)

        self._settings = AppSettings()

        self._setup_window()
        self._setup_ui()

        self.grab_set()
        self.focus_force()
        self.bind("<Escape>", lambda e: self.destroy())

    def _setup_window(self):
        w, h = 460, 260
        self.geometry(f"{w}x{h}")
        self.resizable(False, False)
        self.title("Configuración")
        self.configure(fg_color=THEME_COLORS["bg_primary"])

        # Center over parent
        self.update_idletasks()
        parent = self.master
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _setup_ui(self):
        # Title
        ctk.CTkLabel(
            self,
            text="Configuración",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["heading"], weight="bold"),
            text_color=THEME_COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", padx=24, pady=(20, 4))

        # Separator
        ctk.CTkFrame(self, height=1, fg_color=THEME_COLORS["primary_dark"]).pack(
            fill="x", padx=24, pady=(0, 16)
        )

        # Section: Metadatos
        ctk.CTkLabel(
            self,
            text="Metadatos",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"], weight="bold"),
            text_color=THEME_COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", padx=28, pady=(0, 8))

        # Checkbox: rename on save
        self._rename_var = ctk.StringVar(
            value="1" if self._settings.rename_on_save else "0"
        )

        cb = ctk.CTkCheckBox(
            self,
            text="Renombrar archivo en disco al guardar metadatos",
            variable=self._rename_var,
            onvalue="1",
            offvalue="0",
            command=self._on_rename_toggle,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_primary"],
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
            border_color=THEME_COLORS["primary_dark"],
            checkmark_color=THEME_COLORS["text_primary"],
        )
        cb.pack(anchor="w", padx=36, pady=(0, 4))

        # Format hint
        ctk.CTkLabel(
            self,
            text='Formato: "Artista - Título.extensión"',
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["small"]),
            text_color=THEME_COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x", padx=56, pady=(0, 20))

        # Close button — right-aligned
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(0, 20))
        btn_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            btn_frame,
            text="Cerrar",
            command=self.destroy,
            width=90,
            height=34,
            corner_radius=8,
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
            text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"]),
        ).grid(row=0, column=1)

    def _on_rename_toggle(self):
        self._settings.rename_on_save = self._rename_var.get() == "1"
