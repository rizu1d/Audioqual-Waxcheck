#!/usr/bin/env python3
"""
UI Verification Tests for WaxCheck.

Instantiates the full app (without mainloop) and verifies that all
UI components are present, functional, and error-free.

Usage:
    python tests/verify_ui.py          # run standalone
    python tests/run_tests.py --suite verify   # via test runner

15 checks: VUI_001 to VUI_015
"""
import os
import sys
import time
import threading

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


# ─── Exception Capture ───────────────────────────────────────────────

class ExceptionCapture:
    """Capture unhandled exceptions during UI verification."""

    def __init__(self):
        self.exceptions = []
        self._orig_excepthook = None
        self._orig_threading_excepthook = None

    def install(self):
        self._orig_excepthook = sys.excepthook
        sys.excepthook = self._on_exception
        if hasattr(threading, "excepthook"):
            self._orig_threading_excepthook = threading.excepthook
            threading.excepthook = self._on_threading_exception

    def uninstall(self):
        if self._orig_excepthook:
            sys.excepthook = self._orig_excepthook
        if self._orig_threading_excepthook and hasattr(threading, "excepthook"):
            threading.excepthook = self._orig_threading_excepthook

    def _on_exception(self, exc_type, exc_value, exc_tb):
        self.exceptions.append(f"{exc_type.__name__}: {exc_value}")

    def _on_threading_exception(self, args):
        self.exceptions.append(f"Thread {args.thread}: {args.exc_type.__name__}: {args.exc_value}")


# ─── Helpers ─────────────────────────────────────────────────────────

def _pump_events(root, ms=100):
    """Process tkinter events for `ms` milliseconds."""
    deadline = time.time() + ms / 1000.0
    while time.time() < deadline:
        try:
            root.update()
        except Exception:
            break
        time.sleep(0.01)


def _has_display():
    """Check if a display is available (for headless CI)."""
    if sys.platform == "darwin":
        return True  # macOS always has a display when logged in
    return os.environ.get("DISPLAY") is not None


def _make_result(check_id, description, passed, detail=""):
    """Create a result dict in the standard test format."""
    return {
        "id": check_id,
        "description": description,
        "test_type": "verify",
        "status": "PASS" if passed else "FAIL",
        "detail": detail or ("OK" if passed else "FAIL"),
    }


def _make_skip(check_id, description, reason="No display available"):
    return {
        "id": check_id,
        "description": description,
        "test_type": "verify",
        "status": "SKIP",
        "detail": reason,
    }


# ─── UI Verifier ─────────────────────────────────────────────────────

