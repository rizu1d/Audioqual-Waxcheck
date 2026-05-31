#!/usr/bin/env python3
"""Quick check: peak-energy gradients for Summerbreeze and notaiff-undetected."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core.audio_loader import load_audio
from src.core.frequency_detector import compute_band_peak_energy, compute_band_energy_simple, compute_band_temporal_variance
from src.utils.constants import FFT_SIZE, HOP_LENGTH, BRICKWALL_MIN_GRADIENT_DB_PER_KHZ, BRICKWALL_MAX_POST_VARIANCE
import librosa

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    ("Summerbreeze", "references/test-files/errores/cluster-4/09 - Sluts'n'Strings & 909 - Summerbreeze.mp3"),
    ("notaiff-undet", "references/test-files/base/notaiff-undetected.aiff"),
]

for name, path in FILES:
    abs_path = os.path.join(PROJECT, path)
    if not os.path.exists(abs_path): continue
    audio = load_audio(abs_path)
    stft = librosa.stft(audio.samples, n_fft=FFT_SIZE, hop_length=HOP_LENGTH)
    spec_db = librosa.amplitude_to_db(np.abs(stft), ref=np.max)
    freqs = librosa.fft_frequencies(sr=audio.metadata.sample_rate, n_fft=FFT_SIZE)
    fe = np.mean(spec_db, axis=0)
    active = fe > np.max(fe) - 30
    rb = spec_db[(freqs >= 2000) & (freqs <= 8000), :]
    rs = float(np.std(np.mean(rb[:, active] if np.any(active) else rb, axis=0)))

    print(f"\n=== {name} ===")
    for f in range(14000, 20000, 1000):
        pg = compute_band_peak_energy(spec_db, freqs, f, f+1000) - compute_band_peak_energy(spec_db, freqs, f+1000, f+2000)
        mg = compute_band_energy_simple(spec_db, freqs, f, f+1000) - compute_band_energy_simple(spec_db, freqs, f+1000, f+2000)
        pv = compute_band_temporal_variance(spec_db, freqs, f+1000, f+2000, active, rs)
        bw = pg >= BRICKWALL_MIN_GRADIENT_DB_PER_KHZ and pv <= BRICKWALL_MAX_POST_VARIANCE
        print(f"  {f/1000:.0f}-{(f+1000)/1000:.0f}kHz: peak_grad={pg:.1f} mean_grad={mg:.1f} var={pv:.2f} {'PEAK_BW' if bw else ''}")
