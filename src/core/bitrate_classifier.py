"""Bitrate classification based on frequency cutoff analysis."""

from dataclasses import dataclass
from typing import Optional

from .frequency_detector import FrequencyAnalysis
from .audio_loader import AudioMetadata
from ..utils.constants import (
    BITRATE_THRESHOLDS,
    STATUS_OK,
    STATUS_TRANSCODE,
    STATUS_LOSSLESS,
    STATUS_LOW_QUALITY,
    STATUS_ERROR,
    STATUS_UNCERTAIN,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
)


@dataclass
class QualityAssessment:
    """Complete quality assessment results."""
    detected_quality: str  # e.g., "320kbps", "256kbps", "lossless"
    declared_bitrate: Optional[int]  # from metadata, in kbps
    cutoff_frequency_khz: float
    status: str  # OK, Transcode detectado, Lossless, etc.
    is_transcode: bool
    confidence: float
    details: str
    is_uncertain: bool = False  # True if result should be verified manually
    uncertainty_reason: str = ""  # Explanation for uncertainty


def classify_by_frequency(cutoff_khz: float) -> str:
    """
    Classify audio quality based on detected cutoff frequency.

    Args:
        cutoff_khz: Detected cutoff frequency in kHz

    Returns:
        Quality classification string
    """
    for quality, thresholds in BITRATE_THRESHOLDS.items():
        if thresholds["min_freq"] <= cutoff_khz <= thresholds["max_freq"]:
            return quality

    # If frequency is very high, likely lossless
    if cutoff_khz > 20.5:
        return "lossless"

    # If frequency is very low
    if cutoff_khz < 13.0:
        return "low"

    # Default to nearest match based on proximity
    return "unknown"


def detect_transcode(
    declared_bitrate: Optional[int],
    detected_quality: str,
    file_format: str,
) -> bool:
    """
    Detect if a file is likely a transcode (upscaled from lower quality).

    Args:
        declared_bitrate: Bitrate from file metadata (kbps)
        detected_quality: Quality detected from spectral analysis
        file_format: File format (MP3, FLAC, etc.)

    Returns:
        True if transcode is likely
    """
    if declared_bitrate is None:
        return False

    # Map detected quality to expected minimum bitrate
    quality_to_min_bitrate = {
        "lossless": 900,  # For FLAC/WAV typically much higher
        "320kbps": 280,
        "256kbps": 220,
        "192kbps": 160,
        "160kbps": 140,
        "128kbps": 96,
        "96kbps": 64,
        "low": 0,
    }

    # Map detected quality to a numeric value for comparison (ordered low to high)
    quality_order = ["low", "96kbps", "128kbps", "160kbps", "192kbps", "256kbps", "320kbps", "lossless"]

    # Get the expected quality based on declared bitrate
    expected_quality = "low"
    if declared_bitrate >= 280:
        expected_quality = "320kbps"
    elif declared_bitrate >= 220:
        expected_quality = "256kbps"
    elif declared_bitrate >= 160:
        expected_quality = "192kbps"
    elif declared_bitrate >= 140:
        expected_quality = "160kbps"
    elif declared_bitrate >= 96:
        expected_quality = "128kbps"
    elif declared_bitrate >= 64:
        expected_quality = "96kbps"

    # For lossless formats, check if detected quality matches
    if file_format.upper() in ["FLAC", "WAV", "AIFF"]:
        if detected_quality != "lossless":
            return True
        return False

    # For lossy formats, check if detected quality is significantly lower than declared
    try:
        expected_idx = quality_order.index(expected_quality)
        detected_idx = quality_order.index(detected_quality)

        # Transcode if detected is more than 1 step below expected
        return detected_idx < expected_idx - 1
    except ValueError:
        return False


def assess_quality(
    frequency_analysis: FrequencyAnalysis,
    metadata: AudioMetadata,
) -> QualityAssessment:
    """
    Perform complete quality assessment of an audio file.

    Args:
        frequency_analysis: Results from frequency analysis
        metadata: Audio file metadata

    Returns:
        QualityAssessment with complete results
    """
    cutoff_khz = frequency_analysis.cutoff_frequency_khz
    confidence = frequency_analysis.confidence
    is_uncertain = frequency_analysis.is_uncertain
    uncertainty_reason = frequency_analysis.uncertainty_reason

    # MP3-specific heuristics: MP3 320kbps encoders cut at ~20kHz, never 22kHz
    # If MP3 shows cutoff >21kHz, cap it at 20kHz
    is_mp3 = metadata.format.upper() == "MP3"
    if is_mp3 and cutoff_khz > 21.0:
        cutoff_khz = 20.0
        confidence = confidence * 0.8  # Lower confidence since we adjusted
        if not is_uncertain:
            is_uncertain = True
            uncertainty_reason = "MP3 ajustado: corte real ~20kHz"

    detected_quality = classify_by_frequency(cutoff_khz)

    # Additional MP3 heuristic: MP3 cannot truly be lossless
    if is_mp3 and detected_quality == "lossless":
        detected_quality = "320kbps"
        is_uncertain = True
        uncertainty_reason = "MP3 no puede ser lossless real"

    is_transcode = detect_transcode(
        metadata.bitrate,
        detected_quality,
        metadata.format,
    )

    # Determine status
    if detected_quality == "lossless":
        status = STATUS_LOSSLESS
    elif is_transcode:
        status = STATUS_TRANSCODE
    elif detected_quality in ("low", "96kbps"):
        status = STATUS_LOW_QUALITY
    else:
        status = STATUS_OK

    # Check for low confidence scenarios
    if confidence < CONFIDENCE_LOW and not is_uncertain:
        is_uncertain = True
        uncertainty_reason = "Baja confianza en la detección"

    # Modify status for uncertain cases (except errors and transcodes)
    if is_uncertain and status not in (STATUS_TRANSCODE,):
        status = STATUS_UNCERTAIN

    # Generate details message
    details = generate_details(
        detected_quality,
        metadata.bitrate,
        cutoff_khz,
        is_transcode,
        metadata.format,
    )

    # Add uncertainty reason to details if present
    if uncertainty_reason:
        details = f"{details} | {uncertainty_reason}"

    return QualityAssessment(
        detected_quality=detected_quality,
        declared_bitrate=metadata.bitrate,
        cutoff_frequency_khz=cutoff_khz,
        status=status,
        is_transcode=is_transcode,
        confidence=confidence,
        details=details,
        is_uncertain=is_uncertain,
        uncertainty_reason=uncertainty_reason,
    )


def generate_details(
    detected_quality: str,
    declared_bitrate: Optional[int],
    cutoff_khz: float,
    is_transcode: bool,
    file_format: str,
) -> str:
    """Generate a human-readable details message."""
    parts = []

    parts.append(f"Frecuencia de corte: {cutoff_khz:.1f} kHz")

    if declared_bitrate:
        parts.append(f"Bitrate declarado: {declared_bitrate} kbps")

    if is_transcode:
        if file_format.upper() in ["FLAC", "WAV", "AIFF"]:
            parts.append(f"Archivo {file_format} convertido desde fuente de menor calidad")
        else:
            parts.append(f"Posible conversión desde ~{detected_quality}")

    return " | ".join(parts)
