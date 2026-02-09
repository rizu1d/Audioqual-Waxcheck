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

There is no test suite or linter configured.

## Architecture

### Core Analysis Pipeline (`src/core/`)

Three-stage pipeline orchestrated by `AudioAnalyzer` in `analyzer.py`:

1. **audio_loader.py** - Loads audio via librosa, extracts metadata via mutagen (bitrate, duration, format, bit depth)
2. **frequency_detector.py** - Spectral analysis (STFT) to detect frequency cutoff where real content ends
3. **bitrate_classifier.py** - Classifies quality based on cutoff vs thresholds, detects transcodes by comparing declared vs detected quality. Includes MP3 bitrate plausibility safety net: caps detected cutoff to the physical maximum possible for the declared MP3 bitrate (e.g., 128kbps MP3 can't have cutoff above ~17kHz).

### Frequency Detection Algorithm (`src/core/frequency_detector.py`)

Key insight: musical content has high temporal variance (follows dynamics), while noise/artifacts have constant energy. The algorithm uses *relative* variance drop between frequency bands rather than absolute thresholds.

**Primary method: Transition-based detection (`find_cutoff_by_transition`)**

Searches 500Hz bands from 10kHz to 21kHz for the first "musical content → noise" transition.

- **Phase 1** - Find the FIRST band where musical content ends:
  - Band must have musical content (variance >= frequency-dependent threshold: 0.4 at 14kHz, interpolating down to 0.25 at 20kHz — this accommodates acapellas with lower high-frequency variance)
  - Detection triggers on: (a) energy drop >= 8dB, (b) variance transition (absolute or relative >= 35%), (c) cumulative drop across 3 consecutive bands >= 12dB
  - Anti-sibilance: recovery check requires 2+ consecutive bands with both energy AND variance >= 0.3 (isolated sibilance spikes don't count)
- **Phase 2** (fallback) - Best-score method for lossless/edge cases

**Secondary method: Segment-based percentile analysis**

Divides audio into 50 temporal segments, finds cutoff per segment, uses 85th percentile as the predominant cutoff (ignores top 15% peaks/outliers).

**Decision logic:**
- Transition confidence >= 0.7 → use it
- Both methods agree within 2kHz → average, boost confidence
- Transition is lower with confidence >= 0.5 → prefer it (conservative)
- Otherwise → segment method

**Verification:** Cutoffs > 21kHz are verified by comparing variance ratios between 20-22kHz and 15-20kHz bands.

### GUI Layer (`src/gui/`)

Built with customtkinter and tkinterdnd2 for drag-and-drop:
- **file_drop_zone.py** - Reusable drag-and-drop zone with file/folder selection dialog. Parses platform-specific drop formats (Windows braces vs Unix spaces). Uses `file_utils.get_audio_files_from_path` for recursive directory scanning.
- **main_window.py** - Main layout with empty state overlay, results table, player controls, progress bar, status bar. Drop targets on both content frame and results table scroll_frame.
- **spectrogram_window.py** - Separate `CTkToplevel` window; background thread renders matplotlib figure to PIL Image via Agg backend, then progressive left-to-right reveal animation (12 steps, 25ms each)
- **results_table.py** - Analysis results with status colors (ttk.Treeview)
- **audio_player.py** - Playback engine using sounddevice callback-based OutputStream. Dual-loader: uses `soundfile` for WAV/FLAC/OGG/AIFF (low GIL contention, faster), falls back to `librosa` for MP3/M4A/AAC/WMA.
- **player_controls.py** - Transport controls (play/pause, seek, volume, prev/next)
- **waveform_display.py** - DJ-style amplitude bar visualization with played/unplayed coloring and gold playhead. Background thread computes peaks, main thread updates display. Playhead updates skip if movement < 2px to reduce redraws.

Icon assets live in `src/assets/` (drop-icon.png, spectrum.jpg, clean.jpg, wave-icon.png).

### Application Entry & Wiring

- `src/main.py` - Entry point, adds `src` parent to path for package imports
- `src/app.py` - `AudioQualApp` creates root window (TkinterDnD.Tk if available, else CTk), wires analyzer + audio player + main window + spectrogram window. Manages LRU spectrogram cache (max 10 entries, OrderedDict). Configures matplotlib `Agg` backend and `dark_background` style once at module load.

### Threading Patterns

Four threading patterns are used:

1. **Batch analysis** (`analyzer.py`): `ThreadPoolExecutor(max_workers=4)`. Progress callback is rate-limited to 100ms intervals in `main_window.py` to prevent event loop saturation.
2. **Spectrogram rendering** (`spectrogram_window.py`): `threading.Thread` + `threading.Event` for cancellation. Incremental `_render_id` ensures only the latest render displays. Resize debounced at 400ms.
3. **Audio playback** (`audio_player.py`): sounddevice callback-based OutputStream runs in audio thread. File loading in background thread.
4. **Waveform rendering** (`waveform_display.py`): Background thread computes peaks, delivers via `schedule_callback_from_thread`.

All background-to-UI communication uses `schedule_callback_from_thread()` from `src/utils/tk_utils.py`, which combines `root.after(0, callback)` with `event_generate("<<ThreadCallback>>")` to wake macOS's dormant event loop.

### macOS Event Loop Workaround

`app.py` runs a 50ms heartbeat (`_heartbeat` → `update_idletasks`) to keep macOS tkinter responsive. Combined with the `event_generate` wake-up in `tk_utils.py`, this prevents UI freezes when callbacks are scheduled from threads.

### Utilities (`src/utils/`)

- **constants.py** - All configurable parameters (see below)
- **tk_utils.py** - `schedule_callback_from_thread()` for thread-safe UI updates
- **file_utils.py** - Audio file discovery (`get_audio_files_from_path` with recursive dir walk), format validation against `SUPPORTED_FORMATS`, duration formatting

## Key Constants (`src/utils/constants.py`)

Constants are grouped by purpose:
- **BITRATE_THRESHOLDS** - Frequency ranges for quality tier classification (low through lossless)
- **FFT/spectral params** - FFT_SIZE=4096, HOP_LENGTH=512, SAMPLE_RATE=44100
- **TRANSITION_*** - Primary detection algorithm params (drop thresholds, band widths, variance criteria, frequency-dependent interpolation, cumulative drop, anti-sibilance)
- **SEGMENT_***/PREDOMINANT_*** - Segment-based percentile analysis params
- **RELATIVE_*** - Relative energy detection params (reference band, variance thresholds)
- **SHELF_*** - Shelf detection (legacy/fallback algorithm)
- **MP3_BITRATE_MAX_CUTOFF_KHZ** - Physical cutoff limits per MP3 bitrate (safety net)
- **STATUS_*** - Analysis status strings (in Spanish)
- **THEME_COLORS, STATUS_COLORS** - Purple/gold/dark gray UI palette
- **FONT_FAMILY ("Inter"), FONT_SIZES, FONT_WEIGHTS** - Typography
- **Window/panel dimensions** - WINDOW_WIDTH, PANEL_WIDTH, MIN_* constraints

## Memory Management

- `AnalysisResult.frequency_analysis` is transient (~4MB per file of spectrogram data). It is passed to the UI once via progress callback, then the `BatchAnalysisState` stores a copy with `frequency_analysis=None`.
- `app.py` maintains an LRU spectrogram cache (max 10 entries) so previously viewed spectrograms don't require re-analysis.

## Important Constraints

- **Tkinter thread safety:** All UI updates from background threads MUST go through `schedule_callback_from_thread()` (in `src/utils/tk_utils.py`). Direct tkinter calls from non-main threads cause crashes.
- **Matplotlib backend:** Must use `'Agg'` (non-interactive), configured once at module load in `app.py`. Interactive backends conflict with tkinter.
- **macOS event loop:** The heartbeat + event_generate pattern is required. Removing either causes UI freezes on macOS when thread callbacks fire.
- **No test suite exists.** There are no automated tests.

## Language

The UI text and status messages are in Spanish (e.g., "Transcode detectado", "Analizando...", "Listo").
