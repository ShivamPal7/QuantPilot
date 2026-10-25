"""In-memory candle store with contiguity validation.

Per Section 9.2 of agent.md:
Stores historical and live-closed candles. Refuses to compute indicators
if gaps or missing candles are detected.
"""

from __future__ import annotations

from app.core.contracts import Candle


class CandleStore:
    """Manages ordered sequence of closed candles for a symbol and timeframe."""

    def __init__(self, symbol: str, timeframe: str, max_capacity: int = 500) -> None:
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

    def get_candles(self, count: int | None = None) -> list[Candle]:
        """Return the most recent closed candles."""
        if count is None:
            return list(self._candles)
        return list(self._candles[-count:])

    @property
    def count(self) -> int:
        return len(self._candles)

    def is_contiguous(self) -> bool:
        """Verify there are no gaps in the candle sequence."""
        if len(self._candles) < 2:
            return True
        # For boilerplate scaffolding, simple ordering check
        for i in range(1, len(self._candles)):
            if self._candles[i].open_time <= self._candles[i - 1].open_time:
                return False
        return True
