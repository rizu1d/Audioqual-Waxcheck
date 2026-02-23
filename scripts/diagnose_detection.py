"""
Diagnostic script: analyze Silicone Soul (BASE_003) and Agoria (BASE_002)
to debug why Silicone Soul detects at 19kHz instead of 20kHz.

Focuses on the "trap zone" hypothesis: has_absolute_variance_drop uses
a fixed 0.25 threshold while is_musical_content uses a frequency-dependent
threshold that goes as low as 0.15 at 20kHz.

Usage: python scripts/diagnose_detection.py
"""

import os
import sys

# Add src parent to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

import librosa
import numpy as np

from src.core.frequency_detector import (
    analyze_frequency_cutoff,
    compute_spectrogram,
    compute_reference_band_stats,
    identify_active_frames,
    find_cutoff_by_transition,
    find_segment_cutoffs,
    calculate_predominant_cutoff,
    compute_band_energy_simple,
    compute_band_temporal_variance,
)
from src.utils.constants import (
    FFT_SIZE,
    HOP_LENGTH,
    SAMPLE_RATE,
    SEGMENT_COUNT,
    PREDOMINANT_PERCENTILE,
    TRANSITION_MIN_DROP_DB,
    TRANSITION_BAND_WIDTH_HZ,
    TRANSITION_SEARCH_START_HZ,
    TRANSITION_SEARCH_END_HZ,
    TRANSITION_MIN_PRE_VARIANCE,
    TRANSITION_VARIANCE_FREQ_LOW_HZ,
    TRANSITION_VARIANCE_FREQ_HIGH_HZ,
    TRANSITION_MIN_PRE_VARIANCE_HIGH_FREQ,
    TRANSITION_CUMULATIVE_BANDS,
    TRANSITION_CUMULATIVE_DROP_DB,
    TRANSITION_RECOVERY_THRESHOLD_DB,
    TRANSITION_RECOVERY_CONSECUTIVE_BANDS,
    TRANSITION_RECOVERY_MIN_VARIANCE,
)


def get_min_pre_variance(freq_hz: float) -> float:
    """Frequency-dependent variance threshold (same as in frequency_detector.py)."""
    if freq_hz <= TRANSITION_VARIANCE_FREQ_LOW_HZ:
        return TRANSITION_MIN_PRE_VARIANCE
    if freq_hz >= TRANSITION_VARIANCE_FREQ_HIGH_HZ:
        return TRANSITION_MIN_PRE_VARIANCE_HIGH_FREQ
    t = (freq_hz - TRANSITION_VARIANCE_FREQ_LOW_HZ) / (
        TRANSITION_VARIANCE_FREQ_HIGH_HZ - TRANSITION_VARIANCE_FREQ_LOW_HZ
    )
    return TRANSITION_MIN_PRE_VARIANCE + t * (
        TRANSITION_MIN_PRE_VARIANCE_HIGH_FREQ - TRANSITION_MIN_PRE_VARIANCE
    )


