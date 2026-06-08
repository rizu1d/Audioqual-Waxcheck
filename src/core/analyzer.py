"""Batch audio analysis engine with threading support."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .audio_loader import load_audio, AudioData
from .frequency_detector import analyze_frequency_cutoff, FrequencyAnalysis
from .bitrate_classifier import assess_quality, QualityAssessment
from ..utils.constants import (
    STATUS_ERROR,
    STATUS_PENDING,
    SAMPLE_RATE,
    FFT_SIZE,
    HOP_LENGTH,
)
from ..utils.file_utils import get_filename

# Lotes con al menos este numero de archivos se analizan en PROCESOS auxiliares
# (no hilos). Cada proceso libera su RAM pesada (~1.5 GB/archivo de STFT) al SO
# al terminar, en vez de dejar esa "marca de agua" pegada en la app para siempre
# (los hilos comparten el espacio de memoria del proceso principal). Por debajo
# del umbral se usan hilos: arrancar un proceso reimporta numpy/scipy (~0.5 s) y
# no compensa para 1-2 archivos sueltos (p.ej. el watcher o un drag pequeno).
PROCESS_POOL_MIN_FILES = 4


@dataclass
class AnalysisResult:
    """Complete analysis result for a single file.

    Note: frequency_analysis is only populated temporarily during analysis
    and passed to the UI for visualization. It's NOT stored permanently
    to avoid memory accumulation (~100-200MB per file depending on duration).
    """
    filepath: str
    filename: str
    format: str
    duration: float
    declared_bitrate: Optional[int]
    detected_quality: str
    cutoff_frequency_khz: float
    status: str
    confidence: float
    details: str
    error: Optional[str] = None
    frequency_analysis: Optional[FrequencyAnalysis] = None  # Transient - cleared after UI display
    is_uncertain: bool = False  # True if result should be verified manually
    uncertainty_reason: str = ""  # Explanation for uncertainty
    display_cutoff_override: Optional[str] = None  # e.g., ">20 kHz" for genuine lossless


@dataclass
class BatchAnalysisState:
    """State of a batch analysis operation."""
    total_files: int = 0
    completed_files: int = 0
    current_file: str = ""
    is_running: bool = False
    is_cancelled: bool = False
    results: Dict[str, AnalysisResult] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


ProgressCallback = Callable[[int, int, str, Optional[AnalysisResult]], None]


def _analyze(filepath: str, sample_rate: int, n_fft: int, hop_length: int) -> AnalysisResult:
    """Nucleo del analisis de un archivo. Devuelve un AnalysisResult CON el
    `frequency_analysis` (el espectrograma pesado, ~100-200 MB).

    Es una funcion a nivel de modulo -no un metodo- a proposito: asi puede
    ejecutarse dentro de un proceso auxiliar (ProcessPoolExecutor), que exige
    objetos serializables y no transfiere bien los metodos enlazados.
    """
    filename = get_filename(filepath)

    try:
        audio_data = load_audio(filepath, sample_rate)

        frequency_analysis = analyze_frequency_cutoff(
            audio_data.samples,
            audio_data.sample_rate,
            n_fft,
            hop_length,
        )

        quality = assess_quality(frequency_analysis, audio_data.metadata)

        return AnalysisResult(
            filepath=filepath,
            filename=filename,
            format=audio_data.metadata.format,
            duration=audio_data.metadata.duration,
            declared_bitrate=audio_data.metadata.bitrate,
            detected_quality=quality.detected_quality,
            cutoff_frequency_khz=quality.cutoff_frequency_khz,
            status=quality.status,
            confidence=quality.confidence,
            details=quality.details,
            frequency_analysis=frequency_analysis,  # Passed for UI, cleared later
            is_uncertain=quality.is_uncertain,
            uncertainty_reason=quality.uncertainty_reason,
            display_cutoff_override=quality.display_cutoff_override,
        )

    except Exception as e:
        return AnalysisResult(
            filepath=filepath,
            filename=filename,
            format="",
            duration=0,
            declared_bitrate=None,
            detected_quality="unknown",
            cutoff_frequency_khz=0,
            status=STATUS_ERROR,
            confidence=0,
            details=str(e),
            error=str(e),
        )


def _analyze_file_worker(
    filepath: str, sample_rate: int, n_fft: int, hop_length: int
) -> AnalysisResult:
    """Ejecutado dentro de un PROCESO auxiliar.

    Analiza el archivo y, antes de devolver, vuelca el espectrograma a la cache
    de disco (~4 MB) ahi mismo. Luego suelta el espectrograma pesado y devuelve
    un resultado LIGERO (solo texto y numeros). Asi los ~100-200 MB nacen y
    mueren dentro del proceso auxiliar: cuando el pool lo cierra, el SO recupera
    toda esa RAM en vez de dejarla retenida en la app principal.

    Si el volcado a disco falla, no pasa nada critico: la app sabe recalcular el
    espectrograma bajo demanda al seleccionar el archivo.
    """
    result = _analyze(filepath, sample_rate, n_fft, hop_length)

    if result.frequency_analysis is not None:
        try:
            from ..utils.spectrogram_cache import save_to_cache
            save_to_cache(filepath, result.frequency_analysis, result.cutoff_frequency_khz)
        except Exception:
            pass  # red de seguridad: recalculo bajo demanda en la UI
        result.frequency_analysis = None

    return result


class AudioAnalyzer:
    """Main audio analysis engine."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        n_fft: int = FFT_SIZE,
        hop_length: int = HOP_LENGTH,
        max_workers: int = min(4, os.cpu_count() or 2),
    ):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.max_workers = max_workers
        self._state = BatchAnalysisState()
        self._executor: Optional[ThreadPoolExecutor] = None

    def analyze_file(self, filepath: str) -> AnalysisResult:
        """
        Analyze a single audio file.

        Args:
            filepath: Path to the audio file

        Returns:
            AnalysisResult with complete analysis data (incl. frequency_analysis)
        """
        return _analyze(filepath, self.sample_rate, self.n_fft, self.hop_length)

    def analyze_batch(
        self,
        filepaths: List[str],
        progress_callback: Optional[ProgressCallback] = None,
    ) -> List[AnalysisResult]:
        """
        Analyze multiple audio files with threading.

        Args:
            filepaths: List of file paths to analyze
            progress_callback: Optional callback for progress updates
                              (completed, total, current_file, result)

        Returns:
            List of AnalysisResult objects
        """
        with self._state.lock:
            self._state.total_files = len(filepaths)
            self._state.completed_files = 0
            self._state.is_running = True
            self._state.is_cancelled = False
            self._state.results.clear()

        results = []

        # Lotes grandes -> procesos auxiliares (liberan su RAM al SO al terminar,
        # ver PROCESS_POOL_MIN_FILES). Lotes pequenos -> hilos (sin coste de
        # arranque de proceso). Solo el modo procesos vuelca el espectrograma a
        # disco dentro del worker; el modo hilos sigue devolviendolo en memoria
        # para que la UI lo cachee como hasta ahora.
        use_processes = len(filepaths) >= PROCESS_POOL_MIN_FILES

        if use_processes:
            self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        else:
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

        try:
            if use_processes:
                futures = {
                    self._executor.submit(
                        _analyze_file_worker, fp,
                        self.sample_rate, self.n_fft, self.hop_length,
                    ): fp
                    for fp in filepaths
                }
            else:
                futures = {
                    self._executor.submit(self._analyze_with_state, fp): fp
                    for fp in filepaths
                }

            for future in as_completed(futures):
                if self._state.is_cancelled:
                    break

                filepath = futures[future]
                try:
                    result = future.result()
                except Exception as e:
                    result = AnalysisResult(
                        filepath=filepath,
                        filename=get_filename(filepath),
                        format="",
                        duration=0,
                        declared_bitrate=None,
                        detected_quality="unknown",
                        cutoff_frequency_khz=0,
                        status=STATUS_ERROR,
                        confidence=0,
                        details=str(e),
                        error=str(e),
                    )

                # Capture values inside lock to avoid race condition
                with self._state.lock:
                    self._state.completed_files += 1
                    completed = self._state.completed_files
                    total = self._state.total_files
                    # Store result WITHOUT frequency_analysis to save memory
                    # Create a lightweight copy for storage
                    stored_result = AnalysisResult(
                        filepath=result.filepath,
                        filename=result.filename,
                        format=result.format,
                        duration=result.duration,
                        declared_bitrate=result.declared_bitrate,
                        detected_quality=result.detected_quality,
                        cutoff_frequency_khz=result.cutoff_frequency_khz,
                        status=result.status,
                        confidence=result.confidence,
                        details=result.details,
                        error=result.error,
                        frequency_analysis=None,  # Don't store heavy spectrogram data
                        is_uncertain=result.is_uncertain,
                        uncertainty_reason=result.uncertainty_reason,
                        display_cutoff_override=result.display_cutoff_override,
                    )
                    self._state.results[filepath] = stored_result

                # Use lightweight copy (no spectrogram) for results list
                results.append(stored_result)

                if progress_callback:
                    # Pass full result with frequency_analysis for UI display
                    progress_callback(
                        completed,
                        total,
                        result.filename,
                        result,
                    )

        finally:
            self._executor.shutdown(wait=True)
            self._executor = None
            with self._state.lock:
                self._state.is_running = False

        return results

    def _analyze_with_state(self, filepath: str) -> AnalysisResult:
        """Analyze a file while updating state."""
        with self._state.lock:
            self._state.current_file = get_filename(filepath)

        return self.analyze_file(filepath)

    def cancel(self):
        """Cancel the current batch analysis."""
        with self._state.lock:
            self._state.is_cancelled = True

        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def get_state(self) -> BatchAnalysisState:
        """Get the current state of batch analysis."""
        return self._state

    def is_running(self) -> bool:
        """Check if analysis is currently running."""
        with self._state.lock:
            return self._state.is_running


def create_pending_result(filepath: str) -> AnalysisResult:
    """Create a pending result placeholder for a file."""
    return AnalysisResult(
        filepath=filepath,
        filename=get_filename(filepath),
        format="",
        duration=0,
        declared_bitrate=None,
        detected_quality="",
        cutoff_frequency_khz=0,
        status=STATUS_PENDING,
        confidence=0,
        details="Esperando análisis...",
    )
