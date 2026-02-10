"""
Diagnostic script: compare transition vs segment detection methods
for LaTour and YouTube rip files to calibrate the natural rolloff guard.

Usage: python scripts/diagnose_latour.py
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
    compute_energy_per_frequency,
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
    Run transition detection with detailed logging of which band/condition triggered.
    Returns (cutoff_hz, confidence, trigger_info).
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

    # Print all band stats
    print("  Band analysis (500Hz bands, 10kHz-21kHz):")
    print(f"  {'Band':>12s}  {'Energy':>8s}  {'Variance':>8s}  {'MinVar':>8s}  {'Musical?':>8s}")
    for freq, energy, variance in band_stats:
        min_var = get_min_pre_variance(freq)
        is_musical = variance >= min_var
        marker = " *" if is_musical else ""
        print(f"  {freq/1000:>7.1f} kHz  {energy:>8.1f}  {variance:>8.3f}  {min_var:>8.3f}  {'YES' if is_musical else 'no':>6s}{marker}")

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

    # Scan for triggers (same logic as frequency_detector.py)
    print("\n  Transition scan:")
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
        has_abs_var_drop = variance_high < 0.3
        has_rel_var_drop = variance_drop_ratio >= 0.35
        has_two_band = False
        if i + 2 < len(band_stats):
            _, _, v2 = band_stats[i + 2]
            has_two_band = v2 < 0.2 and variance_high < 0.5
        is_var_transition = is_musical and (has_abs_var_drop or has_rel_var_drop or has_two_band) and drop > 0

        has_cumulative = False
        if i + TRANSITION_CUMULATIVE_BANDS < len(band_stats):
            cum_drop = 0.0
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
                    if vk > vp + 0.05:
                        all_declining = False
                        break
                has_sliding_decay = all_declining

        triggered = has_significant_drop or is_var_transition or has_cumulative or has_sliding_decay
        if triggered:
            methods = []
            if has_significant_drop:
                methods.append(f"1a(drop={drop:.1f}dB)")
            if is_var_transition:
                parts = []
                if has_abs_var_drop:
                    parts.append(f"abs(v={variance_high:.3f}<0.3)")
                if has_rel_var_drop:
                    parts.append(f"rel({variance_drop_ratio:.1%}>=35%)")
                if has_two_band:
                    parts.append("2band")
                methods.append(f"1b({'+'.join(parts)})")
            if has_cumulative:
                methods.append(f"1c(cum={cum_drop:.1f}dB)")
            if has_sliding_decay:
                methods.append(f"1d(decay)")

            recovers = energy_recovers_after(i, energy_high)
            status = "BLOCKED(recovery)" if recovers else "TRIGGERED"
            print(f"    {freq_low/1000:.1f}-{freq_high/1000:.1f}kHz: {status} by {', '.join(methods)}")
            if not recovers:
                return freq_high, methods
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

    gap = cutoff_seg - cutoff_trans

    print(f"\n  RESULTS:")
    print(f"    Transition:  {cutoff_trans/1000:.1f} kHz  (conf={conf_trans:.3f})")
    print(f"    Segments:    {cutoff_seg/1000:.1f} kHz  (conf={conf_seg:.3f}, outliers={has_outliers})")
    print(f"    Gap:         {gap/1000:.1f} kHz  (segment - transition)")
    print(f"    Conf >= 0.7: {conf_trans >= 0.7}")

    # Use the actual analyze_frequency_cutoff function to get the real result
    result = analyze_frequency_cutoff(samples, sr)
    final = result.cutoff_frequency_hz
    decision = f"analyze_frequency_cutoff → {final/1000:.1f}kHz (conf={result.confidence:.3f})"
    if result.is_uncertain:
        decision += f" [UNCERTAIN: {result.uncertainty_reason}]"

    print(f"    ACTUAL result: {final/1000:.1f} kHz  (conf={result.confidence:.3f}, uncertain={result.is_uncertain})")
    if result.uncertainty_reason:
        print(f"    Reason:      {result.uncertainty_reason}")

    # Detailed transition diagnosis
    print(f"\n  TRANSITION DETAIL:")
    trigger_freq, trigger_methods = diagnose_transition_detail(spectrogram_db, frequencies, sr)

    return {
        "filename": filename,
        "cutoff_transition": cutoff_trans,
        "conf_transition": conf_trans,
        "cutoff_segment": cutoff_seg,
        "conf_segment": conf_seg,
        "has_outliers": has_outliers,
        "gap": gap,
        "decision": decision,
        "final_cutoff": final,
    }


def main():
    test_dir = os.path.join(project_dir, "references", "test-files")

    # LaTour file
    latour = os.path.join(test_dir, "casos-excepcionales", "LaTour - People Are Still Having Sex.mp3")

    # YouTube rips
    yt_dir = os.path.join(test_dir, "youtuberips")

    # Other exceptional cases
    exc_dir = os.path.join(test_dir, "casos-excepcionales")

    files_to_analyze = []

    # Priority: LaTour first
    if os.path.exists(latour):
        files_to_analyze.append(latour)
    else:
        print(f"WARNING: LaTour file not found at {latour}")

    # YouTube rips
    if os.path.isdir(yt_dir):
        for f in sorted(os.listdir(yt_dir)):
            if f.endswith(('.mp3', '.wav', '.flac', '.m4a', '.aiff', '.aif')):
                files_to_analyze.append(os.path.join(yt_dir, f))

    # Other exceptional cases (skip LaTour since already included)
    if os.path.isdir(exc_dir):
        for f in sorted(os.listdir(exc_dir)):
            if f.endswith(('.mp3', '.wav', '.flac', '.m4a', '.aiff', '.aif')) and "LaTour" not in f:
                files_to_analyze.append(os.path.join(exc_dir, f))

    print(f"Analyzing {len(files_to_analyze)} files...\n")

    results = []
    for filepath in files_to_analyze:
        try:
            result = analyze_file(filepath)
            results.append(result)
        except Exception as e:
            print(f"\n  ERROR analyzing {os.path.basename(filepath)}: {e}")

    # Summary table
    print(f"\n\n{'='*120}")
    print("SUMMARY TABLE")
    print(f"{'='*120}")
    print(f"{'File':<55s}  {'Trans':>7s}  {'Conf':>5s}  {'Seg':>7s}  {'Conf':>5s}  {'Gap':>6s}  {'Out':>3s}  {'Decision':<35s}  {'Final':>7s}")
    print("-" * 120)
    for r in results:
        print(
            f"{r['filename'][:54]:<55s}  "
            f"{r['cutoff_transition']/1000:>6.1f}k  "
            f"{r['conf_transition']:>5.3f}  "
            f"{r['cutoff_segment']/1000:>6.1f}k  "
            f"{r['conf_segment']:>5.3f}  "
            f"{r['gap']/1000:>5.1f}k  "
            f"{'Y' if r['has_outliers'] else 'N':>3s}  "
            f"{r['decision']:<35s}  "
            f"{r['final_cutoff']/1000:>6.1f}k"
        )


if __name__ == "__main__":
    main()
