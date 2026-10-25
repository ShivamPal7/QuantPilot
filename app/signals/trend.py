"""Strategy A: Volatility-Scaled Trend Following.

ZONE: RED (HUMAN-AUTHORED ONLY)
Owner: Human Lead (See docs/ownership.md)
Reference: Section 10.2 of agent.md

Idea:
Crypto returns exhibit time-series momentum at suitable horizons (Moskowitz et al., 2012).
Direction from moving average crossover or breakout, scaled by volatility (ATR).
Stand-aside when regime is RANGING or CHAOTIC.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.contracts import Candle, Direction, Signal
from app.signals.base import StrategyProtocol


class TrendFollowingStrategy(StrategyProtocol):
    """Strategy A: Pure trend following with ATR-based stop."""

    def __init__(
        self,
        fast_period: int = 20,
        slow_period: int = 50,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        min_history_candles: int = 55,
    ) -> None:
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self._min_history = min_history_candles

    @property
    def name(self) -> str:
        return "trend_following"

    @property
    def min_history(self) -> int:
        return self._min_history

    def evaluate(self, candles: list[Candle]) -> Signal:
        """Evaluate trend signal on closed candle history.

        HUMAN TEAM IMPLEMENTATION:
        1. Compute fast and slow moving averages on candles.
        2. Compute ATR for stop distance.
        3. Return Signal with Direction.LONG, Direction.SHORT, or Direction.FLAT.
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

        # Baseline stub: returns FLAT signal with reason code until human implements crossover
        last_candle = candles[-1]
        return Signal(
            strategy_name=self.name,
            symbol=last_candle.symbol,
            direction=Direction.FLAT,
            strength=0.0,
            proposed_stop_distance=Decimal("100.0"),
            reason_codes=["NO_TREND_CONFIRMED"],
            numeric_values={"fast_ma": float(last_candle.close), "slow_ma": float(last_candle.close)},
        )
