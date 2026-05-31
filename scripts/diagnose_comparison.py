"""
Compare band metrics between cluster-4 files (false positives) and
YouTube rips (true transcodes) to find distinguishing features.
"""

import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)

from scripts.diagnose_detection import analyze_file


def main():
    # A few YouTube rips (true transcodes) for comparison
    yt_dir = os.path.join(project_dir, "references", "test-files", "youtube-rips")
    cluster_dir = os.path.join(
        project_dir, "references", "test-files", "errores", "cluster-4"
    )

    print("=" * 80)
    print("YOUTUBE RIPS (TRUE TRANSCODES)")
    print("=" * 80)

    yt_files = [
        "C.R.E.A.M. (A Cappella).mp3",
        "transcode-thebox.mp3",
    ]

    base_dir = os.path.join(project_dir, "references", "test-files", "base")
    base_files = [
        ("notaiff-detected.aiff", base_dir),
        ("notaiff-undetected.aiff", base_dir),
    ]

    for filename in yt_files:
        filepath = os.path.join(yt_dir, filename)
        if not os.path.exists(filepath):
            print(f"WARNING: Not found: {filepath}")
            continue
        try:
            analyze_file(filepath)
        except Exception as e:
            print(f"ERROR: {e}")

    for filename, directory in base_files:
        filepath = os.path.join(directory, filename)
        if not os.path.exists(filepath):
            print(f"WARNING: Not found: {filepath}")
            continue
        try:
            analyze_file(filepath)
        except Exception as e:
            print(f"ERROR: {e}")

    print("\n" + "=" * 80)
    print("CLUSTER-4 FILES (FALSE POSITIVES - PATTERN A)")
    print("=" * 80)

    c4_files = [
        "19 - Tyson Bruun - Future.mp3",
        "33 - Heckmann - Espectaculo.mp3",
        "The 45 King - Beat Suite One (Part Four).mp3",
    ]

    for filename in c4_files:
        filepath = os.path.join(cluster_dir, filename)
        if not os.path.exists(filepath):
            print(f"WARNING: Not found: {filepath}")
            continue
        try:
            analyze_file(filepath)
        except Exception as e:
            print(f"ERROR: {e}")


if __name__ == "__main__":
    main()
