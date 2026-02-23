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

# Run tests (full suite, ~42s — analyzes 32 audio files)
python tests/run_tests.py

# Run only UI tests (fast, ~2s, no audio analysis)
python tests/run_tests.py --suite ui

# Run only detection or classification tests
python tests/run_tests.py --suite detection
python tests/run_tests.py --suite classification

# Summary only (no per-test output)
python tests/run_tests.py --summary

# Save results to tests/results_YYYYMMDD_HHMMSS.json
python tests/run_tests.py --save

# Build standalone app
pyinstaller build/audioqual_macos.spec   # macOS
pyinstaller build/audioqual_windows.spec  # Windows
```

No linter is configured.

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
  - Band must have musical content (variance >= frequency-dependent threshold: 0.30 at 14kHz, interpolating down to 0.15 at 20kHz — this accommodates acapellas with lower high-frequency variance)
  - Detection triggers on: (a) energy drop >= 8dB, (b) variance transition (absolute: post-band variance below its own frequency-dependent musical threshold, or relative >= 35%), (c) cumulative drop across 3 consecutive bands >= 12dB, (d) sliding-window variance decay (variance drops >= 50% across 3 consecutive bands, ending below 0.25, strictly monotonically decreasing with 0.01 tolerance — catches gradual rolloffs where no single step exceeds thresholds)
  - Anti-sibilance: recovery check requires 2+ consecutive bands with both energy AND variance >= 0.3 (isolated sibilance spikes don't count)
- **Phase 2** (fallback) - Best-score method for lossless/edge cases

**Secondary method: Segment-based percentile analysis**

Divides audio into 50 temporal segments, finds cutoff per segment, uses 90th percentile as the predominant cutoff (ignores top 10% peaks/outliers).

**Decision logic:**
- Transition confidence >= 0.7 → use it, UNLESS noise-plateau pattern detected (segments much lower with outliers and gap > 2kHz → trust segments instead, as transition may be seeing noise-to-silence rather than music-to-noise). The noise-plateau guard verifies the gap bands actually lack musical content before overriding transition — if bands between the segment and transition cutoffs have musical variance (frequency-dependent threshold), the transition is trusted (prevents false positives on older recordings with genuine high-frequency content like LaTour).
- Both methods agree within 2kHz → average, boost confidence
- Transition is lower with confidence >= 0.5 → prefer it (conservative). If gap >= 1kHz, apply transcode-signature confidence boost (up to +0.15)
- Otherwise → segment method

**Verification:** Cutoffs > 21kHz are verified by comparing variance ratios between 20-22kHz and 15-20kHz bands.

### GUI Layer (`src/gui/`)

Built with customtkinter and tkinterdnd2 for drag-and-drop:
- **file_drop_zone.py** - Reusable drag-and-drop zone with file/folder selection dialog. Parses platform-specific drop formats (Windows braces vs Unix spaces). Uses `file_utils.get_audio_files_from_path` for recursive directory scanning.
- **main_window.py** - Main layout with empty state overlay, results table, player controls, progress bar, status bar, and toolbar (add files, clear, spectrogram, metadata editor, settings). Drop targets on both content frame and results table scroll_frame.
- **spectrogram_window.py** - Separate `CTkToplevel` window; background thread renders matplotlib figure to PIL Image via Agg backend, then progressive left-to-right reveal animation (12 steps, 25ms each). Displays reliability label ("Fiabilidad: Alta/Media/Baja") with color instead of raw confidence percentage.
- **results_table.py** - Analysis results with status colors (ttk.Treeview). Supports draggable column resize grips with 30ms throttling and minimum column widths. `update_filepath()` re-keys results when files are renamed.
- **metadata_editor.py** - iTunes-style metadata editor (`CTkToplevel`). Edits ID3 tags (MP3/WAV/AIFF) and Vorbis comments (FLAC). Fields: title, artist, album, genre (combobox with 300+ genre autocomplete), year, track/disc numbers, compilation, BPM, comments. Optional file renaming on save ("Artist - Title.ext") controlled by `AppSettings.rename_on_save`.
- **settings_window.py** - Modal configuration panel. Settings: `rename_on_save` (rename file on disk when saving metadata), `watcher_folder` and `watcher_auto_start` (FolderWatcher configuration).
- **audio_player.py** - Playback engine using sounddevice callback-based OutputStream. Dual-loader: uses `soundfile` for WAV/FLAC/OGG/AIFF (low GIL contention, faster), falls back to `librosa` for MP3/M4A/AAC/WMA.
- **player_controls.py** - Transport controls (play/pause, seek, volume, prev/next)
- **waveform_display.py** - DJ-style amplitude bar visualization with played/unplayed coloring and gold playhead. Background thread computes peaks, main thread updates display. Playhead updates skip if movement < 2px to reduce redraws.
- **quality_popup.py** - Floating popup explaining quality verdicts. Shows quality badge, cutoff frequency, declared vs detected bitrate comparison, and contextual explanation text. Animated entrance/exit (fade + slide). Positioned relative to the quality badge that triggered it.
- **icons.py** - Programmatic icon generation using PIL.ImageDraw. Draws icons at 2x resolution on transparent RGBA canvases, wrapped in CTkImage for HiDPI. Module-level cache prevents regeneration.

Icon assets live in `src/assets/` as SVGs (V2/V3 versions) with PNG fallbacks. Fonts: Outfit (UI) and Space Mono (numeric data) in `src/assets/fonts/`.

### Application Entry & Wiring

- `src/main.py` - Entry point, adds `src` parent to path for package imports
- `src/app.py` - `AudioQualApp` creates root window (TkinterDnD.Tk if available, else CTk), wires analyzer + audio player + main window + spectrogram window. Manages LRU spectrogram cache (max 10 entries, OrderedDict). Configures matplotlib `Agg` backend and `dark_background` style once at module load. Sets up global keyboard shortcuts via `_setup_keyboard_bindings()` (platform-aware: Cmd on macOS, Ctrl on Windows/Linux).

### Threading Patterns

Four threading patterns are used:

1. **Batch analysis** (`analyzer.py`): `ThreadPoolExecutor(max_workers=4)`. Progress callback is rate-limited to 100ms intervals in `main_window.py` to prevent event loop saturation.
2. **Spectrogram rendering** (`spectrogram_window.py`): `threading.Thread` + `threading.Event` for cancellation. Incremental `_render_id` ensures only the latest render displays. Resize debounced at 400ms.
3. **Audio playback** (`audio_player.py`): sounddevice callback-based OutputStream runs in audio thread. File loading in background thread.
4. **Waveform rendering** (`waveform_display.py`): Background thread computes peaks, delivers via `schedule_callback_from_thread`.

All background-to-UI communication uses `schedule_callback_from_thread()` from `src/utils/tk_utils.py`. On macOS, it uses an OS-level pipe + `createfilehandler` (backed by kqueue) with a keep-alive thread for reliable event loop waking. On other platforms, it falls back to `event_generate("<<ThreadCallback>>")`.

### macOS Event Loop Workaround

`app.py` runs a 200ms heartbeat (`_heartbeat` → `update_idletasks`) to keep macOS tkinter responsive. Combined with the pipe + createfilehandler wake-up in `tk_utils.py`, this prevents UI freezes when callbacks are scheduled from threads.

### Keyboard Shortcuts (`app.py → _setup_keyboard_bindings`)

Platform-aware (Cmd on macOS, Ctrl on Windows/Linux):
- **Space** - Play/pause toggle
- **Return** - Load and play selected file
- **Up/Down** - Navigate file list
- **Left/Right** - Seek ±5 seconds
- **Delete/Backspace** - Remove selected file
- **Cmd/Ctrl-O** - Open file dialog
- **Cmd/Ctrl-E / Cmd/Ctrl-I** - Open metadata editor
- **Escape** - Stop playback

### Utilities (`src/utils/`)

- **constants.py** - All configurable parameters (see below)
- **tk_utils.py** - `schedule_callback_from_thread()` for thread-safe UI updates
- **file_utils.py** - Audio file discovery (`get_audio_files_from_path` with recursive dir walk), format validation against `SUPPORTED_FORMATS`, duration formatting
- **settings.py** - Singleton `AppSettings` with JSON persistence at `~/.audioqual/settings.json`. Auto-saves on property changes.

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
- **RELIABILITY_COLORS** - Green/gold/red for Alta/Media/Baja fiabilidad display in spectrogram panel
- **THEME_COLORS, STATUS_COLORS** - Purple/gold/dark gray UI palette
- **FONT_FAMILY ("Outfit"), FONT_FAMILY_MONO ("Space Mono"), FONT_SIZES, FONT_WEIGHTS** - Typography
- **Window/panel dimensions** - WINDOW_WIDTH, PANEL_WIDTH, MIN_* constraints

## Memory Management

- `AnalysisResult.frequency_analysis` is transient (~4MB per file of spectrogram data). It is passed to the UI once via progress callback, then the `BatchAnalysisState` stores a copy with `frequency_analysis=None`.
- `app.py` maintains an LRU spectrogram cache (max 10 entries) so previously viewed spectrograms don't require re-analysis.

## Important Constraints

- **Tkinter thread safety:** All UI updates from background threads MUST go through `schedule_callback_from_thread()` (in `src/utils/tk_utils.py`). Direct tkinter calls from non-main threads cause crashes.
- **Matplotlib backend:** Must use `'Agg'` (non-interactive), configured once at module load in `app.py`. Interactive backends conflict with tkinter.
- **macOS event loop:** The heartbeat + pipe/createfilehandler pattern is required. Removing either causes UI freezes on macOS when thread callbacks fire.
- **Test suite:** Run `python tests/run_tests.py` before and after algorithm changes. Tests in `tests/tests.json` are append-only (never edit or delete existing entries). The test suite analyzes 32 real audio files and checks cutoff detection + classification against known baselines. Exit code 0 = all pass, 1 = regressions detected. Each test entry has: `id`, `file` (path to audio), `description`, `expected` (with `status`, `detected_quality_in`, `cutoff_above_khz`), `known_bug`, `notes`, and `_baseline` (recorded actual values for reference).

## Diagnostic Scripts (`scripts/`)

- **diagnose_latour.py** - Band-by-band analysis for LaTour and YouTube rips (calibrating the noise-plateau guard)
- **diagnose_detection.py** - Band-by-band analysis for Silicone Soul and Agoria, highlighting the "trap zone" between frequency-dependent musical threshold and fixed absolute variance drop threshold

Usage: `python scripts/diagnose_latour.py` or `python scripts/diagnose_detection.py`

## Language

The UI text and status messages are in Spanish (e.g., "Transcode detectado", "Analizando...", "Listo").

## Knowledge Base (`knowledge/`)

- **ALGORITMO.txt** - Plain-Spanish explanation of the detection algorithm (useful for understanding the "why" behind `frequency_detector.py` decisions)
- **VERIFICACION.txt** - Full architecture of the verification/testing system (layers, edge cases, dependency diagram)

## Post-Implementation Verification

After every code change, run the appropriate verification before reporting the task as complete. See `knowledge/VERIFICACION.txt` for the full verification system architecture. Quick reference:

| Change type | Command | Time |
|------------|---------|------|
| UI changes | `bash tests/quick_check.sh` | ~30s |
| Algorithm/constants | `bash tests/full_check.sh` | ~2-3min |
| Simple bugfix (1-2 files) | `python tests/verify_implementation.py --quick` | ~15s |
| Large refactor (3+ files) | `bash tests/full_check.sh` | ~2-3min |
| Docs/configs only | `python tests/verify_implementation.py --quick` | ~15s |

**Rule: never report a task as completed without running verification.**
