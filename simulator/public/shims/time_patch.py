"""Patch time.sleep and time.monotonic for browser environment.

Strategy: We patch time.sleep to store the requested delay, then the
async wrapper around main_loop actually does the yielding via JS setTimeout.
This avoids needing Pyodide's run_sync/JSPI stack-switching.
"""
import time
from js import self as _worker_self

# Pending sleep duration (set by patched sleep, consumed by async wrapper)
_pending_sleep_ms = 0
_sleep_requested = False


def _patched_monotonic():
    """Use performance.now() for sub-millisecond precision."""
    return _worker_self.performance.now() / 1000.0


def _patched_sleep(seconds):
    """Record the sleep request. The async main loop wrapper will do the actual yield."""
    global _pending_sleep_ms, _sleep_requested
    _pending_sleep_ms = max(1, int(seconds * 1000))
    _sleep_requested = True


# Apply patches
time.monotonic = _patched_monotonic
time.sleep = _patched_sleep
