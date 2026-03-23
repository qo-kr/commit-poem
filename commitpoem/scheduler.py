from __future__ import annotations

import asyncio
import logging
import re
import threading
from collections.abc import Callable
from typing import Any

__all__ = ["run_scheduler", "run_once"]

logger = logging.getLogger(__name__)

# Regex to parse duration strings like '30s', '5m', '1h', '2h30m', '1h5m30s'
_DURATION_RE = re.compile(
    r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$"
)


def _parse_duration(expr: str) -> float:
    """Convert a duration string (e.g. '30s', '5m', '1h', '2h30m') to positive seconds.

    Args:
        expr: A duration string with optional hours (h), minutes (m), seconds (s) components.

    Returns:
        A positive float representing the number of seconds.

    Raises:
        ValueError: When the expression is empty, unrecognised, results in zero, or is otherwise invalid.
    """
    stripped = expr.strip()
    if not stripped:
        raise ValueError(f"Invalid interval expression: {expr!r}. Expected a duration like '30s', '5m', '1h', '2h30m'.")

    match = _DURATION_RE.match(stripped)
    if match is None or not any(match.groups()):
        raise ValueError(
            f"Unrecognised interval format: {expr!r}. "
            "Expected a duration like '30s', '5m', '1h', '2h30m'."
        )

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    total = float(hours * 3600 + minutes * 60 + seconds)

    if total <= 0:
        raise ValueError(
            f"Interval must be positive, got {total!r} seconds from expression {expr!r}."
        )

    return total


def run_once(pipeline: Callable[[], Any]) -> None:
    """Invoke pipeline exactly once, catching and logging any Exception.

    Args:
        pipeline: A zero-argument callable to invoke.

    Returns:
        None. Any Exception raised by pipeline is logged at ERROR level and suppressed.
        BaseException subclasses (KeyboardInterrupt, SystemExit) are not caught.
    """
    try:
        pipeline()
    except Exception:
        logger.error("Pipeline raised an exception in run_once", exc_info=True)


def run_scheduler(
    schedule_expr: str,
    pipeline: Callable[[], Any],
    *,
    stop_event: threading.Event | None = None,
) -> None:
    """Repeatedly invoke pipeline on the parsed interval until stop_event is set.

    Runs the pipeline in a loop: check stop → run pipeline → check stop → wait interval.
    Any Exception raised by pipeline is caught, logged at ERROR level, and the loop continues.
    BaseException subclasses (KeyboardInterrupt, SystemExit) propagate unmodified.
    Returns cleanly when stop_event.is_set() becomes True.

    Args:
        schedule_expr: A duration string (e.g. '30s', '5m', '1h', '2h30m') defining the interval.
        pipeline: A zero-argument callable to invoke on each tick. Must not be a coroutine function.
        stop_event: Optional threading.Event; when set, the scheduler exits cleanly after the
                    current pipeline call (or immediately if set before the loop starts).

    Raises:
        ValueError: When schedule_expr cannot be parsed as a valid positive duration.
        TypeError: When pipeline is not a callable or is a coroutine function.
    """
    if not callable(pipeline):
        raise TypeError(f"pipeline must be a callable, got {type(pipeline)!r}")
    if asyncio.iscoroutinefunction(pipeline):
        raise TypeError(
            f"pipeline must not be a coroutine function; wrap it in asyncio.run() if needed. Got {pipeline!r}"
        )

    interval = _parse_duration(schedule_expr)

    # Use a sentinel Event when none is provided so the loop logic is uniform.
    if stop_event is None:
        stop_event = threading.Event()

    while True:
        if stop_event.is_set():
            return

        try:
            pipeline()
        except Exception:
            logger.error("Pipeline raised an exception; continuing to next scheduled run", exc_info=True)

        if stop_event.is_set():
            return

        # Wait for the interval, but wake early if stop_event is set.
        stop_event.wait(timeout=interval)
