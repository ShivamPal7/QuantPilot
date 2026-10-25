"""Empirical stress test suite for Milestone 2 closed candle guards, lookahead prevention, and Thompson sampling allocator.

Authored by: challenger_m2_2_2 (Empirical Challenger)
Covers:
1. Closed candle guards and lookahead prevention across CandleStore, TrendFollowingStrategy, MeanReversionStrategy, RegimeFilter, and CandleBuilder.
2. 100 iterations of StrategyAllocator under CHAOTIC conditions confirming 100% stand-aside.
3. 100 iterations of StrategyAllocator under TRENDING conditions confirming exploitation dominance and cold-start mapping.
4. 100 iterations of StrategyAllocator under RANGING conditions confirming exploitation dominance and cold-start mapping.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.core.contracts import (
    AllocationDecision,
    Candle,
    Direction,
    RegimeLabel,
    RegimeReading,
    ShadowStats,
)
from app.data.builder import CandleBuilder
from app.data.store import CandleStore
from app.shadow.allocator import StrategyAllocator
from app.signals.regime import RegimeFilter
from app.signals.reversion import MeanReversionStrategy
from app.signals.trend import TrendFollowingStrategy


def make_test_candle(
    minute_offset: int,
    base_time: datetime,
    open_p: Decimal = Decimal("65000.0"),
    high_p: Decimal = Decimal("65050.0"),
    low_p: Decimal = Decimal("64950.0"),
    close_p: Decimal = Decimal("65000.0"),
    volume: Decimal = Decimal("10.0"),
    is_closed: bool = True,
    symbol: str = "BTCUSD",
) -> Candle:
    t = base_time + timedelta(minutes=minute_offset)
    return Candle(
        symbol=symbol,
        timeframe="1m",
        open_time=t,
        close_time=t + timedelta(minutes=1),
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=volume,
        is_closed=is_closed,
    )


class TestMilestone2ChallengerStress(unittest.TestCase):
    """Rigorous empirical challenge suite for Milestone 2 guards and bandit allocator."""

    def setUp(self) -> None:
        self.base_time = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)

    # -------------------------------------------------------------------------
    # 1. Closed Candle Guards & Lookahead Prevention
    # -------------------------------------------------------------------------
    def test_unclosed_candle_pure_history_does_not_trigger_evaluation(self) -> None:
        """Verify feeding purely unclosed candles does NOT trigger strategy or regime calculation."""
        only_unclosed = [
            make_test_candle(i, self.base_time, is_closed=False, close_p=Decimal(str(65000 + i * 20)))
            for i in range(70)
        ]

        # 1. TrendFollowingStrategy
        trend_strat = TrendFollowingStrategy(fast_period=20, slow_period=50, min_history_candles=55)
        sig_trend = trend_strat.evaluate(only_unclosed)
        self.assertEqual(sig_trend.direction, Direction.FLAT)
        self.assertEqual(sig_trend.strength, 0.0)
        self.assertIn("INSUFFICIENT_HISTORY", sig_trend.reason_codes)

        # 2. MeanReversionStrategy
        rev_strat = MeanReversionStrategy(lookback_period=30, min_history_candles=35)
        sig_rev = rev_strat.evaluate(only_unclosed)
        self.assertEqual(sig_rev.direction, Direction.FLAT)
        self.assertEqual(sig_rev.strength, 0.0)
        self.assertIn("INSUFFICIENT_HISTORY", sig_rev.reason_codes)

        # 3. RegimeFilter
        rf = RegimeFilter(volatility_lookback=20)
        reading = rf.evaluate(only_unclosed)
        self.assertEqual(reading.label, RegimeLabel.RANGING)

    def test_unclosed_candle_lookahead_prevention_on_strategy_signals(self) -> None:
        """Verify an unclosed forming candle with extreme price action does NOT contaminate signals."""
        trend_strat = TrendFollowingStrategy(fast_period=20, slow_period=50, min_history_candles=55)
        rev_strat = MeanReversionStrategy(lookback_period=30, min_history_candles=35)
        rf = RegimeFilter(volatility_lookback=20, chaotic_vol_ratio=2.5)

        # 1. TrendFollowing: 60 downtrend candles
        downtrend_closed = [
            make_test_candle(
                i,
                self.base_time,
                is_closed=True,
                open_p=Decimal(str(65000 - i * 30)),
                close_p=Decimal(str(65000 - (i + 1) * 30)),
                low_p=Decimal(str(65000 - (i + 1) * 30 - 10)),
                high_p=Decimal(str(65000 - i * 30 + 10)),
            )
            for i in range(60)
        ]
        sig_trend_baseline = trend_strat.evaluate(downtrend_closed)
        self.assertEqual(sig_trend_baseline.direction, Direction.SHORT)

        # Append unclosed forming candle with massive price moonshot (+30,000)
        unclosed_moonshot = make_test_candle(
            60,
            self.base_time,
            is_closed=False,
            open_p=Decimal("63000.0"),
            high_p=Decimal("96000.0"),
            low_p=Decimal("63000.0"),
            close_p=Decimal("95000.0"),
        )
        sig_trend_with_unclosed = trend_strat.evaluate(downtrend_closed + [unclosed_moonshot])

        # Strict lookahead guard: unclosed bar must be completely ignored
        self.assertEqual(sig_trend_with_unclosed.direction, sig_trend_baseline.direction)
        self.assertEqual(sig_trend_with_unclosed.strength, sig_trend_baseline.strength)
        self.assertEqual(sig_trend_with_unclosed.numeric_values, sig_trend_baseline.numeric_values)
        self.assertEqual(sig_trend_with_unclosed.indicators_snapshot, sig_trend_baseline.indicators_snapshot)

        # 2. MeanReversion: 40 flat candles
        ranging_closed = [
            make_test_candle(
                i,
                self.base_time,
                is_closed=True,
                open_p=Decimal("65000.0"),
                close_p=Decimal("65000.0"),
                high_p=Decimal("65010.0"),
                low_p=Decimal("64990.0"),
            )
            for i in range(40)
        ]
        sig_rev_baseline = rev_strat.evaluate(ranging_closed)
        self.assertEqual(sig_rev_baseline.direction, Direction.FLAT)

        # Append unclosed forming candle with extreme price drop (-10,000)
        unclosed_crash = make_test_candle(
            40,
            self.base_time,
            is_closed=False,
            open_p=Decimal("65000.0"),
            high_p=Decimal("65000.0"),
            low_p=Decimal("54000.0"),
            close_p=Decimal("55000.0"),
        )
        sig_rev_with_unclosed = rev_strat.evaluate(ranging_closed + [unclosed_crash])

        self.assertEqual(sig_rev_with_unclosed.direction, sig_rev_baseline.direction)
        self.assertEqual(sig_rev_with_unclosed.numeric_values, sig_rev_baseline.numeric_values)
        self.assertEqual(sig_rev_with_unclosed.indicators_snapshot, sig_rev_baseline.indicators_snapshot)

        # 3. RegimeFilter: 40 flat candles
        reading_baseline = rf.evaluate(ranging_closed)
        self.assertEqual(reading_baseline.label, RegimeLabel.RANGING)

        # Append unclosed forming candle with extreme wick (TR=40,000)
        unclosed_wick = make_test_candle(
            40,
            self.base_time,
            is_closed=False,
            open_p=Decimal("65000.0"),
            high_p=Decimal("85000.0"),
            low_p=Decimal("45000.0"),
            close_p=Decimal("65005.0"),
        )
        reading_with_unclosed = rf.evaluate(ranging_closed + [unclosed_wick])
        self.assertEqual(reading_with_unclosed.label, RegimeLabel.RANGING)
        self.assertEqual(reading_with_unclosed.metrics, reading_baseline.metrics)

    def test_candle_store_unclosed_forming_isolation_and_replacement(self) -> None:
        """Verify CandleStore excludes unclosed candles from closed queries and handles forming bar replacement."""
        store = CandleStore("BTCUSD", "1m", max_capacity=100)
        for i in range(50):
            store.add_candle(make_test_candle(i, self.base_time, is_closed=True))

        # Add unclosed forming candle
        unclosed_c = make_test_candle(50, self.base_time, is_closed=False, close_p=Decimal("79999.0"))
        store.add_candle(unclosed_c)

        self.assertEqual(store.count, 51)
        closed_candles = store.get_closed_candles()
        self.assertEqual(len(closed_candles), 50)
        self.assertTrue(all(c.is_closed for c in closed_candles))
        self.assertEqual(closed_candles[-1].open_time, make_test_candle(49, self.base_time).open_time)

        # Overwrite forming candle with final closed candle
        final_closed = make_test_candle(50, self.base_time, is_closed=True, close_p=Decimal("65550.0"))
        store.add_candle(final_closed)
        self.assertEqual(store.count, 51)
        closed_after_replace = store.get_closed_candles()
        self.assertEqual(len(closed_after_replace), 51)
        self.assertTrue(closed_after_replace[-1].is_closed)
        self.assertEqual(closed_after_replace[-1].close, Decimal("65550.0"))

    def test_candle_builder_ticks_do_not_trigger_premature_candle_closed(self) -> None:
        """Verify CandleBuilder does not emit CandleClosedEvent on forming intra-bucket ticks."""
        closed_events = []
        builder = CandleBuilder(
            symbol="BTCUSD",
            timeframe="1m",
            on_candle_closed=lambda evt: closed_events.append(evt),
        )
        t0 = datetime(2026, 10, 25, 12, 0, 10, tzinfo=timezone.utc)

        # Tick 1, 2, 3 in same minute bucket: returns None, no event fired, candle is forming
        self.assertIsNone(builder.push_tick(Decimal("65000.0"), Decimal("1.0"), t0))
        self.assertIsNone(builder.push_tick(Decimal("65100.0"), Decimal("2.0"), t0 + timedelta(seconds=15)))
        self.assertIsNone(builder.push_tick(Decimal("64900.0"), Decimal("1.5"), t0 + timedelta(seconds=45)))
        self.assertEqual(len(closed_events), 0)
        self.assertIsNotNone(builder.current_candle)
        self.assertFalse(builder.current_candle.is_closed)

        # Tick 4 in new bucket (12:01:05): closes previous candle and fires event
        c_closed = builder.push_tick(Decimal("65200.0"), Decimal("3.0"), t0 + timedelta(seconds=55))
        self.assertIsNotNone(c_closed)
        self.assertTrue(c_closed.is_closed)
        self.assertEqual(len(closed_events), 1)
        self.assertTrue(closed_events[0].candle.is_closed)
        self.assertEqual(closed_events[0].close_price, 64900.0)
        self.assertFalse(builder.current_candle.is_closed)

    # -------------------------------------------------------------------------
    # 2. StrategyAllocator 100-Iteration Stress Tests
    # -------------------------------------------------------------------------
    def test_allocator_100_iterations_chaotic_stand_aside_guarantee(self) -> None:
        """Verify StrategyAllocator enforces 100% stand-aside under CHAOTIC across multiple configurations."""
        chaotic_reading = RegimeReading(
            label=RegimeLabel.CHAOTIC,
            metrics={"adx": 15.0, "realized_vol": 0.05, "vol_ratio": 3.2, "atr_spike": 4.1},
            previous_label=RegimeLabel.TRENDING,
            confidence=0.95,
        )

        stats_high_performing = {
            "trend_following": ShadowStats(
                strategy_name="trend_following",
                trade_count=50,
                win_count=45,
                loss_count=5,
                win_rate=0.90,
                net_profit=Decimal("2500.0"),
                max_drawdown_pct=0.01,
            ),
            "mean_reversion": ShadowStats(
                strategy_name="mean_reversion",
                trade_count=50,
                win_count=40,
                loss_count=10,
                win_rate=0.80,
                net_profit=Decimal("1800.0"),
                max_drawdown_pct=0.02,
            ),
        }

        stats_cold_start = {
            "trend_following": ShadowStats(
                strategy_name="trend_following",
                trade_count=1,
                win_count=1,
                loss_count=0,
                win_rate=1.0,
                net_profit=Decimal("50.0"),
                max_drawdown_pct=0.0,
            ),
            "mean_reversion": ShadowStats(
                strategy_name="mean_reversion",
                trade_count=1,
                win_count=0,
                loss_count=1,
                win_rate=0.0,
                net_profit=Decimal("-50.0"),
                max_drawdown_pct=0.01,
            ),
        }

        # 1. 100 iterations with standard 10% exploration floor
        alloc = StrategyAllocator(exploration_floor=0.10, seed=42)
        for i in range(100):
            dec = alloc.allocate(chaotic_reading, stats_high_performing)
            self.assertIsNone(dec.selected_strategy, f"Trial {i}: Leaked strategy under CHAOTIC")
            self.assertEqual(dec.weight, 0.0)
            self.assertTrue(dec.is_regime_override)
            self.assertIn("CHAOTIC: standing aside", dec.reason)

        # 2. 100 iterations with 100% exploration floor (pure exploration)
        alloc_pure_explor = StrategyAllocator(exploration_floor=1.0, seed=123)
        for i in range(100):
            dec = alloc_pure_explor.allocate(chaotic_reading, stats_high_performing)
            self.assertIsNone(dec.selected_strategy, f"Trial {i}: Leaked exploration under CHAOTIC")
            self.assertEqual(dec.weight, 0.0)
            self.assertTrue(dec.is_regime_override)

        # 3. 100 iterations with cold-start stats
        for i in range(100):
            dec = alloc.allocate(chaotic_reading, stats_cold_start)
            self.assertIsNone(dec.selected_strategy, f"Trial {i}: Leaked cold-start under CHAOTIC")
            self.assertEqual(dec.weight, 0.0)
            self.assertTrue(dec.is_regime_override)

    def test_allocator_100_iterations_trending_regime_distribution(self) -> None:
        """Verify StrategyAllocator in TRENDING regime exploits trend_following and adheres to exploration floor."""
        trending_reading = RegimeReading(
            label=RegimeLabel.TRENDING,
            metrics={"adx": 32.0, "realized_vol": 0.015, "vol_ratio": 1.2, "atr_spike": 1.1},
            previous_label=RegimeLabel.RANGING,
            confidence=0.88,
        )

        stats_trend_winning = {
            "trend_following": ShadowStats(
                strategy_name="trend_following",
                trade_count=30,
                win_count=24,
                loss_count=6,
                win_rate=0.80,
                net_profit=Decimal("1200.0"),
                max_drawdown_pct=0.03,
            ),
            "mean_reversion": ShadowStats(
                strategy_name="mean_reversion",
                trade_count=30,
                win_count=6,
                loss_count=24,
                win_rate=0.20,
                net_profit=Decimal("-800.0"),
                max_drawdown_pct=0.15,
            ),
        }

        alloc = StrategyAllocator(exploration_floor=0.10, seed=777)
        decisions = [alloc.allocate(trending_reading, stats_trend_winning) for _ in range(100)]

        trend_count = sum(1 for d in decisions if d.selected_strategy == "trend_following")
        rev_count = sum(1 for d in decisions if d.selected_strategy == "mean_reversion")
        exploration_count = sum(1 for d in decisions if d.is_exploration)
        regime_override_count = sum(1 for d in decisions if d.is_regime_override)

        # Sanity assertions
        self.assertEqual(regime_override_count, 0)
        self.assertGreaterEqual(trend_count, 90, f"Expected trend_following >= 90%, got {trend_count}%")
        self.assertLessEqual(rev_count, 10)
        # All non-exploration decisions must strictly exploit trend_following
        for d in decisions:
            if not d.is_exploration:
                self.assertEqual(d.selected_strategy, "trend_following")

        # Cold start in TRENDING: 100/100 must select trend_following
        stats_cold = {
            "trend_following": ShadowStats("trend_following", 1, 1, 0, 1.0, Decimal("10"), 0.0),
            "mean_reversion": ShadowStats("mean_reversion", 1, 0, 1, 0.0, Decimal("-10"), 0.01),
        }
        cold_decisions = [alloc.allocate(trending_reading, stats_cold) for _ in range(100)]
        self.assertTrue(all(d.selected_strategy == "trend_following" for d in cold_decisions))
        self.assertTrue(all(d.weight == 1.0 for d in cold_decisions))

    def test_allocator_100_iterations_ranging_regime_distribution(self) -> None:
        """Verify StrategyAllocator in RANGING regime exploits mean_reversion and adheres to exploration floor."""
        ranging_reading = RegimeReading(
            label=RegimeLabel.RANGING,
            metrics={"adx": 16.0, "realized_vol": 0.010, "vol_ratio": 0.95, "atr_spike": 0.9},
            previous_label=RegimeLabel.TRENDING,
            confidence=0.85,
        )

        stats_revert_winning = {
            "trend_following": ShadowStats(
                strategy_name="trend_following",
                trade_count=30,
                win_count=6,
                loss_count=24,
                win_rate=0.20,
                net_profit=Decimal("-800.0"),
                max_drawdown_pct=0.15,
            ),
            "mean_reversion": ShadowStats(
                strategy_name="mean_reversion",
                trade_count=30,
                win_count=24,
                loss_count=6,
                win_rate=0.80,
                net_profit=Decimal("1200.0"),
                max_drawdown_pct=0.03,
            ),
        }

        alloc = StrategyAllocator(exploration_floor=0.10, seed=888)
        decisions = [alloc.allocate(ranging_reading, stats_revert_winning) for _ in range(100)]

        revert_count = sum(1 for d in decisions if d.selected_strategy == "mean_reversion")
        trend_count = sum(1 for d in decisions if d.selected_strategy == "trend_following")
        exploration_count = sum(1 for d in decisions if d.is_exploration)
        regime_override_count = sum(1 for d in decisions if d.is_regime_override)

        self.assertEqual(regime_override_count, 0)
        self.assertGreaterEqual(revert_count, 90, f"Expected mean_reversion >= 90%, got {revert_count}%")
        self.assertLessEqual(trend_count, 10)
        # All non-exploration decisions must strictly exploit mean_reversion
        for d in decisions:
            if not d.is_exploration:
                self.assertEqual(d.selected_strategy, "mean_reversion")

        # Cold start in RANGING: 100/100 must select mean_reversion
        stats_cold = {
            "trend_following": ShadowStats("trend_following", 1, 1, 0, 1.0, Decimal("10"), 0.0),
            "mean_reversion": ShadowStats("mean_reversion", 1, 0, 1, 0.0, Decimal("-10"), 0.01),
        }
        cold_decisions = [alloc.allocate(ranging_reading, stats_cold) for _ in range(100)]
        self.assertTrue(all(d.selected_strategy == "mean_reversion" for d in cold_decisions))
        self.assertTrue(all(d.weight == 1.0 for d in cold_decisions))


if __name__ == "__main__":
    unittest.main()
