"""Frequency cutoff detection through spectral analysis."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import librosa
import numpy as np

from ..utils.constants import (
    FFT_SIZE,
    HOP_LENGTH,
    NOISE_FLOOR_DB,
    GRADIENT_THRESHOLD,
    SHELF_WINDOW_HZ,
    SHELF_DROP_DB,
    SHELF_SUSTAIN_DB,
    SHELF_REFERENCE_LOW_KHZ,
    SHELF_REFERENCE_HIGH_KHZ,
    SHELF_NOISE_LOW_KHZ,
    SHELF_NOISE_HIGH_KHZ,
    SHELF_SEARCH_START_KHZ,
    SHELF_SEARCH_END_KHZ,
    RELATIVE_REFERENCE_LOW_KHZ,
    RELATIVE_REFERENCE_HIGH_KHZ,
    RELATIVE_DROP_DB,
    RELATIVE_VARIANCE_THRESHOLD,
    RELATIVE_STRICT_VARIANCE_THRESHOLD,
    RELATIVE_BAND_WIDTH_KHZ,
    RELATIVE_SEARCH_START_KHZ,
    RELATIVE_SEARCH_END_KHZ,
    RELATIVE_MIN_ACTIVE_RATIO,
    SEGMENT_COUNT,
    PREDOMINANT_PERCENTILE,
    OUTLIER_THRESHOLD_KHZ,
    TRANSITION_MIN_DROP_DB,
    TRANSITION_BAND_WIDTH_HZ,
    TRANSITION_SEARCH_START_HZ,
    TRANSITION_SEARCH_END_HZ,
    TRANSITION_MIN_ENERGY_DB,
    TRANSITION_CONFIRMATION_BANDS,
    TRANSITION_VARIANCE_DROP_RATIO,
    TRANSITION_RECOVERY_THRESHOLD_DB,
    TRANSITION_MIN_PRE_VARIANCE,
    TRANSITION_VARIANCE_FREQ_LOW_HZ,
    TRANSITION_VARIANCE_FREQ_HIGH_HZ,
    TRANSITION_MIN_PRE_VARIANCE_HIGH_FREQ,
    TRANSITION_CUMULATIVE_BANDS,
    TRANSITION_CUMULATIVE_DROP_DB,
    TRANSITION_RECOVERY_CONSECUTIVE_BANDS,
    TRANSITION_RECOVERY_MIN_VARIANCE,
)


@dataclass
class FrequencyAnalysis:
    """Results of frequency analysis."""
    cutoff_frequency_hz: float
    cutoff_frequency_khz: float
    max_frequency_hz: float
    energy_spectrum: np.ndarray
    frequencies: np.ndarray
    spectrogram_db: np.ndarray
    confidence: float  # 0-1, how confident we are in the detection
    is_uncertain: bool = False  # True if detection has low confidence
    uncertainty_reason: str = ""  # Explanation for uncertainty
    cutoff_range_khz: Optional[Tuple[float, float]] = None  # (min, max) for variable quality
    energy_at_cutoff_db: float = -80.0  # Average energy in band just before cutoff (dB)


def compute_spectrogram(
    samples: np.ndarray,
    sample_rate: int,
    n_fft: int = FFT_SIZE,
    hop_length: int = HOP_LENGTH,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute the spectrogram of audio samples.

    Args:
        samples: Audio samples
        sample_rate: Sample rate
        n_fft: FFT window size
        hop_length: Hop length between frames

    Returns:
        Tuple of (spectrogram in dB, frequency bins)
    """
    # Compute STFT
    stft = librosa.stft(samples, n_fft=n_fft, hop_length=hop_length)

    # Convert to magnitude (float32 for half memory and better cache locality)
    magnitude = np.abs(stft).astype(np.float32)
    spectrogram_db = librosa.amplitude_to_db(magnitude, ref=np.max)

    # Get frequency bins
    frequencies = librosa.fft_frequencies(sr=sample_rate, n_fft=n_fft)

    return spectrogram_db, frequencies


def compute_energy_per_frequency(spectrogram_db: np.ndarray) -> np.ndarray:
    """
    Compute average energy per frequency band across all time frames.

    Args:
        spectrogram_db: Spectrogram in dB scale

    Returns:
        Array of average energy values for each frequency bin
    """
    return np.mean(spectrogram_db, axis=1)


def find_cutoff_frequency_basic(
    energy_spectrum: np.ndarray,
    frequencies: np.ndarray,
    noise_floor_db: float = NOISE_FLOOR_DB,
) -> Tuple[float, float]:
    """
    Find the cutoff frequency using basic threshold method.

    Args:
        energy_spectrum: Average energy per frequency band
        frequencies: Frequency bins
        noise_floor_db: Threshold below which we consider noise

    Returns:
        Tuple of (cutoff frequency in Hz, confidence)
    """
    # Find frequencies where energy is above noise floor
    above_noise = energy_spectrum > noise_floor_db

    if not np.any(above_noise):
        return 0.0, 0.0

    # Find the highest frequency with significant energy
    indices_above = np.where(above_noise)[0]
    max_index = indices_above[-1] if len(indices_above) > 0 else 0

    cutoff_hz = frequencies[max_index]

    # Calculate confidence based on how clear the cutoff is
    # Higher confidence if there's a clear drop in energy
    if max_index < len(energy_spectrum) - 1:
        energy_drop = energy_spectrum[max_index] - energy_spectrum[min(max_index + 5, len(energy_spectrum) - 1)]
        confidence = min(1.0, max(0.0, energy_drop / 20.0))
    else:
        confidence = 0.5

    return cutoff_hz, confidence


def find_cutoff_frequency_gradient(
    energy_spectrum: np.ndarray,
    frequencies: np.ndarray,
    gradient_threshold: float = GRADIENT_THRESHOLD,
) -> Tuple[float, float]:
    """
    Find the cutoff frequency using gradient analysis.
    Detects abrupt drops in energy that indicate codec filtering.

    Args:
        energy_spectrum: Average energy per frequency band
        frequencies: Frequency bins
        gradient_threshold: Threshold for detecting abrupt drops

    Returns:
        Tuple of (cutoff frequency in Hz, confidence)
    """
    # Smooth the energy spectrum slightly
    window_size = 5
    smoothed = np.convolve(energy_spectrum, np.ones(window_size) / window_size, mode='same')

    # Calculate gradient
    gradient = np.gradient(smoothed)

    # Look for significant negative gradients (sharp drops) in the high frequency range
    # Focus on frequencies above 10 kHz
    min_freq_idx = np.searchsorted(frequencies, 10000)

    if min_freq_idx >= len(gradient):
        return 0.0, 0.0

    # Find the first significant drop after 10 kHz
    gradient_subset = gradient[min_freq_idx:]
    frequencies_subset = frequencies[min_freq_idx:]

    # Find indices where gradient is below threshold (sharp drop)
    drop_indices = np.where(gradient_subset < gradient_threshold)[0]

    if len(drop_indices) == 0:
        # No sharp drop found, might be lossless or high quality
        return frequencies[-1], 0.5

    # The cutoff is at the first significant drop
    cutoff_idx = drop_indices[0]
    cutoff_hz = frequencies_subset[cutoff_idx]

    # Calculate confidence based on the magnitude of the drop
    drop_magnitude = abs(gradient_subset[cutoff_idx])
    confidence = min(1.0, drop_magnitude / 10.0)

    return cutoff_hz, confidence


