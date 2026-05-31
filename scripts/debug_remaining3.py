#!/usr/bin/env python3
"""Debug the 3 remaining false positives after is_natural_rolloff changes."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.analyzer import AudioAnalyzer

FILES = [
    ("Future", "references/test-files/errores/cluster-4/19 - Tyson Bruun - Future.mp3"),
    ("PirateMat", "references/test-files/miron/Nicolás Mirón - Hi-Tech Thoughts - 01 Pirate Material.mp3"),
    ("Summerbreeze", "references/test-files/errores/cluster-4/09 - Sluts'n'Strings & 909 - Summerbreeze.mp3"),
]

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
analyzer = AudioAnalyzer()
for name, path in FILES:
    abs_path = os.path.join(PROJECT, path)
    if not os.path.exists(abs_path):
        print(f"{name}: FILE NOT FOUND at {abs_path}")
        continue
    r = analyzer.analyze_file(abs_path)
    print(f"{name}: cutoff={r.cutoff_frequency_khz:.1f}kHz status={r.status} quality={r.detected_quality} conf={r.confidence:.2f}")
