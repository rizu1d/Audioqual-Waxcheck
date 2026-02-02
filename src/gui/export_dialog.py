"""Export dialog for saving analysis results."""

from tkinter import filedialog, messagebox
from typing import List

import customtkinter as ctk

from ..core.analyzer import AnalysisResult
from ..utils.export_utils import export_results, get_suggested_filename
from ..utils.constants import EXPORT_CSV, EXPORT_TXT, THEME_COLORS


class ExportDialog(ctk.CTkToplevel):
    """
    Dialog for exporting analysis results to CSV or TXT.
    """

    def __init__(self, master, results: List[AnalysisResult], **kwargs):
        super().__init__(master, **kwargs)

        self.results = results
        self.selected_format = ctk.StringVar(value=EXPORT_CSV)

        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        """Configure the dialog window."""
        self.title("Exportar Resultados")
        self.geometry("400x250")
        self.resizable(False, False)

        # Center on parent
        self.transient(self.master)

        # Make modal
        self.grab_set()

    def _setup_ui(self):
        """Set up the dialog UI."""
        self.configure(fg_color=THEME_COLORS["bg_primary"])
        self.grid_columnconfigure(0, weight=1)

        # Title
        title_label = ctk.CTkLabel(
            self,
            text="Exportar Resultados del Analisis",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=THEME_COLORS["text_primary"],
        )
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # File count info
        count_label = ctk.CTkLabel(
            self,
            text=f"{len(self.results)} archivo{'s' if len(self.results) != 1 else ''} para exportar",
            font=ctk.CTkFont(size=12),
            text_color=THEME_COLORS["text_secondary"],
        )
        count_label.grid(row=1, column=0, padx=20, pady=(0, 20))

        # Format selection frame
        format_frame = ctk.CTkFrame(self, fg_color="transparent")
        format_frame.grid(row=2, column=0, padx=20, pady=10)

        format_label = ctk.CTkLabel(
            format_frame,
            text="Formato:",
            font=ctk.CTkFont(size=14),
            text_color=THEME_COLORS["text_primary"],
        )
        format_label.grid(row=0, column=0, padx=(0, 10))

        # CSV radio button
        csv_radio = ctk.CTkRadioButton(
            format_frame,
            text="CSV (Excel)",
            variable=self.selected_format,
            value=EXPORT_CSV,
            text_color=THEME_COLORS["text_primary"],
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
        )
        csv_radio.grid(row=0, column=1, padx=10)

        # TXT radio button
        txt_radio = ctk.CTkRadioButton(
            format_frame,
            text="TXT (Texto)",
            variable=self.selected_format,
            value=EXPORT_TXT,
            text_color=THEME_COLORS["text_primary"],
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
        )
        txt_radio.grid(row=0, column=2, padx=10)

        # Buttons frame
        buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        buttons_frame.grid(row=3, column=0, padx=20, pady=30)

        # Cancel button - secondary style with purple border
        cancel_btn = ctk.CTkButton(
            buttons_frame,
            text="Cancelar",
            command=self._on_cancel,
            width=120,
            fg_color="transparent",
            border_width=2,
            border_color=THEME_COLORS["primary"],
            text_color=THEME_COLORS["text_primary"],
            hover_color=THEME_COLORS["primary_dark"],
        )
        cancel_btn.grid(row=0, column=0, padx=10)

        # Export button - primary purple style
        export_btn = ctk.CTkButton(
            buttons_frame,
            text="Exportar",
            command=self._on_export,
            width=120,
            fg_color=THEME_COLORS["primary"],
            hover_color=THEME_COLORS["primary_dark"],
            text_color=THEME_COLORS["text_primary"],
        )
        export_btn.grid(row=0, column=1, padx=10)

    def _on_cancel(self):
        """Handle cancel button click."""
        self.destroy()

    def _on_export(self):
        """Handle export button click."""
        format = self.selected_format.get()
        suggested_name = get_suggested_filename(format)

        # Configure file dialog based on format
        if format == EXPORT_CSV:
            filetypes = [("CSV files", "*.csv"), ("All files", "*.*")]
            default_ext = ".csv"
        else:
            filetypes = [("Text files", "*.txt"), ("All files", "*.*")]
            default_ext = ".txt"

        # Show save dialog
        filepath = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar reporte",
            initialfile=suggested_name,
            filetypes=filetypes,
            defaultextension=default_ext,
        )

        if not filepath:
            return

        # Export results
        success = export_results(self.results, filepath, format)

        if success:
            messagebox.showinfo(
                "Exportacion Exitosa",
                f"El reporte se guardo correctamente en:\n{filepath}",
                parent=self,
            )
            self.destroy()
        else:
            messagebox.showerror(
                "Error de Exportacion",
                "No se pudo guardar el archivo. Verifica los permisos.",
                parent=self,
            )
