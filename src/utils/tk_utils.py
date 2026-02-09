"""Tkinter utilities for thread-safe callbacks."""


def schedule_callback_from_thread(root, callback, *args):
    """
    Schedule a callback from a background thread to run on the main thread.

    Uses event_generate() to wake up the tkinter event loop on macOS,
    which can become dormant after after() calls from threads.
    """
    root.after(0, lambda: callback(*args))
    # Force event loop to wake up (fixes macOS tkinter bug)
    try:
        root.event_generate("<<ThreadCallback>>", when="tail")
    except Exception:
        pass  # Widget might be destroyed
