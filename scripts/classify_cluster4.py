"""Get full classification for cluster-4 files."""
import os, sys
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

from src.core.analyzer import AudioAnalyzer

analyzer = AudioAnalyzer()
cluster_dir = os.path.join(
    project_dir, "references", "test-files", "errores", "cluster-4"
)

files = [
    "09 - Sluts'n'Strings & 909 - Summerbreeze.wav",
    "09 - Sluts'n'Strings & 909 - Summerbreeze.mp3",
    "08 - Haris Laus - Supadrug.mp3",
    "19 - Tyson Bruun - Future.mp3",
    "33 - Heckmann - Espectaculo.mp3",
    "The 45 King - Beat Suite One (Part Four).mp3",
]

for filename in files:
    filepath = os.path.join(cluster_dir, filename)
    if not os.path.exists(filepath):
        print(f"NOT FOUND: {filename}")
        continue
    result = analyzer.analyze_file(filepath)
    print(f"{filename}")
    print(f"  Cutoff: {result.cutoff_frequency_khz:.1f} kHz")
    print(f"  Quality: {result.detected_quality}")
    print(f"  Status: {result.status}")
    print(f"  Confidence: {result.confidence:.3f}")
    print(f"  Details: {result.details}")
    print()
