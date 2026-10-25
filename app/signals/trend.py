"""Strategy A: Volatility-Scaled Trend Following.

Reference: Section 10.2 of agent.md
Owner: Human Lead (See docs/ownership.md)

Idea:
Crypto returns exhibit time-series momentum at suitable horizons (Moskowitz et al., 2012).
Direction from moving average crossover (fast MA vs slow MA), stop distance scaled by ATR.
Pure deterministic function without I/O or look-ahead.
"""

from __future__ import annotations

import math
from decimal import Decimal

from app.core.contracts import Candle, Direction, Signal
from app.signals.base import StrategyProtocol
from app.signals.indicators import atr_latest, ema_latest


class TrendFollowingStrategy(StrategyProtocol):
    """Strategy A: Pure trend following with ATR-based bracket stop."""

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
        self._min_history = max(min_history_candles, slow_period + 1)

    @property
    def name(self) -> str:
        return "trend_following"

    @property
    def min_history(self) -> int:
        return self._min_history

    def evaluate(self, candles: list[Candle]) -> Signal:
        """Pure evaluation function over closed candles up to candle N."""
        closed_candles = [c for c in candles if c.is_closed]
        if not closed_candles or len(closed_candles) < self._min_history:
            symbol = closed_candles[-1].symbol if closed_candles else (candles[-1].symbol if candles else "BTCUSD")
            return Signal(
                strategy_name=self.name,
                symbol=symbol,
                direction=Direction.FLAT,
                strength=0.0,
                proposed_stop_distance=Decimal("0"),
                reason_codes=["INSUFFICIENT_HISTORY"],
            )

        candles = closed_candles

        closes = [float(c.close) for c in candles]
        fast_ma = ema_latest(closes, self.fast_period)
        slow_ma = ema_latest(closes, self.slow_period)

        prev_closes = closes[:-1]
        prev_fast = ema_latest(prev_closes, self.fast_period)
        prev_slow = ema_latest(prev_closes, self.slow_period)

        current_atr = atr_latest(candles, self.atr_period)
        if math.isnan(current_atr) or current_atr <= 0:
            current_atr = max(10.0, closes[-1] * 0.002)

        stop_dist = Decimal(str(round(current_atr * self.atr_multiplier, 2)))
        tp_dist = Decimal(str(round(current_atr * self.atr_multiplier * 2.0, 2)))
        last_candle = candles[-1]

        # Calculate normalized trend strength in [0.1, 1.0]
        ma_diff = abs(fast_ma - slow_ma)
        normalized_strength = min(1.0, max(0.1, ma_diff / (current_atr + 1e-6)))

        numeric_vals = {
            "fast_ma": round(fast_ma, 2),
            "slow_ma": round(slow_ma, 2),
            "atr": round(current_atr, 2),
            "ma_diff": round(ma_diff, 2),
        }
        indicators = {
            "fast_ma": fast_ma,
            "slow_ma": slow_ma,
            "atr": current_atr,
        }

        # Deadband threshold to avoid whipsaw on infinitesimal differences
        deadband = current_atr * 0.05

        if fast_ma > slow_ma + deadband:
            reasons = ["MA_CROSS_BULLISH", "TREND_UP_CONFIRMED"] if prev_fast <= prev_slow else ["TREND_UP_PERSISTENT"]
            return Signal(
                strategy_name=self.name,
                symbol=last_candle.symbol,
                direction=Direction.LONG,
                strength=round(normalized_strength, 3),
                proposed_stop_distance=stop_dist,
                proposed_tp_distance=tp_dist,
                reason_codes=reasons,
                numeric_values=numeric_vals,
                indicators_snapshot=indicators,
            )
        elif fast_ma < slow_ma - deadband:
            reasons = ["MA_CROSS_BEARISH", "TREND_DOWN_CONFIRMED"] if prev_fast >= prev_slow else ["TREND_DOWN_PERSISTENT"]
            return Signal(
                strategy_name=self.name,
                symbol=last_candle.symbol,
                direction=Direction.SHORT,
                strength=round(normalized_strength, 3),
                proposed_stop_distance=stop_dist,
                proposed_tp_distance=tp_dist,
                reason_codes=reasons,
                numeric_values=numeric_vals,
                indicators_snapshot=indicators,
            )
        else:
            return Signal(
                strategy_name=self.name,
                symbol=last_candle.symbol,
                direction=Direction.FLAT,
                strength=0.0,
                proposed_stop_distance=stop_dist,
                proposed_tp_distance=tp_dist,
                reason_codes=["NO_TREND_CONFIRMED"],
                numeric_values=numeric_vals,
                indicators_snapshot=indicators,
            )
