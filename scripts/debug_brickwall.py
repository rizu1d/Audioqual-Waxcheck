#!/usr/bin/env python3
"""Debug brickwall detection for real transcodes."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.audio_loader import load_audio
from src.core.frequency_detector import (
    compute_band_energy_simple, compute_band_peak_energy,
    compute_band_temporal_variance,
)
from src.utils.constants import (
    BRICKWALL_MIN_GRADIENT_DB_PER_KHZ, BRICKWALL_MAX_POST_VARIANCE,
    BRICKWALL_ELEVATED_ENERGY_DB, BRICKWALL_ELEVATED_RATIO,
    FFT_SIZE, HOP_LENGTH,
)
import librosa

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = {
    "manuchao": "references/test-files/base/transcode-manuchao.mp3",
    "portishead": "references/test-files/base/transcode-portishead.mp3",
    "sickomode": "references/test-files/base/transcode-sickomode.mp3",
    "thebox": "references/test-files/base/transcode-thebox.mp3",
    "PirateMat": "references/test-files/miron/Nicolás Mirón - Hi-Tech Thoughts - 01 Pirate Material.mp3",
}

scan_bw = 1000

for name, path in FILES.items():
    abs_path = os.path.join(PROJECT, path)
    if not os.path.exists(abs_path):
        print(f"{name}: NOT FOUND")
        continue

    audio = load_audio(abs_path)
    stft = librosa.stft(audio.samples, n_fft=FFT_SIZE, hop_length=HOP_LENGTH)
    magnitude = np.abs(stft)
    spec_db = librosa.amplitude_to_db(magnitude, ref=np.max)
    frequencies = librosa.fft_frequencies(sr=audio.metadata.sample_rate, n_fft=FFT_SIZE)

    # Active frames
    frame_energy = np.mean(spec_db, axis=0)
    threshold = np.max(frame_energy) - 30
    active = frame_energy > threshold
    ref_band = spec_db[(frequencies >= 2000) & (frequencies <= 8000), :]
    ref_std = float(np.std(np.mean(ref_band[:, active] if np.any(active) else ref_band, axis=0))) if ref_band.size > 0 else 1.0

    print(f"\n=== {name} ===")
    print(f"  Thresholds: grad>={BRICKWALL_MIN_GRADIENT_DB_PER_KHZ}, var<={BRICKWALL_MAX_POST_VARIANCE}, elev>{BRICKWALL_ELEVATED_ENERGY_DB}")

    # Scan for brickwall using MEAN energy
    print(f"  --- Brickwall scan (mean energy, {scan_bw}Hz bands) ---")
    brickwall_freq = None
    for f in range(8000, 19000, scan_bw):
        pre_mean = compute_band_energy_simple(spec_db, frequencies, f, f + scan_bw)
        post_mean = compute_band_energy_simple(spec_db, frequencies, f + scan_bw, f + 2 * scan_bw)
        grad_mean = pre_mean - post_mean

        post_var = compute_band_temporal_variance(spec_db, frequencies, f + scan_bw, f + 2 * scan_bw, active, ref_std)

        marker = ""
        if grad_mean >= BRICKWALL_MIN_GRADIENT_DB_PER_KHZ and post_var <= BRICKWALL_MAX_POST_VARIANCE:
            marker = " *** BRICKWALL ***"
            if brickwall_freq is None:
                brickwall_freq = f + scan_bw

        if f >= 10000 or marker:
            print(f"    {f/1000:.0f}-{(f+scan_bw)/1000:.0f}kHz: mean_pre={pre_mean:.1f} mean_post={post_mean:.1f} grad={grad_mean:.1f} var={post_var:.2f}{marker}")

    # Elevated content check using PEAK energy
    print(f"  --- Elevated content (peak energy) from brickwall={brickwall_freq} ---")
    check_start = int(brickwall_freq) if brickwall_freq else 15000
    elevated = 0
    total = 0
    for f in range(check_start, 20000, scan_bw):
        e = compute_band_peak_energy(spec_db, frequencies, f, f + scan_bw)
        total += 1
        is_elev = e > BRICKWALL_ELEVATED_ENERGY_DB
        if is_elev:
            elevated += 1
        print(f"    {f/1000:.0f}-{(f+scan_bw)/1000:.0f}kHz: peak={e:.1f} {'ELEVATED' if is_elev else ''}")
    ratio = elevated / total if total > 0 else 0
    print(f"  Ratio: {elevated}/{total} = {ratio:.2f} (threshold: {BRICKWALL_ELEVATED_RATIO})")
    result = "NATURAL (override brickwall)" if brickwall_freq and ratio >= BRICKWALL_ELEVATED_RATIO else "NATURAL (no brickwall)" if not brickwall_freq and ratio >= BRICKWALL_ELEVATED_RATIO else "CODEC CUT"
    print(f"  Result: {result}")
