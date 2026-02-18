#!/usr/bin/env python3
"""
Post-implementation verification for WaxCheck.

Two modes:
    --quick  (~15s) Boot check + analyze 2 files
    --full   (~2-3min) Quick + UI verification + full algorithm tests

Usage:
    python tests/verify_implementation.py          # quick mode (default)
    python tests/verify_implementation.py --quick
    python tests/verify_implementation.py --full
"""
import argparse
import json
import os
import subprocess
import sys
import time

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_JSON = os.path.join(TESTS_DIR, "tests.json")

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _find_mp3_test_files(count=2):
    """Find MP3 test files from tests.json."""
    with open(TESTS_JSON, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    mp3_files = []
    for tc in test_cases:
        filepath = tc["file"]
        if filepath.lower().endswith(".mp3"):
            abs_path = filepath if os.path.isabs(filepath) else os.path.join(PROJECT_ROOT, filepath)
            if os.path.exists(abs_path):
                mp3_files.append((abs_path, tc))
                if len(mp3_files) >= count:
                    break
    return mp3_files


def _phase_boot():
    """Phase 1: Boot check - instantiate app, verify components, destroy."""
    from src.app import AudioQualApp
    from src.utils.tk_utils import cleanup_thread_scheduler

    app = AudioQualApp()
    app.root.update()

    # Verify core components exist
    assert hasattr(app, "main_window"), "main_window missing"
    assert hasattr(app, "analyzer"), "analyzer missing"
    assert hasattr(app, "audio_player"), "audio_player missing"
    assert app.main_window.results_table is not None, "results_table missing"
    assert app.main_window.top_bar.winfo_exists(), "top_bar not rendered"
    assert app.main_window.status_bar.winfo_exists(), "status_bar not rendered"

    cleanup_thread_scheduler()
    app.root.destroy()


def _phase_analysis():
    """Phase 2: Analyze 2 MP3 files and verify results."""
    from src.core.analyzer import AudioAnalyzer

    mp3_files = _find_mp3_test_files(2)
    if len(mp3_files) < 2:
        raise RuntimeError(f"Solo se encontraron {len(mp3_files)} MP3 de test (necesario: 2)")

    analyzer = AudioAnalyzer()
    for abs_path, tc in mp3_files:
        filename = os.path.basename(abs_path)
        result = analyzer.analyze_file(abs_path)

        # Basic sanity checks
        assert result is not None, f"{filename}: resultado None"
        assert result.cutoff_frequency_khz > 0, f"{filename}: cutoff = {result.cutoff_frequency_khz}"
        assert result.status != "Error", f"{filename}: status = Error"
        assert result.detected_quality is not None, f"{filename}: detected_quality None"

        # Check against expected values from tests.json
        expected = tc.get("expected", {})
        min_cutoff = expected.get("cutoff_above_khz", 0)
        if min_cutoff > 0:
            assert result.cutoff_frequency_khz >= min_cutoff, (
                f"{filename}: cutoff {result.cutoff_frequency_khz:.1f} < expected {min_cutoff}"
            )


def run_quick():
    """Run quick verification (~15s): boot + 2 file analysis."""
    print(f"\n{BOLD}=== WaxCheck Verificacion Rapida ==={RESET}\n")
    all_ok = True

    # Phase 1: Boot
    start = time.time()
    try:
        _phase_boot()
        elapsed = time.time() - start
        print(f"  {GREEN}[OK]{RESET} Fase 1: Boot ({elapsed:.1f}s)")
    except Exception as e:
        elapsed = time.time() - start
        print(f"  {RED}[FAIL]{RESET} Fase 1: Boot ({elapsed:.1f}s) - {e}")
        all_ok = False

    # Phase 2: Analysis
    start = time.time()
    try:
        _phase_analysis()
        elapsed = time.time() - start
        print(f"  {GREEN}[OK]{RESET} Fase 2: Analisis de 2 archivos ({elapsed:.1f}s)")
    except Exception as e:
        elapsed = time.time() - start
        print(f"  {RED}[FAIL]{RESET} Fase 2: Analisis de 2 archivos ({elapsed:.1f}s) - {e}")
        all_ok = False

    print()
    if all_ok:
        print(f"  {GREEN}{BOLD}RESULTADO: TODO OK{RESET}")
    else:
        print(f"  {RED}{BOLD}RESULTADO: FALLOS DETECTADOS{RESET}")

    return all_ok


def run_full():
    """Run full verification (~2-3min): quick + UI verification + algorithm tests."""
    print(f"\n{BOLD}=== WaxCheck Verificacion Completa ==={RESET}\n")
    all_ok = True

    # Phase 1: Quick mode (in-process)
    start = time.time()
    try:
        _phase_boot()
        _phase_analysis()
        elapsed = time.time() - start
        print(f"  {GREEN}[OK]{RESET} Fase 1: Boot + Analisis ({elapsed:.1f}s)")
    except Exception as e:
        elapsed = time.time() - start
        print(f"  {RED}[FAIL]{RESET} Fase 1: Boot + Analisis ({elapsed:.1f}s) - {e}")
        all_ok = False

    # Phase 2: UI Verification (subprocess for process isolation)
    start = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(TESTS_DIR, "verify_ui.py")],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT,
        )
        elapsed = time.time() - start
        if proc.returncode == 0:
            print(f"  {GREEN}[OK]{RESET} Fase 2: UI Verification ({elapsed:.1f}s)")
        else:
            print(f"  {RED}[FAIL]{RESET} Fase 2: UI Verification ({elapsed:.1f}s)")
            # Show last few lines of output for debugging
            output = proc.stdout.strip() or proc.stderr.strip()
            if output:
                for line in output.split("\n")[-5:]:
                    print(f"         {DIM}{line}{RESET}")
            all_ok = False
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        print(f"  {RED}[FAIL]{RESET} Fase 2: UI Verification ({elapsed:.1f}s) - TIMEOUT")
        all_ok = False
    except Exception as e:
        elapsed = time.time() - start
        print(f"  {RED}[FAIL]{RESET} Fase 2: UI Verification ({elapsed:.1f}s) - {e}")
        all_ok = False

    # Phase 3: Algorithm Tests (subprocess for process isolation)
    start = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(TESTS_DIR, "run_tests.py"), "--summary",
             "--suite", "detection"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=PROJECT_ROOT,
        )
        elapsed_det = time.time() - start

        start2 = time.time()
        proc2 = subprocess.run(
            [sys.executable, os.path.join(TESTS_DIR, "run_tests.py"), "--summary",
             "--suite", "classification"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=PROJECT_ROOT,
        )
        elapsed_cls = time.time() - start2
        elapsed = elapsed_det + elapsed_cls

        if proc.returncode == 0 and proc2.returncode == 0:
            print(f"  {GREEN}[OK]{RESET} Fase 3: Algorithm Tests ({elapsed:.1f}s)")
        else:
            print(f"  {RED}[FAIL]{RESET} Fase 3: Algorithm Tests ({elapsed:.1f}s)")
            for p, name in [(proc, "detection"), (proc2, "classification")]:
                if p.returncode != 0:
                    output = p.stdout.strip() or p.stderr.strip()
                    if output:
                        for line in output.split("\n")[-5:]:
                            print(f"         {DIM}[{name}] {line}{RESET}")
            all_ok = False
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        print(f"  {RED}[FAIL]{RESET} Fase 3: Algorithm Tests ({elapsed:.1f}s) - TIMEOUT")
        all_ok = False
    except Exception as e:
        elapsed = time.time() - start
        print(f"  {RED}[FAIL]{RESET} Fase 3: Algorithm Tests ({elapsed:.1f}s) - {e}")
        all_ok = False

    print()
    if all_ok:
        print(f"  {GREEN}{BOLD}RESULTADO: TODO OK{RESET}")
    else:
        print(f"  {RED}{BOLD}RESULTADO: FALLOS DETECTADOS{RESET}")

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="WaxCheck post-implementation verification")
    parser.add_argument("--quick", action="store_true", default=True,
                        help="Quick verification: boot + 2 files (default)")
    parser.add_argument("--full", action="store_true",
                        help="Full verification: quick + UI + algorithm tests")
    args = parser.parse_args()

    if args.full:
        ok = run_full()
    else:
        ok = run_quick()

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