def smooth_energy_spectrum(
    energy_spectrum: np.ndarray,
    frequencies: np.ndarray,
    window_hz: float = SHELF_WINDOW_HZ,
) -> np.ndarray:
    """
    Smooth the energy spectrum using a window of specified Hz width.

    Args:
        energy_spectrum: Energy per frequency bin
        frequencies: Frequency bins array
        window_hz: Width of smoothing window in Hz

    Returns:
        Smoothed energy spectrum
    """
    if len(frequencies) < 2:
        return energy_spectrum

    # Calculate frequency resolution
    freq_resolution = frequencies[1] - frequencies[0] if len(frequencies) > 1 else 1.0

    # Calculate window size in bins
    window_bins = max(1, int(window_hz / freq_resolution))
    if window_bins % 2 == 0:
        window_bins += 1  # Make odd for symmetric window

    # Apply moving average
    kernel = np.ones(window_bins) / window_bins
    smoothed = np.convolve(energy_spectrum, kernel, mode='same')

    return smoothed


def estimate_noise_floor(
    energy_spectrum: np.ndarray,
    frequencies: np.ndarray,
    low_khz: float = SHELF_NOISE_LOW_KHZ,
    high_khz: float = SHELF_NOISE_HIGH_KHZ,
) -> float:
    """
    Estimate the noise floor by measuring energy in the highest frequency band.

    Args:
        energy_spectrum: Energy per frequency bin
        frequencies: Frequency bins array
        low_khz: Lower bound for noise estimation (kHz)
        high_khz: Upper bound for noise estimation (kHz)

    Returns:
        Estimated noise floor in dB
    """
    low_hz = low_khz * 1000
    high_hz = high_khz * 1000

    # Find indices for the noise estimation range
    low_idx = np.searchsorted(frequencies, low_hz)
    high_idx = np.searchsorted(frequencies, high_hz)

    if low_idx >= len(frequencies):
        low_idx = len(frequencies) - 1
    if high_idx >= len(frequencies):
        high_idx = len(frequencies)

    if low_idx >= high_idx:
        # Fallback: use the last 5% of frequencies
        low_idx = int(len(frequencies) * 0.95)
        high_idx = len(frequencies)

    noise_region = energy_spectrum[low_idx:high_idx]
    if len(noise_region) == 0:
        return NOISE_FLOOR_DB

    return np.mean(noise_region)


def estimate_signal_reference(
    energy_spectrum: np.ndarray,
    frequencies: np.ndarray,
    low_khz: float = SHELF_REFERENCE_LOW_KHZ,
    high_khz: float = SHELF_REFERENCE_HIGH_KHZ,
) -> float:
    """
    Estimate the reference signal level from the active frequency band.

    Args:
        energy_spectrum: Energy per frequency bin
        frequencies: Frequency bins array
        low_khz: Lower bound for reference (kHz)
        high_khz: Upper bound for reference (kHz)

    Returns:
        Reference signal level in dB
    """
    low_hz = low_khz * 1000
    high_hz = high_khz * 1000

    low_idx = np.searchsorted(frequencies, low_hz)
    high_idx = np.searchsorted(frequencies, high_hz)

    if high_idx > len(frequencies):
        high_idx = len(frequencies)

    if low_idx >= high_idx:
        return 0.0

    signal_region = energy_spectrum[low_idx:high_idx]
    return np.mean(signal_region)


# =============================================================================
# Relative Energy Detection Functions (improved algorithm for transcode detection)
# =============================================================================


def compute_reference_band_stats(
    spectrogram_db: np.ndarray,
    frequencies: np.ndarray,
    low_khz: float = RELATIVE_REFERENCE_LOW_KHZ,
    high_khz: float = RELATIVE_REFERENCE_HIGH_KHZ,
) -> Tuple[np.ndarray, float, float]:
    """
    Compute reference band energy statistics.

    The reference band (2-8 kHz) contains musical content in virtually all audio.
    We use this as a baseline to compare other frequency bands against.

    Args:
        spectrogram_db: Full spectrogram (frequency_bins x time_frames)
        frequencies: Frequency bins array
        low_khz: Lower bound for reference band (kHz)
        high_khz: Upper bound for reference band (kHz)

    Returns:
        Tuple of (energy_per_frame, overall_mean, overall_std)
    """
    low_hz = low_khz * 1000
    high_hz = high_khz * 1000

    low_idx = np.searchsorted(frequencies, low_hz)
    high_idx = np.searchsorted(frequencies, high_hz)

    if high_idx > len(frequencies):
        high_idx = len(frequencies)

    if low_idx >= high_idx:
        # Fallback if indices are invalid
        return np.zeros(spectrogram_db.shape[1]), -60.0, 1.0

    # Extract reference band
    ref_band = spectrogram_db[low_idx:high_idx, :]

    # Mean energy per frame (average across frequency bins)
    energy_per_frame = np.mean(ref_band, axis=0)

    return energy_per_frame, np.mean(energy_per_frame), np.std(energy_per_frame)


def identify_active_frames(
    ref_energy_per_frame: np.ndarray,
    ref_mean: float,
    ref_std: float,
    silence_threshold_std: float = 2.0,
) -> np.ndarray:
    """
    Identify frames that contain active musical content (non-silent).

    A frame is "active" if its reference energy is above:
    mean - (silence_threshold_std * std)

    Args:
        ref_energy_per_frame: Energy per frame in reference band
        ref_mean: Mean energy across all frames
        ref_std: Standard deviation of energy
        silence_threshold_std: Number of std below mean to consider silence

    Returns:
        Boolean mask of active frames
    """
    # Handle edge case of very low std
    effective_std = max(ref_std, 1.0)
    threshold = ref_mean - (silence_threshold_std * effective_std)
    return ref_energy_per_frame > threshold


def compute_band_relative_energy(
    spectrogram_db: np.ndarray,
    frequencies: np.ndarray,
    band_low_hz: float,
    band_high_hz: float,
    ref_energy_per_frame: np.ndarray,
    active_frames_mask: np.ndarray,
) -> float:
    """
    Compute the relative energy of a frequency band compared to reference.

    Only uses active (non-silent) frames for the calculation.

    Args:
        spectrogram_db: Full spectrogram
        frequencies: Frequency bins array
        band_low_hz: Lower bound of band (Hz)
        band_high_hz: Upper bound of band (Hz)
        ref_energy_per_frame: Reference band energy per frame
        active_frames_mask: Boolean mask of active frames

    Returns:
        Relative energy in dB (negative = lower than reference)
    """
    low_idx = np.searchsorted(frequencies, band_low_hz)
    high_idx = np.searchsorted(frequencies, band_high_hz)

    if high_idx > len(frequencies):
        high_idx = len(frequencies)

    if low_idx >= high_idx:
        return -60.0  # Very low energy if invalid band

    # Extract band for active frames only
    band_data = spectrogram_db[low_idx:high_idx, :]
    band_data_active = band_data[:, active_frames_mask]
    ref_active = ref_energy_per_frame[active_frames_mask]

    if band_data_active.size == 0 or ref_active.size == 0:
        return -60.0

    # Mean energy per active frame
    band_energy_per_frame = np.mean(band_data_active, axis=0)

    # Calculate relative energy (band - reference) per frame, then average
    relative_per_frame = band_energy_per_frame - ref_active
    return np.mean(relative_per_frame)


