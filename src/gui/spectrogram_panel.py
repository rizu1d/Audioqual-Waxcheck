"""Spectrogram visualization panel with matplotlib."""

from typing import Optional

import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

from ..core.frequency_detector import FrequencyAnalysis


class SpectrogramPanel(ctk.CTkFrame):
    """
    Panel for displaying audio spectrograms with frequency cutoff visualization.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self._setup_ui()
        self._current_analysis: Optional[FrequencyAnalysis] = None

    def _setup_ui(self):
        """Set up the panel UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Title bar
        self.title_frame = ctk.CTkFrame(self, height=40)
        self.title_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.title_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.title_frame,
            text="Espectrograma",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.title_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.file_label = ctk.CTkLabel(
            self.title_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60"),
        )
        self.file_label.grid(row=0, column=1, padx=10, pady=5, sticky="e")

        # Matplotlib figure container
        self.figure_frame = ctk.CTkFrame(self)
        self.figure_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.figure_frame.grid_columnconfigure(0, weight=1)
        self.figure_frame.grid_rowconfigure(0, weight=1)

        # Create matplotlib figure
        self._setup_figure()

        # Info panel
        self.info_frame = ctk.CTkFrame(self, height=80)
        self.info_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        self.info_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Cutoff frequency info
        self.cutoff_label = ctk.CTkLabel(
            self.info_frame,
            text="Frec. de corte: -",
            font=ctk.CTkFont(size=14),
        )
        self.cutoff_label.grid(row=0, column=0, padx=10, pady=10)

        # Max frequency info
        self.max_freq_label = ctk.CTkLabel(
            self.info_frame,
            text="Frec. max: -",
            font=ctk.CTkFont(size=14),
        )
        self.max_freq_label.grid(row=0, column=1, padx=10, pady=10)

        # Confidence info
        self.confidence_label = ctk.CTkLabel(
            self.info_frame,
            text="Confianza: -",
            font=ctk.CTkFont(size=14),
        )
        self.confidence_label.grid(row=0, column=2, padx=10, pady=10)

        # Empty state message
        self.empty_label = ctk.CTkLabel(
            self.figure_frame,
            text="Selecciona un archivo para ver el espectrograma",
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray60"),
        )
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")

    def _setup_figure(self):
        """Set up the matplotlib figure."""
        # Create figure with dark theme
        plt.style.use('dark_background')

        self.fig = Figure(figsize=(6, 4), dpi=100, facecolor='#2b2b2b')
        self.ax_spectrogram = self.fig.add_subplot(211)
        self.ax_energy = self.fig.add_subplot(212)

        self.fig.tight_layout(pad=2.0)

        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.figure_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=0, sticky="nsew")

        # Initially hide canvas
        self.canvas_widget.grid_remove()

    def show_spectrogram(
        self,
        analysis: FrequencyAnalysis,
        filename: str,
        cutoff_khz: float,
    ):
        """
        Display the spectrogram and energy spectrum for an analysis.

        Args:
            analysis: FrequencyAnalysis object with spectral data
            filename: Name of the file being displayed
            cutoff_khz: Detected cutoff frequency in kHz
        """
        self._current_analysis = analysis

        # Hide empty state, show canvas
        self.empty_label.place_forget()
        self.canvas_widget.grid()

        # Update title
        self.file_label.configure(text=filename)

        # Clear axes
        self.ax_spectrogram.clear()
        self.ax_energy.clear()

        # Plot spectrogram
        self._plot_spectrogram(analysis)

        # Plot energy spectrum with cutoff line
        self._plot_energy_spectrum(analysis, cutoff_khz)

        # Update figure
        self.fig.tight_layout(pad=2.0)
        self.canvas.draw()

        # Update info labels
        self.cutoff_label.configure(text=f"Frec. de corte: {cutoff_khz:.1f} kHz")
        self.max_freq_label.configure(
            text=f"Frec. max: {analysis.max_frequency_hz / 1000:.1f} kHz"
        )
        self.confidence_label.configure(
            text=f"Confianza: {analysis.confidence * 100:.0f}%"
        )

    def _plot_spectrogram(self, analysis: FrequencyAnalysis):
        """Plot the spectrogram."""
        ax = self.ax_spectrogram

        # Get data
        spectrogram_db = analysis.spectrogram_db
        frequencies = analysis.frequencies

        # Create time axis (simplified)
        n_frames = spectrogram_db.shape[1]
        times = np.arange(n_frames)

        # Plot spectrogram
        img = ax.imshow(
            spectrogram_db,
            aspect='auto',
            origin='lower',
            cmap='magma',
            extent=[0, n_frames, frequencies[0] / 1000, frequencies[-1] / 1000],
            vmin=-80,
            vmax=0,
        )

        # Add cutoff line
        cutoff_khz = analysis.cutoff_frequency_khz
        ax.axhline(y=cutoff_khz, color='cyan', linestyle='--', linewidth=1.5, alpha=0.8)

        # Labels
        ax.set_xlabel('Tiempo (frames)', fontsize=10, color='white')
        ax.set_ylabel('Frecuencia (kHz)', fontsize=10, color='white')
        ax.set_title('Espectrograma', fontsize=12, color='white')

        # Limit y-axis to relevant range
        ax.set_ylim(0, min(24, frequencies[-1] / 1000))

        ax.tick_params(colors='white', labelsize=8)

    def _plot_energy_spectrum(self, analysis: FrequencyAnalysis, cutoff_khz: float):
        """Plot the average energy spectrum with cutoff indicator."""
        ax = self.ax_energy

        # Get data
        energy = analysis.energy_spectrum
        frequencies = analysis.frequencies / 1000  # Convert to kHz

        # Plot energy curve
        ax.fill_between(frequencies, energy, -80, alpha=0.3, color='cyan')
        ax.plot(frequencies, energy, color='cyan', linewidth=1.5)

        # Add cutoff line
        ax.axvline(x=cutoff_khz, color='red', linestyle='--', linewidth=2, alpha=0.8)

        # Add noise floor line
        ax.axhline(y=-60, color='gray', linestyle=':', linewidth=1, alpha=0.5)

        # Add cutoff annotation
        ax.annotate(
            f'{cutoff_khz:.1f} kHz',
            xy=(cutoff_khz, -30),
            xytext=(cutoff_khz + 1, -20),
            fontsize=10,
            color='red',
            arrowprops=dict(arrowstyle='->', color='red', alpha=0.7),
        )

        # Labels
        ax.set_xlabel('Frecuencia (kHz)', fontsize=10, color='white')
        ax.set_ylabel('Energia (dB)', fontsize=10, color='white')
        ax.set_title('Espectro de Energia Promedio', fontsize=12, color='white')

        # Set limits
        ax.set_xlim(0, min(24, frequencies[-1]))
        ax.set_ylim(-80, 0)

        ax.tick_params(colors='white', labelsize=8)
        ax.grid(True, alpha=0.2)

    def clear(self):
        """Clear the spectrogram display."""
        self._current_analysis = None

        # Clear axes
        self.ax_spectrogram.clear()
        self.ax_energy.clear()
        self.canvas.draw()

        # Hide canvas, show empty state
        self.canvas_widget.grid_remove()
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")

        # Reset labels
        self.file_label.configure(text="")
        self.cutoff_label.configure(text="Frec. de corte: -")
        self.max_freq_label.configure(text="Frec. max: -")
        self.confidence_label.configure(text="Confianza: -")

    def get_current_analysis(self) -> Optional[FrequencyAnalysis]:
        """Get the currently displayed analysis."""
        return self._current_analysis
