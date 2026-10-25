"""Strategy B: Short-Horizon Mean Reversion.

ZONE: RED (HUMAN-AUTHORED ONLY)
Owner: Human Lead / Team Member B (See docs/ownership.md)
Reference: Section 10.3 of agent.md

Idea:
Fade statistically large deviations from short-term mean (z-score),
only when series is confirmed mean-reverting.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.contracts import Candle, Direction, Signal
from app.signals.base import StrategyProtocol


class MeanReversionStrategy(StrategyProtocol):
    """Strategy B: Pure mean reversion with stationarity and z-score checks."""

    def __init__(
        self,
        lookback_period: int = 30,
        z_score_threshold: float = 2.0,
        atr_period: int = 14,
        atr_multiplier: float = 1.5,
        min_history_candles: int = 35,
    ) -> None:
        self.lookback_period = lookback_period
        self.z_score_threshold = z_score_threshold
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self._min_history = min_history_candles

    @property
    def name(self) -> str:
        return "mean_reversion"

    @property
    def min_history(self) -> int:
        return self._min_history

    def evaluate(self, candles: list[Candle]) -> Signal:
        """Evaluate mean reversion signal on closed candle history.

        HUMAN TEAM IMPLEMENTATION:
        1. Calculate mean and standard deviation over lookback.
        2. Compute z-score of latest close.
        3. Return Signal if z-score exceeds threshold.
        """
        if len(candles) < self._min_history:
            return Signal(
                strategy_name=self.name,
                symbol=candles[-1].symbol if candles else "BTCUSD",
                direction=Direction.FLAT,
                strength=0.0,
                proposed_stop_distance=Decimal("0"),
                reason_codes=["INSUFFICIENT_HISTORY"],
            )

        last_candle = candles[-1]
        return Signal(
            strategy_name=self.name,
            symbol=last_candle.symbol,
            direction=Direction.FLAT,
            strength=0.0,
            proposed_stop_distance=Decimal("80.0"),
            reason_codes=["WITHIN_NORMAL_BAND"],
            numeric_values={"z_score": 0.0},
        )