def compute_band_temporal_variance(
    spectrogram_db: np.ndarray,
    frequencies: np.ndarray,
    band_low_hz: float,
    band_high_hz: float,
    active_frames_mask: np.ndarray,
    ref_std: float,
) -> float:
    """
    Compute normalized temporal variance of a frequency band.

    Musical content has HIGH variance (energy changes with the music).
    Noise/artifacts have LOW variance (constant energy level).

    Args:
        spectrogram_db: Full spectrogram
        frequencies: Frequency bins array
        band_low_hz: Lower bound of band (Hz)
        band_high_hz: Upper bound of band (Hz)
        active_frames_mask: Boolean mask of active frames
        ref_std: Reference band standard deviation (for normalization)

    Returns:
        Normalized variance (0 = no variation, 1 = variation equal to reference)
    """
    low_idx = np.searchsorted(frequencies, band_low_hz)
    high_idx = np.searchsorted(frequencies, band_high_hz)

    if high_idx > len(frequencies):
        high_idx = len(frequencies)

    if low_idx >= high_idx:
        return 0.0

    # Extract band for active frames
    band_data = spectrogram_db[low_idx:high_idx, :]
    band_data_active = band_data[:, active_frames_mask]

    if band_data_active.size == 0:
        return 0.0

    # Mean energy per frame
    band_energy_per_frame = np.mean(band_data_active, axis=0)

    # Calculate variance (standard deviation)
    band_std = np.std(band_energy_per_frame)

    # Normalize by reference std (avoid division by zero)
    if ref_std < 0.1:
        ref_std = 0.1

    return band_std / ref_std


def generate_band_edges(
    start_khz: float,
    end_khz: float,
    width_khz: float,
) -> List[Tuple[float, float]]:
    """
    Generate band edges for analysis, from high to low frequency.

    Args:
        start_khz: Starting frequency (high end)
        end_khz: Ending frequency (low end)
        width_khz: Width of each band

    Returns:
        List of (high_khz, low_khz) tuples
    """
    bands = []
    current = start_khz
    while current > end_khz:
        band_high = current
        band_low = max(end_khz, current - width_khz)
        bands.append((band_high, band_low))
        current -= width_khz
    return bands


def classify_band_as_musical(
    relative_energy: float,
    variance: float,
    energy_threshold: float = RELATIVE_DROP_DB,
    variance_threshold: float = RELATIVE_VARIANCE_THRESHOLD,
    strict_variance_threshold: float = RELATIVE_STRICT_VARIANCE_THRESHOLD,
) -> bool:
    """
    Classify a frequency band as musical content or noise.

    Classification logic:
    1. High energy (>= threshold): Definitely musical content
    2. Low energy + High variance (>= strict threshold): Likely quiet music
    3. Low energy + Medium/Low variance: Noise (reject)

    The strict variance threshold prevents high-frequency noise with moderate
    temporal variance from being classified as musical content.

    Args:
        relative_energy: Energy relative to reference band (dB)
        variance: Normalized temporal variance (band_std / ref_std)
        energy_threshold: Threshold for energy (dB)
        variance_threshold: Normal variance threshold (unused, kept for compatibility)
        strict_variance_threshold: Stricter threshold for low-energy bands

    Returns:
        True if band contains musical content
    """
    # Case 1: High energy = definitely musical content
    if relative_energy >= energy_threshold:
        return True

    # Case 2: Low energy - require STRICT variance to consider as music
    # This prevents noise with moderate variance from being classified as music
    # Noise typically has variance < 0.5 of reference, real music has > 0.5
    if variance >= strict_variance_threshold:
        return True

    # Case 3: Low energy + insufficient variance = noise
    return False


def find_cutoff_relative_energy(
    spectrogram_db: np.ndarray,
    frequencies: np.ndarray,
    sample_rate: int = 44100,
    reference_low_khz: float = RELATIVE_REFERENCE_LOW_KHZ,
    reference_high_khz: float = RELATIVE_REFERENCE_HIGH_KHZ,
    band_width_khz: float = RELATIVE_BAND_WIDTH_KHZ,
    relative_drop_db: float = RELATIVE_DROP_DB,
    variance_threshold: float = RELATIVE_VARIANCE_THRESHOLD,
    search_start_khz: float = RELATIVE_SEARCH_START_KHZ,
    search_end_khz: float = RELATIVE_SEARCH_END_KHZ,
    min_active_frames_ratio: float = RELATIVE_MIN_ACTIVE_RATIO,
) -> Tuple[float, float]:
    """
    Find cutoff frequency using relative energy and temporal variance analysis.

    This method distinguishes between real musical content and noise/artifacts
    by analyzing:
    1. Energy relative to reference band (2-8 kHz)
    2. Temporal variance (music varies, noise is constant)

    Args:
        spectrogram_db: Full spectrogram (frequency_bins x time_frames)
        frequencies: Frequency bins array
        sample_rate: Sample rate of audio
        reference_low_khz: Lower bound of reference band (kHz)
        reference_high_khz: Upper bound of reference band (kHz)
        band_width_khz: Width of analysis bands (kHz)
        relative_drop_db: Energy drop threshold from reference (dB)
        variance_threshold: Normalized variance threshold
        search_start_khz: Start frequency for search (kHz)
        search_end_khz: End frequency for search (kHz)
        min_active_frames_ratio: Minimum ratio of active frames required

    Returns:
        Tuple of (cutoff frequency in Hz, confidence)
    """
    # Calculate Nyquist frequency
    nyquist_hz = sample_rate / 2

    # Step 1: Calculate reference band statistics
    ref_energy_per_frame, ref_mean, ref_std = compute_reference_band_stats(
        spectrogram_db, frequencies, reference_low_khz, reference_high_khz
    )

    # Step 2: Identify active frames (non-silent)
    active_frames_mask = identify_active_frames(
        ref_energy_per_frame, ref_mean, ref_std
    )

    # Check if enough active frames
    active_ratio = np.mean(active_frames_mask)
    if active_ratio < min_active_frames_ratio:
        # Too few active frames - likely silent or very quiet file
        return nyquist_hz, 0.2

    # Step 3: Search for cutoff frequency
    cutoff_hz = nyquist_hz  # Default: no cutoff found (lossless)
    best_confidence = 0.3

    # Generate band boundaries (from high to low)
    band_edges = generate_band_edges(search_start_khz, search_end_khz, band_width_khz)

    for band_high_khz, band_low_khz in band_edges:
        band_low_hz = band_low_khz * 1000
        band_high_hz = band_high_khz * 1000

        # Calculate relative energy for this band
        band_relative_energy = compute_band_relative_energy(
            spectrogram_db, frequencies,
            band_low_hz, band_high_hz,
            ref_energy_per_frame, active_frames_mask
        )

        # Calculate temporal variance (normalized)
        band_variance = compute_band_temporal_variance(
            spectrogram_db, frequencies,
            band_low_hz, band_high_hz,
            active_frames_mask, ref_std
        )

        # Classify this band
        is_musical = classify_band_as_musical(
            band_relative_energy, band_variance,
            relative_drop_db, variance_threshold
        )

        if is_musical:
            # Found musical content - this is the cutoff
            cutoff_hz = band_high_hz  # Use upper edge of band

            # Calculate confidence based on how clear the distinction is
            energy_margin = (band_relative_energy - relative_drop_db) / 10.0
            variance_margin = (band_variance - variance_threshold) / variance_threshold
            best_confidence = min(1.0, 0.5 + energy_margin * 0.25 + variance_margin * 0.25)
            best_confidence = max(0.3, best_confidence)  # Minimum confidence
            break

    return cutoff_hz, best_confidence


