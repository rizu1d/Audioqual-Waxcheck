"""Quick diagnostic for BASE_009 and a couple YouTube rips."""
import os, sys
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)
from scripts.diagnose_detection import analyze_file

def main():
    base = os.path.join(project_dir, "references", "test-files", "base")
    yt = os.path.join(project_dir, "references", "test-files", "youtube-rips")

    files = [
        os.path.join(base, "transcode-thebox.mp3"),
        os.path.join(yt, "C.R.E.A.M. (A Cappella).mp3"),
        os.path.join(yt, "Walkman Music (Acapella).mp3"),
    ]
    for f in files:
        if os.path.exists(f):
            analyze_file(f)
        else:
            print(f"NOT FOUND: {f}")

if __name__ == "__main__":
    main()
