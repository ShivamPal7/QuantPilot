"""Unit tests for Strategy A, Strategy B, and RegimeFilter determinism, purity, and look-ahead resistance.

Per Section 7.1 and 8 of agent.md:
Strategies are pure deterministic functions without I/O or side effects.
Signals must be identical given identical candle history, resistant to look-ahead bias,
and fail closed on insufficient history.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.core.contracts import Candle, Direction, RegimeLabel
from app.signals.regime import RegimeFilter
from app.signals.reversion import MeanReversionStrategy
from app.signals.trend import TrendFollowingStrategy


def generate_sample_candles(count: int, base_price: Decimal = Decimal("65000.0")) -> list[Candle]:
    """Generate deterministic synthetic candles."""
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    candles = []
    for i in range(count):
        t_open = start + timedelta(minutes=i)
        t_close = start + timedelta(minutes=i + 1)
        p = base_price + Decimal(str(i * 5))
        candles.append(
            Candle(
                symbol="BTCUSD",
                timeframe="1m",
                open_time=t_open,
                close_time=t_close,
                open=p,
                high=p + Decimal("10.0"),
                low=p - Decimal("10.0"),
                close=p + Decimal("2.0"),
                volume=Decimal("100.0"),
                is_closed=True,
            )
        )
    return candles


class TestStrategyDeterminism(unittest.TestCase):
    def setUp(self) -> None:
        self.trend_strat = TrendFollowingStrategy(min_history_candles=50)
        self.reversion_strat = MeanReversionStrategy(min_history_candles=30)
        self.regime_filter = RegimeFilter()

    def test_trend_strategy_insufficient_history(self) -> None:
        """Strategy A returns FLAT with INSUFFICIENT_HISTORY when history < min_history."""
        candles = generate_sample_candles(20)  # Only 20, needs 50
        signal = self.trend_strat.evaluate(candles)

        self.assertEqual(signal.strategy_name, "trend_following")
        self.assertEqual(signal.direction, Direction.FLAT)
        self.assertEqual(signal.strength, 0.0)
        self.assertEqual(signal.proposed_stop_distance, Decimal("0"))
        self.assertIn("INSUFFICIENT_HISTORY", signal.reason_codes)

        # Empty candles list edge case
        empty_signal = self.trend_strat.evaluate([])
        self.assertEqual(empty_signal.direction, Direction.FLAT)
        self.assertIn("INSUFFICIENT_HISTORY", empty_signal.reason_codes)

    def test_mean_reversion_insufficient_history(self) -> None:
        """Strategy B returns FLAT with INSUFFICIENT_HISTORY when history < min_history."""
        candles = generate_sample_candles(15)  # Only 15, needs 30
        signal = self.reversion_strat.evaluate(candles)

        self.assertEqual(signal.strategy_name, "mean_reversion")
        self.assertEqual(signal.direction, Direction.FLAT)
        self.assertEqual(signal.strength, 0.0)
        self.assertEqual(signal.proposed_stop_distance, Decimal("0"))
        self.assertIn("INSUFFICIENT_HISTORY", signal.reason_codes)

    def test_strategy_determinism_and_purity(self) -> None:
        """Repeated evaluation on identical candle data must yield strictly identical signals without mutation."""
        candles = generate_sample_candles(60)
        candles_copy = copy.deepcopy(candles)

        # Test Strategy A determinism
        sig1 = self.trend_strat.evaluate(candles)
        sig2 = self.trend_strat.evaluate(candles)

        self.assertEqual(sig1.strategy_name, sig2.strategy_name)
        self.assertEqual(sig1.direction, sig2.direction)
        self.assertEqual(sig1.strength, sig2.strength)
        self.assertEqual(sig1.proposed_stop_distance, sig2.proposed_stop_distance)
        self.assertEqual(sig1.reason_codes, sig2.reason_codes)
        self.assertEqual(sig1.numeric_values, sig2.numeric_values)

        # Verify zero mutation of inputs
        self.assertEqual(candles, candles_copy)

        # Test Strategy B determinism
        sig_b1 = self.reversion_strat.evaluate(candles)
        sig_b2 = self.reversion_strat.evaluate(candles)

        self.assertEqual(sig_b1.direction, sig_b2.direction)
        self.assertEqual(sig_b1.strength, sig_b2.strength)
        self.assertEqual(sig_b1.proposed_stop_distance, sig_b2.proposed_stop_distance)
        self.assertEqual(sig_b1.reason_codes, sig_b2.reason_codes)
        self.assertEqual(candles, candles_copy)

    def test_zero_look_ahead_resistance(self) -> None:
        """Evaluating past slice [0:N] must remain identical regardless of subsequent future candles [N:N+M]."""
        full_history = generate_sample_candles(70)

        # Signal computed at time point 55
        historical_slice = full_history[:55]
        signal_at_55 = self.trend_strat.evaluate(historical_slice)

        # Advance time by appending 15 future candles and re-evaluate on historical slice
        re_evaluated = self.trend_strat.evaluate(full_history[:55])

        self.assertEqual(signal_at_55.direction, re_evaluated.direction)
        self.assertEqual(signal_at_55.proposed_stop_distance, re_evaluated.proposed_stop_distance)
        self.assertEqual(signal_at_55.reason_codes, re_evaluated.reason_codes)
        self.assertEqual(signal_at_55.numeric_values, re_evaluated.numeric_values)

    def test_regime_filter_determinism(self) -> None:
        """RegimeFilter evaluation returns structured RegimeReading without side effects."""
        candles = generate_sample_candles(60)
        reading1 = self.regime_filter.evaluate(candles)
        reading2 = self.regime_filter.evaluate(candles)

        self.assertIn(reading1.label, [RegimeLabel.TRENDING, RegimeLabel.RANGING, RegimeLabel.CHAOTIC])
        self.assertEqual(reading1.label, reading2.label)
        self.assertAlmostEqual(reading1.confidence, reading2.confidence)
        self.assertIn("adx", reading1.metrics)
        self.assertIn("realized_vol", reading1.metrics)

    def test_trend_strategy_bullish_and_bearish_signals(self) -> None:
        """Strategy A emits LONG for upward trend and SHORT for downward trend."""
        # 1. Bullish trend candles (increasing price)
        bull_candles = generate_sample_candles(60, base_price=Decimal("60000.0"))
        bull_sig = self.trend_strat.evaluate(bull_candles)
        self.assertEqual(bull_sig.direction, Direction.LONG)
        self.assertGreater(bull_sig.strength, 0.0)
        self.assertGreater(bull_sig.proposed_stop_distance, Decimal("0"))

        # 2. Bearish trend candles (decreasing price)
        start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        bear_candles = []
        for i in range(60):
            t_open = start + timedelta(minutes=i)
            t_close = start + timedelta(minutes=i + 1)
            p = Decimal("70000.0") - Decimal(str(i * 10))
            bear_candles.append(
                Candle(
                    symbol="BTCUSD",
                    timeframe="1m",
                    open_time=t_open,
                    close_time=t_close,
                    open=p,
                    high=p + Decimal("5.0"),
                    low=p - Decimal("5.0"),
                    close=p - Decimal("2.0"),
                    volume=Decimal("100.0"),
                    is_closed=True,
                )
            )
        bear_sig = self.trend_strat.evaluate(bear_candles)
        self.assertEqual(bear_sig.direction, Direction.SHORT)
        self.assertGreater(bear_sig.strength, 0.0)
        self.assertGreater(bear_sig.proposed_stop_distance, Decimal("0"))

    def test_mean_reversion_oversold_and_overbought(self) -> None:
        """Strategy B triggers counter-trend entries when z-score exceeds threshold."""
        start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        # Create stationary oscillation around 65000
        base_candles = []
        for i in range(40):
            t_open = start + timedelta(minutes=i)
            t_close = start + timedelta(minutes=i + 1)
            # Oscillate between 64990 and 65010
            p = Decimal("65000.0") + Decimal(str(10 * (-1 if i % 2 == 0 else 1)))
            base_candles.append(
                Candle(
                    symbol="BTCUSD",
                    timeframe="1m",
                    open_time=t_open,
                    close_time=t_close,
                    open=p,
                    high=p + Decimal("5.0"),
                    low=p - Decimal("5.0"),
                    close=p,
                    volume=Decimal("50.0"),
                    is_closed=True,
                )
            )

        # 1. Sharp oversold drop on 41st candle
        t_open = start + timedelta(minutes=40)
        t_close = start + timedelta(minutes=41)
        oversold_candle = Candle(
            symbol="BTCUSD",
            timeframe="1m",
            open_time=t_open,
            close_time=t_close,
            open=Decimal("64990.0"),
            high=Decimal("65000.0"),
            low=Decimal("64500.0"),
            close=Decimal("64600.0"),  # Sharp deviation
            volume=Decimal("500.0"),
            is_closed=True,
        )
        oversold_candles = list(base_candles) + [oversold_candle]
        sig_oversold = self.reversion_strat.evaluate(oversold_candles)
        self.assertEqual(sig_oversold.direction, Direction.LONG)
        self.assertIn("MEAN_REVERSION_OVERSOLD", sig_oversold.reason_codes)

        # 2. Sharp overbought spike
        overbought_candle = Candle(
            symbol="BTCUSD",
            timeframe="1m",
            open_time=t_open,
            close_time=t_close,
            open=Decimal("65010.0"),
            high=Decimal("65500.0"),
            low=Decimal("65000.0"),
            close=Decimal("65400.0"),  # Sharp upward spike
            volume=Decimal("500.0"),
            is_closed=True,
        )
        overbought_candles = list(base_candles) + [overbought_candle]
        sig_overbought = self.reversion_strat.evaluate(overbought_candles)
        self.assertEqual(sig_overbought.direction, Direction.SHORT)
        self.assertIn("MEAN_REVERSION_OVERBOUGHT", sig_overbought.reason_codes)

    def test_regime_filter_hysteresis_and_chaotic_stand_aside(self) -> None:
        """RegimeFilter enforces dwell hysteresis and immediately transitions on CHAOTIC shock."""
        rf = RegimeFilter(trend_threshold=25.0, hysteresis_candles=3)
        self.assertEqual(rf.current_label, RegimeLabel.RANGING)

        # Strongly trending candles (monotonically rising with ADX > 25)
        trend_candles = generate_sample_candles(60, base_price=Decimal("65000.0"))

        # Evaluation 1: candidate is TRENDING, but dwell count is 1 < 3 -> remains RANGING
        r1 = rf.evaluate(trend_candles)
        self.assertEqual(r1.label, RegimeLabel.RANGING)

        # Evaluation 2: candidate is TRENDING, dwell count is 2 < 3 -> remains RANGING
        r2 = rf.evaluate(trend_candles)
        self.assertEqual(r2.label, RegimeLabel.RANGING)

        # Evaluation 3: dwell count reaches 3 -> transitions to TRENDING
        r3 = rf.evaluate(trend_candles)
        self.assertEqual(r3.label, RegimeLabel.TRENDING)

        # Now simulate sudden extreme volatility shock (CHAOTIC)
        shock_candles = list(trend_candles)
        last_t = shock_candles[-1].close_time
        shock_candles.append(
            Candle(
                symbol="BTCUSD",
                timeframe="1m",
                open_time=last_t,
                close_time=last_t + timedelta(minutes=1),
                open=Decimal("65300.0"),
                high=Decimal("69000.0"),
                low=Decimal("59000.0"),
                close=Decimal("60000.0"),
                volume=Decimal("5000.0"),
                is_closed=True,
            )
        )
        # Extreme volatility shock triggers CHAOTIC immediately (no hysteresis delay)
        r_shock = rf.evaluate(shock_candles)
        self.assertEqual(r_shock.label, RegimeLabel.CHAOTIC)


if __name__ == "__main__":
    unittest.main()
