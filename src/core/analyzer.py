"""Batch audio analysis engine with threading support."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .audio_loader import load_audio, AudioData
from .frequency_detector import analyze_frequency_cutoff, FrequencyAnalysis
from .bitrate_classifier import assess_quality, QualityAssessment
from ..utils.constants import (
    STATUS_ERROR,
    STATUS_PENDING,
    STATUS_ANALYZING,
    SAMPLE_RATE,
    FFT_SIZE,
    HOP_LENGTH,
)
from ..utils.file_utils import get_filename


@dataclass
class AnalysisResult:
    """Complete analysis result for a single file.

    Note: frequency_analysis is only populated temporarily during analysis
    and passed to the UI for visualization. It's NOT stored permanently
    to avoid memory accumulation (~4MB per file).
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


class AudioAnalyzer:
    """Main audio analysis engine."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        n_fft: int = FFT_SIZE,
        hop_length: int = HOP_LENGTH,
        max_workers: int = 4,
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
            AnalysisResult with complete analysis data
        """
        filename = get_filename(filepath)

        try:
            # Load audio
            audio_data = load_audio(filepath, self.sample_rate)

            # Analyze frequency cutoff
            frequency_analysis = analyze_frequency_cutoff(
                audio_data.samples,
                audio_data.sample_rate,
                self.n_fft,
                self.hop_length,
            )

            # Assess quality
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
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

        try:
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

                results.append(result)

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
                        frequency_analysis=None,  # Don't store - saves ~4MB per file
                        is_uncertain=result.is_uncertain,
                        uncertainty_reason=result.uncertainty_reason,
                        display_cutoff_override=result.display_cutoff_override,
                    )
                    self._state.results[filepath] = stored_result

                if progress_callback:
                    # Pass full result with frequency_analysis for UI display
                    progress_callback(
                        completed,
                        total,
                        result.filename,
                        result,
                    )

        finally:
            self._executor.shutdown(wait=False)
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


def create_analyzing_result(filepath: str) -> AnalysisResult:
    """Create an analyzing result placeholder for a file."""
    return AnalysisResult(
        filepath=filepath,
        filename=get_filename(filepath),
        format="",
        duration=0,
        declared_bitrate=None,
        detected_quality="",
        cutoff_frequency_khz=0,
        status=STATUS_ANALYZING,
        confidence=0,
        details="Analizando...",
    )
