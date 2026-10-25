"""In-memory candle store with contiguity validation.

Per Section 9.2 of agent.md:
Stores historical and live-closed candles. Refuses to compute indicators
if gaps, misalignments, or missing candles are detected.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from app.core.contracts import Candle
from app.core.logging import get_logger

logger = get_logger("candle_store")


def parse_timeframe_seconds(timeframe: str) -> int:
    """Parse timeframe string (e.g. '1m', '5m', '1h', '1d') into integer seconds."""
    timeframe = timeframe.strip().lower()
    if timeframe.endswith("m"):
        return int(timeframe[:-1]) * 60
    elif timeframe.endswith("h"):
        return int(timeframe[:-1]) * 3600
    elif timeframe.endswith("d"):
        return int(timeframe[:-1]) * 86400
    elif timeframe.endswith("s"):
        return int(timeframe[:-1])
    else:
        # Default or fallback
        try:
            return int(timeframe)
        except ValueError:
            return 60


def validate_contiguity(
    candles: list[Candle],
    expected_timeframe: str | None = None,
) -> tuple[bool, str | None]:
    """Validate that candles form a contiguous, chronological, gap-free, aligned sequence.

    Returns:
        (True, None) if contiguous and aligned.
        (False, error_reason) if a gap, misalignment, or ordering violation is detected.
    """
    if not candles or len(candles) < 2:
        return True, None

    tf = expected_timeframe or candles[0].timeframe or "1m"
    step_seconds = parse_timeframe_seconds(tf)
    step_delta = timedelta(seconds=step_seconds)

    for i in range(len(candles)):
        curr = candles[i]

        # 1. Check candle internal duration
        candle_duration = (curr.close_time - curr.open_time).total_seconds()
        if candle_duration != step_seconds:
            return False, (
                f"Candle duration mismatch at index {i}: open={curr.open_time.isoformat()}, "
                f"close={curr.close_time.isoformat()} (duration {candle_duration}s != expected {step_seconds}s)"
            )

        # 2. Check timeframe boundary alignment (seconds must align to step boundary)
        curr_ts = int(curr.open_time.timestamp())
        if curr_ts % step_seconds != 0:
            return False, (
                f"Candle boundary misalignment at index {i}: open_time {curr.open_time.isoformat()} "
                f"not aligned to {step_seconds}s timeframe boundary"
            )

        if i > 0:
            prev = candles[i - 1]

            # 3. Check chronological ordering
            if curr.open_time < prev.open_time:
                return False, (
                    f"Chronological ordering violation at index {i}: "
                    f"current open_time {curr.open_time.isoformat()} < previous {prev.open_time.isoformat()}"
                )

            # 4. Check duplicate timestamp
            if curr.open_time == prev.open_time:
                return False, (
                    f"Duplicate candle timestamp at index {i}: open_time {curr.open_time.isoformat()}"
                )

            # 5. Check gap / continuity between consecutive candles
            if curr.open_time != prev.close_time:
                gap_seconds = (curr.open_time - prev.close_time).total_seconds()
                return False, (
                    f"Contiguity gap of {gap_seconds}s detected between index {i - 1} "
                    f"(close={prev.close_time.isoformat()}) and index {i} (open={curr.open_time.isoformat()})"
                )

    return True, None


class CandleStore:
    """Manages ordered sequence of closed candles for a symbol and timeframe."""

    def __init__(self, symbol: str, timeframe: str = "1m", max_capacity: int = 500) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.max_capacity = max_capacity
        self._candles: list[Candle] = []

    def add_candle(self, candle: Candle) -> None:
        """Append a closed candle, maintaining chronological ordering and capacity."""
        if not self._candles:
            self._candles.append(candle)
            return

        last = self._candles[-1]
        if candle.open_time > last.open_time:
            self._candles.append(candle)
            if len(self._candles) > self.max_capacity:
                self._candles.pop(0)
        elif candle.open_time == last.open_time:
            # Overwrite forming candle with final closed candle
            self._candles[-1] = candle
        else:
            # Out of order insertion: insert at appropriate chronological spot
            # if maintaining sort order
            insert_idx = next((i for i, c in enumerate(self._candles) if c.open_time >= candle.open_time), len(self._candles))
            if insert_idx < len(self._candles) and self._candles[insert_idx].open_time == candle.open_time:
                self._candles[insert_idx] = candle
            else:
                self._candles.insert(insert_idx, candle)
                if len(self._candles) > self.max_capacity:
                    self._candles.pop(0)

    def get_candles(self, count: int | None = None, closed_only: bool = False) -> list[Candle]:
        """Return stored candles, optionally filtering for closed candles only."""
        candles = [c for c in self._candles if c.is_closed] if closed_only else list(self._candles)
        if count is None:
            return candles
        return candles[-count:]

    def get_closed_candles(self, count: int | None = None) -> list[Candle]:
        """Return only closed candles, preventing look-ahead bias into forming candles."""
        return self.get_candles(count=count, closed_only=True)

    @property
    def count(self) -> int:
        return len(self._candles)

    def validate_contiguity(self, candles: list[Candle] | None = None) -> tuple[bool, str | None]:
        """Validate contiguity of current candles or provided slice."""
        target = self._candles if candles is None else candles
        return validate_contiguity(target, expected_timeframe=self.timeframe)

    def is_contiguous(self, candles: list[Candle] | None = None) -> bool:
        """Verify there are no gaps, misalignments, or ordering issues in candle sequence."""
        target = self._candles if candles is None else candles
        valid, _ = validate_contiguity(target, expected_timeframe=self.timeframe)
        return valid
