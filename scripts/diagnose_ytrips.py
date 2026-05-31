"""Quick diagnostic for YouTube rips to verify decision logic guard safety."""
import os, sys
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
sys.path.insert(0, project_dir)
from scripts.diagnose_detection import analyze_file

def main():
    yt = os.path.join(project_dir, "references", "test-files", "youtuberips")
    files = [
        "C.R.E.A.M. (A Cappella).mp3",
        "Walkman Music (Acapella).mp3",
        "Poison (Isolated Vocals).mp3",
    ]
    for f in files:
        path = os.path.join(yt, f)
        if os.path.exists(path):
            analyze_file(path)
        else:
            print(f"NOT FOUND: {path}")

if __name__ == "__main__":
    main()
