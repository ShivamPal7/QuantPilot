"""Milestone 2 Remediation Unit Tests.

Covers:
1. Double-slippage accounting fix in ShadowAccount.
2. WebSocket heartbeat watchdog active socket closure on pong timeout.
3. WebSocket public vs private endpoint channel routing.
4. Dual-threshold hysteresis and dwell timer in RegimeFilter.
5. Closed candle guard in CandleStore, TrendFollowingStrategy, MeanReversionStrategy, and RegimeFilter.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from unittest.mock import AsyncMock

from app.core.contracts import Candle, Direction, RegimeLabel
from app.data.store import CandleStore
from app.exchange.websocket import (
    DeltaWebSocketClient,
    PRIVATE_CHANNELS,
    PUBLIC_CHANNELS,
)
from app.shadow.account import ShadowAccount
from app.shadow.cost_model import ShadowCostModel
from app.signals.regime import RegimeFilter
from app.signals.reversion import MeanReversionStrategy
from app.signals.trend import TrendFollowingStrategy


def make_test_candle(
    minute_offset: int,
    base_time: datetime,
    open_p: Decimal = Decimal("65000.0"),
    high_p: Decimal = Decimal("65100.0"),
    low_p: Decimal = Decimal("64900.0"),
    close_p: Decimal = Decimal("65050.0"),
    is_closed: bool = True,
    volume: Decimal = Decimal("10.0"),
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


class TestMilestone2Remediation(unittest.IsolatedAsyncioTestCase):
    """Test suite verifying all Milestone 2 gate remediations."""

    def setUp(self) -> None:
        self.base_time = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)

    # -------------------------------------------------------------------------
    # 1. Double-Slippage Fix in ShadowAccount
    # -------------------------------------------------------------------------
    def test_shadow_account_no_double_slippage(self) -> None:
        """Verify that realized net PnL is gross_pnl - total_fees, without double-subtracting slippage."""
        # 10 bps slippage = 0.1% = 0.0010
        cost_model = ShadowCostModel(
            taker_fee_pct=Decimal("0.0005"),
            maker_fee_pct=Decimal("0.0002"),
            default_slippage_bps=Decimal("10.0"),
        )
        acc = ShadowAccount(
            strategy_name="trend_following",
            initial_capital=Decimal("10000.0"),
            cost_model=cost_model,
            contract_multiplier=Decimal("1.0"),
        )

        entry_raw = Decimal("100.0")
        entry_time = self.base_time

        # Open long position: raw price 100.0 -> slipped entry = 100.10
        acc._open_new_position(
            direction=Direction.LONG,
            raw_price=entry_raw,
            entry_time=entry_time,
            stop_dist=Decimal("10.0"),
            tp_dist=Decimal("20.0"),
        )
        pos = acc.open_position
        self.assertIsNotNone(pos)
        self.assertEqual(pos["entry_price"], Decimal("100.10000"))

        # Close long position at raw price 100.0 -> slipped exit = 99.90
        exit_time = entry_time + timedelta(minutes=5)
        acc._close_position(
            exit_price=Decimal("100.0"),
            exit_time=exit_time,
            exit_reason="TEST_CLOSE",
        )

        self.assertEqual(len(acc.trades), 1)
        trade = acc.trades[0]

        # Slipped gross_pnl = (99.90 - 100.10) * contracts * multiplier
        # For contracts = 100 (risk budget = 1000 / 10 = 100 contracts):
        # gross_pnl = -0.20 * 100 = -20.00
        # Slippage is embedded in fill prices (-0.10 entry + -0.10 exit = -0.20/contract).
        # net_pnl must be gross_pnl - total_fees, NOT gross_pnl - total_fees - total_slippage!
        self.assertEqual(trade.net_pnl, trade.gross_pnl - trade.fees)
        self.assertGreater(trade.slippage, Decimal("0"))  # Recorded for analytics
        self.assertEqual(acc.current_cash, acc.initial_capital + trade.net_pnl)

    # -------------------------------------------------------------------------
    # 2. WebSocket Watchdog Pong Timeout Socket Closure
    # -------------------------------------------------------------------------
    async def test_websocket_watchdog_closes_socket_on_pong_timeout(self) -> None:
        """Verify _heartbeat_watchdog explicitly closes the active socket upon pong timeout."""
        ws = DeltaWebSocketClient(
            pong_timeout_s=0.02,
            ping_interval_s=0.01,
        )
        mock_socket = AsyncMock()
        ws._active_socket = mock_socket
        ws._connected = True
        ws._running = True
        # Set last pong far in the past
        ws._last_pong_time = 1.0

        await ws._heartbeat_watchdog()

        # Check that socket close was awaited and connection marked disconnected
        mock_socket.close.assert_awaited_once()
        self.assertFalse(ws.is_connected)

    # -------------------------------------------------------------------------
    # 3. WebSocket Public vs Private Channel Routing
    # -------------------------------------------------------------------------
    def test_websocket_channel_routing_and_partitioning(self) -> None:
        """Verify private channels route to private_url and public channels route to public_url."""
        ws = DeltaWebSocketClient(
            public_url="wss://socket-ind-pub.testnet.deltaex.org",
            private_url="wss://socket-ind.testnet.deltaex.org",
        )

        # 1. Channel classification checks
        for ch in ["orders", "positions", "user_trades", "margins"]:
            self.assertEqual(ws.get_endpoint_for_channel(ch), ws.private_url)
            self.assertIn(ch, PRIVATE_CHANNELS)

        for ch in ["v2/ticker", "candlestick_1m", "l2_orderbook", "mark_price"]:
            self.assertEqual(ws.get_endpoint_for_channel(ch), ws.public_url)
            self.assertIn(ch, PUBLIC_CHANNELS)

        # 2. Subscriptions partitioning
        ws.subscribe("v2/ticker", ["BTCUSD"])
        ws.subscribe("candlestick_1m", ["BTCUSD"])
        ws.subscribe("orders", ["BTCUSD"])
        ws.subscribe("positions", ["BTCUSD"])

        pub_subs, priv_subs = ws.partition_subscriptions()
        pub_names = [s["name"] for s in pub_subs]
        priv_names = [s["name"] for s in priv_subs]

        self.assertEqual(set(pub_names), {"v2/ticker", "candlestick_1m"})
        self.assertEqual(set(priv_names), {"orders", "positions"})

    # -------------------------------------------------------------------------
    # 4. Dual-Threshold Hysteresis in RegimeFilter
    # -------------------------------------------------------------------------
    def test_regime_filter_dual_threshold_hysteresis(self) -> None:
        """Verify separate entry and exit thresholds combined with dwell time in RegimeFilter."""
        rf = RegimeFilter(
            trend_threshold=25.0,        # Enter TRENDING at ADX >= 25.0
            trend_exit_threshold=20.0,   # Exit TRENDING to RANGING at ADX <= 20.0
            hysteresis_candles=3,
            chaotic_vol_ratio=2.5,       # Enter CHAOTIC at vol_ratio > 2.5
            chaotic_vol_ratio_exit=2.0,  # Exit CHAOTIC at vol_ratio <= 2.0
        )
        self.assertEqual(rf.current_label, RegimeLabel.RANGING)

        # Generate base synthetic candles
        candles: list[Candle] = []
        for i in range(40):
            candles.append(make_test_candle(i, self.base_time))

        # Evaluate initially in flat market -> RANGING
        reading = rf.evaluate(candles)
        self.assertEqual(reading.label, RegimeLabel.RANGING)

        # 1. Test hysteresis zone between 20.0 and 25.0:
        # While currently RANGING, an ADX of 23.0 must NOT trigger TRENDING
        # Mock ADX calculation to simulate precise values
        with unittest.mock.patch("app.signals.regime.adx") as mock_adx:
            # ADX = 23.0 while in RANGING -> stays RANGING
            mock_adx.return_value = 23.0
            reading = rf.evaluate(candles)
            self.assertEqual(reading.label, RegimeLabel.RANGING)

            # ADX rises to 26.0 (>= 25.0 enter threshold)
            # Requires 3 candles dwell time
            mock_adx.return_value = 26.0
            r1 = rf.evaluate(candles)
            self.assertEqual(r1.label, RegimeLabel.RANGING)  # Dwell 1
            r2 = rf.evaluate(candles)
            self.assertEqual(r2.label, RegimeLabel.RANGING)  # Dwell 2
            r3 = rf.evaluate(candles)
            self.assertEqual(r3.label, RegimeLabel.TRENDING) # Dwell 3 -> Enter TRENDING!

            # 2. While in TRENDING, ADX dips to 22.0 (below enter 25.0, but above exit 20.0)
            # Dual-threshold hysteresis ensures it STAYS in TRENDING!
            mock_adx.return_value = 22.0
            r_dip1 = rf.evaluate(candles)
            self.assertEqual(r_dip1.label, RegimeLabel.TRENDING)
            r_dip2 = rf.evaluate(candles)
            self.assertEqual(r_dip2.label, RegimeLabel.TRENDING)

            # 3. ADX drops to 18.0 (<= 20.0 exit threshold)
            # Dwell time required to exit to RANGING
            mock_adx.return_value = 18.0
            r_exit1 = rf.evaluate(candles)
            self.assertEqual(r_exit1.label, RegimeLabel.TRENDING)  # Dwell 1
            r_exit2 = rf.evaluate(candles)
            self.assertEqual(r_exit2.label, RegimeLabel.TRENDING)  # Dwell 2
            r_exit3 = rf.evaluate(candles)
            self.assertEqual(r_exit3.label, RegimeLabel.RANGING)   # Dwell 3 -> Exit to RANGING!

    # -------------------------------------------------------------------------
    # 5. Closed Candle Guard in CandleStore and Strategies
    # -------------------------------------------------------------------------
    def test_closed_candle_guard_across_layers(self) -> None:
        """Verify unclosed forming candles are excluded from strategy evaluation."""
        store = CandleStore("BTCUSD", "1m", max_capacity=50)

        # Ingest 40 closed candles
        for i in range(40):
            store.add_candle(make_test_candle(i, self.base_time, is_closed=True))

        # Ingest 1 unclosed forming candle
        forming_candle = make_test_candle(40, self.base_time, close_p=Decimal("99999.0"), is_closed=False)
        store.add_candle(forming_candle)

        self.assertEqual(store.count, 41)
        # get_closed_candles returns only the 40 closed candles
        closed_only = store.get_closed_candles()
        self.assertEqual(len(closed_only), 40)
        self.assertTrue(all(c.is_closed for c in closed_only))

        # Test TrendFollowingStrategy ignores unclosed candle
        trend = TrendFollowingStrategy(fast_period=10, slow_period=20, min_history_candles=25)
        # Pass list ending in unclosed candle
        all_candles = store.get_candles()
        sig_all = trend.evaluate(all_candles)
        sig_closed = trend.evaluate(closed_only)
        # Numerical indicators and signal must be identical since unclosed candle was filtered out
        self.assertEqual(sig_all.direction, sig_closed.direction)
        self.assertEqual(sig_all.numeric_values, sig_closed.numeric_values)

        # Test MeanReversionStrategy ignores unclosed candle
        reversion = MeanReversionStrategy(lookback_period=20, min_history_candles=25)
        sig_rev_all = reversion.evaluate(all_candles)
        sig_rev_closed = reversion.evaluate(closed_only)
        self.assertEqual(sig_rev_all.direction, sig_rev_closed.direction)
        self.assertEqual(sig_rev_all.numeric_values, sig_rev_closed.numeric_values)


if __name__ == "__main__":
    unittest.main()