def combine_detection_methods(
    cutoff_relative: float, conf_relative: float,
    cutoff_shelf: float, conf_shelf: float,
    cutoff_gradient: float, conf_gradient: float,
) -> Tuple[float, float]:
    """
    Combine multiple detection methods for robust cutoff detection.

    Priority:
    1. If relative method has high confidence (>=0.7), trust it
    2. If multiple methods agree (within 2kHz), boost confidence
    3. If disagreement, prefer the LOWER cutoff (more conservative)

    Args:
        cutoff_relative: Cutoff from relative energy method (Hz)
        conf_relative: Confidence from relative energy method
        cutoff_shelf: Cutoff from shelf detection method (Hz)
        conf_shelf: Confidence from shelf detection method
        cutoff_gradient: Cutoff from gradient method (Hz)
        conf_gradient: Confidence from gradient method

    Returns:
        Tuple of (final cutoff Hz, final confidence)
    """
    # Case 1: Relative method is very confident
    if conf_relative >= 0.7:
        return cutoff_relative, conf_relative

    # Case 2: Check for agreement between methods
    cutoffs = [cutoff_relative, cutoff_shelf, cutoff_gradient]
    confidences = [conf_relative, conf_shelf, conf_gradient]

    # Find pairs that agree (within 2kHz)
    agreements = []
    for i in range(len(cutoffs)):
        for j in range(i + 1, len(cutoffs)):
            if abs(cutoffs[i] - cutoffs[j]) < 2000:
                avg_cutoff = (cutoffs[i] + cutoffs[j]) / 2
                avg_conf = (confidences[i] + confidences[j]) / 2
                agreements.append((avg_cutoff, min(1.0, avg_conf + 0.15)))

    if agreements:
        # Return the agreement with highest boosted confidence
        return max(agreements, key=lambda x: x[1])

    # Case 3: Disagreement - prefer lower cutoff (more conservative)
    # Lower cutoff avoids false "lossless" classification for transcodes
    weighted_cutoffs = list(zip(cutoffs, confidences))

    # Sort by cutoff (ascending) and pick lowest with decent confidence
    weighted_cutoffs.sort(key=lambda x: x[0])
    for cutoff, conf in weighted_cutoffs:
        if conf >= 0.4:
            return cutoff, conf

    # Fallback: return relative method result
    return cutoff_relative, conf_relative


# =============================================================================
# Shelf Detection Functions (original algorithm)
# =============================================================================


def validate_cutoff(
    energy_spectrum: np.ndarray,
    frequencies: np.ndarray,
    cutoff_hz: float,
    noise_floor_db: float,
    signal_ref_db: float,
    sustain_db: float = SHELF_SUSTAIN_DB,
) -> Tuple[bool, float]:
    """
    Validate that a detected cutoff is a real brick-wall filter.

    Checks that:
    1. Energy before cutoff is significantly above noise floor
    2. Energy after cutoff stays consistently low (near noise floor)

    Args:
        energy_spectrum: Energy per frequency bin
        frequencies: Frequency bins array
        cutoff_hz: Detected cutoff frequency
        noise_floor_db: Estimated noise floor
        signal_ref_db: Reference signal level
        sustain_db: Maximum variation allowed post-cutoff

    Returns:
        Tuple of (is_valid, confidence)
    """
    cutoff_idx = np.searchsorted(frequencies, cutoff_hz)

    if cutoff_idx >= len(frequencies) - 5:
        # Cutoff is too close to Nyquist, might be lossless
        return True, 0.5

    if cutoff_idx < 5:
        return False, 0.0

    # Check energy before cutoff (should be above noise)
    pre_cutoff_range = max(5, int(cutoff_idx * 0.1))
    pre_start = max(0, cutoff_idx - pre_cutoff_range)
    energy_before = np.mean(energy_spectrum[pre_start:cutoff_idx])

    # Check energy after cutoff (should be near noise floor)
    post_range = min(len(frequencies) - cutoff_idx, 20)
    if post_range > 5:
        energy_after = np.mean(energy_spectrum[cutoff_idx:cutoff_idx + post_range])
        energy_after_std = np.std(energy_spectrum[cutoff_idx:cutoff_idx + post_range])
    else:
        energy_after = noise_floor_db
        energy_after_std = 0

    # Calculate drop from before to after cutoff
    actual_drop = energy_before - energy_after

    # Calculate how close the post-cutoff energy is to noise floor
    post_noise_diff = abs(energy_after - noise_floor_db)

    # Validate the cutoff
    is_valid = (
        actual_drop > SHELF_DROP_DB * 0.5 and  # Significant drop
        post_noise_diff < sustain_db * 2 and   # Post-cutoff is near noise floor
        energy_after_std < sustain_db          # Post-cutoff is consistent
    )

    # Calculate confidence
    if is_valid:
        # Higher confidence for clearer drops
        drop_factor = min(1.0, actual_drop / SHELF_DROP_DB)
        stability_factor = max(0.0, 1.0 - (energy_after_std / sustain_db))
        noise_proximity = max(0.0, 1.0 - (post_noise_diff / sustain_db))
        confidence = (drop_factor * 0.5 + stability_factor * 0.25 + noise_proximity * 0.25)
    else:
        confidence = 0.2

    return is_valid, confidence


def find_cutoff_shelf_detection(
    energy_spectrum: np.ndarray,
    frequencies: np.ndarray,
    noise_floor_db: float = NOISE_FLOOR_DB,
    window_hz: float = SHELF_WINDOW_HZ,
) -> Tuple[float, float]:
    """
    Find the cutoff frequency using shelf detection (brick-wall filter detection).

    This method searches from high frequencies downward to find where the energy
    rises above the noise floor, which indicates the codec's low-pass filter cutoff.

    Args:
        energy_spectrum: Average energy per frequency band
        frequencies: Frequency bins
        noise_floor_db: Threshold for noise floor
        window_hz: Smoothing window width in Hz

    Returns:
        Tuple of (cutoff frequency in Hz, confidence)
    """
    # Smooth the energy spectrum
    smoothed = smooth_energy_spectrum(energy_spectrum, frequencies, window_hz)

    # Estimate noise floor from highest frequencies
    estimated_noise = estimate_noise_floor(smoothed, frequencies)

    # Estimate reference signal level
    signal_ref = estimate_signal_reference(smoothed, frequencies)

    # If signal is not much above noise, can't reliably detect cutoff
    if signal_ref - estimated_noise < SHELF_DROP_DB * 0.5:
        return frequencies[-1], 0.3

    # Define threshold for "significant energy" above noise
    threshold_db = estimated_noise + SHELF_DROP_DB * 0.5

    # Find search range indices
    start_hz = SHELF_SEARCH_START_KHZ * 1000
    end_hz = SHELF_SEARCH_END_KHZ * 1000

    start_idx = min(np.searchsorted(frequencies, start_hz), len(frequencies) - 1)
    end_idx = np.searchsorted(frequencies, end_hz)

    if start_idx <= end_idx:
        # Invalid range
        return frequencies[-1], 0.3

    # Search from high frequencies downward
    cutoff_idx = start_idx
    found_cutoff = False

    for idx in range(start_idx, end_idx, -1):
        current_energy = smoothed[idx]

        # Check if energy rises significantly above noise
        if current_energy > threshold_db:
            # Found a potential cutoff point
            # Verify this is consistent (not just a spike)

            # Check a small window before this point
            window_start = max(end_idx, idx - 5)
            window_energies = smoothed[window_start:idx+1]

            # Count how many points are above threshold
            above_threshold = np.sum(window_energies > threshold_db)

            if above_threshold >= 3 or idx - window_start < 3:
                # Confirmed: consistent energy above threshold
                cutoff_idx = idx
                found_cutoff = True
                break

    cutoff_hz = frequencies[cutoff_idx]

    # Validate the detected cutoff
    if found_cutoff:
        is_valid, confidence = validate_cutoff(
            smoothed, frequencies, cutoff_hz, estimated_noise, signal_ref
        )
        if not is_valid:
            # Cutoff didn't validate, might be lossless
            return frequencies[-1], 0.4
        return cutoff_hz, confidence
    else:
        # No clear cutoff found - likely lossless or very high quality
        return frequencies[-1], 0.5


