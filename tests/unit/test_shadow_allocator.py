"""Unit tests for ShadowAccount paper trading and Thompson sampling StrategyAllocator.

Per Section 9.4 of agent.md:
- Virtual accounts track positions with realistic fee & slippage friction.
- Trades are entered on next candle open (never same candle close).
- Allocator uses Thompson sampling with exploration floor and hard regime override.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.core.contracts import Candle, Direction, RegimeLabel, RegimeReading, ShadowStats, Signal
from app.shadow.account import ShadowAccount
from app.shadow.allocator import StrategyAllocator
from app.shadow.cost_model import ShadowCostModel


def make_candle(
    minute_offset: int,
    base_price: Decimal,
    high_delta: Decimal = Decimal("20.0"),
    low_delta: Decimal = Decimal("20.0"),
    close_delta: Decimal = Decimal("0.0"),
) -> Candle:
    start = datetime(2026, 10, 25, 0, 0, 0, tzinfo=timezone.utc)
    t_open = start + timedelta(minutes=minute_offset)
    t_close = start + timedelta(minutes=minute_offset + 1)
    open_p = base_price
    high_p = base_price + high_delta
    low_p = base_price - low_delta
    close_p = base_price + close_delta
    return Candle(
        symbol="BTCUSD",
        timeframe="1m",
        open_time=t_open,
        close_time=t_close,
        open=open_p,
        high=high_p,
        low=low_p,
        close=close_p,
        volume=Decimal("100.0"),
        is_closed=True,
    )


class TestShadowAllocator(unittest.TestCase):
    def setUp(self) -> None:
        self.allocator = StrategyAllocator(exploration_floor=0.10, min_trades_for_prior=5, seed=42)

    def test_hard_regime_override_chaotic(self) -> None:
        """When regime is CHAOTIC, allocator strictly stands aside (returns None) regardless of scores."""
        chaotic_regime = RegimeReading(
            label=RegimeLabel.CHAOTIC,
            metrics={"adx": 15.0, "realized_vol": 0.08, "vol_ratio": 3.5},
            previous_label=RegimeLabel.RANGING,
            confidence=0.95,
        )

        dummy_stats = {
            "trend_following": ShadowStats(
                strategy_name="trend_following",
                trade_count=20,
                win_count=18,
                loss_count=2,
                win_rate=0.90,
                net_profit=Decimal("500.0"),
                max_drawdown_pct=0.02,
            ),
            "mean_reversion": ShadowStats(
                strategy_name="mean_reversion",
                trade_count=20,
                win_count=15,
                loss_count=5,
                win_rate=0.75,
                net_profit=Decimal("300.0"),
                max_drawdown_pct=0.03,
            ),
        }

        decision = self.allocator.allocate(chaotic_regime, dummy_stats)
        self.assertIsNone(decision.selected_strategy)
        self.assertEqual(decision.weight, 0.0)
        self.assertTrue(decision.is_regime_override)
        self.assertIn("CHAOTIC", decision.reason)

    def test_cold_start_regime_defaults(self) -> None:
        """Under cold start (< 5 trades), allocator uses regime mapping prior."""
        few_stats = {
            "trend_following": ShadowStats(
                strategy_name="trend_following",
                trade_count=2,
                win_count=1,
                loss_count=1,
                win_rate=0.50,
                net_profit=Decimal("10.0"),
                max_drawdown_pct=0.01,
            ),
            "mean_reversion": ShadowStats(
                strategy_name="mean_reversion",
                trade_count=1,
                win_count=1,
                loss_count=0,
                win_rate=1.0,
                net_profit=Decimal("15.0"),
                max_drawdown_pct=0.0,
            ),
        }

        # 1. In TRENDING regime -> trend_following
        trending = RegimeReading(
            label=RegimeLabel.TRENDING,
            metrics={"adx": 35.0, "realized_vol": 0.01},
            previous_label=RegimeLabel.TRENDING,
            confidence=0.85,
        )
        dec_trend = self.allocator.allocate(trending, few_stats)
        self.assertEqual(dec_trend.selected_strategy, "trend_following")
        self.assertIn("Cold start", dec_trend.reason)

        # 2. In RANGING regime -> mean_reversion
        ranging = RegimeReading(
            label=RegimeLabel.RANGING,
            metrics={"adx": 18.0, "realized_vol": 0.01},
            previous_label=RegimeLabel.RANGING,
            confidence=0.80,
        )
        dec_range = self.allocator.allocate(ranging, few_stats)
        self.assertEqual(dec_range.selected_strategy, "mean_reversion")
        self.assertIn("Cold start", dec_range.reason)

    def test_thompson_sampling_determinism_with_seed(self) -> None:
        """With fixed seed, Thompson sampling allocation is completely deterministic."""
        stats = {
            "trend_following": ShadowStats(
                strategy_name="trend_following",
                trade_count=15,
                win_count=12,
                loss_count=3,
                win_rate=0.80,
                net_profit=Decimal("200.0"),
                max_drawdown_pct=0.02,
            ),
            "mean_reversion": ShadowStats(
                strategy_name="mean_reversion",
                trade_count=15,
                win_count=6,
                loss_count=9,
                win_rate=0.40,
                net_profit=Decimal("-50.0"),
                max_drawdown_pct=0.05,
            ),
        }
        regime = RegimeReading(
            label=RegimeLabel.TRENDING,
            metrics={"adx": 32.0, "realized_vol": 0.01},
            previous_label=RegimeLabel.TRENDING,
            confidence=0.85,
        )

        alloc1 = StrategyAllocator(exploration_floor=0.0, seed=123)
        dec1 = alloc1.allocate(regime, stats)

        alloc2 = StrategyAllocator(exploration_floor=0.0, seed=123)
        dec2 = alloc2.allocate(regime, stats)

        self.assertEqual(dec1.selected_strategy, dec2.selected_strategy)
        self.assertEqual(dec1.sampled_values, dec2.sampled_values)
        self.assertEqual(dec1.reason, dec2.reason)
        # Winning strategy with 80% win rate should easily dominate
        self.assertEqual(dec1.selected_strategy, "trend_following")

    def test_exploration_floor(self) -> None:
        """When exploration_floor=1.0, allocator always marks decision as exploration."""
        stats = {
            "trend_following": ShadowStats(
                strategy_name="trend_following",
                trade_count=10,
                win_count=8,
                loss_count=2,
                win_rate=0.80,
                net_profit=Decimal("100.0"),
                max_drawdown_pct=0.01,
            ),
        }
        regime = RegimeReading(
            label=RegimeLabel.TRENDING,
            metrics={"adx": 30.0, "realized_vol": 0.01},
            previous_label=RegimeLabel.TRENDING,
            confidence=0.8,
        )

        alloc_explore = StrategyAllocator(exploration_floor=1.0, seed=999)
        dec = alloc_explore.allocate(regime, stats)
        self.assertTrue(dec.is_exploration)
        self.assertIn("Exploration floor", dec.reason)

    def test_shadow_account_full_lifecycle_and_take_profit(self) -> None:
        """Verify ShadowAccount order queueing, slippage, fees, take-profit execution, and statistics."""
        cost_model = ShadowCostModel(
            taker_fee_pct=Decimal("0.0005"),
            maker_fee_pct=Decimal("0.0002"),
            default_slippage_bps=Decimal("10.0"),  # 0.10%
        )
        account = ShadowAccount("trend_following", initial_capital=Decimal("10000.0"), cost_model=cost_model)

        c0 = make_candle(0, Decimal("65000.0"))
        # 1. Propose LONG trade at candle 0 close
        sig = Signal(
            strategy_name="trend_following",
            symbol="BTCUSD",
            direction=Direction.LONG,
            strength=0.8,
            proposed_stop_distance=Decimal("200.0"),
            proposed_tp_distance=Decimal("400.0"),
            reason_codes=["MA_CROSS_BULLISH"],
        )
        account.on_signal(sig, c0)

        # Nothing executed yet at candle 0 (orders fill on NEXT candle open)
        self.assertFalse(account.has_open_position)
        self.assertEqual(account.current_cash, Decimal("10000.0"))

        # 2. Candle 1 arrives: opens position at 65000 + slippage (0.10% = 65065.0)
        c1 = make_candle(1, Decimal("65000.0"), high_delta=Decimal("50.0"), low_delta=Decimal("50.0"))
        account.process_closed_candle(c1)
        self.assertTrue(account.has_open_position)

        # Check entry fill price after slippage: 65000 * 1.001 = 65065.0
        pos = account._open_position
        self.assertIsNotNone(pos)
        self.assertEqual(pos["entry_price"], Decimal("65065.0"))
        # TP should be 65065.0 + 400.0 = 65465.0
        self.assertEqual(pos["take_profit"], Decimal("65465.0"))
        # SL should be 65065.0 - 200.0 = 64865.0
        self.assertEqual(pos["stop_loss"], Decimal("64865.0"))

        # 3. Candle 2 triggers take profit (price rallies to 65600)
        c2 = make_candle(2, Decimal("65300.0"), high_delta=Decimal("300.0"), low_delta=Decimal("10.0"))
        account.process_closed_candle(c2)

        # Position should now be closed via TAKE_PROFIT
        self.assertFalse(account.has_open_position)
        self.assertEqual(len(account.trades), 1)
        trade = account.trades[0]
        self.assertEqual(trade.exit_reason, "TAKE_PROFIT")
        self.assertTrue(trade.is_win)
        self.assertGreater(trade.net_pnl, Decimal("0"))
        self.assertGreater(account.current_equity, Decimal("10000.0"))

        stats = account.get_stats()
        self.assertEqual(stats.trade_count, 1)
        self.assertEqual(stats.win_count, 1)
        self.assertEqual(stats.win_rate, 1.0)
        self.assertEqual(stats.max_drawdown_pct, 0.0)

    def test_shadow_account_stop_loss_execution(self) -> None:
        """Verify ShadowAccount correctly triggers stop loss and updates drawdown."""
        account = ShadowAccount("reversion", initial_capital=Decimal("10000.0"))

        c0 = make_candle(0, Decimal("65000.0"))
        sig = Signal(
            strategy_name="reversion",
            symbol="BTCUSD",
            direction=Direction.LONG,
            strength=0.7,
            proposed_stop_distance=Decimal("150.0"),
            proposed_tp_distance=Decimal("300.0"),
        )
        account.on_signal(sig, c0)

        # Candle 1 opens position
        c1 = make_candle(1, Decimal("65000.0"), high_delta=Decimal("10.0"), low_delta=Decimal("10.0"))
        account.process_closed_candle(c1)
        self.assertTrue(account.has_open_position)

        # Candle 2 drops sharply, triggering stop loss
        c2 = make_candle(2, Decimal("64900.0"), high_delta=Decimal("10.0"), low_delta=Decimal("400.0"))
        account.process_closed_candle(c2)

        self.assertFalse(account.has_open_position)
        self.assertEqual(len(account.trades), 1)
        trade = account.trades[0]
        self.assertEqual(trade.exit_reason, "STOP_LOSS")
        self.assertFalse(trade.is_win)
        self.assertLess(trade.net_pnl, Decimal("0"))
        self.assertLess(account.current_equity, Decimal("10000.0"))

        stats = account.get_stats()
        self.assertEqual(stats.trade_count, 1)
        self.assertEqual(stats.loss_count, 1)
        self.assertEqual(stats.win_rate, 0.0)
        self.assertGreater(stats.max_drawdown_pct, 0.0)


if __name__ == "__main__":
    unittest.main()
