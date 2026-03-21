"""
Diagnostic script: analyze the 6 files with suspected false-negative classification.
These files are classified as "Bajo" but should be "Bueno" or "Medio".

Prints band-by-band stats, trigger methods, and method comparison to identify
why the cutoff is being underestimated.

Usage: python scripts/diagnose_false_negatives.py
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
from src.core.analyzer import AudioAnalyzer
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
    get_quality_level,
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


def diagnose_file(filepath):
    """Full diagnosis of a single file."""
    filename = os.path.basename(filepath)
    print(f"\n{'='*90}")
    print(f"  FILE: {filename}")
    print(f"{'='*90}")

    # Load audio
    samples, sr = librosa.load(filepath, sr=SAMPLE_RATE, mono=True)
    duration = len(samples) / sr
    print(f"  Duration: {duration:.1f}s | Sample rate: {sr}Hz")

    # Compute spectrogram
    spectrogram_db, frequencies = compute_spectrogram(samples, sr, FFT_SIZE, HOP_LENGTH)

    # Reference stats
    ref_energy_per_frame, ref_mean, ref_std = compute_reference_band_stats(
        spectrogram_db, frequencies
    )
    active_frames_mask = identify_active_frames(ref_energy_per_frame, ref_mean, ref_std)

    # Compute band stats
    band_stats = []
    current_freq = TRANSITION_SEARCH_START_HZ
    nyquist_hz = sr / 2
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

    # Print band stats focused on 15-21kHz (the critical zone)
    print(f"\n  Band analysis (500Hz bands, critical zone 15-21kHz):")
    print(f"  {'Band':>12s}  {'Energy':>8s}  {'Var':>8s}  {'Thresh':>7s}  {'Musical':>7s}  {'Drop→next':>10s}  {'VarDrop%':>8s}")
    for i, (freq, energy, variance) in enumerate(band_stats):
        if freq < 15000:
            continue
        min_var = get_min_pre_variance(freq)
        is_musical = variance >= min_var

        # Energy drop to next band
        drop_str = ""
        var_drop_str = ""
        if i + 1 < len(band_stats):
            _, e_next, v_next = band_stats[i + 1]
            drop = energy - e_next
            drop_str = f"{drop:>+.1f}dB"
            if variance > 0.1:
                var_drop = (variance - v_next) / variance
                var_drop_str = f"{var_drop:.0%}"

        print(
            f"  {freq/1000:>7.1f} kHz  {energy:>8.1f}  {variance:>8.3f}  "
            f"{min_var:>7.3f}  {'YES' if is_musical else 'no':>7s}  "
            f"{drop_str:>10s}  {var_drop_str:>8s}"
        )

    # Method 1: Transition
    cutoff_trans, conf_trans = find_cutoff_by_transition(
        spectrogram_db, frequencies, sr,
        ref_stats=(ref_energy_per_frame, ref_mean, ref_std, active_frames_mask),
    )

    # Method 2: Segments
    segment_cutoffs = find_segment_cutoffs(spectrogram_db, frequencies, sr, n_segments=SEGMENT_COUNT)
    cutoff_seg, conf_seg, has_outliers = calculate_predominant_cutoff(
        segment_cutoffs, percentile=PREDOMINANT_PERCENTILE
    )

    # Full analysis
    result = analyze_frequency_cutoff(samples, sr)

    print(f"\n  METHOD RESULTS:")
    print(f"    Transition:  {cutoff_trans/1000:.1f} kHz  (conf={conf_trans:.3f})")
    print(f"    Segments:    {cutoff_seg/1000:.1f} kHz  (conf={conf_seg:.3f}, outliers={has_outliers})")
    print(f"    FINAL:       {result.cutoff_frequency_khz:.1f} kHz  (conf={result.confidence:.3f})")

    # Scan for which trigger fired
    print(f"\n  TRIGGER ANALYSIS:")

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
                    parts.append(f"abs(v={variance_high:.3f}<{thresh:.3f})")
                if has_rel_var_drop:
                    parts.append(f"rel({variance_drop_ratio:.0%}>=35%)")
                if has_two_band:
                    parts.append("2band")
                methods.append(f"1b({'+'.join(parts)})")
            if has_cumulative:
                methods.append(f"1c(cum={cum_drop:.1f}dB)")
            if has_sliding_decay:
                methods.append("1d(decay)")

            recovers = energy_recovers_after(i, energy_high)
            status = "BLOCKED(recovery)" if recovers else ">>> FIRED <<<"
            print(f"    {freq_low/1000:.1f}-{freq_high/1000:.1f}kHz: {status}  {', '.join(methods)}")
            if not recovers:
                print(f"    ==> DETECTION AT: {freq_high/1000:.1f} kHz")
                break

    # Full app analysis for classification
    analyzer = AudioAnalyzer()
    app_result = analyzer.analyze_file(filepath)
    quality_level = get_quality_level(app_result.cutoff_frequency_khz, app_result.status)

    print(f"\n  APP RESULT:")
    print(f"    Cutoff: {app_result.cutoff_frequency_khz:.1f} kHz")
    print(f"    Status: {app_result.status}")
    print(f"    Quality: {app_result.detected_quality}")
    print(f"    Badge: {quality_level}")
    print(f"    Details: {app_result.details}")

    return app_result


def main():
    music_dir = "/Users/alexandrecombret/Music/Música descargada"

    # The 6 problematic files
    problem_files = [
        os.path.join(music_dir, "303-training/DUBRIDER - 04 Legal ALTO.mp3"),
        os.path.join(music_dir, "Nuevas songs via lexmusik/02 - Orchestre Esperanza Et Jean Leroy - Ou Pas Bel.mp3"),
        os.path.join(music_dir, "prueba/prueba2/19 - Tim Love Lee - Sombre Hombre.mp3"),
        os.path.join(music_dir, "303-training/YMC - Endless Roads MEDIO.mp3"),
        os.path.join(music_dir, "Nicolás Mirón - Hi-Tech Thoughts (pre-order)/Nicolás Mirón - Hi-Tech Thoughts - 02 Space Rodeo.mp3"),
        os.path.join(music_dir, "prueba/prueba2/02 - The Wiseguys - Too Easy.mp3"),
    ]

    # Control files (must NOT regress)
    base_dir = os.path.join(project_dir, "references", "test-files", "base")
    control_files = [
        os.path.join(base_dir, "Agoria - Teardrops (Don't Stop The Music) (Nick Morgan Remix).mp3"),
        os.path.join(base_dir, "Silicone Soul - Chic-O-Laa (H-Foundation Remix).mp3"),
        os.path.join(base_dir, "transcode-manuchao.mp3"),
    ]

    print("=" * 90)
    print("  PROBLEMATIC FILES (currently Bajo, should be Bueno/Medio)")
    print("=" * 90)

    for filepath in problem_files:
        if not os.path.exists(filepath):
            print(f"\n  WARNING: File not found: {filepath}")
            continue
        try:
            diagnose_file(filepath)
        except Exception as e:
            print(f"\n  ERROR analyzing {os.path.basename(filepath)}: {e}")
            import traceback
            traceback.print_exc()

    print("\n\n")
    print("=" * 90)
    print("  CONTROL FILES (must NOT regress)")
    print("=" * 90)

    for filepath in control_files:
        if not os.path.exists(filepath):
            print(f"\n  WARNING: File not found: {filepath}")
            continue
        try:
            diagnose_file(filepath)
        except Exception as e:
            print(f"\n  ERROR analyzing {os.path.basename(filepath)}: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
