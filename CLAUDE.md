# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AudioQual is a desktop application for analyzing the real quality of audio files through spectral analysis. It detects "fake" high-bitrate files (files upscaled/transcoded from lower quality sources) by examining frequency cutoff patterns.

**Python version:** 3.9+

## Commands

```bash
# Run the application
python src/main.py

# Install dependencies
pip install -r requirements.txt

# Build standalone app
pyinstaller build/audioqual_macos.spec   # macOS
pyinstaller build/audioqual_windows.spec  # Windows
```

## Architecture

### Core Analysis Pipeline (`src/core/`)

The analysis follows a three-stage pipeline:

1. **audio_loader.py** - Loads audio files using librosa, extracts metadata via mutagen (bitrate, duration, format, bit depth)
2. **frequency_detector.py** - Performs spectral analysis using STFT to detect frequency cutoff
3. **bitrate_classifier.py** - Classifies quality based on cutoff frequency thresholds, detects transcodes by comparing declared vs detected quality

`analyzer.py` orchestrates the pipeline with `AudioAnalyzer` class, supporting batch analysis with threading via `ThreadPoolExecutor`.

### Frequency Detection Algorithm (`src/core/frequency_detector.py`)

Uses a multi-method approach to detect codec low-pass filter cutoffs:

1. **Transition-based detection (primary)** - Finds where energy DROPS significantly between adjacent 500Hz bands; uses relative variance drop (>30%) to distinguish music→noise transitions from natural energy variations
2. **Segment-based percentile analysis (secondary)** - Divides audio into 50 segments, calculates cutoff for each, uses 85th percentile to find predominant cutoff (ignores peaks/outliers)
3. **High-frequency verification** - Validates cutoffs >21kHz by comparing variance ratios between 20-22kHz and 15-20kHz bands

Key insight: Musical content has high temporal variance (follows dynamics), while noise/artifacts have constant energy. The algorithm uses *relative* variance drop between bands rather than absolute thresholds to avoid detection failures.

### GUI Layer (`src/gui/`)

Built with customtkinter and tkinterdnd2 for drag-and-drop support:
- **main_window.py** - Main layout with drop zone, results table, progress bar
- **spectrogram_panel.py** - Renders spectrograms in background thread using matplotlib's Agg backend, displays as PIL Image to keep UI responsive
- **file_drop_zone.py** - Drag-and-drop file input
- **results_table.py** - Displays analysis results with status colors (uses ttk.Treeview)

### Threading Patterns

Two threading patterns are used for UI responsiveness:

1. **Batch analysis** (`analyzer.py`): Uses `ThreadPoolExecutor` to process multiple files in parallel
2. **Spectrogram rendering** (`spectrogram_panel.py`): Uses `threading.Thread` + `threading.Event` for cancellable background rendering. Incremental `_render_id` ensures only the latest render is displayed.

### Application Entry

- `src/main.py` - Entry point
- `src/app.py` - `AudioQualApp` class creates root window, wires components together, and manages the resizable panel divider between main content and spectrogram panel

## Key Constants (`src/utils/constants.py`)

- **BITRATE_THRESHOLDS** - Frequency ranges (kHz) for quality tiers: low (<13kHz), 96kbps (13-15kHz), 128kbps (15-16kHz), 160kbps (16-17kHz), 192kbps (17-18.5kHz), 256kbps (18.5-19.5kHz), 320kbps (19.5-20.5kHz), lossless (20.5-22.5kHz)
- **FFT_SIZE=4096, HOP_LENGTH=512, SAMPLE_RATE=44100** - Spectral analysis parameters
- **TRANSITION_*** - Parameters for transition detection (min drop: 8dB, variance drop ratio: 30%, band width: 500Hz)
- **SEGMENT_COUNT=50, PREDOMINANT_PERCENTILE=85** - Segment analysis parameters
- **CONFIDENCE_HIGH=0.7, CONFIDENCE_LOW=0.5** - Thresholds for certain vs uncertain results
- **SUPPORTED_FORMATS** - .mp3, .wav, .flac, .m4a, .aac, .ogg, .wma, .aiff, .aif
- **THEME_COLORS, STATUS_COLORS** - UI color palette (purple/gold/dark gray theme)
- **FONT_FAMILY, FONT_SIZES** - Typography constants (Inter font family)

## Language

The UI text and status messages are in Spanish (e.g., "Transcode detectado", "Analizando...").

## Notes

- No test suite exists currently
- The codebase uses matplotlib's Agg backend (non-interactive) for spectrogram rendering to avoid GUI conflicts with tkinter
