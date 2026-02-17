"""Tkinter utilities for thread-safe callbacks.

On macOS, Tcl timers can stop firing when the Cocoa run loop goes dormant.
This module uses an OS-level pipe + createfilehandler (backed by kqueue on
macOS) to reliably wake the event loop.  A keep-alive thread writes to the
pipe every ~50 ms so the run loop never stays dormant long enough for the
user to perceive a freeze.
"""
import os
import sys
import queue
import threading
import time

_callback_queue = queue.Queue()
_pipe_write_fd = None
_pipe_read_fd = None
_tk_root = None
_initialized = False
_shutting_down = False
_keepalive_thread = None


def init_thread_scheduler(root):
    """Initialize thread-safe scheduler. Call once from main thread."""
    global _pipe_write_fd, _pipe_read_fd, _tk_root, _initialized, _keepalive_thread
    if _initialized:
        return
    _initialized = True
    _tk_root = root

    if sys.platform == 'darwin':
        try:
            import fcntl
            import tkinter
            _pipe_read_fd, _pipe_write_fd = os.pipe()
            flags = fcntl.fcntl(_pipe_read_fd, fcntl.F_GETFL)
            fcntl.fcntl(_pipe_read_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            def _on_pipe_readable(fd, mask):
                try:
                    os.read(fd, 4096)
                except OSError:
                    pass
                process_pending_callbacks()

            root.tk.createfilehandler(
                _pipe_read_fd, tkinter.READABLE, _on_pipe_readable
            )

            # Keep-alive: prevent Cocoa run loop dormancy by sending
            # periodic I/O that kqueue will always deliver.
            _keepalive_thread = threading.Thread(
                target=_keepalive_loop, daemon=True, name="TkKeepAlive"
            )
            _keepalive_thread.start()
        except (AttributeError, OSError, Exception):
            # createfilehandler not available — fallback to heartbeat-only
            for fd in (_pipe_read_fd, _pipe_write_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            _pipe_read_fd = _pipe_write_fd = None


def _keepalive_loop():
    """Write a byte to the pipe every ~200 ms to keep the Cocoa run loop alive.

    200ms balances responsiveness (thread callbacks delivered within 200ms
    worst case) against not flooding the event loop with file-handler
    invocations that could interfere with mouse event processing.
    """
    while not _shutting_down:
        time.sleep(0.2)
        if _shutting_down:
            break
        fd = _pipe_write_fd
        if fd is not None:
            try:
                os.write(fd, b'\x00')
            except OSError:
                break


def cleanup_thread_scheduler():
    """Deregister file handler and close pipe FDs."""
    global _pipe_write_fd, _pipe_read_fd, _tk_root, _initialized, _shutting_down
    _shutting_down = True

    if _pipe_read_fd is not None and _tk_root is not None:
        try:
            _tk_root.tk.deletefilehandler(_pipe_read_fd)
        except Exception:
            pass

    for fd in (_pipe_read_fd, _pipe_write_fd):
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass

    _pipe_read_fd = _pipe_write_fd = None
    _tk_root = None
    _initialized = False


def process_pending_callbacks():
    """Drain and execute all queued callbacks. Main thread only."""
    if _shutting_down:
        return
    while True:
        try:
            callback, args = _callback_queue.get_nowait()
            try:
                callback(*args)
            except Exception:
                pass
        except queue.Empty:
            break


def schedule_callback_from_thread(root, callback, *args):
    """Schedule callback from any thread to main thread. Thread-safe."""
    _callback_queue.put((callback, args))

    if _pipe_write_fd is not None:
        # macOS: OS-level wake via pipe (no tkinter calls from bg threads)
        try:
            os.write(_pipe_write_fd, b'\x00')
        except OSError:
            pass
    else:
        # Windows/Linux: event_generate works reliably from bg threads
        try:
            root.event_generate("<<ThreadCallback>>", when="tail")
        except Exception:
            pass