def diagnose_transition_detail(spectrogram_db, frequencies, sample_rate):
    """
    Run transition detection with detailed logging showing the trap zone issue.
    """
    ref_energy_per_frame, ref_mean, ref_std = compute_reference_band_stats(
        spectrogram_db, frequencies
    )
    active_frames_mask = identify_active_frames(ref_energy_per_frame, ref_mean, ref_std)

    band_stats = []
    current_freq = TRANSITION_SEARCH_START_HZ
    nyquist_hz = sample_rate / 2

    while current_freq < min(TRANSITION_SEARCH_END_HZ, nyquist_hz):
        band_low = current_freq
        band_high = current_freq + TRANSITION_BAND_WIDTH_HZ
        energy = compute_band_energy_simple(spectrogram_db, frequencies, band_low, band_high)
        variance = compute_band_temporal_variance(
            spectrogram_db, frequencies, band_low, band_high,
            active_frames_mask, ref_std
        )
        band_stats.append((current_freq, energy, variance))
        current_freq += TRANSITION_BAND_WIDTH_HZ

    # Print all band stats with BOTH thresholds to highlight the trap zone
    print("  Band analysis (500Hz bands, 10kHz-21kHz):")
    print(f"  {'Band':>12s}  {'Energy':>8s}  {'Var':>8s}  {'MusThresh':>9s}  {'Musical?':>8s}  {'AbsThresh':>9s}  {'AbsDrop?':>8s}  {'TRAP?':>5s}")
    for freq, energy, variance in band_stats:
        min_var = get_min_pre_variance(freq)
        is_musical = variance >= min_var
        abs_drop = variance < 0.25  # Current fixed threshold
        # Trap zone: band is considered musical but NEXT band could trigger abs_drop
        trap = is_musical and abs_drop
        print(
            f"  {freq/1000:>7.1f} kHz  {energy:>8.1f}  {variance:>8.3f}  "
            f"{min_var:>9.3f}  {'YES' if is_musical else 'no':>8s}  "
            f"{'0.250':>9s}  {'YES' if abs_drop else 'no':>8s}  "
            f"{'TRAP!' if trap else '':>5s}"
        )

    # Helper: energy recovery check
    def energy_recovers_after(band_index, post_energy):
        consecutive = 0
        for j in range(band_index + 2, len(band_stats)):
            _, future_energy, future_variance = band_stats[j]
            if (future_energy > post_energy + TRANSITION_RECOVERY_THRESHOLD_DB
                    and future_variance >= TRANSITION_RECOVERY_MIN_VARIANCE):
                consecutive += 1
                if consecutive >= TRANSITION_RECOVERY_CONSECUTIVE_BANDS:
                    return True
            else:
                consecutive = 0
        return False

    # Scan for triggers
    print("\n  Phase 1 transition scan (looking for first trigger):")
    for i in range(len(band_stats) - 1):
        freq_low, energy_low, variance_low = band_stats[i]
        freq_high, energy_high, variance_high = band_stats[i + 1]

        drop = energy_low - energy_high
        min_variance = get_min_pre_variance(freq_low)
        is_musical = variance_low >= min_variance

        if not is_musical:
            continue

        has_significant_drop = drop >= TRANSITION_MIN_DROP_DB

        variance_drop_ratio = (variance_low - variance_high) / variance_low if variance_low > 0.1 else 0.0
        has_abs_var_drop = variance_high < get_min_pre_variance(freq_high)
        has_rel_var_drop = variance_drop_ratio >= 0.35
        has_two_band = False
        if i + 2 < len(band_stats):
            _, _, v2 = band_stats[i + 2]
            has_two_band = v2 < 0.2 and variance_high < 0.5
            # HF guard: at >=18kHz, detection point must not be musical
            if has_two_band and freq_high >= 18000:
                if variance_high >= get_min_pre_variance(freq_high):
                    has_two_band = False
        is_var_transition = is_musical and (has_abs_var_drop or has_rel_var_drop or has_two_band) and drop > 0

        has_cumulative = False
        cum_drop = 0.0
        if i + TRANSITION_CUMULATIVE_BANDS < len(band_stats):
            all_dropping = True
            for k in range(TRANSITION_CUMULATIVE_BANDS):
                _, e_c, _ = band_stats[i + k]
                _, e_n, _ = band_stats[i + k + 1]
                bd = e_c - e_n
                if bd <= 0:
                    all_dropping = False
                    break
                cum_drop += bd
            if all_dropping and cum_drop >= TRANSITION_CUMULATIVE_DROP_DB:
                has_cumulative = True

        VARIANCE_DECAY_WINDOW = 3
        has_sliding_decay = False
        if i + VARIANCE_DECAY_WINDOW < len(band_stats):
            _, _, v_end = band_stats[i + VARIANCE_DECAY_WINDOW]
            total_ratio = (variance_low - v_end) / variance_low if variance_low > 0.1 else 0.0
            if total_ratio >= 0.50 and v_end < 0.25:
                all_declining = True
                for k in range(1, VARIANCE_DECAY_WINDOW + 1):
                    _, _, vk = band_stats[i + k]
                    _, _, vp = band_stats[i + k - 1]
                    if vk > vp + 0.01:
                        all_declining = False
                        break
                if all_declining:
                    # High-frequency guard (>=18kHz): skip if band i+1 is still musical
                    if freq_high >= 18000:
                        post_thresh = get_min_pre_variance(freq_high)
                        if variance_high >= post_thresh:
                            all_declining = False
                    if all_declining:
                        has_sliding_decay = True

        triggered = has_significant_drop or is_var_transition or has_cumulative or has_sliding_decay
        if triggered:
            methods = []
            if has_significant_drop:
                methods.append(f"1a(drop={drop:.1f}dB)")
            if is_var_transition:
                parts = []
                if has_abs_var_drop:
                    thresh = get_min_pre_variance(freq_high)
                    parts.append(f"abs(v_high={variance_high:.3f}<thresh={thresh:.3f})")
                if has_rel_var_drop:
                    parts.append(f"rel({variance_drop_ratio:.1%}>=35%)")
                if has_two_band:
                    parts.append("2band")
                methods.append(f"1b({' + '.join(parts)})")
            if has_cumulative:
                methods.append(f"1c(cum={cum_drop:.1f}dB)")
            if has_sliding_decay:
                methods.append("1d(decay)")

            recovers = energy_recovers_after(i, energy_high)
            status = "BLOCKED(recovery)" if recovers else ">>> TRIGGERED <<<"
            print(f"    {freq_low/1000:.1f}-{freq_high/1000:.1f}kHz: {status}")
            for m in methods:
                print(f"      Method: {m}")
            if not recovers:
                print(f"    ==> DETECTION POINT: {freq_high/1000:.1f} kHz")
                return freq_high, methods

    print("    No Phase 1 trigger found (would fall through to Phase 2)")
    return None, []


