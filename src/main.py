#!/usr/bin/env python3
"""WaxCheck - Audio Quality Analyzer

A desktop application for analyzing the real quality of audio files
through spectral analysis, detecting "fake" files (upscaled from lower quality).
"""

import sys
from pathlib import Path

# Add src to path for relative imports when running directly
if __name__ == "__main__":
    # CRITICO con ProcessPoolExecutor: en la app EMPAQUETADA (PyInstaller) cada
    # proceso auxiliar relanza el ejecutable; sin freeze_support() eso entraria
    # en un bucle infinito de arranques. Debe ser lo primero del proceso. En
    # macOS/Windows el arranque es "spawn", asi que el hijo hereda este sys.path.
    import multiprocessing
    multiprocessing.freeze_support()

    src_path = Path(__file__).parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def main():
    """Main entry point for the application."""
    from src.app import create_app

    app = create_app()
    app.run()


if __name__ == "__main__":
    main()
