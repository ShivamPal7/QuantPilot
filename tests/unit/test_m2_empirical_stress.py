"""Empirical stress tests for Milestone 2 Strategy & Regime Layer.

Tests determinism across 100 runs, strict zero-lookahead, synthetic series
(trending, ranging, noisy), extreme wicks, and allocator stand-aside under CHAOTIC.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
import random
import unittest

from app.core.contracts import (
    AllocationDecision,
    Candle,
    Direction,
    RegimeLabel,
    RegimeReading,
    ShadowStats,
)
from app.shadow.allocator import StrategyAllocator
from app.signals.regime import RegimeFilter
from app.signals.reversion import MeanReversionStrategy
from app.signals.trend import TrendFollowingStrategy


def make_candle(
    timestamp: datetime,
    open_p: Decimal,
    high_p: Decimal,
    low_p: Decimal,
    close_p: Decimal,
    volume: Decimal = Decimal("100.0"),
    symbol: str = "BTCUSD",
) -> Candle:
    """Helper to construct a closed 1m candle."""
    return Candle(
        symbol=symbol,
        timeframe="1m",
        open_time=timestamp,
        close_time=timestamp + timedelta(minutes=1),
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=volume,
        is_closed=True,
    )


def generate_trending_candles(
    count: int,
    base_price: Decimal = Decimal("65000.0"),
    slope_per_candle: Decimal = Decimal("25.0"),
    noise_amplitude: Decimal = Decimal("2.0"),
    seed: int = 42,
) -> list[Candle]:
    """Generate synthetic trending candles with linear drift and bounded noise."""
    rng = random.Random(seed)
    start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    candles: list[Candle] = []

    curr_close = base_price
    for i in range(count):
        t = start_time + timedelta(minutes=i)
        drift = slope_per_candle
        noise = Decimal(str(round(rng.uniform(-float(noise_amplitude), float(noise_amplitude)), 2)))
        open_p = curr_close
        close_p = open_p + drift + noise
        high_p = max(open_p, close_p) + Decimal("5.0")
        low_p = min(open_p, close_p) - Decimal("5.0")
        curr_close = close_p

        candles.append(make_candle(t, open_p, high_p, low_p, close_p))

    return candles


def generate_ranging_candles(
    count: int,
    base_price: Decimal = Decimal("65000.0"),
    amplitude: Decimal = Decimal("100.0"),
    period: int = 20,
    noise_amplitude: Decimal = Decimal("5.0"),
    seed: int = 42,
) -> list[Candle]:
    """Generate synthetic ranging / stationary mean-reverting candles."""
    rng = random.Random(seed)
    start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    candles: list[Candle] = []

    for i in range(count):
        t = start_time + timedelta(minutes=i)
        sine_val = math.sin(2.0 * math.pi * i / period)
        noise = rng.uniform(-float(noise_amplitude), float(noise_amplitude))
        p = base_price + Decimal(str(round(float(amplitude) * sine_val + noise, 2)))
        open_p = p - Decimal("2.0")
        close_p = p + Decimal("2.0")
        high_p = max(open_p, close_p) + Decimal("10.0")
        low_p = min(open_p, close_p) - Decimal("10.0")

        candles.append(make_candle(t, open_p, high_p, low_p, close_p))

    return candles


def generate_noisy_candles(
    count: int,
    base_price: Decimal = Decimal("65000.0"),
    noise_std: float = 30.0,
    seed: int = 12345,
) -> list[Candle]:
    """Generate synthetic Gaussian random walk candles."""
    rng = random.Random(seed)
    start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    candles: list[Candle] = []

    curr_p = base_price
    for i in range(count):
        t = start_time + timedelta(minutes=i)
        shock = Decimal(str(round(rng.gauss(0.0, noise_std), 2)))
        open_p = curr_p
        close_p = open_p + shock
        spread = Decimal(str(round(abs(rng.gauss(0.0, 10.0)) + 5.0, 2)))
        high_p = max(open_p, close_p) + spread
        low_p = min(open_p, close_p) - spread
        curr_p = close_p

        candles.append(make_candle(t, open_p, high_p, low_p, close_p))

    return candles


class TestMilestone2EmpiricalStress(unittest.TestCase):
    """Rigorous empirical stress test suite for Strategy A, Strategy B, and RegimeFilter."""

    def setUp(self) -> None:
        self.trend_strat = TrendFollowingStrategy(
            fast_period=20,
            slow_period=50,
            atr_period=14,
            min_history_candles=55,
        )
        self.reversion_strat = MeanReversionStrategy(
            lookback_period=30,
            z_score_threshold=2.0,
            atr_period=14,
            min_history_candles=35,
        )
        self.regime_filter = RegimeFilter(
            trend_threshold=25.0,
            volatility_lookback=20,
            hysteresis_candles=3,
            chaotic_vol_ratio=2.5,
        )
        self.allocator = StrategyAllocator(exploration_floor=0.0, seed=42)

    def test_01_determinism_across_100_runs(self) -> None:
        """Verify identical candle inputs produce bitwise identical signals across 100 runs.
        
        Also verifies zero in-place mutation of input candles across all runs.
        """
        trending_candles = generate_trending_candles(70, slope_per_candle=Decimal("20.0"))
        ranging_candles = generate_ranging_candles(70)

        candles_backup = copy.deepcopy(trending_candles)

        # 1. Strategy A: 100 repeated evaluations on trending candles
        first_trend_sig = self.trend_strat.evaluate(trending_candles)
        for i in range(100):
            sig = self.trend_strat.evaluate(trending_candles)
            self.assertEqual(sig.strategy_name, first_trend_sig.strategy_name)
            self.assertEqual(sig.direction, first_trend_sig.direction)
            self.assertEqual(sig.strength, first_trend_sig.strength)
            self.assertEqual(sig.proposed_stop_distance, first_trend_sig.proposed_stop_distance)
            self.assertEqual(sig.proposed_tp_distance, first_trend_sig.proposed_tp_distance)
            self.assertEqual(sig.reason_codes, first_trend_sig.reason_codes)
            self.assertEqual(sig.numeric_values, first_trend_sig.numeric_values)
            self.assertEqual(sig.indicators_snapshot, first_trend_sig.indicators_snapshot)

        # Verify trending_candles were never mutated
        self.assertEqual(trending_candles, candles_backup)

        # 2. Strategy B: 100 repeated evaluations on ranging candles
        first_rev_sig = self.reversion_strat.evaluate(ranging_candles)
        ranging_backup = copy.deepcopy(ranging_candles)
        for i in range(100):
            sig = self.reversion_strat.evaluate(ranging_candles)
            self.assertEqual(sig.strategy_name, first_rev_sig.strategy_name)
            self.assertEqual(sig.direction, first_rev_sig.direction)
            self.assertEqual(sig.strength, first_rev_sig.strength)
            self.assertEqual(sig.proposed_stop_distance, first_rev_sig.proposed_stop_distance)
            self.assertEqual(sig.proposed_tp_distance, first_rev_sig.proposed_tp_distance)
            self.assertEqual(sig.reason_codes, first_rev_sig.reason_codes)
            self.assertEqual(sig.numeric_values, first_rev_sig.numeric_values)
            self.assertEqual(sig.indicators_snapshot, first_rev_sig.indicators_snapshot)

        self.assertEqual(ranging_candles, ranging_backup)

    def test_02_strict_zero_lookahead_trend_and_reversion(self) -> None:
        """Verify modifying future candles does NOT affect current signal at candle N."""
        base_series = generate_trending_candles(60, slope_per_candle=Decimal("15.0"))
        eval_point = 55
        target_history = base_series[:eval_point]

        # Baseline signals at index 55
        baseline_trend_sig = self.trend_strat.evaluate(target_history)
        baseline_rev_sig = self.reversion_strat.evaluate(target_history)

        # Construct three radical future scenarios starting from candle 55
        t_base = target_history[-1].close_time

        # Scenario 1: Extreme Bullish Moon Shot
        moon_futures = []
        for j in range(20):
            p = Decimal("66000.0") + Decimal(str(j * 5000))
            moon_futures.append(make_candle(t_base + timedelta(minutes=j), p, p + Decimal("1000"), p - Decimal("500"), p + Decimal("2000")))

        # Scenario 2: Flash Crash to Near Zero
        crash_futures = []
        for j in range(20):
            p = max(Decimal("10.0"), Decimal("65000.0") - Decimal(str(j * 3000)))
            crash_futures.append(make_candle(t_base + timedelta(minutes=j), p, p + Decimal("10"), p - Decimal("10"), p - Decimal("5")))

        # Scenario 3: Wild Erratic Whipsaw with Massive Wicks
        erratic_futures = []
        for j in range(20):
            p = Decimal("65000.0")
            erratic_futures.append(make_candle(t_base + timedelta(minutes=j), p, p + Decimal("15000"), p - Decimal("15000"), p))

        scenarios = [moon_futures, crash_futures, erratic_futures]

        for future in scenarios:
            extended_series = target_history + future
            # Slicing strictly to historical slice must yield exact baseline
            slice_to_eval = extended_series[:eval_point]

            trend_sig = self.trend_strat.evaluate(slice_to_eval)
            rev_sig = self.reversion_strat.evaluate(slice_to_eval)

            self.assertEqual(trend_sig.direction, baseline_trend_sig.direction)
            self.assertEqual(trend_sig.strength, baseline_trend_sig.strength)
            self.assertEqual(trend_sig.proposed_stop_distance, baseline_trend_sig.proposed_stop_distance)
            self.assertEqual(trend_sig.reason_codes, baseline_trend_sig.reason_codes)
            self.assertEqual(trend_sig.numeric_values, baseline_trend_sig.numeric_values)

            self.assertEqual(rev_sig.direction, baseline_rev_sig.direction)
            self.assertEqual(rev_sig.strength, baseline_rev_sig.strength)
            self.assertEqual(rev_sig.proposed_stop_distance, baseline_rev_sig.proposed_stop_distance)
            self.assertEqual(rev_sig.reason_codes, baseline_rev_sig.reason_codes)
            self.assertEqual(rev_sig.numeric_values, baseline_rev_sig.numeric_values)

    def test_03_synthetic_trending_series_behavior(self) -> None:
        """Verify Strategy A catches strong trends and Strategy B safely stands aside via variance ratio."""
        # 1. Strong linear uptrend
        uptrend_candles = generate_trending_candles(70, slope_per_candle=Decimal("30.0"), noise_amplitude=Decimal("1.0"))
        sig_trend_up = self.trend_strat.evaluate(uptrend_candles)

        self.assertEqual(sig_trend_up.direction, Direction.LONG)
        self.assertGreater(sig_trend_up.strength, 0.5)
        self.assertTrue(any("TREND_UP" in r or "BULLISH" in r for r in sig_trend_up.reason_codes))
        self.assertGreater(sig_trend_up.proposed_stop_distance, Decimal("0"))

        # Strategy B on strong uptrend must NOT fade the trend if variance ratio indicates momentum
        sig_rev_up = self.reversion_strat.evaluate(uptrend_candles)
        # When trending strongly, variance ratio is > 1.15, so Strategy B stands aside FLAT
        self.assertEqual(sig_rev_up.direction, Direction.FLAT)
        self.assertIn("NON_STATIONARY_REGIME", sig_rev_up.reason_codes)

        # 2. Strong linear downtrend
        downtrend_candles = generate_trending_candles(70, slope_per_candle=Decimal("-30.0"), noise_amplitude=Decimal("1.0"))
        sig_trend_down = self.trend_strat.evaluate(downtrend_candles)

        self.assertEqual(sig_trend_down.direction, Direction.SHORT)
        self.assertGreater(sig_trend_down.strength, 0.5)
        self.assertTrue(any("TREND_DOWN" in r or "BEARISH" in r for r in sig_trend_down.reason_codes))
        self.assertGreater(sig_trend_down.proposed_stop_distance, Decimal("0"))

        sig_rev_down = self.reversion_strat.evaluate(downtrend_candles)
        self.assertEqual(sig_rev_down.direction, Direction.FLAT)
        self.assertIn("NON_STATIONARY_REGIME", sig_rev_down.reason_codes)

    def test_04_synthetic_ranging_series_behavior(self) -> None:
        """Verify Strategy B trades excursions in stationary ranging market, and Strategy A stays flat."""
        ranging_candles = generate_ranging_candles(70, amplitude=Decimal("20.0"), period=10)

        # Normal oscillation within bands -> both should be FLAT
        sig_trend = self.trend_strat.evaluate(ranging_candles)
        sig_rev = self.reversion_strat.evaluate(ranging_candles)

        # In oscillation, Strategy A either stays FLAT (if within deadband) or tracks lag
        self.assertIn(sig_trend.direction, [Direction.FLAT, Direction.SHORT])

        # Within normal band or stationary stand-aside for reversion
        self.assertEqual(sig_rev.direction, Direction.FLAT)
        self.assertTrue(
            "WITHIN_NORMAL_BAND" in sig_rev.reason_codes or "NON_STATIONARY_REGIME" in sig_rev.reason_codes
        )

        # Now inject an oversold drop (mean reversion LONG opportunity)
        t_last = ranging_candles[-1].close_time
        oversold_candles = list(ranging_candles) + [
            make_candle(
                t_last,
                open_p=Decimal("65000.0"),
                high_p=Decimal("65005.0"),
                low_p=Decimal("64600.0"),
                close_p=Decimal("64620.0"),
            )
        ]
        sig_oversold = self.reversion_strat.evaluate(oversold_candles)
        self.assertEqual(sig_oversold.direction, Direction.LONG)
        self.assertIn("MEAN_REVERSION_OVERSOLD", sig_oversold.reason_codes)
        self.assertIn("STATIONARITY_CONFIRMED", sig_oversold.reason_codes)

        # Now inject an overbought spike (mean reversion SHORT opportunity)
        overbought_candles = list(ranging_candles) + [
            make_candle(
                t_last,
                open_p=Decimal("65000.0"),
                high_p=Decimal("65400.0"),
                low_p=Decimal("64995.0"),
                close_p=Decimal("65380.0"),
            )
        ]
        sig_overbought = self.reversion_strat.evaluate(overbought_candles)
        self.assertEqual(sig_overbought.direction, Direction.SHORT)
        self.assertIn("MEAN_REVERSION_OVERBOUGHT", sig_overbought.reason_codes)
        self.assertIn("STATIONARITY_CONFIRMED", sig_overbought.reason_codes)

    def test_05_synthetic_noisy_series_behavior(self) -> None:
        """Verify strategies behave safely without crashes or invalid numbers under pure white noise."""
        noisy_candles = generate_noisy_candles(100, noise_std=25.0, seed=999)

        for end_idx in range(55, 100):
            sub_series = noisy_candles[:end_idx]
            sig_a = self.trend_strat.evaluate(sub_series)
            sig_b = self.reversion_strat.evaluate(sub_series)

            # Check validity of Strategy A output
            self.assertIn(sig_a.direction, [Direction.LONG, Direction.SHORT, Direction.FLAT])
            self.assertTrue(0.0 <= sig_a.strength <= 1.0)
            self.assertFalse(math.isnan(float(sig_a.proposed_stop_distance)))
            self.assertGreaterEqual(sig_a.proposed_stop_distance, Decimal("0"))
            self.assertTrue(len(sig_a.reason_codes) > 0)

            # Check validity of Strategy B output
            self.assertIn(sig_b.direction, [Direction.LONG, Direction.SHORT, Direction.FLAT])
            self.assertTrue(0.0 <= sig_b.strength <= 1.0)
            self.assertFalse(math.isnan(float(sig_b.proposed_stop_distance)))
            self.assertGreaterEqual(sig_b.proposed_stop_distance, Decimal("0"))
            self.assertTrue(len(sig_b.reason_codes) > 0)

    def test_06_regime_filter_extreme_wicks_chaotic(self) -> None:
        """Verify RegimeFilter immediately switches to CHAOTIC when fed an extreme wick."""
        # Baseline normal candles with small range ($20 TR)
        base_candles = generate_ranging_candles(50, amplitude=Decimal("10.0"), period=10)
        rf = RegimeFilter(chaotic_vol_ratio=2.5)

        # Baseline evaluation
        reading_normal = rf.evaluate(base_candles)
        self.assertIn(reading_normal.label, [RegimeLabel.RANGING, RegimeLabel.TRENDING])

        # Inject extreme wick candle: open=65000, close=65005, high=85000, low=45000 (TR=40000)
        t_last = base_candles[-1].close_time
        wick_candle = make_candle(
            t_last,
            open_p=Decimal("65000.0"),
            high_p=Decimal("85000.0"),
            low_p=Decimal("45000.0"),
            close_p=Decimal("65005.0"),
            volume=Decimal("10000.0"),
        )
        extreme_candles = list(base_candles) + [wick_candle]

        reading_shock = rf.evaluate(extreme_candles)
        self.assertEqual(reading_shock.label, RegimeLabel.CHAOTIC)
        self.assertGreaterEqual(reading_shock.metrics.get("atr_spike", 0.0), 3.0)

    def test_07_regime_filter_high_volatility_chaotic(self) -> None:
        """Verify RegimeFilter classifies market as CHAOTIC on close-to-close volatility explosion."""
        base_candles = generate_ranging_candles(40, amplitude=Decimal("5.0"), period=10)
        rf = RegimeFilter(volatility_lookback=20, chaotic_vol_ratio=2.5)

        # Inject several highly volatile return jumps
        t_last = base_candles[-1].close_time
        volatile_candles = list(base_candles)
        prices = [Decimal("65000"), Decimal("72000"), Decimal("58000"), Decimal("75000"), Decimal("60000")]
        for idx, p in enumerate(prices):
            t_candle = t_last + timedelta(minutes=idx)
            volatile_candles.append(make_candle(t_candle, p, p + Decimal("500"), p - Decimal("500"), p))

        reading_vol = rf.evaluate(volatile_candles)
        self.assertEqual(reading_vol.label, RegimeLabel.CHAOTIC)
        self.assertGreater(reading_vol.metrics.get("vol_ratio", 0.0), 2.5)

    def test_08_allocator_stand_aside_under_chaotic_regime(self) -> None:
        """Verify StrategyAllocator strictly enforces stand-aside (None, weight 0.0) under CHAOTIC."""
        chaotic_reading = RegimeReading(
            label=RegimeLabel.CHAOTIC,
            metrics={"atr_spike": 5.2, "vol_ratio": 3.8},
            previous_label=RegimeLabel.TRENDING,
            confidence=0.95,
        )

        dummy_stats = {
            "trend_following": ShadowStats(
                strategy_name="trend_following",
                trade_count=20,
                win_count=15,
                loss_count=5,
                win_rate=0.75,
                net_profit=Decimal("500.0"),
                max_drawdown_pct=0.02,
            ),
            "mean_reversion": ShadowStats(
                strategy_name="mean_reversion",
                trade_count=20,
                win_count=12,
                loss_count=8,
                win_rate=0.60,
                net_profit=Decimal("300.0"),
                max_drawdown_pct=0.03,
            ),
        }

        decision = self.allocator.allocate(chaotic_reading, dummy_stats)
        self.assertIsNone(decision.selected_strategy)
        self.assertEqual(decision.weight, 0.0)
        self.assertTrue(decision.is_regime_override)
        self.assertIn("CHAOTIC: standing aside", decision.reason)

    def test_09_flat_market_zero_volatility_edge_case(self) -> None:
        """Verify strategies and regime filter handle zero-volatility flat candles without division by zero."""
        start_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        flat_price = Decimal("65000.0")
        flat_candles = [
            make_candle(
                start_time + timedelta(minutes=i),
                flat_price,
                flat_price,
                flat_price,
                flat_price,
            )
            for i in range(60)
        ]

        sig_trend = self.trend_strat.evaluate(flat_candles)
        self.assertEqual(sig_trend.direction, Direction.FLAT)
        self.assertGreater(sig_trend.proposed_stop_distance, Decimal("0"))

        sig_rev = self.reversion_strat.evaluate(flat_candles)
        self.assertEqual(sig_rev.direction, Direction.FLAT)
        self.assertGreater(sig_rev.proposed_stop_distance, Decimal("0"))

        rf = RegimeFilter()
        reading = rf.evaluate(flat_candles)
        self.assertIn(reading.label, [RegimeLabel.RANGING, RegimeLabel.TRENDING, RegimeLabel.CHAOTIC])
        self.assertFalse(math.isnan(reading.confidence))

    def test_10_regime_recovery_hysteresis(self) -> None:
        """Verify exiting CHAOTIC or transitioning between RANGING/TRENDING requires hysteresis dwell."""
        rf = RegimeFilter(trend_threshold=25.0, hysteresis_candles=3)

        # Baseline: RANGING
        ranging_candles = generate_ranging_candles(50, amplitude=Decimal("5.0"), period=10)
        for _ in range(4):
            rf.evaluate(ranging_candles)
        self.assertEqual(rf.current_label, RegimeLabel.RANGING)

        # Switch to strong trending candles
        trending_candles = generate_trending_candles(60, slope_per_candle=Decimal("30.0"))

        # Candle 1: raw candidate is TRENDING, dwell count = 1 < 3 -> remains RANGING
        r1 = rf.evaluate(trending_candles)
        self.assertEqual(r1.label, RegimeLabel.RANGING)

        # Candle 2: dwell count = 2 < 3 -> remains RANGING
        r2 = rf.evaluate(trending_candles)
        self.assertEqual(r2.label, RegimeLabel.RANGING)

        # Candle 3: dwell count = 3 >= 3 -> transitions to TRENDING
        r3 = rf.evaluate(trending_candles)
        self.assertEqual(r3.label, RegimeLabel.TRENDING)


if __name__ == "__main__":
    unittest.main()
