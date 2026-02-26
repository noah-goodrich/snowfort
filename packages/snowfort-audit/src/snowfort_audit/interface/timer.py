"""Timer for long-lived CLI operations: human-readable start/end/duration on stderr."""

import sys
import time
from contextlib import contextmanager
from datetime import datetime


def _format_ts() -> str:
    """Human-readable local timestamp (e.g. Mar 3, 2026 7:47 PM)."""
    return datetime.now().strftime("%b %d, %Y %I:%M %p")


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f}s"
    mins, secs = divmod(seconds, 60)
    if mins < 60:
        return f"{int(mins)}:{secs:06.3f}"
    hours, mins = divmod(mins, 60)
    return f"{int(hours)}:{int(mins):02d}:{secs:06.3f}"


@contextmanager
def timed_operation(operation_name: str):
    """Context manager that prints Started at / Ended at / Duration to stderr."""
    started = _format_ts()
    start_wall = time.perf_counter()
    print(f"[{operation_name}] Started at:  {started}", file=sys.stderr)
    try:
        yield
    finally:
        ended = _format_ts()
        duration = time.perf_counter() - start_wall
        print(f"[{operation_name}] Ended at:    {ended}", file=sys.stderr)
        print(f"[{operation_name}] Duration:    {_format_duration(duration)}", file=sys.stderr)
