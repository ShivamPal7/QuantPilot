"""Empirical Challenger Test Suite for Milestone 2 Iteration 2.

Exhaustively stress-tests:
1. ShadowAccount Realized PnL Mathematical Alignment:
   - Verifies net_pnl == gross_pnl - total_fees across long, short, win, loss, and breakeven.
   - Verifies no double-subtraction of slippage.
   - Verifies cash accounting: current_cash == initial_capital + sum(net_pnl).
   - Runs 1,000 randomized trades generator with property assertions.
2. WebSocket Watchdog Pong Timeout Socket Closure:
   - Verifies active socket closure upon pong timeout.
   - Verifies both async and sync socket.close() handling.
   - Verifies multi-socket closure across public and private feeds.
   - Verifies exception resilience if socket.close() raises errors.
   - Verifies healthy pong feeds do not trigger closure.
3. RegimeFilter Dual-Threshold Hysteresis Boundary Conditions:
   - Verifies ADX oscillation between 21.0 and 24.0 in RANGING never flips to TRENDING.
   - Verifies ADX oscillation between 21.0 and 24.0 in TRENDING never flips to RANGING.
   - Verifies dwell time requirements (3 consecutive candles).
   - Verifies immediate preemption into CHAOTIC on vol spikes.
   - Verifies 5,000 steps of property-based random walk state transitions.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import random
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.contracts import Candle, Direction, RegimeLabel, Signal
from app.exchange.websocket import DeltaWebSocketClient
from app.shadow.account import ShadowAccount
from app.shadow.cost_model import ShadowCostModel
from app.signals.regime import RegimeFilter


def make_candle(
    minute_offset: int,
    base_time: datetime,
    open_p: Decimal = Decimal("50000.0"),
    high_p: Decimal = Decimal("50100.0"),
    low_p: Decimal = Decimal("49900.0"),
    close_p: Decimal = Decimal("50050.0"),
    volume: Decimal = Decimal("10.0"),
    is_closed: bool = True,
) -> Candle:
    t = base_time + timedelta(minutes=minute_offset)
    return Candle(
        symbol="BTCUSD",
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


class TestShadowAccountRealizedPnLAlignment(unittest.TestCase):
    """Empirical challenge on ShadowAccount mathematical alignment."""

    def setUp(self) -> None:
        self.base_time = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)
        self.cost_model = ShadowCostModel(
            taker_fee_pct=Decimal("0.0005"),      # 5 bps
            maker_fee_pct=Decimal("0.0002"),      # 2 bps
            default_slippage_bps=Decimal("10.0"), # 10 bps
        )

    def test_long_winning_trade_exact_alignment(self) -> None:
        """Verify LONG winning trade: net_pnl == gross_pnl - total_fees, exact cash alignment."""
        acc = ShadowAccount(
            strategy_name="test_strat",
            initial_capital=Decimal("10000.0"),
            cost_model=self.cost_model,
            contract_multiplier=Decimal("0.001"),
            risk_fraction=0.01,
        )

        entry_raw = Decimal("50000.0")
        stop_dist = Decimal("500.0")

        acc._open_new_position(
            direction=Direction.LONG,
            raw_price=entry_raw,
            entry_time=self.base_time,
            stop_dist=stop_dist,
            tp_dist=Decimal("1000.0"),
        )

        pos = acc.open_position
        self.assertIsNotNone(pos)
        # 10 bps slippage on 50000 = 50. Slipped entry = 50050.0
        expected_slipped_entry = Decimal("50050.0")
        self.assertEqual(pos["entry_price"], expected_slipped_entry)

        # Exit with profit at raw 52000.0
        exit_raw = Decimal("52000.0")
        acc._close_position(
            exit_price=exit_raw,
            exit_time=self.base_time + timedelta(minutes=10),
            exit_reason="TP_TEST",
        )

        self.assertEqual(len(acc.trades), 1)
        trade = acc.trades[0]

        # Slipped exit for long = exit_raw * (1 - 0.0010) = 51948.0
        expected_slipped_exit = Decimal("51948.0")
        self.assertEqual(trade.exit_price, expected_slipped_exit)

        contracts = pos["contracts"]
        expected_gross = (expected_slipped_exit - expected_slipped_entry) * contracts * Decimal("0.001")
        self.assertEqual(trade.gross_pnl, expected_gross)
        self.assertGreater(trade.gross_pnl, Decimal("0"))

        # Exact mathematical identity: net_pnl == gross_pnl - total_fees
        self.assertEqual(trade.net_pnl, trade.gross_pnl - trade.fees)

        # Cash balance update must strictly equal initial + net_pnl
        self.assertEqual(acc.current_cash, acc.initial_capital + trade.net_pnl)
        self.assertEqual(acc.current_equity, acc.current_cash)
        self.assertTrue(trade.is_win)

    def test_long_losing_trade_exact_alignment(self) -> None:
        """Verify LONG losing trade: net_pnl == gross_pnl - total_fees, exact cash alignment."""
        acc = ShadowAccount(
            strategy_name="test_strat",
            initial_capital=Decimal("10000.0"),
            cost_model=self.cost_model,
            contract_multiplier=Decimal("0.001"),
            risk_fraction=0.01,
        )

        acc._open_new_position(
            direction=Direction.LONG,
            raw_price=Decimal("50000.0"),
            entry_time=self.base_time,
            stop_dist=Decimal("500.0"),
            tp_dist=Decimal("1000.0"),
        )

        # Exit with loss at raw 49000.0
        acc._close_position(
            exit_price=Decimal("49000.0"),
            exit_time=self.base_time + timedelta(minutes=10),
            exit_reason="SL_TEST",
        )

        trade = acc.trades[0]
        self.assertLess(trade.gross_pnl, Decimal("0"))
        self.assertLess(trade.net_pnl, trade.gross_pnl)  # Fees make loss worse
        self.assertEqual(trade.net_pnl, trade.gross_pnl - trade.fees)
        self.assertEqual(acc.current_cash, acc.initial_capital + trade.net_pnl)
        self.assertFalse(trade.is_win)

    def test_short_winning_trade_exact_alignment(self) -> None:
        """Verify SHORT winning trade: net_pnl == gross_pnl - total_fees."""
        acc = ShadowAccount(
            strategy_name="test_strat",
            initial_capital=Decimal("10000.0"),
            cost_model=self.cost_model,
            contract_multiplier=Decimal("0.001"),
            risk_fraction=0.01,
        )

        entry_raw = Decimal("50000.0")
        acc._open_new_position(
            direction=Direction.SHORT,
            raw_price=entry_raw,
            entry_time=self.base_time,
            stop_dist=Decimal("500.0"),
            tp_dist=Decimal("1000.0"),
        )

        pos = acc.open_position
        self.assertIsNotNone(pos)
        # Slipped short entry = 50000 * (1 - 0.0010) = 49950.0
        expected_slipped_entry = Decimal("49950.0")
        self.assertEqual(pos["entry_price"], expected_slipped_entry)

        # Exit with profit at raw 48000.0
        exit_raw = Decimal("48000.0")
        acc._close_position(
            exit_price=exit_raw,
            exit_time=self.base_time + timedelta(minutes=10),
            exit_reason="TP_SHORT_TEST",
        )

        trade = acc.trades[0]
        # Slipped short exit = 48000 * (1 + 0.0010) = 48048.0
        expected_slipped_exit = Decimal("48048.0")
        self.assertEqual(trade.exit_price, expected_slipped_exit)

        expected_gross = (expected_slipped_entry - expected_slipped_exit) * pos["contracts"] * Decimal("0.001")
        self.assertEqual(trade.gross_pnl, expected_gross)
        self.assertGreater(trade.gross_pnl, Decimal("0"))
        self.assertEqual(trade.net_pnl, trade.gross_pnl - trade.fees)
        self.assertEqual(acc.current_cash, acc.initial_capital + trade.net_pnl)
        self.assertTrue(trade.is_win)

    def test_short_losing_trade_exact_alignment(self) -> None:
        """Verify SHORT losing trade: net_pnl == gross_pnl - total_fees."""
        acc = ShadowAccount(
            strategy_name="test_strat",
            initial_capital=Decimal("10000.0"),
            cost_model=self.cost_model,
            contract_multiplier=Decimal("0.001"),
            risk_fraction=0.01,
        )

        acc._open_new_position(
            direction=Direction.SHORT,
            raw_price=Decimal("50000.0"),
            entry_time=self.base_time,
            stop_dist=Decimal("500.0"),
            tp_dist=Decimal("1000.0"),
        )

        # Exit with loss at raw 52000.0
        acc._close_position(
            exit_price=Decimal("52000.0"),
            exit_time=self.base_time + timedelta(minutes=10),
            exit_reason="SL_SHORT_TEST",
        )

        trade = acc.trades[0]
        self.assertLess(trade.gross_pnl, Decimal("0"))
        self.assertEqual(trade.net_pnl, trade.gross_pnl - trade.fees)
        self.assertEqual(acc.current_cash, acc.initial_capital + trade.net_pnl)
        self.assertFalse(trade.is_win)

    def test_breakeven_raw_price_slippage_friction(self) -> None:
        """Verify trade closed at identical raw price has gross_pnl < 0 due to slippage friction and net_pnl == gross - fees."""
        acc = ShadowAccount(
            strategy_name="test_strat",
            initial_capital=Decimal("10000.0"),
            cost_model=self.cost_model,
            contract_multiplier=Decimal("0.001"),
        )

        raw_price = Decimal("50000.0")
        acc._open_new_position(
            direction=Direction.LONG,
            raw_price=raw_price,
            entry_time=self.base_time,
            stop_dist=Decimal("500.0"),
            tp_dist=Decimal("1000.0"),
        )
        acc._close_position(
            exit_price=raw_price,
            exit_time=self.base_time + timedelta(minutes=5),
            exit_reason="BREAKEVEN_RAW",
        )

        trade = acc.trades[0]
        # Long entry = 50050, exit = 49950 -> gross_pnl is -100 * contracts * 0.001
        self.assertLess(trade.gross_pnl, Decimal("0"))
        self.assertEqual(trade.net_pnl, trade.gross_pnl - trade.fees)
        self.assertGreater(trade.slippage, Decimal("0"))
        # Verify slippage is NOT doubly subtracted
        self.assertNotEqual(trade.net_pnl, trade.gross_pnl - trade.fees - trade.slippage)

    def test_1000_randomized_trades_property_invariants(self) -> None:
        """Property-based generator: 1,000 randomized trades must preserve exact math invariants."""
        rng = random.Random(20261025)
        acc = ShadowAccount(
            strategy_name="stress_strat",
            initial_capital=Decimal("100000.0"),
            cost_model=self.cost_model,
            contract_multiplier=Decimal("0.001"),
            risk_fraction=0.01,
        )

        cumulative_net = Decimal("0.0")

        for i in range(1000):
            direction = Direction.LONG if rng.random() > 0.5 else Direction.SHORT
            raw_entry = Decimal(str(round(rng.uniform(20000.0, 90000.0), 2)))
            raw_exit = Decimal(str(round(raw_entry * Decimal(str(rng.uniform(0.85, 1.15))), 2)))
            stop_dist = Decimal(str(round(rng.uniform(200.0, 1000.0), 2)))

            acc._open_new_position(
                direction=direction,
                raw_price=raw_entry,
                entry_time=self.base_time + timedelta(minutes=i * 10),
                stop_dist=stop_dist,
                tp_dist=stop_dist * 2,
            )

            acc._close_position(
                exit_price=raw_exit,
                exit_time=self.base_time + timedelta(minutes=i * 10 + 5),
                exit_reason="STRESS_CLOSE",
            )

            trade = acc.trades[-1]

            # Invariant 1: net_pnl == gross_pnl - fees
            self.assertEqual(
                trade.net_pnl,
                trade.gross_pnl - trade.fees,
                f"Iteration {i}: trade net_pnl ({trade.net_pnl}) != gross_pnl - fees ({trade.gross_pnl - trade.fees})",
            )

            # Invariant 2: fees strictly positive
            self.assertGreater(trade.fees, Decimal("0"))

            # Invariant 3: win flag consistency
            self.assertEqual(trade.is_win, trade.net_pnl > Decimal("0"))

            cumulative_net += trade.net_pnl

            # Invariant 4: Cash matches initial + cumulative net PnL
            self.assertEqual(acc.current_cash, acc.initial_capital + cumulative_net)
            self.assertEqual(acc.current_equity, acc.current_cash)

        stats = acc.get_stats()
        self.assertEqual(stats.trade_count, 1000)
        self.assertEqual(stats.net_profit, cumulative_net)


class TestWebSocketWatchdogPongTimeoutClosure(unittest.IsolatedAsyncioTestCase):
    """Empirical challenge on WebSocket watchdog pong timeout and socket closure."""

    async def test_watchdog_pong_timeout_closes_async_socket(self) -> None:
        """Verify watchdog awaits coroutine socket.close() and disconnects."""
        ws = DeltaWebSocketClient(
            pong_timeout_s=0.02,
            ping_interval_s=0.01,
        )
        mock_socket = AsyncMock()
        ws._active_socket = mock_socket
        ws._active_sockets.add(mock_socket)
        ws._connected = True
        ws._running = True
        ws._last_pong_time = 1.0  # Far in past

        await ws._heartbeat_watchdog()

        mock_socket.close.assert_awaited()
        self.assertFalse(ws.is_connected)

    async def test_watchdog_pong_timeout_closes_sync_socket(self) -> None:
        """Verify watchdog handles synchronous socket.close() without error."""
        ws = DeltaWebSocketClient(
            pong_timeout_s=0.02,
            ping_interval_s=0.01,
        )
        mock_socket = MagicMock()
        mock_socket.close.return_value = None  # Sync return
        ws._active_socket = mock_socket
        ws._active_sockets.add(mock_socket)
        ws._connected = True
        ws._running = True
        ws._last_pong_time = 1.0

        await ws._heartbeat_watchdog()

        mock_socket.close.assert_called()
        self.assertFalse(ws.is_connected)

    async def test_watchdog_closes_all_active_sockets_in_set(self) -> None:
        """Verify all sockets in _active_sockets (e.g. pub + priv) are closed upon pong timeout."""
        ws = DeltaWebSocketClient(
            pong_timeout_s=0.02,
            ping_interval_s=0.01,
        )
        sock1 = AsyncMock()
        sock2 = AsyncMock()
        ws._active_socket = sock1
        ws._active_sockets.add(sock1)
        ws._active_sockets.add(sock2)
        ws._connected = True
        ws._running = True
        ws._last_pong_time = 1.0

        await ws._heartbeat_watchdog()

        sock1.close.assert_awaited()
        sock2.close.assert_awaited()
        self.assertFalse(ws.is_connected)

    async def test_watchdog_handles_socket_close_exception_gracefully(self) -> None:
        """Verify watchdog does not crash if socket.close() raises an exception."""
        ws = DeltaWebSocketClient(
            pong_timeout_s=0.02,
            ping_interval_s=0.01,
        )
        broken_socket = AsyncMock()
        broken_socket.close.side_effect = ConnectionResetError("Socket broken")
        ws._active_socket = broken_socket
        ws._active_sockets.add(broken_socket)
        ws._connected = True
        ws._running = True
        ws._last_pong_time = 1.0

        # Should not raise
        await ws._heartbeat_watchdog()

        self.assertFalse(ws.is_connected)

    async def test_watchdog_healthy_pong_stream_does_not_close(self) -> None:
        """Verify timely pongs keep the watchdog alive and connected."""
        ws = DeltaWebSocketClient(
            pong_timeout_s=0.05,
            ping_interval_s=0.01,
        )
        mock_socket = AsyncMock()
        ws._active_socket = mock_socket
        ws._active_sockets.add(mock_socket)
        ws._connected = True
        ws._running = True

        async def simulate_healthy_pongs():
            for _ in range(4):
                await asyncio.sleep(0.01)
                await ws.handle_message({"type": "pong"})
            ws._running = False  # Graceful exit

        await asyncio.gather(
            ws._heartbeat_watchdog(),
            simulate_healthy_pongs(),
        )

        mock_socket.close.assert_not_called()


class TestRegimeFilterDualThresholdHysteresis(unittest.TestCase):
    """Empirical challenge on RegimeFilter dual-threshold hysteresis boundary conditions."""

    def setUp(self) -> None:
        self.base_time = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)
        self.rf = RegimeFilter(
            trend_threshold=25.0,        # Enter TRENDING at >= 25.0
            trend_exit_threshold=20.0,   # Exit TRENDING at <= 20.0
            hysteresis_candles=3,
            chaotic_vol_ratio=2.5,
            chaotic_vol_ratio_exit=2.0,
        )
        self.candles = [make_candle(i, self.base_time) for i in range(40)]

    def test_adx_oscillating_between_21_and_24_in_ranging_never_flips(self) -> None:
        """Verify ADX oscillating between 21.0 and 24.0 does NOT flip RANGING to TRENDING."""
        self.assertEqual(self.rf.current_label, RegimeLabel.RANGING)

        oscillating_adx = [21.0, 24.0, 22.5, 23.8, 21.2, 24.5, 22.0, 24.9, 21.8, 23.5]
        with patch("app.signals.regime.adx") as mock_adx:
            for adx_val in oscillating_adx:
                mock_adx.return_value = adx_val
                reading = self.rf.evaluate(self.candles)
                self.assertEqual(
                    reading.label,
                    RegimeLabel.RANGING,
                    f"Flipped to {reading.label} on ADX={adx_val} while in RANGING!",
                )
                self.assertEqual(self.rf.current_label, RegimeLabel.RANGING)

    def test_adx_oscillating_between_21_and_24_in_trending_never_flips(self) -> None:
        """Verify ADX oscillating between 21.0 and 24.0 does NOT flip TRENDING to RANGING."""
        # 1. Drive into TRENDING via 3 candles of ADX >= 25.0
        with patch("app.signals.regime.adx") as mock_adx:
            mock_adx.return_value = 26.0
            for _ in range(3):
                reading = self.rf.evaluate(self.candles)
            self.assertEqual(reading.label, RegimeLabel.TRENDING)
            self.assertEqual(self.rf.current_label, RegimeLabel.TRENDING)

            # 2. Now oscillate ADX in deadband [21.0, 24.0]
            oscillating_adx = [24.0, 21.0, 23.5, 21.2, 24.8, 22.0, 24.5, 21.5, 23.0]
            for adx_val in oscillating_adx:
                mock_adx.return_value = adx_val
                reading = self.rf.evaluate(self.candles)
                self.assertEqual(
                    reading.label,
                    RegimeLabel.TRENDING,
                    f"Flipped to {reading.label} on ADX={adx_val} while in TRENDING!",
                )
                self.assertEqual(self.rf.current_label, RegimeLabel.TRENDING)

    def test_exact_boundary_conditions(self) -> None:
        """Verify behavior at exact threshold boundaries."""
        with patch("app.signals.regime.adx") as mock_adx:
            # At RANGING: ADX = 24.9999 -> Candidate is RANGING
            mock_adx.return_value = 24.9999
            for _ in range(5):
                r = self.rf.evaluate(self.candles)
                self.assertEqual(r.label, RegimeLabel.RANGING)

            # At RANGING: ADX = 25.0000 -> Candidate is TRENDING (requires 3 dwells)
            mock_adx.return_value = 25.0
            r1 = self.rf.evaluate(self.candles)
            self.assertEqual(r1.label, RegimeLabel.RANGING)  # Dwell 1
            r2 = self.rf.evaluate(self.candles)
            self.assertEqual(r2.label, RegimeLabel.RANGING)  # Dwell 2
            r3 = self.rf.evaluate(self.candles)
            self.assertEqual(r3.label, RegimeLabel.TRENDING) # Dwell 3 -> TRENDING!

            # At TRENDING: ADX = 20.0001 -> Candidate is still TRENDING
            mock_adx.return_value = 20.0001
            for _ in range(5):
                r = self.rf.evaluate(self.candles)
                self.assertEqual(r.label, RegimeLabel.TRENDING)

            # At TRENDING: ADX = 20.0000 -> Candidate is RANGING (requires 3 dwells)
            mock_adx.return_value = 20.0
            r1 = self.rf.evaluate(self.candles)
            self.assertEqual(r1.label, RegimeLabel.TRENDING) # Dwell 1
            r2 = self.rf.evaluate(self.candles)
            self.assertEqual(r2.label, RegimeLabel.TRENDING) # Dwell 2
            r3 = self.rf.evaluate(self.candles)
            self.assertEqual(r3.label, RegimeLabel.RANGING)  # Dwell 3 -> RANGING!

    def test_dwell_reset_on_intermittent_jitter(self) -> None:
        """Verify that intermittent jitter resets the dwell counter."""
        with patch("app.signals.regime.adx") as mock_adx:
            # 2 candles above threshold, then 1 candle dip
            mock_adx.return_value = 26.0
            self.rf.evaluate(self.candles) # Dwell 1
            self.rf.evaluate(self.candles) # Dwell 2
            self.assertEqual(self.rf.current_label, RegimeLabel.RANGING)

            mock_adx.return_value = 24.0 # Dip -> resets dwell
            self.rf.evaluate(self.candles)
            self.assertEqual(self.rf.current_label, RegimeLabel.RANGING)

            # Requires 3 brand new consecutive candles
            mock_adx.return_value = 26.0
            self.rf.evaluate(self.candles) # Dwell 1
            self.rf.evaluate(self.candles) # Dwell 2
            self.assertEqual(self.rf.current_label, RegimeLabel.RANGING)
            self.rf.evaluate(self.candles) # Dwell 3
            self.assertEqual(self.rf.current_label, RegimeLabel.TRENDING)

    def test_immediate_chaotic_preemption_and_hysteresis_exit(self) -> None:
        """Verify immediate entrance into CHAOTIC without dwell, and dwell-governed exit."""
        rf = RegimeFilter(
            chaotic_vol_ratio=2.5,
            chaotic_vol_ratio_exit=2.0,
            hysteresis_candles=3,
        )

        with patch("app.signals.regime.rolling_std_latest") as mock_std:
            # Make short_vol / realized_vol = 3.0 (> 2.5 enter)
            mock_std.side_effect = [0.03, 0.01]  # short_vol, realized_vol -> ratio = 3.0
            reading = rf.evaluate(self.candles)
            self.assertEqual(reading.label, RegimeLabel.CHAOTIC)
            self.assertEqual(rf.current_label, RegimeLabel.CHAOTIC)

            # Volatility cools to 2.2 (> 2.0 exit threshold): stays CHAOTIC
            mock_std.side_effect = [0.022, 0.01] # ratio = 2.2
            r_cool = rf.evaluate(self.candles)
            self.assertEqual(r_cool.label, RegimeLabel.CHAOTIC)

            # Volatility cools to 1.5 (<= 2.0 exit threshold): requires 3 dwells to exit
            mock_std.side_effect = [0.015, 0.01] # ratio 1.5 -> dwell 1
            self.assertEqual(rf.evaluate(self.candles).label, RegimeLabel.CHAOTIC)
            mock_std.side_effect = [0.015, 0.01] # ratio 1.5 -> dwell 2
            self.assertEqual(rf.evaluate(self.candles).label, RegimeLabel.CHAOTIC)
            mock_std.side_effect = [0.015, 0.01] # ratio 1.5 -> dwell 3 -> exits CHAOTIC!
            self.assertEqual(rf.evaluate(self.candles).label, RegimeLabel.RANGING)

    def test_5000_steps_property_random_walk(self) -> None:
        """Property-based generator: 5,000 steps of random ADX / Vol inputs never violate regime contract."""
        rng = random.Random(98765)
        rf = RegimeFilter(
            trend_threshold=25.0,
            trend_exit_threshold=20.0,
            hysteresis_candles=3,
            chaotic_vol_ratio=2.5,
            chaotic_vol_ratio_exit=2.0,
        )

        with patch("app.signals.regime.adx") as mock_adx, \
             patch("app.signals.regime.rolling_std_latest") as mock_std:

            for step in range(5000):
                sim_adx = rng.uniform(10.0, 40.0)
                sim_short_vol = rng.uniform(0.005, 0.05)
                sim_realized_vol = 0.01

                mock_adx.return_value = sim_adx
                mock_std.side_effect = [sim_short_vol, sim_realized_vol]

                reading = rf.evaluate(self.candles)

                self.assertIn(reading.label, [RegimeLabel.TRENDING, RegimeLabel.RANGING, RegimeLabel.CHAOTIC])
                self.assertTrue(0.0 <= reading.confidence <= 1.0)
                self.assertIn("adx", reading.metrics)
                self.assertIn("vol_ratio", reading.metrics)


if __name__ == "__main__":
    unittest.main()
