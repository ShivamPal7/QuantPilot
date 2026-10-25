"""Strategy B: Short-Horizon Mean Reversion.

Reference: Section 10.3 of agent.md
Owner: Human Lead / Team Member B (See docs/ownership.md)

Idea:
Fade statistically large deviations from short-term mean (z-score),
only when the series is verified stationary via Lo-MacKinlay Variance Ratio test.
Exit at reversion to mean, protective ATR stop, or time stop.
"""

from __future__ import annotations

import math
from decimal import Decimal

from app.core.contracts import Candle, Direction, Signal
from app.signals.base import StrategyProtocol
from app.signals.indicators import atr_latest, variance_ratio, z_score


class MeanReversionStrategy(StrategyProtocol):
    """Strategy B: Pure mean reversion with stationarity and z-score checks."""

    def __init__(
        self,
        lookback_period: int = 30,
        z_score_threshold: float = 2.0,
        atr_period: int = 14,
        atr_multiplier: float = 1.5,
        min_history_candles: int = 35,
        variance_ratio_max: float = 1.15,
    ) -> None:
        self.lookback_period = lookback_period
        self.z_score_threshold = z_score_threshold
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self._min_history = max(min_history_candles, lookback_period + 2)
        self.variance_ratio_max = variance_ratio_max

    @property
    def name(self) -> str:
        return "mean_reversion"

    @property
    def min_history(self) -> int:
        return self._min_history

    def evaluate(self, candles: list[Candle]) -> Signal:
        """Evaluate mean reversion signal on closed candle history."""
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
        z = z_score(closes, self.lookback_period)
        vr = variance_ratio(closes, k=2, period=self.lookback_period)

        current_atr = atr_latest(candles, self.atr_period)
        if math.isnan(current_atr) or current_atr <= 0:
            current_atr = max(10.0, closes[-1] * 0.002)

        stop_dist = Decimal(str(round(current_atr * self.atr_multiplier, 2)))
        tp_dist = Decimal(str(round(current_atr * 1.0, 2)))
        last_candle = candles[-1]

        numeric_vals = {
            "z_score": round(z, 3),
            "variance_ratio": round(vr, 3),
            "atr": round(current_atr, 2),
            "threshold": self.z_score_threshold,
        }
        indicators = {
            "z_score": z,
            "variance_ratio": vr,
            "atr": current_atr,
        }

        # Check stationarity / variance ratio condition
        # If variance ratio indicates strong trending (VR > variance_ratio_max), stand aside
        if vr > self.variance_ratio_max:
            return Signal(
                strategy_name=self.name,
                symbol=last_candle.symbol,
                direction=Direction.FLAT,
                strength=0.0,
                proposed_stop_distance=stop_dist,
                proposed_tp_distance=tp_dist,
                reason_codes=["NON_STATIONARY_REGIME", "MOMENTUM_PREVENTS_REVERSION"],
                numeric_values=numeric_vals,
                indicators_snapshot=indicators,
            )

        # Check deviation triggers
        if z < -self.z_score_threshold:
            # Oversold -> fade move by going LONG
            dev_excess = abs(z) - self.z_score_threshold
            strength = min(1.0, max(0.2, dev_excess / 2.0 + 0.5))
            return Signal(
                strategy_name=self.name,
                symbol=last_candle.symbol,
                direction=Direction.LONG,
                strength=round(strength, 3),
                proposed_stop_distance=stop_dist,
                proposed_tp_distance=tp_dist,
                reason_codes=["MEAN_REVERSION_OVERSOLD", "STATIONARITY_CONFIRMED"],
                numeric_values=numeric_vals,
                indicators_snapshot=indicators,
            )
        elif z > self.z_score_threshold:
            # Overbought -> fade move by going SHORT
            dev_excess = abs(z) - self.z_score_threshold
            strength = min(1.0, max(0.2, dev_excess / 2.0 + 0.5))
            return Signal(
                strategy_name=self.name,
                symbol=last_candle.symbol,
                direction=Direction.SHORT,
                strength=round(strength, 3),
                proposed_stop_distance=stop_dist,
                proposed_tp_distance=tp_dist,
                reason_codes=["MEAN_REVERSION_OVERBOUGHT", "STATIONARITY_CONFIRMED"],
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
                reason_codes=["WITHIN_NORMAL_BAND"],
                numeric_values=numeric_vals,
                indicators_snapshot=indicators,
            )
