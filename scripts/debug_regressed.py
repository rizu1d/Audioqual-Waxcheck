#!/usr/bin/env python3
"""Debug the regressed files: energy and variance above cutoff."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.audio_loader import load_audio
from src.core.frequency_detector import compute_band_peak_energy, compute_band_temporal_variance
from src.utils.constants import FFT_SIZE, HOP_LENGTH
import librosa

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = {
    "notaiff-undet[LEGIT]": ("references/test-files/base/notaiff-undetected.aiff", 16000),
    "PlaisirFrance[LEGIT]": ("references/test-files/casos-excepcionales/Plaisir de France - Américaine (2002 Mix).mp3", 16000),
    "PoppaLarge   [LEGIT]": ("references/test-files/youtuberips/poppa large acapella ultramagnetic mcs.mp3", 15000),
    "PirateMat    [LEGIT]": ("references/test-files/miron/Nicolás Mirón - Hi-Tech Thoughts - 01 Pirate Material.mp3", 10500),
    "YT_003       [YTRIP]": ("references/test-files/youtuberips/De La Soul  Chaka Khan  All Good Acapella.mp3", 15000),
    "YT_012       [YTRIP]": ("references/test-files/youtuberips/Supreme NTM - Boogie man acapellaaaa.mp3", 15000),
}

scan_bw = 1000

for name, (path, approx_cutoff) in FILES.items():
    abs_path = os.path.join(PROJECT, path)
    if not os.path.exists(abs_path):
        print(f"{name}: NOT FOUND")
        continue

    audio = load_audio(abs_path)
    stft = librosa.stft(audio.samples, n_fft=FFT_SIZE, hop_length=HOP_LENGTH)
    spec_db = librosa.amplitude_to_db(np.abs(stft), ref=np.max)
    frequencies = librosa.fft_frequencies(sr=audio.metadata.sample_rate, n_fft=FFT_SIZE)

    frame_energy = np.mean(spec_db, axis=0)
    threshold = np.max(frame_energy) - 30
    active = frame_energy > threshold
    ref_band = spec_db[(frequencies >= 2000) & (frequencies <= 8000), :]
    ref_std = float(np.std(np.mean(ref_band[:, active] if np.any(active) else ref_band, axis=0)))

    print(f"\n{name} (cutoff~{approx_cutoff/1000:.1f}kHz)")
    strong65 = 0
    elev76 = 0
    musical = 0
    total = 0
    for f in range(approx_cutoff, 20000, scan_bw):
        e = compute_band_peak_energy(spec_db, frequencies, f, f + scan_bw)
        v = compute_band_temporal_variance(spec_db, frequencies, f, f + scan_bw, active, ref_std)
        total += 1
        if e > -65: strong65 += 1
        if e > -76: elev76 += 1
        if v > 0.25: musical += 1
        print(f"  {f/1000:.0f}-{(f+scan_bw)/1000:.0f}kHz: peak={e:.1f} var={v:.2f}")
    print(f"  Strong(>-65): {strong65}  Elevated(>-76): {elev76}/{total}={elev76/total:.2f}  Musical(var>0.25): {musical}")