class UIVerifier:
    """Runs all UI verification checks against a live app instance."""

    CHECKS = [
        ("VUI_001", "App arranca sin errores"),
        ("VUI_002", "Ventana principal renderiza completa"),
        ("VUI_003", "Logo visible"),
        ("VUI_004", "Botones existen y tienen comando"),
        ("VUI_005", "Empty state / drop zone visible"),
        ("VUI_006", "Tabla con 7 columnas"),
        ("VUI_007", "Headers clickables (sorting)"),
        ("VUI_008", "Resize no rompe layout"),
        ("VUI_009", "Settings abre y cierra"),
        ("VUI_010", "Spectrogram sin archivo (no-op)"),
        ("VUI_011", "Metadata sin archivo (no-op)"),
        ("VUI_012", "Player controls existen"),
        ("VUI_013", "Clear button funciona"),
        ("VUI_014", "Status bar completa"),
        ("VUI_015", "Sin excepciones no manejadas"),
    ]

    def __init__(self):
        self.results = []
        self.app = None
        self.exc_capture = ExceptionCapture()

    def run_all(self):
        """Run all checks. Returns list of result dicts."""
        if not _has_display():
            return [_make_skip(cid, desc) for cid, desc in self.CHECKS]

        self.exc_capture.install()

        try:
            # VUI_001: App boots
            self._check_001_app_boot()
            if self.app is None:
                # If boot failed, skip all remaining checks
                for cid, desc in self.CHECKS[1:]:
                    self.results.append(_make_skip(cid, desc, "App no pudo arrancar"))
                return self.results

            # Run remaining checks
            self._check_002_main_window()
            self._check_003_logo()
            self._check_004_buttons()
            self._check_005_empty_state()
            self._check_006_columns()
            self._check_007_sorting()
            self._check_008_resize()
            self._check_009_settings()
            self._check_010_spectrogram_noop()
            self._check_011_metadata_noop()
            self._check_012_player_controls()
            self._check_013_clear()
            self._check_014_status_bar()
            self._check_015_no_exceptions()

        finally:
            self.exc_capture.uninstall()
            self._destroy_app()

        return self.results

    def _destroy_app(self):
        """Safely destroy the app instance."""
        if self.app:
            try:
                from src.utils.tk_utils import cleanup_thread_scheduler
                cleanup_thread_scheduler()
                self.app.root.destroy()
            except Exception:
                pass
            self.app = None

    # ─── Individual checks ───────────────────────────────────────────

    def _check_001_app_boot(self):
        """VUI_001: App instantiates without errors."""
        try:
            from src.app import AudioQualApp
            self.app = AudioQualApp()
            self.app.root.update()
            self.results.append(_make_result(
                "VUI_001", "App arranca sin errores", True,
                "AudioQualApp() + root.update() OK"
            ))
        except Exception as e:
            self.app = None
            self.results.append(_make_result(
                "VUI_001", "App arranca sin errores", False,
                f"Error: {e}"
            ))

    def _check_002_main_window(self):
        """VUI_002: Main window has all major frame sections."""
        try:
            mw = self.app.main_window
            checks = {
                "top_bar": hasattr(mw, "top_bar") and mw.top_bar.winfo_exists(),
                "content_frame": hasattr(mw, "content_frame") and mw.content_frame.winfo_exists(),
                "status_bar": hasattr(mw, "status_bar") and mw.status_bar.winfo_exists(),
            }
            missing = [k for k, v in checks.items() if not v]
            passed = len(missing) == 0
            detail = "Todos presentes" if passed else f"Faltan: {', '.join(missing)}"
            self.results.append(_make_result("VUI_002", "Ventana principal renderiza completa", passed, detail))
        except Exception as e:
            self.results.append(_make_result("VUI_002", "Ventana principal renderiza completa", False, f"Error: {e}"))

    def _check_003_logo(self):
        """VUI_003: Logo/title label is visible with image."""
        try:
            mw = self.app.main_window
            label = mw.title_label
            exists = label.winfo_exists()
            # CTkLabel stores the CTkImage in _image attribute
            has_image = hasattr(label, "_image") and label._image is not None
            # Also accept text fallback "WaxCheck"
            has_text = False
            try:
                text = label.cget("text")
                has_text = text == "WaxCheck"
            except Exception:
                pass
            passed = exists and (has_image or has_text)
            detail = "Logo con imagen" if has_image else ("Fallback texto WaxCheck" if has_text else "Sin logo ni texto")
            self.results.append(_make_result("VUI_003", "Logo visible", passed, detail))
        except Exception as e:
            self.results.append(_make_result("VUI_003", "Logo visible", False, f"Error: {e}"))

    def _check_004_buttons(self):
        """VUI_004: All toolbar buttons exist and have commands."""
        try:
            mw = self.app.main_window
            buttons = {
                "add_files_btn": mw.add_files_btn,
                "clear_btn": mw.clear_btn,
                "spectrogram_btn": mw.spectrogram_btn,
                "metadata_btn": mw.metadata_btn,
                "settings_btn": mw.settings_btn,
                "watcher_btn": mw.watcher_btn,
            }
            missing = []
            no_command = []
            for name, btn in buttons.items():
                if not btn.winfo_exists():
                    missing.append(name)
                    continue
                # CTkButton stores command in _command attribute
                cmd = getattr(btn, "_command", None)
                if not callable(cmd):
                    no_command.append(name)

            passed = len(missing) == 0 and len(no_command) == 0
            if passed:
                detail = f"6/6 botones con comando"
            else:
                parts = []
                if missing:
                    parts.append(f"faltan: {', '.join(missing)}")
                if no_command:
                    parts.append(f"sin comando: {', '.join(no_command)}")
                detail = "; ".join(parts)
            self.results.append(_make_result("VUI_004", "Botones existen y tienen comando", passed, detail))
        except Exception as e:
            self.results.append(_make_result("VUI_004", "Botones existen y tienen comando", False, f"Error: {e}"))

    def _check_005_empty_state(self):
        """VUI_005: Empty state overlay is visible when no files loaded."""
        try:
            mw = self.app.main_window
            es = mw.empty_state
            exists = es.winfo_exists()
            visible = es.winfo_viewable() if exists else False
            passed = exists and visible
            detail = "Visible" if passed else ("Existe pero no visible" if exists else "No existe")
            self.results.append(_make_result("VUI_005", "Empty state / drop zone visible", passed, detail))
        except Exception as e:
            self.results.append(_make_result("VUI_005", "Empty state / drop zone visible", False, f"Error: {e}"))

    def _check_006_columns(self):
        """VUI_006: Results table has exactly 7 columns with expected IDs."""
        try:
            rt = self.app.main_window.results_table
            cols = rt.COLUMNS
            expected_ids = ["filename", "format", "duration", "declared_bitrate",
                            "cutoff_frequency", "detected_quality", "status"]
            actual_ids = [c[0] for c in cols]
            count_ok = len(cols) == 7
            ids_ok = actual_ids == expected_ids
            passed = count_ok and ids_ok
            if passed:
                detail = "7 columnas con IDs correctos"
            else:
                detail = f"count={len(cols)}, ids={actual_ids}"
            self.results.append(_make_result("VUI_006", "Tabla con 7 columnas", passed, detail))
        except Exception as e:
            self.results.append(_make_result("VUI_006", "Tabla con 7 columnas", False, f"Error: {e}"))

    def _check_007_sorting(self):
        """VUI_007: Clicking a header sets sort column."""
        try:
            rt = self.app.main_window.results_table
            # Initially no sort
            rt._on_header_click("filename")
            passed = rt._sort_column == "filename"
            # Click again to toggle direction
            asc_before = rt._sort_ascending
            rt._on_header_click("filename")
            toggled = rt._sort_ascending != asc_before
            passed = passed and toggled
            # Reset sort state
            rt._sort_column = None
            rt._sort_ascending = True
            detail = "Sort y toggle funcionan" if passed else "Sort no funciono correctamente"
            self.results.append(_make_result("VUI_007", "Headers clickables (sorting)", passed, detail))
        except Exception as e:
            self.results.append(_make_result("VUI_007", "Headers clickables (sorting)", False, f"Error: {e}"))

    def _check_008_resize(self):
        """VUI_008: Resizing window doesn't cause errors."""
        try:
            root = self.app.root
            # Try two different sizes
            root.geometry("1000x700")
            _pump_events(root, 100)
            root.geometry("900x800")
            _pump_events(root, 100)
            # Restore original
            root.geometry("1100x750")
            _pump_events(root, 50)
            self.results.append(_make_result("VUI_008", "Resize no rompe layout", True, "3 resizes sin error"))
        except Exception as e:
            self.results.append(_make_result("VUI_008", "Resize no rompe layout", False, f"Error: {e}"))

    def _check_009_settings(self):
        """VUI_009: Settings window opens and closes."""
        try:
            mw = self.app.main_window
            root = self.app.root

            # Open settings
            mw._on_open_settings()
            _pump_events(root, 200)

            # Find CTkToplevel in children
            import customtkinter as ctk
            settings_win = None
            for child in root.winfo_children():
                if isinstance(child, ctk.CTkToplevel):
                    settings_win = child
                    break

            if settings_win is None:
                self.results.append(_make_result(
                    "VUI_009", "Settings abre y cierra", False,
                    "CTkToplevel no encontrada"
                ))
                return

            # Release grab and destroy
            try:
                settings_win.grab_release()
            except Exception:
                pass
            settings_win.destroy()
            _pump_events(root, 50)

            self.results.append(_make_result("VUI_009", "Settings abre y cierra", True, "Abrio y cerro OK"))
        except Exception as e:
            self.results.append(_make_result("VUI_009", "Settings abre y cierra", False, f"Error: {e}"))

    def _check_010_spectrogram_noop(self):
        """VUI_010: Spectrogram button without file selected is a no-op."""
        try:
            # With no file selected, this should return gracefully
            self.app._show_spectrogram_window()
            self.results.append(_make_result(
                "VUI_010", "Spectrogram sin archivo (no-op)", True,
                "Retorno sin error"
            ))
        except Exception as e:
            self.results.append(_make_result(
                "VUI_010", "Spectrogram sin archivo (no-op)", False,
                f"Error: {e}"
            ))

    def _check_011_metadata_noop(self):
        """VUI_011: Metadata button without file selected is a no-op."""
        try:
            mw = self.app.main_window
            # No file selected, should return gracefully
            mw._on_edit_metadata()
            self.results.append(_make_result(
                "VUI_011", "Metadata sin archivo (no-op)", True,
                "Retorno sin error"
            ))
        except Exception as e:
            self.results.append(_make_result(
                "VUI_011", "Metadata sin archivo (no-op)", False,
                f"Error: {e}"
            ))

    def _check_012_player_controls(self):
        """VUI_012: Player controls widget exists."""
        try:
            mw = self.app.main_window
            pc = mw._player_controls
            exists = pc is not None and pc.winfo_exists()
            self.results.append(_make_result(
                "VUI_012", "Player controls existen", exists,
                "PlayerControls presente" if exists else "PlayerControls ausente"
            ))
        except Exception as e:
            self.results.append(_make_result("VUI_012", "Player controls existen", False, f"Error: {e}"))

    def _check_013_clear(self):
        """VUI_013: Clear button invocation doesn't crash."""
        try:
            mw = self.app.main_window
            mw._on_clear()
            _pump_events(self.app.root, 50)
            self.results.append(_make_result("VUI_013", "Clear button funciona", True, "Clear sin error"))
        except Exception as e:
            self.results.append(_make_result("VUI_013", "Clear button funciona", False, f"Error: {e}"))

    def _check_014_status_bar(self):
        """VUI_014: Status bar has status_label and count_label with text."""
        try:
            mw = self.app.main_window
            sl = mw.status_label
            cl = mw.count_label
            sl_ok = sl.winfo_exists() and sl.cget("text")
            cl_ok = cl.winfo_exists() and cl.cget("text")
            passed = sl_ok and cl_ok
            detail = f"status='{sl.cget('text')}', count='{cl.cget('text')}'" if passed else "Labels incompletos"
            self.results.append(_make_result("VUI_014", "Status bar completa", passed, detail))
        except Exception as e:
            self.results.append(_make_result("VUI_014", "Status bar completa", False, f"Error: {e}"))

    def _check_015_no_exceptions(self):
        """VUI_015: No unhandled exceptions during all checks."""
        excs = self.exc_capture.exceptions
        passed = len(excs) == 0
        detail = "Sin excepciones" if passed else f"{len(excs)} excepciones: {'; '.join(excs[:3])}"
        self.results.append(_make_result("VUI_015", "Sin excepciones no manejadas", passed, detail))


