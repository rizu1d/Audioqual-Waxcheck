"""Batch audio analysis engine with threading support."""

import multiprocessing
import os
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

# El paralelismo (cuantos auxiliares) y el reciclado (cada cuantos archivos muere
# y renace cada auxiliar, via maxtasksperchild) se deciden por la RAM DISPONIBLE
# en cada analisis (no la total: el publico objetivo suele tener la DAW abierta
# comiendo varios GB). Dos motivos para reciclar: un auxiliar de vida larga
# arrastra la marca de agua del allocator de cada archivo y se infla a varios GB
# (medido: ~4 GB tras 34 archivos); reciclando vuelve a su coste real (~1.5 GB).
# Con holgura -> mas workers + reciclado relajado (rapido). Justo -> menos workers
# + reciclado por archivo (pico minimo, mas lento, pero no ahoga el equipo).
RAM_RESERVED_GB = 1.5             # margen para el SO y la propia app
RAM_PER_WORKER_GB = 1.8           # pico de un auxiliar RECICLADO, por worker
RAM_GLUTTON_PER_WORKER_GB = 2.0   # pico de un auxiliar con reciclado relajado
RECYCLE_AGGRESSIVE = 1            # reciclar cada archivo: pico minimo, mas lento
RECYCLE_RELAXED = 6              # reciclar cada 6: techo de RAM, casi sin coste


def _total_ram_gb():
    """RAM fisica total en GB, sin psutil (es solo dependencia de dev, no se
    empaqueta). Multiplataforma. Devuelve None si no se puede determinar."""
    try:
        # POSIX (macOS, Linux)
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / (1024 ** 3)
    except (ValueError, AttributeError, OSError):
        pass
    try:
        # Windows
        import ctypes

        class _MemStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = _MemStatus()
        stat.dwLength = ctypes.sizeof(_MemStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return stat.ullTotalPhys / (1024 ** 3)
    except Exception:
        return None


def _available_ram_gb():
    """RAM DISPONIBLE ahora mismo en GB (no la total). psutil la calcula bien en
    los 3 SO; en macOS la 'libre' cruda engana (el SO usa RAM como cache y la
    comprime), por eso no basta sysconf. Fallback a la total si psutil fallara."""
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 ** 3)
    except Exception:
        return _total_ram_gb()


def _plan_parallelism():
    """Decide (max_workers, recycle_every) segun la RAM disponible AHORA.

    workers: cuantos auxiliares en paralelo, limitado por nucleos y por la RAM
    disponible (cada uno necesita ~RAM_PER_WORKER_GB de holgura).
    recycle: si el presupuesto cubre el pico gloton de esos workers, se recicla
    relajado (rapido); si va justo, se recicla cada archivo (pico minimo).
    """
    cpu = min(4, os.cpu_count() or 2)
    avail = _available_ram_gb()
    if avail is None:
        return min(2, cpu), RECYCLE_AGGRESSIVE  # RAM desconocida: conservador
    budget = avail - RAM_RESERVED_GB
    workers = max(1, min(cpu, int(budget / RAM_PER_WORKER_GB)))
    if budget >= workers * RAM_GLUTTON_PER_WORKER_GB:
        recycle = RECYCLE_RELAXED
    else:
        recycle = RECYCLE_AGGRESSIVE
    return workers, recycle


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


def _analyze_worker_star(args):
    """Adaptador para Pool.imap_unordered, que pasa un solo argumento."""
    return _analyze_file_worker(*args)


