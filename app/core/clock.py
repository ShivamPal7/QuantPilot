"""Clock abstraction and exchange time drift verification.

Per Section 6.2 of agent.md, signatures older than 5 seconds fail.
Drift between system time and Delta Exchange server time must be detected.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    """Protocol for abstracting time measurement."""

    def now_utc(self) -> datetime:
        """Return current timezone-aware UTC datetime."""
        ...

    def time_seconds(self) -> float:
        """Return unix epoch timestamp in seconds."""
        ...


class SystemClock:
    """Production wall-clock using OS system time."""

    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def time_seconds(self) -> float:
        return time.time()


class SimulatedClock:
    """Simulated clock for backtesting, replays, and unit tests."""

    def __init__(self, start_time: datetime | None = None) -> None:
        self._current_time = start_time or datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def now_utc(self) -> datetime:
        return self._current_time

    def time_seconds(self) -> float:
        return self._current_time.timestamp()

    def advance(self, seconds: float) -> None:
        """Advance simulated clock by given seconds."""
        self._current_time = datetime.fromtimestamp(
            self._current_time.timestamp() + seconds, tz=timezone.utc
        )

    def set_time(self, new_time: datetime) -> None:
        """Explicitly set current simulated time."""
        self._current_time = new_time


def check_clock_drift(local_time_s: float, exchange_time_s: float, max_drift_s: float = 2.0) -> tuple[bool, float]:
    """Verify that local clock drift is within acceptable tolerance.

    Returns:
        (is_valid, drift_seconds)
    """
    drift = abs(local_time_s - exchange_time_s)
    return (drift <= max_drift_s, drift)
