#!/usr/bin/env python3
"""Debug portishead: why is_natural_rolloff returns True."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.audio_loader import load_audio
from src.core.frequency_detector import (
    compute_band_energy_simple, compute_band_peak_energy,
    compute_band_temporal_variance, find_cutoff_by_transition,
    find_segment_cutoffs, calculate_predominant_cutoff,
)
from src.utils.constants import (
    BRICKWALL_MIN_GRADIENT_DB_PER_KHZ, BRICKWALL_MAX_POST_VARIANCE,
    BRICKWALL_ELEVATED_ENERGY_DB, BRICKWALL_OVERRIDE_ENERGY_DB,
    BRICKWALL_ELEVATED_RATIO, FFT_SIZE, HOP_LENGTH,
)
import librosa

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(PROJECT, "references/test-files/base/transcode-portishead.mp3")

audio = load_audio(path)
stft = librosa.stft(audio.samples, n_fft=FFT_SIZE, hop_length=HOP_LENGTH)
magnitude = np.abs(stft)
spec_db = librosa.amplitude_to_db(magnitude, ref=np.max)
frequencies = librosa.fft_frequencies(sr=audio.metadata.sample_rate, n_fft=FFT_SIZE)

# Active frames
frame_energy = np.mean(spec_db, axis=0)
threshold = np.max(frame_energy) - 30
active = frame_energy > threshold
ref_band = spec_db[(frequencies >= 2000) & (frequencies <= 8000), :]
ref_std = float(np.std(np.mean(ref_band[:, active] if np.any(active) else ref_band, axis=0)))

# Find cutoffs
ref_stats = (np.mean(np.mean(ref_band, axis=0)), ref_std)
cutoff_tr, conf_tr = find_cutoff_by_transition(spec_db, frequencies, audio.metadata.sample_rate, ref_stats=ref_stats)
print(f"Transition cutoff: {cutoff_tr:.0f} Hz ({cutoff_tr/1000:.1f} kHz), conf={conf_tr:.2f}")

segment_cutoffs = find_segment_cutoffs(audio.samples, audio.metadata.sample_rate)
cutoff_seg = calculate_predominant_cutoff(segment_cutoffs)
print(f"Segment cutoff: {cutoff_seg:.0f} Hz ({cutoff_seg/1000:.1f} kHz)")

# Simulate is_natural_rolloff with actual cutoff
# Try different potential cutoff values
for test_cutoff in [cutoff_tr, 14000, 15000, 13000]:
    scan_bw = 1000
    scan_start = max(int(test_cutoff) - 1000, 8000)

    print(f"\n--- is_natural_rolloff simulation, cutoff={test_cutoff:.0f} Hz ---")

    brickwall_freq = None
    for f in range(scan_start, 19000, scan_bw):
        pre = compute_band_energy_simple(spec_db, frequencies, f, f + scan_bw)
        post = compute_band_energy_simple(spec_db, frequencies, f + scan_bw, f + 2 * scan_bw)
        gradient = pre - post
        post_var = compute_band_temporal_variance(spec_db, frequencies, f + scan_bw, f + 2 * scan_bw, active, ref_std)

        is_bw = gradient >= BRICKWALL_MIN_GRADIENT_DB_PER_KHZ and post_var <= BRICKWALL_MAX_POST_VARIANCE
        if f >= 10000 or is_bw:
            print(f"  {f/1000:.0f}-{(f+scan_bw)/1000:.0f}: grad={gradient:.1f} var={post_var:.2f} {'*** BW ***' if is_bw else ''}")
        if is_bw and brickwall_freq is None:
            brickwall_freq = f + scan_bw

    if brickwall_freq:
        print(f"  Brickwall at {brickwall_freq} Hz. Elevated check (threshold={BRICKWALL_OVERRIDE_ENERGY_DB}):")
        check_start = brickwall_freq
    else:
        print(f"  No brickwall. Elevated check (threshold={BRICKWALL_ELEVATED_ENERGY_DB}):")
        check_start = int(test_cutoff)

    elev = 0
    total = 0
    threshold_db = BRICKWALL_OVERRIDE_ENERGY_DB if brickwall_freq else BRICKWALL_ELEVATED_ENERGY_DB
    for f in range(check_start, 20000, scan_bw):
        e = compute_band_peak_energy(spec_db, frequencies, f, f + scan_bw)
        total += 1
        is_e = e > threshold_db
        if is_e:
            elev += 1
        print(f"    {f/1000:.0f}-{(f+scan_bw)/1000:.0f}: peak={e:.1f} {'ELEV' if is_e else ''}")

    ratio = elev / total if total > 0 else 0
    result = ratio >= BRICKWALL_ELEVATED_RATIO
    print(f"  Ratio: {elev}/{total} = {ratio:.2f} → {'NATURAL' if result else 'CODEC'}")
