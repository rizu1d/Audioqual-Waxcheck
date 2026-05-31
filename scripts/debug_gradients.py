#!/usr/bin/env python3
"""Check max mean-energy gradients for all test files to calibrate threshold."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.audio_loader import load_audio
from src.core.frequency_detector import compute_band_energy_simple
from src.utils.constants import FFT_SIZE, HOP_LENGTH
import librosa

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = {
    "portishead": "references/test-files/base/transcode-portishead.mp3",
    "manuchao": "references/test-files/base/transcode-manuchao.mp3",
    "sickomode": "references/test-files/base/transcode-sickomode.mp3",
    "thebox": "references/test-files/base/transcode-thebox.mp3",
    "Future": "references/test-files/errores/cluster-4/19 - Tyson Bruun - Future.mp3",
    "PirateMat": "references/test-files/miron/Nicolás Mirón - Hi-Tech Thoughts - 01 Pirate Material.mp3",
    "Summerbreeze": "references/test-files/errores/cluster-4/09 - Sluts'n'Strings & 909 - Summerbreeze.mp3",
    "SpaceRodeo": "references/test-files/errores/cluster-4/02 - Space Rodeo.mp3",
    "Agoria": "references/test-files/base/Agoria - Teardrops (Don't Stop The Music) (Nick Morgan Remix).mp3",
    "Silicone": "references/test-files/base/Silicone Soul - Chic-O-Laa (H-Foundation Remix).mp3",
}

scan_bw = 1000

for name, path in FILES.items():
    abs_path = os.path.join(PROJECT, path)
    if not os.path.exists(abs_path):
        continue

    audio = load_audio(abs_path)
    stft = librosa.stft(audio.samples, n_fft=FFT_SIZE, hop_length=HOP_LENGTH)
    spec_db = librosa.amplitude_to_db(np.abs(stft), ref=np.max)
    frequencies = librosa.fft_frequencies(sr=audio.metadata.sample_rate, n_fft=FFT_SIZE)

    max_grad = 0
    max_grad_freq = 0
    for f in range(10000, 19000, scan_bw):
        pre = compute_band_energy_simple(spec_db, frequencies, f, f + scan_bw)
        post = compute_band_energy_simple(spec_db, frequencies, f + scan_bw, f + 2 * scan_bw)
        grad = pre - post
        if grad > max_grad:
            max_grad = grad
            max_grad_freq = f

    label = "TRANSCODE" if name in ["portishead", "manuchao", "sickomode", "thebox"] else "LEGIT"
    print(f"{name:15s} [{label:9s}]: max_grad={max_grad:.1f} dB/kHz at {max_grad_freq/1000:.0f}-{(max_grad_freq+scan_bw)/1000:.0f}kHz")