# ─── Integration with run_tests.py ──────────────────────────────────

def run_as_suite():
    """Run UI verification as a suite for run_tests.py integration.

    Resets tk_utils singleton state to allow fresh app instantiation
    (necessary when test_ui.py already created and destroyed an app).
    """
    import src.utils.tk_utils as tk_utils
    tk_utils._initialized = False
    tk_utils._shutting_down = False

    verifier = UIVerifier()
    return verifier.run_all()


# ─── Standalone execution ────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="WaxCheck UI Verification")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON (for integration with run_tests.py)")
    args = parser.parse_args()

    verifier = UIVerifier()
    results = verifier.run_all()

    if args.json:
        import json
        print(json.dumps(results))
        failed = sum(1 for r in results if r["status"] == "FAIL")
        sys.exit(1 if failed > 0 else 0)

    print(f"\n{BOLD}--- UI Verification ---{RESET}")

    passed = 0
    failed = 0
    skipped = 0
    for r in results:
        status = r["status"]
        if status == "PASS":
            icon = f"{GREEN}OK{RESET}"
            passed += 1
        elif status == "FAIL":
            icon = f"{RED}FAIL{RESET}"
            failed += 1
        else:
            icon = f"{YELLOW}SKIP{RESET}"
            skipped += 1
        print(f"  [{icon}]  {r['id']}: {r['description']}", end="")
        if status != "PASS":
            print(f" - {DIM}{r['detail']}{RESET}")
        else:
            print()

    print(f"\n{BOLD}Resumen: {passed}/{len(results)} OK", end="")
    if failed > 0:
        print(f", {RED}{failed} FAIL{RESET}", end="")
    if skipped > 0:
        print(f", {YELLOW}{skipped} SKIP{RESET}", end="")
    print(RESET)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
