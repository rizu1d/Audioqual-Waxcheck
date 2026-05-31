"""
Diagnostic script for cluster-4 files.
Runs band-by-band analysis to understand why each file is misclassified.

Usage: python3 scripts/diagnose_cluster4.py
"""

import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

from scripts.diagnose_detection import analyze_file


def main():
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
            print(f"WARNING: File not found: {filepath}")
            continue
        try:
            analyze_file(filepath)
        except Exception as e:
            print(f"ERROR analyzing {filename}: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
