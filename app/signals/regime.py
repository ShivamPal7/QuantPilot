"""Market Regime Filter (Meta-Layer).

Reference: Section 10.4 of agent.md
Owner: Human Lead / Team Member A (See docs/ownership.md)

Purpose:
Decide whether the market is TRENDING, RANGING, or CHAOTIC (stand-aside).
Inputs: Trend-strength measure (ADX), realized volatility ratio.
Enforces: Hysteresis (enter and exit thresholds differ) and minimum dwell time to prevent flickering.
In CHAOTIC conditions, enforces immediate stand-aside.
"""

from __future__ import annotations

from app.core.contracts import Candle, RegimeLabel, RegimeReading
from app.signals.indicators import adx, atr_latest, rolling_std_latest


class RegimeFilter:
    """Classifies current market environment into TRENDING, RANGING, or CHAOTIC."""

    def __init__(
        self,
        trend_threshold: float = 25.0,
        trend_exit_threshold: float = 20.0,
        volatility_lookback: int = 20,
        hysteresis_candles: int = 3,
        chaotic_vol_ratio: float = 2.5,
        chaotic_vol_ratio_exit: float = 2.0,
        atr_spike_enter: float = 3.0,
        atr_spike_exit: float = 2.0,
    ) -> None:
        self.trend_threshold = trend_threshold
        self.trend_enter_threshold = trend_threshold
        self.trend_exit_threshold = trend_exit_threshold
        self.volatility_lookback = volatility_lookback
        self.hysteresis_candles = hysteresis_candles
        self.chaotic_vol_ratio = chaotic_vol_ratio
        self.chaotic_vol_ratio_enter = chaotic_vol_ratio
        self.chaotic_vol_ratio_exit = chaotic_vol_ratio_exit
        self.atr_spike_enter = atr_spike_enter
        self.atr_spike_exit = atr_spike_exit

        self._current_label: RegimeLabel = RegimeLabel.RANGING
        self._pending_label: RegimeLabel = RegimeLabel.RANGING
        self._dwell_count: int = 0

    @property
    def current_label(self) -> RegimeLabel:
        return self._current_label

    def evaluate(self, candles: list[Candle]) -> RegimeReading:
        """Pure function evaluating market regime from closed candles with dual-threshold hysteresis."""
        closed_candles = [c for c in candles if c.is_closed]
        if not closed_candles or len(closed_candles) < self.volatility_lookback:
            metrics = {
                "adx": 20.0,
                "realized_vol": 0.02,
                "vol_ratio": 1.0,
            }
            return RegimeReading(
                label=self._current_label,
                metrics=metrics,
                previous_label=self._current_label,
                confidence=0.8,
            )

        candles = closed_candles

        # 1. Trend strength via ADX
        adx_val = adx(candles, period=14)

        # 2. Volatility analysis: short vs baseline long realized volatility
        closes = [float(c.close) for c in candles]
        returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]

        short_window = min(5, len(returns))
        short_vol = rolling_std_latest(returns, short_window)

        # Baseline window excludes recent short shock if sufficient history exists
        if len(returns) >= self.volatility_lookback + short_window:
            baseline_returns = returns[:-short_window]
        else:
            baseline_returns = returns

        realized_vol = rolling_std_latest(baseline_returns, min(self.volatility_lookback, len(baseline_returns)))

        if realized_vol is None or realized_vol <= 1e-9:
            vol_ratio = 1.0
            realized_vol = 0.0001
        else:
            vol_ratio = (short_vol / realized_vol) if short_vol is not None else 1.0

        # 3. Check for ATR volatility spike
        short_atr = atr_latest(candles, 5)
        long_atr = atr_latest(candles, min(20, len(candles) - 1))
        atr_spike = (short_atr / long_atr) if (long_atr > 1e-6 and not (short_atr != short_atr)) else 1.0

        # 4. Determine raw candidate label with dual-threshold hysteresis
        if self._current_label == RegimeLabel.CHAOTIC:
            # While in CHAOTIC, exit only if volatility cools below exit thresholds
            is_chaotic = (vol_ratio > self.chaotic_vol_ratio_exit) or (atr_spike > self.atr_spike_exit)
        else:
            # While not in CHAOTIC, enter CHAOTIC if volatility spikes above enter thresholds
            is_chaotic = (vol_ratio > self.chaotic_vol_ratio_enter) or (atr_spike > self.atr_spike_enter)

        if is_chaotic:
            raw_candidate = RegimeLabel.CHAOTIC
            confidence = min(1.0, max(0.6, vol_ratio / 3.0))
        elif self._current_label == RegimeLabel.TRENDING:
            # While currently TRENDING, stay TRENDING unless ADX falls to or below trend_exit_threshold
            if adx_val <= self.trend_exit_threshold:
                raw_candidate = RegimeLabel.RANGING
                confidence = max(0.5, 1.0 - (adx_val / self.trend_enter_threshold) * 0.5)
            else:
                raw_candidate = RegimeLabel.TRENDING
                confidence = min(1.0, max(0.5, adx_val / 50.0))
        elif self._current_label == RegimeLabel.RANGING:
            # While currently RANGING, enter TRENDING only if ADX reaches or exceeds trend_enter_threshold
            if adx_val >= self.trend_enter_threshold:
                raw_candidate = RegimeLabel.TRENDING
                confidence = min(1.0, max(0.5, adx_val / 50.0))
            else:
                raw_candidate = RegimeLabel.RANGING
                confidence = max(0.5, 1.0 - (adx_val / self.trend_enter_threshold) * 0.5)
        else:
            # Exiting CHAOTIC: use standard enter thresholds to pick target candidate
            if adx_val >= self.trend_enter_threshold:
                raw_candidate = RegimeLabel.TRENDING
                confidence = min(1.0, max(0.5, adx_val / 50.0))
            else:
                raw_candidate = RegimeLabel.RANGING
                confidence = max(0.5, 1.0 - (adx_val / self.trend_enter_threshold) * 0.5)

        # 5. Dwell hysteresis logic
        prev_label = self._current_label

        if raw_candidate == RegimeLabel.CHAOTIC:
            # Immediate transition into CHAOTIC for safety
            self._current_label = RegimeLabel.CHAOTIC
            self._pending_label = RegimeLabel.CHAOTIC
            self._dwell_count = 0
        elif raw_candidate == self._current_label:
            # Already in target state
            self._pending_label = raw_candidate
            self._dwell_count = 0
        else:
            # Candidate differs from current state -> require dwell count
            if raw_candidate == self._pending_label:
                self._dwell_count += 1
                if self._dwell_count >= self.hysteresis_candles:
                    self._current_label = raw_candidate
                    self._dwell_count = 0
            else:
                self._pending_label = raw_candidate
                self._dwell_count = 1

        metrics = {
            "adx": round(adx_val, 2),
            "realized_vol": round(realized_vol, 6),
            "vol_ratio": round(vol_ratio, 3),
            "atr_spike": round(atr_spike, 2),
        }

        return RegimeReading(
            label=self._current_label,
            metrics=metrics,
            previous_label=prev_label,
            confidence=round(confidence, 2),
        )
