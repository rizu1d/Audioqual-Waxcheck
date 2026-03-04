"""Settings window (configuration panel)."""

import os
from tkinter import filedialog

import customtkinter as ctk

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

from ..utils.constants import THEME_COLORS, FONT_FAMILY, FONT_SIZES
from ..utils.settings import AppSettings


class SettingsWindow(ctk.CTkToplevel):
    """Modal window for application settings."""

    def __init__(self, master):
        super().__init__(master)
        self.withdraw()  # Hide until positioned

        self._settings = AppSettings()

        self._setup_window()
        self._setup_ui()

        self.deiconify()  # Show at correct position
        self.lift()
        self.grab_set()
        self.focus_force()
        # Ensure focus after window is fully mapped (macOS needs a delay)
        self.after(50, self.focus_force)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda e: self._on_close())

    def _setup_window(self):
        w, h = 460, 500
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

        # Section: Salida de audio
        ctk.CTkLabel(
            self,
            text="Salida de audio",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"], weight="bold"),
            text_color=THEME_COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", padx=28, pady=(0, 8))

        # Build device list
        self._device_names = []  # actual device names (parallel to dropdown values)
        dropdown_values = ["Por defecto del sistema"]

        if HAS_SOUNDDEVICE:
            try:
                default_out_idx = sd.default.device[1]
                for dev in sd.query_devices():
                    if dev["max_output_channels"] > 0:
                        name = dev["name"]
                        label = name
                        if dev["index"] == default_out_idx:
                            label += "  (por defecto)"
                        self._device_names.append(name)
                        dropdown_values.append(label)
            except Exception:
                pass

        # Determine preselected value
        saved = self._settings.output_device
        selected = dropdown_values[0]
        if saved:
            for i, name in enumerate(self._device_names):
                if name == saved:
                    selected = dropdown_values[i + 1]  # +1 because index 0 is "Por defecto"
                    break

        self._device_var = ctk.StringVar(value=selected)

        ctk.CTkOptionMenu(
            self,
            variable=self._device_var,
            values=dropdown_values,
            command=self._on_device_change,
            width=380,
            height=30,
            corner_radius=8,
            fg_color=THEME_COLORS["bg_elevated"],
            button_color=THEME_COLORS["primary_dark"],
            button_hover_color=THEME_COLORS["primary"],
            dropdown_fg_color=THEME_COLORS["bg_elevated"],
            dropdown_hover_color=THEME_COLORS["primary_dark"],
            text_color=THEME_COLORS["text_primary"],
            dropdown_text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            dropdown_font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
        ).pack(anchor="w", padx=36, pady=(0, 16))

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
        ).pack(fill="x", padx=56, pady=(0, 16))

        # Separator
        ctk.CTkFrame(self, height=1, fg_color=THEME_COLORS["primary_dark"]).pack(
            fill="x", padx=24, pady=(0, 16)
        )

        # Section: Monitorización
        ctk.CTkLabel(
            self,
            text="Monitorización de carpeta",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["body"], weight="bold"),
            text_color=THEME_COLORS["text_primary"],
            anchor="w",
        ).pack(fill="x", padx=28, pady=(0, 8))

        # Current folder display
        folder = self._settings.watcher_folder
        folder_text = os.path.basename(folder) if folder else "No configurada"
        self._folder_label = ctk.CTkLabel(
            self,
            text=f"Carpeta: {folder_text}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_secondary"],
            anchor="w",
        )
        self._folder_label.pack(fill="x", padx=36, pady=(0, 6))

        # Change folder button
        ctk.CTkButton(
            self,
            text="Cambiar carpeta...",
            command=self._on_change_watcher_folder,
            width=140,
            height=30,
            corner_radius=8,
            fg_color=THEME_COLORS["bg_elevated"],
            hover_color=THEME_COLORS["primary_dark"],
            text_color=THEME_COLORS["text_primary"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
        ).pack(anchor="w", padx=36, pady=(0, 8))

        # Auto-start checkbox
        self._auto_start_var = ctk.StringVar(
            value="1" if self._settings.watcher_auto_start else "0"
        )

        ctk.CTkCheckBox(
            self,
            text="Iniciar monitorización automáticamente al abrir",
            variable=self._auto_start_var,
            onvalue="1",
            offvalue="0",
            command=self._on_auto_start_toggle,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZES["caption"]),
            text_color=THEME_COLORS["text_primary"],
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
            border_color=THEME_COLORS["primary_dark"],
            checkmark_color=THEME_COLORS["text_primary"],
        ).pack(anchor="w", padx=36, pady=(0, 16))

        # Close button — right-aligned
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(0, 20))
        btn_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            btn_frame,
            text="Cerrar",
            command=self._on_close,
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

    def _on_change_watcher_folder(self):
        folder = filedialog.askdirectory(
            title="Seleccionar carpeta a monitorizar",
            parent=self,
        )
        if folder:
            self._settings.watcher_folder = folder
            self._folder_label.configure(text=f"Carpeta: {os.path.basename(folder)}")

    def _on_auto_start_toggle(self):
        self._settings.watcher_auto_start = self._auto_start_var.get() == "1"

    def _on_device_change(self, choice: str):
        if choice == "Por defecto del sistema":
            self._settings.output_device = ""
        else:
            # Strip the " (por defecto)" suffix to get the real device name
            idx = None
            for i, val in enumerate(self._device_names):
                # dropdown_values[i+1] corresponds to device_names[i]
                if choice.replace("  (por defecto)", "") == val:
                    idx = i
                    break
            self._settings.output_device = self._device_names[idx] if idx is not None else ""

    def _on_close(self):
        """Close settings and restore focus to parent."""
        master = self.master
        self.grab_release()
        self.destroy()
        # Delayed focus restoration — let destroy propagate through
        # the Cocoa event loop before forcing focus back to parent.
        master.after(50, lambda: master.focus_force())