def analyze_file(filepath):
    """Analyze a single file and print detailed diagnostics."""
    filename = os.path.basename(filepath)
    print(f"\n{'='*80}")
    print(f"FILE: {filename}")
    print(f"{'='*80}")

    # Load audio
    samples, sr = librosa.load(filepath, sr=SAMPLE_RATE, mono=True)
    print(f"  Loaded: {len(samples)/sr:.1f}s at {sr}Hz")

    # Compute spectrogram
    spectrogram_db, frequencies = compute_spectrogram(samples, sr, FFT_SIZE, HOP_LENGTH)

    # Method 1: Transition
    cutoff_trans, conf_trans = find_cutoff_by_transition(spectrogram_db, frequencies, sr)

    # Method 2: Segments
    segment_cutoffs = find_segment_cutoffs(spectrogram_db, frequencies, sr, n_segments=SEGMENT_COUNT)
    cutoff_seg, conf_seg, has_outliers = calculate_predominant_cutoff(
        segment_cutoffs, percentile=PREDOMINANT_PERCENTILE
    )

    # Full analysis result
    result = analyze_frequency_cutoff(samples, sr)

    print(f"\n  METHOD RESULTS:")
    print(f"    Transition:  {cutoff_trans/1000:.1f} kHz  (conf={conf_trans:.3f})")
    print(f"    Segments:    {cutoff_seg/1000:.1f} kHz  (conf={conf_seg:.3f}, outliers={has_outliers})")
    print(f"    Gap:         {(cutoff_seg - cutoff_trans)/1000:.1f} kHz")
    print(f"    FINAL:       {result.cutoff_frequency_khz:.1f} kHz  (conf={result.confidence:.3f})")
    if result.is_uncertain:
        print(f"    UNCERTAIN:   {result.uncertainty_reason}")

    # Detailed transition diagnosis
    print(f"\n  DETAILED TRANSITION DIAGNOSIS:")
    trigger_freq, trigger_methods = diagnose_transition_detail(spectrogram_db, frequencies, sr)

    return result


def main():
    base_dir = os.path.join(project_dir, "references", "test-files", "base")

    files = [
        os.path.join(base_dir, "Silicone Soul - Chic-O-Laa (H-Foundation Remix).mp3"),
        os.path.join(base_dir, "Agoria - Teardrops (Don't Stop The Music) (Nick Morgan Remix).mp3"),
    ]

    for filepath in files:
        if not os.path.exists(filepath):
            print(f"WARNING: File not found: {filepath}")
            continue
        try:
            analyze_file(filepath)
        except Exception as e:
            print(f"ERROR analyzing {os.path.basename(filepath)}: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
