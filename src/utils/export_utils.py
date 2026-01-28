"""Export utilities for generating CSV and TXT reports."""

import csv
from datetime import datetime
from pathlib import Path
from typing import List

from ..core.analyzer import AnalysisResult
from .file_utils import format_duration
from .constants import EXPORT_CSV, EXPORT_TXT


def export_to_csv(results: List[AnalysisResult], filepath: str) -> bool:
    """
    Export analysis results to a CSV file.

    Args:
        results: List of AnalysisResult objects
        filepath: Path to the output CSV file

    Returns:
        True if export was successful
    """
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'Archivo',
                'Ruta',
                'Formato',
                'Duracion',
                'Bitrate Declarado (kbps)',
                'Frecuencia de Corte (kHz)',
                'Calidad Detectada',
                'Estado',
                'Confianza (%)',
                'Detalles',
            ])

            # Data rows
            for result in results:
                writer.writerow([
                    result.filename,
                    result.filepath,
                    result.format,
                    format_duration(result.duration) if result.duration > 0 else '',
                    result.declared_bitrate if result.declared_bitrate else '',
                    f'{result.cutoff_frequency_khz:.1f}' if result.cutoff_frequency_khz > 0 else '',
                    result.detected_quality,
                    result.status,
                    f'{result.confidence * 100:.0f}' if result.confidence > 0 else '',
                    result.details,
                ])

        return True

    except Exception:
        return False


def export_to_txt(results: List[AnalysisResult], filepath: str) -> bool:
    """
    Export analysis results to a formatted TXT file.

    Args:
        results: List of AnalysisResult objects
        filepath: Path to the output TXT file

    Returns:
        True if export was successful
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            # Header
            f.write("=" * 80 + "\n")
            f.write("AUDIOQUAL - Reporte de Analisis de Calidad de Audio\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total de archivos: {len(results)}\n")
            f.write("=" * 80 + "\n\n")

            # Summary statistics
            status_counts = {}
            for result in results:
                status_counts[result.status] = status_counts.get(result.status, 0) + 1

            f.write("RESUMEN\n")
            f.write("-" * 40 + "\n")
            for status, count in sorted(status_counts.items()):
                f.write(f"  {status}: {count}\n")
            f.write("\n")

            # Detailed results
            f.write("RESULTADOS DETALLADOS\n")
            f.write("-" * 40 + "\n\n")

            for i, result in enumerate(results, 1):
                f.write(f"[{i}] {result.filename}\n")
                f.write(f"    Ruta: {result.filepath}\n")
                f.write(f"    Formato: {result.format}\n")

                if result.duration > 0:
                    f.write(f"    Duracion: {format_duration(result.duration)}\n")

                if result.declared_bitrate:
                    f.write(f"    Bitrate declarado: {result.declared_bitrate} kbps\n")

                if result.cutoff_frequency_khz > 0:
                    f.write(f"    Frecuencia de corte: {result.cutoff_frequency_khz:.1f} kHz\n")

                f.write(f"    Calidad detectada: {result.detected_quality}\n")
                f.write(f"    Estado: {result.status}\n")

                if result.confidence > 0:
                    f.write(f"    Confianza: {result.confidence * 100:.0f}%\n")

                if result.details:
                    f.write(f"    Detalles: {result.details}\n")

                if result.error:
                    f.write(f"    Error: {result.error}\n")

                f.write("\n")

            # Footer
            f.write("=" * 80 + "\n")
            f.write("Generado por AudioQual\n")
            f.write("=" * 80 + "\n")

        return True

    except Exception:
        return False


def export_results(
    results: List[AnalysisResult],
    filepath: str,
    format: str = EXPORT_CSV,
) -> bool:
    """
    Export analysis results to the specified format.

    Args:
        results: List of AnalysisResult objects
        filepath: Path to the output file
        format: Export format (csv or txt)

    Returns:
        True if export was successful
    """
    if format == EXPORT_CSV:
        return export_to_csv(results, filepath)
    elif format == EXPORT_TXT:
        return export_to_txt(results, filepath)
    else:
        return False


def get_suggested_filename(format: str = EXPORT_CSV) -> str:
    """
    Get a suggested filename with timestamp.

    Args:
        format: Export format

    Returns:
        Suggested filename string
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    extension = format if format in [EXPORT_CSV, EXPORT_TXT] else 'csv'
    return f"audioqual_report_{timestamp}.{extension}"
