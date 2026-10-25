"""Data freshness and feed latency monitor.

Per Section 9.2 of agent.md:
Tracks time elapsed since latest market tick or candle update.
If data stalls beyond configurable threshold, flips freshness flag to False.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone


class FreshnessTracker:
    """Monitors incoming data timestamps to detect feed stalls."""

    def __init__(self, max_staleness_seconds: float = 5.0) -> None:
        self.max_staleness_seconds = max_staleness_seconds
        self._last_update_monotonic = time.monotonic()
        self._last_market_timestamp: datetime | None = None

    def record_update(self, market_timestamp: datetime | None = None) -> None:
        """Mark that a fresh tick, candle, or order book message was received."""
        self._last_update_monotonic = time.monotonic()
        if market_timestamp:
            self._last_market_timestamp = market_timestamp

    @property
    def staleness_seconds(self) -> float:
        """Seconds elapsed since last received market message."""
        return max(0.0, time.monotonic() - self._last_update_monotonic)

    def is_fresh(self, custom_threshold_seconds: float | None = None) -> bool:
        """Return True if data age is strictly within the allowed threshold."""
        threshold = custom_threshold_seconds or self.max_staleness_seconds
        return self.staleness_seconds <= threshold
