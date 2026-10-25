"""Pure strategy interface definition.

Per Section 7.1 and 9.3 of agent.md:
Strategies are pure deterministic functions of candle history.
No I/O, no wall-clock time, no external state, strictly NO look-ahead.
"""

from __future__ import annotations

from typing import Protocol

from app.core.contracts import Candle, Signal


class StrategyProtocol(Protocol):
    """Protocol that every QuantPilot strategy must satisfy."""

    @property
    def name(self) -> str:
        """Unique strategy identifier."""
        ...

    @property
    def min_history(self) -> int:
        """Minimum number of closed candles required before evaluate() can be invoked."""
        ...

    def evaluate(self, candles: list[Candle]) -> Signal:
        """Pure evaluation function.

        Args:
            candles: Chronologically ordered closed candles up to candle N.

        Returns:
            Signal contract with direction, strength, proposed stop distance, and reasons.
        """
        ...