# =============================================================================
# Segment-Based Percentile Analysis (for detecting predominant cutoff)
# =============================================================================


def find_segment_cutoffs(
    spectrogram_db: np.ndarray,
    frequencies: np.ndarray,
    sample_rate: int,
    n_segments: int = SEGMENT_COUNT,
) -> List[float]:
    """
    Analyze cutoff frequency for each temporal segment.

    Divides the spectrogram into n_segments and calculates
    the cutoff for each one independently. This allows us to
    find the PREDOMINANT cutoff rather than being fooled by
    occasional peaks or anomalies.

    Args:
        spectrogram_db: Full spectrogram (frequency_bins x time_frames)
        frequencies: Frequency bins array
        sample_rate: Sample rate of audio
        n_segments: Number of segments to analyze

    Returns:
        List of cutoff frequencies (Hz) for each segment
    """
    total_frames = spectrogram_db.shape[1]
    frames_per_segment = max(1, total_frames // n_segments)

    segment_cutoffs = []
    for i in range(n_segments):
        start = i * frames_per_segment
        end = min((i + 1) * frames_per_segment, total_frames)

        if end <= start:
            continue

        # Extract this segment's spectrogram
        segment_spec = spectrogram_db[:, start:end]

        # Use the relative energy method on this segment
        cutoff, _ = find_cutoff_relative_energy(
            segment_spec, frequencies, sample_rate
        )
        segment_cutoffs.append(cutoff)

    return segment_cutoffs


def calculate_predominant_cutoff(
    segment_cutoffs: List[float],
    percentile: float = PREDOMINANT_PERCENTILE,
    outlier_threshold_khz: float = OUTLIER_THRESHOLD_KHZ,
) -> Tuple[float, float, bool]:
    """
    Calculate the predominant cutoff using percentile analysis.

    Instead of using the maximum cutoff (which can be fooled by peaks),
    we use the 85th percentile to find where MOST of the file cuts off.
    This ignores the top 15% of segments that might have anomalous peaks.

    Args:
        segment_cutoffs: List of cutoff frequencies per segment (Hz)
        percentile: Percentile to use (85 = ignore top 15% of peaks)
        outlier_threshold_khz: Threshold for detecting outliers (kHz)

    Returns:
        Tuple of (predominant_cutoff_hz, confidence, has_outliers)
    """
    if not segment_cutoffs:
        return 22050.0, 0.3, False

    cutoffs = np.array(segment_cutoffs)

    # Calculate statistics
    predominant = np.percentile(cutoffs, percentile)
    max_cutoff = np.max(cutoffs)
    std_cutoff = np.std(cutoffs)

    # Detect if there are significant outliers (peaks)
    # If max is significantly higher than the percentile, there are peaks
    outlier_threshold_hz = outlier_threshold_khz * 1000
    has_outliers = (max_cutoff - predominant) > outlier_threshold_hz

    # Calculate confidence based on consistency
    # High std = inconsistent file = lower confidence
    # Low std = consistent file = higher confidence
    consistency = 1.0 - min(1.0, std_cutoff / 5000)  # 5kHz std = 0 extra confidence
    confidence = 0.5 + (consistency * 0.4)  # Range: 0.5 - 0.9

    return predominant, confidence, has_outliers


def verify_high_frequency_cutoff(
    spectrogram_db: np.ndarray,
    frequencies: np.ndarray,
    detected_cutoff_hz: float,
    ref_energy_per_frame: np.ndarray,
    active_frames_mask: np.ndarray,
    ref_std: float,
) -> Tuple[float, float, bool, str]:
    """
    Verify if a high-frequency cutoff (>21kHz) is real content or noise.

    Compares energy/variance in 20-22kHz vs 15-20kHz band.
    If 20-22kHz has significantly less energy/variance, the real cutoff is ~20kHz.

    Args:
        spectrogram_db: Full spectrogram
        frequencies: Frequency bins array
        detected_cutoff_hz: Originally detected cutoff frequency
        ref_energy_per_frame: Reference band energy per frame
        active_frames_mask: Boolean mask of active frames
        ref_std: Reference band standard deviation

    Returns:
        Tuple of (adjusted_cutoff_hz, confidence, is_uncertain, uncertainty_reason)
    """
    # Compare 20-22kHz band vs 15-20kHz band
    band_high_energy = compute_band_relative_energy(
        spectrogram_db, frequencies, 20000, 22000,
        ref_energy_per_frame, active_frames_mask
    )
    band_high_variance = compute_band_temporal_variance(
        spectrogram_db, frequencies, 20000, 22000,
        active_frames_mask, ref_std
    )

    band_mid_energy = compute_band_relative_energy(
        spectrogram_db, frequencies, 15000, 20000,
        ref_energy_per_frame, active_frames_mask
    )
    band_mid_variance = compute_band_temporal_variance(
        spectrogram_db, frequencies, 15000, 20000,
        active_frames_mask, ref_std
    )

    # If high band has significantly less variance than mid band → it's noise
    # Real music has consistent variance across frequency bands
    variance_ratio = band_high_variance / max(band_mid_variance, 0.01)
    energy_diff = band_high_energy - band_mid_energy

    # Criteria for noise detection:
    # 1. High band variance is less than 50% of mid band variance
    # 2. High band energy is significantly lower than mid band
    is_likely_noise = variance_ratio < 0.5 or energy_diff < -15.0

    if is_likely_noise:
        # The 20-22kHz content is likely noise, adjust cutoff to ~20kHz
        adjusted_cutoff = 20000.0
        confidence = 0.75  # Reasonably confident after verification
        is_uncertain = False
        reason = ""
        return adjusted_cutoff, confidence, is_uncertain, reason

    # Content seems real but unusual (most MP3s don't have content this high)
    # Mark as uncertain
    is_uncertain = True
    reason = "Contenido detectado cerca del límite de Nyquist"
    return detected_cutoff_hz, 0.5, is_uncertain, reason


# =============================================================================
# Transition-Based Detection (primary algorithm for detecting codec cutoff)
# =============================================================================


def compute_band_energy_simple(
    spectrogram_db: np.ndarray,
    frequencies: np.ndarray,
    band_low_hz: float,
    band_high_hz: float,
) -> float:
    """
    Compute average energy for a frequency band across all time frames.

    Args:
        spectrogram_db: Full spectrogram (frequency_bins x time_frames)
        frequencies: Frequency bins array
        band_low_hz: Lower bound of band (Hz)
        band_high_hz: Upper bound of band (Hz)

    Returns:
        Average energy in dB for the band
    """
    low_idx = np.searchsorted(frequencies, band_low_hz)
    high_idx = np.searchsorted(frequencies, band_high_hz)

    if high_idx > len(frequencies):
        high_idx = len(frequencies)

    if low_idx >= high_idx:
        return -80.0  # Very low energy if invalid band

    band_data = spectrogram_db[low_idx:high_idx, :]
    return np.mean(band_data)


def find_cutoff_by_transition(
    spectrogram_db: np.ndarray,
    frequencies: np.ndarray,
    sample_rate: int,
    min_drop_db: float = TRANSITION_MIN_DROP_DB,
    band_width_hz: float = TRANSITION_BAND_WIDTH_HZ,
    search_start_hz: float = TRANSITION_SEARCH_START_HZ,
    search_end_hz: float = TRANSITION_SEARCH_END_HZ,
    min_energy_db: float = TRANSITION_MIN_ENERGY_DB,
    confirmation_bands: int = TRANSITION_CONFIRMATION_BANDS,
    ref_stats: Optional[Tuple] = None,
) -> Tuple[float, float]:
    """
    Detect cutoff frequency by finding the FIRST significant energy TRANSITION
    where real musical content ends.

    Unlike the relative energy method that asks "does this band have content?",
    this method asks "where does the energy DROP significantly?".

    MP3 codecs apply a brick-wall low-pass filter that creates an abrupt
    energy drop (typically 8-20dB) at a specific frequency. This function
    finds that transition point.

    Algorithm (v3 - "First Musical Transition"):
    1. Calculate energy AND variance for each 500Hz band from 10kHz to 21kHz
    2. PHASE 1: Find the FIRST transition where:
       - Pre-transition band has MUSICAL content (variance >= freq-dependent threshold: 0.30 at 14kHz → 0.15 at 20kHz)
       - Energy drops significantly (>= 8dB)
       - Energy doesn't recover after the drop
       This catches transcodes where real music ends but noise continues.
    3. PHASE 2 (fallback): If no musical transition found, use best-score method
       This handles lossless files and edge cases.

    Key insight: Musical content has HIGH temporal variance (follows dynamics).
    Transcode noise/artifacts have LOW variance (constant energy).
    By requiring the pre-transition band to have musical content, we find
    where the REAL music ends, not where the noise finally fades.

    Args:
        spectrogram_db: Full spectrogram (frequency_bins x time_frames)
        frequencies: Frequency bins array
        sample_rate: Sample rate of audio
        min_drop_db: Minimum energy drop to consider a cutoff (dB)
        band_width_hz: Width of analysis bands (Hz)
        search_start_hz: Start analyzing from this frequency (Hz)
        search_end_hz: End analyzing at this frequency (Hz)
        min_energy_db: Minimum energy to consider band as having content (dB)
        confirmation_bands: Number of bands after drop that must stay low
        ref_stats: Pre-computed (ref_energy_per_frame, ref_mean, ref_std, active_frames_mask)
                   to avoid recomputing reference band statistics

    Returns:
        Tuple of (cutoff frequency in Hz, confidence)
    """
    nyquist_hz = sample_rate / 2

    # Use pre-computed reference band stats if available, otherwise compute
    if ref_stats is not None:
        ref_energy_per_frame, ref_mean, ref_std, active_frames_mask = ref_stats
    else:
        ref_energy_per_frame, ref_mean, ref_std = compute_reference_band_stats(
            spectrogram_db, frequencies
        )
        active_frames_mask = identify_active_frames(ref_energy_per_frame, ref_mean, ref_std)

    # Step 1: Calculate energy AND variance for each band
    band_stats = []  # [(freq, energy, variance), ...]
    current_freq = search_start_hz

    while current_freq < min(search_end_hz, nyquist_hz):
        band_low = current_freq
        band_high = current_freq + band_width_hz

        energy = compute_band_energy_simple(
            spectrogram_db, frequencies, band_low, band_high
        )
        variance = compute_band_temporal_variance(
            spectrogram_db, frequencies, band_low, band_high,
            active_frames_mask, ref_std
        )
        band_stats.append((current_freq, energy, variance))
        current_freq += band_width_hz

    if len(band_stats) < 3:
        return nyquist_hz, 0.3  # Not enough bands to analyze

    # Helper function: check if energy recovers after a given band index
    # Anti-sibilance: require TRANSITION_RECOVERY_CONSECUTIVE_BANDS consecutive bands
    # with high energy AND variance >= TRANSITION_RECOVERY_MIN_VARIANCE.
    # Isolated sibilance (S/T/CH sounds) creates intermittent high-energy bands
    # but doesn't sustain across multiple consecutive bands with musical variance.
    def energy_recovers_after(band_index: int, post_energy: float) -> bool:
        consecutive_recovery = 0
        for j in range(band_index + 2, len(band_stats)):
            _, future_energy, future_variance = band_stats[j]
            if (future_energy > post_energy + TRANSITION_RECOVERY_THRESHOLD_DB
                    and future_variance >= TRANSITION_RECOVERY_MIN_VARIANCE):
                consecutive_recovery += 1
                if consecutive_recovery >= TRANSITION_RECOVERY_CONSECUTIVE_BANDS:
                    return True
            else:
                consecutive_recovery = 0
        return False

    # Helper function: compute frequency-dependent variance threshold (2A)
    # At lower frequencies (14kHz), use full TRANSITION_MIN_PRE_VARIANCE (0.30)
    # At higher frequencies (20kHz), use reduced threshold (0.15)
    # Acapellas have lower variance at ~16kHz (~0.25), which a fixed threshold misses
    def get_min_pre_variance(freq_hz: float) -> float:
        if freq_hz <= TRANSITION_VARIANCE_FREQ_LOW_HZ:
            return TRANSITION_MIN_PRE_VARIANCE
        if freq_hz >= TRANSITION_VARIANCE_FREQ_HIGH_HZ:
            return TRANSITION_MIN_PRE_VARIANCE_HIGH_FREQ
        # Linear interpolation
        t = (freq_hz - TRANSITION_VARIANCE_FREQ_LOW_HZ) / (
            TRANSITION_VARIANCE_FREQ_HIGH_HZ - TRANSITION_VARIANCE_FREQ_LOW_HZ
        )
        return TRANSITION_MIN_PRE_VARIANCE + t * (
            TRANSITION_MIN_PRE_VARIANCE_HIGH_FREQ - TRANSITION_MIN_PRE_VARIANCE
        )

    # ==========================================================================
    # PHASE 1: Find the FIRST transition with MUSICAL content before it
    # This is the key fix for transcode detection!
    #
    # Two detection methods:
    # 1a. Energy drop >= 8dB with musical content before
    # 1b. Musical → non-musical variance transition (handles gradual energy drops)
    # ==========================================================================
    for i in range(len(band_stats) - 1):
        freq_low, energy_low, variance_low = band_stats[i]
        freq_high, energy_high, variance_high = band_stats[i + 1]

        # Calculate energy drop (positive if energy decreases)
        drop = energy_low - energy_high

        # Check if pre-transition band has MUSICAL content (high variance)
        # Uses frequency-dependent threshold: 0.30 at 14kHz → 0.15 at 20kHz
        # This catches acapellas where variance at ~16kHz is ~0.25 (below a fixed threshold)
        min_variance = get_min_pre_variance(freq_low)
        is_musical_content = variance_low >= min_variance

        # Method 1a: Significant energy drop with musical content before
        # NOTE: We do NOT require min_energy_db threshold because high variance
        # already confirms musical content.
        has_significant_drop = drop >= min_drop_db

        # Method 1b: Musical → noise transition
        # This catches cases where energy drops gradually but variance clearly
        # shows the musical content has ended.
        #
        # We use THREE criteria (any can trigger detection):
        # 1. Absolute threshold: post-variance < frequency-dependent musical threshold
        # 2. Relative drop: variance drops by >= 35% from pre to post band
        # 3. Two-band lookahead: if the band TWO steps ahead is clearly noise (var < 0.2)
        #    and we're in a musical band, this indicates a gradual transition
        #
        # The relative drop catches "gray zone" cases like gradual transitions
        # where post-variance might be 0.36 (not < 0.3) but dropped from 0.57
        # (a 37% drop, close to significant). Using 35% threshold catches these
        # while avoiding false positives.
        variance_drop_ratio = (variance_low - variance_high) / variance_low if variance_low > 0.1 else 0.0
        has_absolute_variance_drop = variance_high < get_min_pre_variance(freq_high)
        has_relative_variance_drop = variance_drop_ratio >= 0.35

        # Two-band lookahead: check if band i+2 is clearly noise
        has_two_band_transition = False
        if i + 2 < len(band_stats):
            _, _, variance_two_ahead = band_stats[i + 2]
            # If current band is musical and two bands ahead is clearly noise,
            # we're at the start of a gradual transition
            has_two_band_transition = variance_two_ahead < 0.2 and variance_high < 0.5
            # At high frequencies (>=18kHz), natural rolloff can look like a
            # two-band transition. Guard: the detection point must not be musical.
            if has_two_band_transition and freq_high >= 18000:
                if variance_high >= get_min_pre_variance(freq_high):
                    has_two_band_transition = False

        is_variance_transition = is_musical_content and (has_absolute_variance_drop or has_relative_variance_drop or has_two_band_transition) and drop > 0

        # Method 1c: Cumulative drop detection (2B)
        # Detects gradual codec rolloff (e.g., AAC→MP3 double encoding)
        # If TRANSITION_CUMULATIVE_BANDS consecutive bands sum > TRANSITION_CUMULATIVE_DROP_DB
        # in total drop, treat as cutoff even if individual drops are < min_drop_db
        has_cumulative_drop = False
        if is_musical_content and i + TRANSITION_CUMULATIVE_BANDS < len(band_stats):
            cumulative_drop = 0.0
            all_dropping = True
            for k in range(TRANSITION_CUMULATIVE_BANDS):
                _, e_curr, _ = band_stats[i + k]
                _, e_next, _ = band_stats[i + k + 1]
                band_drop = e_curr - e_next
                if band_drop <= 0:
                    all_dropping = False
                    break
                cumulative_drop += band_drop
            if all_dropping and cumulative_drop >= TRANSITION_CUMULATIVE_DROP_DB:
                has_cumulative_drop = True

        # Method 1d: Sliding-window variance decay
        # Detects gradual rolloffs where variance drops consistently across multiple
        # bands but no single band-to-band step exceeds the 35% threshold.
        # Example: variance 0.45 → 0.31 → 0.20 across 1.5kHz (55% total drop,
        # but each step is only ~32%).
        VARIANCE_DECAY_WINDOW = 3
        VARIANCE_DECAY_MIN_DROP = 0.50   # Total variance must drop by >= 50%
        VARIANCE_DECAY_END_MAX = 0.25    # End band must be clearly non-musical
        has_sliding_variance_decay = False
        sliding_total_drop_ratio = 0.0
        sliding_end_variance = 1.0
        if is_musical_content and i + VARIANCE_DECAY_WINDOW < len(band_stats):
            _, _, variance_end = band_stats[i + VARIANCE_DECAY_WINDOW]
            total_drop_ratio = (variance_low - variance_end) / variance_low if variance_low > 0.1 else 0.0
            if total_drop_ratio >= VARIANCE_DECAY_MIN_DROP and variance_end < VARIANCE_DECAY_END_MAX:
                # Verify monotonically decreasing (small tolerance for noise)
                all_declining = True
                for k in range(1, VARIANCE_DECAY_WINDOW + 1):
                    _, _, v_k = band_stats[i + k]
                    _, _, v_prev = band_stats[i + k - 1]
                    if v_k > v_prev + 0.01:
                        all_declining = False
                        break
                if all_declining:
                    # At high frequencies (>=18kHz), natural rolloff can mimic
                    # decay patterns. Guard: the detection point (band i+1) must
                    # not still contain musical content.
                    if freq_high >= 18000:
                        post_thresh = get_min_pre_variance(freq_high)
                        if variance_high >= post_thresh:
                            # Band i+1 is still musical — skip this trigger
                            all_declining = False
                    if all_declining:
                        has_sliding_variance_decay = True
                        sliding_total_drop_ratio = total_drop_ratio
                        sliding_end_variance = variance_end

        if is_musical_content and (has_significant_drop or is_variance_transition or has_cumulative_drop or has_sliding_variance_decay):
            # Verify energy doesn't recover after the drop
            if not energy_recovers_after(i, energy_high):
                # Found the FIRST transition where musical content ends!
                # Calculate confidence based on detection method
                if has_significant_drop:
                    # Higher confidence for clear energy drops
                    confidence = min(0.95, 0.6 + (drop / 20.0) * 0.2 + variance_low * 0.15)
                elif has_cumulative_drop:
                    # Medium-high confidence for cumulative drops
                    confidence = min(0.90, 0.60 + (cumulative_drop / 20.0) * 0.2 + variance_low * 0.15)
                elif has_sliding_variance_decay:
                    # Gradual rolloff confidence based on how steep the decay is
                    confidence = min(0.85, 0.60 + sliding_total_drop_ratio * 0.2 + (1.0 - sliding_end_variance) * 0.1)
                else:
                    # Slightly lower confidence for variance-only transitions
                    confidence = min(0.90, 0.65 + (drop / 20.0) * 0.15 + variance_low * 0.15)
                return freq_high, confidence

    # ==========================================================================
    # PHASE 2: Fallback - use best-score method (for lossless, etc.)
    # If no transition with musical content was found, find the best overall
    # ==========================================================================
    best_score = 0.0
    best_cutoff_hz = nyquist_hz
    best_confidence = 0.3

    for i in range(len(band_stats) - 1):
        freq_low, energy_low, variance_low = band_stats[i]
        freq_high, energy_high, variance_high = band_stats[i + 1]

        # Calculate energy drop (positive if energy decreases)
        drop = energy_low - energy_high

        # Calculate RELATIVE variance drop
        variance_drop_ratio = 0.0
        if variance_low > 0.1:  # Avoid division by very small values
            variance_drop_ratio = (variance_low - variance_high) / variance_low

        # Determine if this is a good variance transition
        is_good_variance_transition = (
            variance_drop_ratio > TRANSITION_VARIANCE_DROP_RATIO or
            (variance_low > 0.3 and variance_high < 0.2)
        )

        if drop >= min_drop_db and energy_low >= min_energy_db:
            # Verify energy doesn't recover after the drop
            if not energy_recovers_after(i, energy_high):
                # Calculate combined score (energy + variance)
                energy_score = drop / 20.0
                variance_score = variance_drop_ratio if is_good_variance_transition else 0.0
                combined_score = energy_score + variance_score * 0.5

                if combined_score > best_score:
                    best_score = combined_score
                    best_cutoff_hz = freq_high
                    best_confidence = min(0.95, 0.5 + combined_score * 0.3)

    return best_cutoff_hz, best_confidence


def analyze_frequency_cutoff(
    samples: np.ndarray,
    sample_rate: int,
    n_fft: int = FFT_SIZE,
    hop_length: int = HOP_LENGTH,
) -> FrequencyAnalysis:
    """
    Perform complete frequency cutoff analysis on audio samples.

    Uses a combination of methods:
    1. Transition detection (primary) - finds abrupt energy drops (brick-wall filter)
    2. Segment-based percentile analysis (secondary) - finds predominant cutoff
    3. Relative energy analysis (fallback) - distinguishes music from noise

    The transition method is primary because it directly detects the codec's
    low-pass filter by finding where energy DROPS significantly, rather than
    asking "does this band have content?" which can be fooled by residual noise.

    Args:
        samples: Audio samples
        sample_rate: Sample rate
        n_fft: FFT window size
        hop_length: Hop length

    Returns:
        FrequencyAnalysis object with complete results
    """
    # Compute spectrogram
    spectrogram_db, frequencies = compute_spectrogram(
        samples, sample_rate, n_fft, hop_length
    )

    # Compute energy spectrum (average across time)
    energy_spectrum = compute_energy_per_frequency(spectrogram_db)

    # Get maximum theoretical frequency
    max_frequency_hz = sample_rate / 2

    # Calculate reference band stats (needed for verification)
    ref_energy_per_frame, ref_mean, ref_std = compute_reference_band_stats(
        spectrogram_db, frequencies
    )
    active_frames_mask = identify_active_frames(ref_energy_per_frame, ref_mean, ref_std)

    # Initialize uncertainty fields
    is_uncertain = False
    uncertainty_reason = ""

    # PRIMARY METHOD: Transition-based detection
    # Finds the most significant energy DROP between adjacent frequency bands
    # This directly detects the codec's brick-wall low-pass filter
    cutoff_transition, conf_transition = find_cutoff_by_transition(
        spectrogram_db, frequencies, sample_rate,
        ref_stats=(ref_energy_per_frame, ref_mean, ref_std, active_frames_mask),
    )

    # SECONDARY METHOD: Segment-based percentile analysis (lazy evaluation)
    # Only computed when the primary method isn't confident enough, or when
    # the noise-plateau guard needs to verify the transition result.
    # ~80% of files have conf_transition >= 0.7 and skip this entirely.
    segment_cutoffs = None
    cutoff_segment = None
    conf_segment = 0.0
    has_outliers = False

    def _ensure_segments():
        """Compute segment analysis on demand."""
        nonlocal segment_cutoffs, cutoff_segment, conf_segment, has_outliers
        if segment_cutoffs is not None:
            return  # Already computed
        segment_cutoffs = find_segment_cutoffs(
            spectrogram_db, frequencies, sample_rate, n_segments=SEGMENT_COUNT
        )
        cutoff_segment, conf_segment, has_outliers = calculate_predominant_cutoff(
            segment_cutoffs, percentile=PREDOMINANT_PERCENTILE
        )

    # Decision logic: choose between methods
    # 1. If transition method found a clear drop (high confidence), trust it
    # 2. If both methods agree (within 2kHz), boost confidence
    # 3. If disagreement, prefer the LOWER cutoff (more conservative)

    if conf_transition >= 0.7:
        # Transition method is confident - use it
        # BUT check for noise-plateau pattern: if segments strongly disagree
        # (much lower cutoff) and found a bimodal distribution (outliers),
        # the transition may be detecting noise-to-silence instead of
        # music-to-noise. Trust segments in that case.
        #
        # However, verify the bands between segment and transition cutoffs
        # are actually non-musical (noise plateau). If they have musical
        # variance, the transition correctly detected where content ends
        # and overriding with segments would be wrong (e.g., older recordings
        # with natural high-frequency rolloff that still have real content).
        _ensure_segments()
        if (has_outliers and cutoff_transition > cutoff_segment + 2000
                and conf_segment >= 0.6):
            # Verify: check if bands between segment and transition cutoffs
            # lack musical content (confirming noise-plateau pattern)
            gap_has_musical_content = False
            check_start = cutoff_segment
            check_end = cutoff_transition
            check_freq = check_start
            while check_freq + TRANSITION_BAND_WIDTH_HZ <= check_end:
                band_var = compute_band_temporal_variance(
                    spectrogram_db, frequencies,
                    check_freq, check_freq + TRANSITION_BAND_WIDTH_HZ,
                    active_frames_mask, ref_std
                )
                # Use frequency-dependent threshold (same as transition method)
                freq_range = TRANSITION_VARIANCE_FREQ_HIGH_HZ - TRANSITION_VARIANCE_FREQ_LOW_HZ
                if check_freq <= TRANSITION_VARIANCE_FREQ_LOW_HZ:
                    min_var = TRANSITION_MIN_PRE_VARIANCE
                elif check_freq >= TRANSITION_VARIANCE_FREQ_HIGH_HZ:
                    min_var = TRANSITION_MIN_PRE_VARIANCE_HIGH_FREQ
                else:
                    t = (check_freq - TRANSITION_VARIANCE_FREQ_LOW_HZ) / freq_range
                    min_var = TRANSITION_MIN_PRE_VARIANCE + t * (
                        TRANSITION_MIN_PRE_VARIANCE_HIGH_FREQ - TRANSITION_MIN_PRE_VARIANCE
                    )
                if band_var >= min_var:
                    gap_has_musical_content = True
                    break
                check_freq += TRANSITION_BAND_WIDTH_HZ

            if gap_has_musical_content:
                # Bands between segment and transition have real musical content,
                # so the transition correctly detected where content ends.
                # Trust transition, not segments.
                cutoff_hz = cutoff_transition
                confidence = conf_transition
            else:
                # Confirmed noise-plateau: bands between cutoffs lack musical content
                cutoff_hz = cutoff_segment
                confidence = conf_segment
        else:
            cutoff_hz = cutoff_transition
            confidence = conf_transition
    else:
        # Transition not confident enough — need segment analysis
        _ensure_segments()
        if abs(cutoff_transition - cutoff_segment) < 2000:
            # Methods agree - use average and boost confidence
            cutoff_hz = (cutoff_transition + cutoff_segment) / 2
            confidence = min(0.95, (conf_transition + conf_segment) / 2 + 0.1)
        elif cutoff_transition < cutoff_segment and conf_transition >= 0.5:
            # Transition found a lower cutoff - prefer it (more conservative)
            # This catches transcodes where residual noise fooled the segment method
            cutoff_hz = cutoff_transition
            # Disagreement where transition < segment is a transcode signature:
            # real content ends at transition cutoff, noise/artifacts extend higher
            gap_khz = (cutoff_segment - cutoff_transition) / 1000
            if gap_khz >= 1.0:
                boost = min(0.15, gap_khz * 0.05)
                confidence = min(0.95, conf_transition + boost)
            else:
                confidence = conf_transition
        else:
            # Fall back to segment method
            cutoff_hz = cutoff_segment
            confidence = conf_segment

    # Mark as uncertain if segment analysis found outliers
    if has_outliers:
        is_uncertain = True
        uncertainty_reason = "Calidad variable detectada"

    # Verify high-frequency cutoffs (>21kHz) to detect noise vs real content
    if cutoff_hz > 21000:
        cutoff_hz, confidence, is_uncertain, uncertainty_reason = verify_high_frequency_cutoff(
            spectrogram_db, frequencies, cutoff_hz,
            ref_energy_per_frame, active_frames_mask, ref_std
        )

    # Compute energy in the band just before the cutoff (for transcode guard)
    energy_at_cutoff_db = compute_band_energy_simple(
        spectrogram_db, frequencies,
        max(500, cutoff_hz - 1000), cutoff_hz
    )

    return FrequencyAnalysis(
        cutoff_frequency_hz=cutoff_hz,
        cutoff_frequency_khz=cutoff_hz / 1000,
        max_frequency_hz=max_frequency_hz,
        energy_spectrum=energy_spectrum,
        frequencies=frequencies,
        spectrogram_db=spectrogram_db,
        confidence=confidence,
        is_uncertain=is_uncertain,
        uncertainty_reason=uncertainty_reason,
        energy_at_cutoff_db=energy_at_cutoff_db,
    )