class AudioAnalyzer:
    """Main audio analysis engine."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        n_fft: int = FFT_SIZE,
        hop_length: int = HOP_LENGTH,
        max_workers: Optional[int] = None,
        recycle_every: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        # None en ambos -> se deciden por la RAM disponible al lanzar cada lote
        # (ver _plan_parallelism). Pasarlos explicitos los fija (util en tests).
        self.max_workers = max_workers
        self.recycle_every = recycle_every
        self._state = BatchAnalysisState()
        self._executor: Optional[ThreadPoolExecutor] = None  # modo hilos (lotes pequenos)
        self._pool = None  # modo procesos (lotes grandes), multiprocessing.Pool

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

        # Decide workers y reciclado por la RAM disponible AHORA (cambia entre
        # analisis: el usuario pudo abrir/cerrar la DAW desde el ultimo lote).
        workers, recycle = self._resolve_plan()

        # Lotes grandes -> procesos auxiliares (liberan su RAM al SO al terminar);
        # lotes pequenos -> hilos (sin coste de arranque de proceso).
        try:
            if len(filepaths) >= PROCESS_POOL_MIN_FILES:
                results = self._run_with_processes(filepaths, progress_callback, workers, recycle)
            else:
                results = self._run_with_threads(filepaths, progress_callback, workers)
        finally:
            with self._state.lock:
                self._state.is_running = False

        return results

    def _resolve_plan(self):
        """(workers, recycle_every) para este lote. Si no se fijaron en el
        constructor, se deciden por la RAM disponible en este momento."""
        auto_workers, auto_recycle = _plan_parallelism()
        workers = self.max_workers if self.max_workers is not None else auto_workers
        recycle = self.recycle_every if self.recycle_every is not None else auto_recycle
        return workers, recycle

    def _run_with_threads(self, filepaths, progress_callback, workers):
        """Modo hilos (lotes pequenos). El resultado conserva el espectrograma en
        memoria y la UI lo cachea, como hasta ahora."""
        results = []
        self._executor = ThreadPoolExecutor(max_workers=workers)
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
                self._store_and_report(result, results, progress_callback)
        finally:
            self._executor.shutdown(wait=True)
            self._executor = None
        return results

    def _run_with_processes(self, filepaths, progress_callback, workers, recycle):
        """Modo procesos (lotes grandes). Cada worker vuelca el espectrograma a
        disco y devuelve un resultado ligero (sin el array pesado).

        maxtasksperchild=recycle hace que cada worker muera y renazca, soltando
        la marca de agua del allocator; si no, un worker que procesa muchos
        archivos se infla a varios GB. El reposo lo libera todo al cerrar el pool;
        el pico queda acotado a ~workers x el coste de un archivo (~1.5 GB).
        """
        results = []
        args = [
            (fp, self.sample_rate, self.n_fft, self.hop_length)
            for fp in filepaths
        ]
        self._pool = multiprocessing.Pool(
            processes=workers,
            maxtasksperchild=recycle,
        )
        try:
            for result in self._pool.imap_unordered(_analyze_worker_star, args):
                if self._state.is_cancelled:
                    break
                self._store_and_report(result, results, progress_callback)
        finally:
            pool = self._pool
            self._pool = None
            if pool is not None:
                pool.terminate()  # mata workers (idempotente si cancel() ya lo hizo)
                pool.join()
        return results

    def _store_and_report(self, result, results, progress_callback):
        """Guarda una copia ligera (sin espectrograma) en el estado y en la lista
        de resultados, y dispara el callback con el resultado completo. Compartido
        por los modos hilos y procesos."""
        with self._state.lock:
            self._state.completed_files += 1
            completed = self._state.completed_files
            total = self._state.total_files
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
                frequency_analysis=None,  # no guardar el espectrograma pesado
                is_uncertain=result.is_uncertain,
                uncertainty_reason=result.uncertainty_reason,
                display_cutoff_override=result.display_cutoff_override,
            )
            self._state.results[result.filepath] = stored_result

        results.append(stored_result)

        if progress_callback:
            # El resultado completo lleva frequency_analysis solo en modo hilos;
            # en modo procesos ya viene None (volcado a disco por el worker).
            progress_callback(completed, total, result.filename, result)

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
        pool = self._pool
        if pool is not None:
            pool.terminate()  # interrumpe imap_unordered en marcha

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
