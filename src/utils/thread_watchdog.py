"""Main thread watchdog — logs every click event to detect lost clicks.

Compares Cocoa-level NSEvents with tkinter bind_all events to find
clicks that macOS delivers but tkinter never processes.

Disable by setting ENABLED = False.
"""
import logging
import os
import sys
import threading
import time
import traceback
from contextlib import contextmanager

# ── Configuration ──────────────────────────────────────────────────────────
ENABLED = True
BLOCK_THRESHOLD_MS = 200   # Log main-thread blocks longer than this
PING_INTERVAL_S = 0.1      # Watchdog checks every 100ms
SLOW_OP_THRESHOLD_MS = 50  # Log operations slower than this

# ── Module state ───────────────────────────────────────────────────────────
_logger = None
_watchdog_thread = None
_main_thread_id = None
_last_heartbeat = 0.0
_running = False
_block_detected = False
_block_duration_ms = 0.0

# Click tracking
_click_count = 0
_last_click_time = 0.0

# Cocoa-level click tracking (macOS only)
_ns_click_count = 0
_ns_monitor = None


def init_watchdog(log_path=None):
    """Start the watchdog. Call once from the main thread at startup."""
    global _logger, _watchdog_thread, _main_thread_id, _last_heartbeat, _running

    if not ENABLED or _running:
        return

    _main_thread_id = threading.current_thread().ident
    _last_heartbeat = time.monotonic()
    _running = True

    # Set up file logger
    if log_path is None:
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "audioqual_thread_debug.log")

    _logger = logging.getLogger("audioqual.watchdog")
    _logger.setLevel(logging.DEBUG)
    _logger.propagate = False
    _logger.handlers.clear()
    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("[%(asctime)s.%(msecs)03d] %(message)s",
                                           datefmt="%H:%M:%S"))
    _logger.addHandler(handler)
    _logger.info("[WATCHDOG_START] click tracking active, log=%s", log_path)

    _start_nsevent_monitor()

    _watchdog_thread = threading.Thread(target=_watchdog_loop, daemon=True, name="WatchdogThread")
    _watchdog_thread.start()


def _start_nsevent_monitor():
    """Install a minimal Cocoa-level event counter.

    IMPORTANT: The callback must do NO I/O, NO logging, and NO string
    formatting.  Any Python overhead in the Cocoa event pipeline causes
    GIL contention that makes macOS drop mouse events (~70% loss in
    testing).  We ONLY increment an integer counter here.
    """
    global _ns_monitor
    if sys.platform != 'darwin':
        return
    try:
        from AppKit import NSEvent, NSLeftMouseDownMask

        def _on_ns_mousedown(event):
            global _ns_click_count
            _ns_click_count += 1
            return event

        _ns_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSLeftMouseDownMask, _on_ns_mousedown,
        )
    except Exception:
        pass


def _stop_nsevent_monitor():
    """Remove the Cocoa event monitor."""
    global _ns_monitor
    if _ns_monitor is not None:
        try:
            from AppKit import NSEvent
            NSEvent.removeMonitor_(_ns_monitor)
        except Exception:
            pass
        _ns_monitor = None


def setup_click_tracking(root):
    """Track every click event at the bind_all level.

    Logs every Button-1 event: coordinates, target widget, and widget class.
    Compares with NS_CLICK count to detect lost clicks.
    """
    def _on_click(event):
        global _click_count, _last_click_time
        if not _logger:
            return

        _click_count += 1
        now = time.monotonic()
        gap_ms = (now - _last_click_time) * 1000 if _last_click_time > 0 else 0
        _last_click_time = now

        # Get widget info
        try:
            widget_class = event.widget.winfo_class()
            widget_name = str(event.widget)
            # Shorten long widget paths
            if len(widget_name) > 80:
                widget_name = "..." + widget_name[-77:]
        except Exception:
            widget_class = "?"
            widget_name = "?"

        # Show delta vs Cocoa clicks — if ns > tk, clicks were lost
        ns_delta = _ns_click_count - _click_count
        lost_tag = f" LOST={ns_delta}" if ns_delta > 0 else ""

        _logger.info(
            "[TK_CLICK #%d] gap=%.0fms xy=(%d,%d) widget=%s class=%s%s",
            _click_count, gap_ms, event.x_root, event.y_root,
            widget_name, widget_class, lost_tag,
        )

    def _on_button_release(event):
        if not _logger:
            return
        try:
            widget_class = event.widget.winfo_class()
            widget_name = str(event.widget)
            if len(widget_name) > 80:
                widget_name = "..." + widget_name[-77:]
        except Exception:
            widget_class = "?"
            widget_name = "?"

        _logger.info(
            "[RELEASE] xy=(%d,%d) widget=%s class=%s",
            event.x_root, event.y_root, widget_name, widget_class,
        )

    # Track clicks at ALL level
    root.bind_all("<Button-1>", _on_click, add="+")
    root.bind_all("<ButtonRelease-1>", _on_button_release, add="+")


def stop_watchdog():
    """Stop the watchdog."""
    global _running
    _running = False
    _stop_nsevent_monitor()
    if _logger:
        _logger.info(
            "[WATCHDOG_STOP] tk_clicks=%d ns_clicks=%d lost=%d",
            _click_count, _ns_click_count,
            max(0, _ns_click_count - _click_count),
        )


def heartbeat_tick():
    """Call from the main-thread heartbeat to signal liveness."""
    global _last_heartbeat, _block_detected
    _last_heartbeat = time.monotonic()
    _block_detected = False


def is_block_detected():
    """Return (blocked: bool, duration_ms: float)."""
    return _block_detected, _block_duration_ms


# ── Watchdog background loop ──────────────────────────────────────────────

def _watchdog_loop():
    global _block_detected, _block_duration_ms
    while _running:
        time.sleep(PING_INTERVAL_S)
        if not _running:
            break
        elapsed_ms = (time.monotonic() - _last_heartbeat) * 1000
        if elapsed_ms > BLOCK_THRESHOLD_MS:
            _block_detected = True
            _block_duration_ms = elapsed_ms
            _log_block(elapsed_ms)


def _log_block(duration_ms):
    if not _logger:
        return
    _logger.warning("[BLOCK_DETECTED] duration=%.0fms", duration_ms)
    frames = sys._current_frames()
    if _main_thread_id and _main_thread_id in frames:
        stack = traceback.format_stack(frames[_main_thread_id])
        _logger.warning("[STACK_TRACE] main_thread:\n%s", "".join(stack))


# ── Operation timing ──────────────────────────────────────────────────────

@contextmanager
def timed_op(name):
    """Log operations slower than SLOW_OP_THRESHOLD_MS."""
    if not ENABLED or not _logger:
        yield
        return
    start = time.monotonic()
    yield
    elapsed_ms = (time.monotonic() - start) * 1000
    if elapsed_ms > SLOW_OP_THRESHOLD_MS:
        _logger.info("[SLOW_OP] %s duration=%.0fms", name, elapsed_ms)
