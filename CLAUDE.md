# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AudioQual is a desktop application for analyzing the real quality of audio files through spectral analysis. It detects "fake" high-bitrate files (files upscaled/transcoded from lower quality sources) by examining frequency cutoff patterns.

**Python version:** 3.9+

## Commands

```bash
# Run the application
python3 src/main.py

# Install dependencies
pip install -r requirements.txt

# Run tests (full suite, ~42s — analyzes 32 audio files)
python3 tests/run_tests.py

# Run only UI tests (fast, ~2s, no audio analysis)
python3 tests/run_tests.py --suite ui

# Run only detection or classification tests
python3 tests/run_tests.py --suite detection
python3 tests/run_tests.py --suite classification

# Summary only (no per-test output)
python3 tests/run_tests.py --summary

# Save results to tests/results_YYYYMMDD_HHMMSS.json
python3 tests/run_tests.py --save

# Build standalone app
pyinstaller build/audioqual_macos.spec   # macOS
pyinstaller build/audioqual_windows.spec  # Windows
```

No linter is configured.

## Architecture

### Core Analysis Pipeline (`src/core/`)

Three-stage pipeline orchestrated by `AudioAnalyzer` in `analyzer.py`:

1. **audio_loader.py** — Loads audio via librosa, extracts metadata via mutagen
2. **frequency_detector.py** — Spectral analysis (STFT) to detect frequency cutoff where real content ends. See `knowledge/ALGORITMO.txt` for full algorithm explanation.
3. **bitrate_classifier.py** — Classifies quality based on cutoff vs thresholds, detects transcodes. Includes MP3 bitrate plausibility safety net (caps cutoff to physical max per bitrate).

### GUI Layer (`src/gui/`)

Built with customtkinter + tkinterdnd2 (drag-and-drop). Examine individual files in `src/gui/` for component details. Key entry point: `main_window.py` (layout, toolbar, progress, status bar). Audio playback via `audio_player.py` (sounddevice callback-based). Keyboard shortcuts in `app.py → _setup_keyboard_bindings()`.

### FolderWatcher (`src/core/folder_watcher.py`)

Monitors a folder for new audio files, auto-queues for analysis. Uses `watchdog.observers.PollingObserver` (not FSEventsObserver — macOS Unicode bug). Stability check before dispatch, temp file filtering, deduplication. Gracefully disabled if `watchdog` not installed.

### Internationalization (`src/utils/i18n.py`)

See `.claude/rules/i18n.md` for full i18n rules and conventions.

### Utilities (`src/utils/`)

- **constants.py** — All configurable parameters: bitrate thresholds, FFT params, detection algorithm params, theme colors, fonts, dimensions. Read the file for specifics.
- **tk_utils.py** — `schedule_callback_from_thread()` for thread-safe UI updates (see constraints below)
- **settings.py** — Singleton `AppSettings` with JSON persistence at `~/.audioqual/settings.json`. Properties: `rename_on_save`, `language`, `output_device`, `watcher_folder`, `watcher_auto_start`.
- **spectrogram_cache.py** — Disk cache for downsampled uint8 spectrograms in `~/.audioqual/cache/`

## Rules

Operational constraints are in `.claude/rules/` (loaded automatically with the same priority as this file):

- `thread-safety.md` — Tkinter threading, matplotlib backend, macOS event loop
- `testing.md` — Test suite rules, post-implementation verification table
- `i18n.md` — Internationalization conventions and constraints
- `memory-management.md` — Transient data lifecycle and eviction

## Knowledge Base

- `knowledge/ALGORITMO.txt` — Full algorithm explanation (read before modifying `frequency_detector.py`)
- `knowledge/VERIFICACION.txt` — Verification system architecture
- `scripts/diagnose_*.py` — Band-by-band diagnostic scripts for algorithm calibration

