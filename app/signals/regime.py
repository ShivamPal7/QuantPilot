"""Market Regime Filter (Meta-Layer).

ZONE: RED (HUMAN-AUTHORED ONLY)
Owner: Human Lead / Team Member A (See docs/ownership.md)
Reference: Section 10.4 of agent.md

Purpose:
Decide whether the market is TRENDING, RANGING, or CHAOTIC (stand-aside).
Inputs: Trend-strength measure (e.g. ADX), realized volatility ratio, choppiness index.
Enforces: Hysteresis (enter and exit thresholds differ) and minimum dwell time.
"""

from __future__ import annotations

from app.core.contracts import Candle, RegimeLabel, RegimeReading


class RegimeFilter:
    """Classifies current market environment into TRENDING, RANGING, or CHAOTIC."""

    def __init__(
        self,
        trend_threshold: float = 25.0,
        volatility_lookback: int = 20,
        hysteresis_candles: int = 3,
    ) -> None:
        self.trend_threshold = trend_threshold
        self.volatility_lookback = volatility_lookback
        self.hysteresis_candles = hysteresis_candles
        self._current_label = RegimeLabel.RANGING
        self._dwell_count = 0

    def evaluate(self, candles: list[Candle]) -> RegimeReading:
        """Pure function evaluating market regime from closed candles.

        NOTE FOR HUMAN TEAM:
        Implement your regime calculation here using indicators (e.g., ADX, ATR, realized vol).
        Must respect hysteresis to avoid state flickering.
        """
        # Baseline human-owned stub returning safe default until fully populated
        metrics = {"adx": 20.0, "realized_vol": 0.02}
        return RegimeReading(
            label=self._current_label,
            metrics=metrics,
            previous_label=self._current_label,
            confidence=0.8,
        )
