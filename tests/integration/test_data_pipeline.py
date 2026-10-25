"""Integration tests for data pipeline: CandleStore contiguity checking, freshness monitoring, and WebSocket reconnection backfill.

Per Section 6.8 and 7.4 of agent.md:
- CandleStore enforces chronological ordering and detects sequence gaps.
- FreshnessTracker monitors feed latency (< 5.0s).
- WebSocket reconnection routine backfills missing candles to restore contiguity.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.core.contracts import Candle
from app.data.builder import CandleBuilder
from app.data.freshness import FreshnessTracker
from app.data.store import CandleStore
from tests.fakes.fake_exchange import FakeExchange


def make_candle(minute_offset: int, base_time: datetime, is_closed: bool = True) -> Candle:
    t_open = base_time + timedelta(minutes=minute_offset)
    t_close = base_time + timedelta(minutes=minute_offset + 1)
    return Candle(
        symbol="BTCUSD",
        timeframe="1m",
        open_time=t_open,
        close_time=t_close,
        open=Decimal("65000.0"),
        high=Decimal("65020.0"),
        low=Decimal("64980.0"),
        close=Decimal("65010.0"),
        volume=Decimal("10.0"),
        is_closed=is_closed,
    )


class TestDataPipeline(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.store = CandleStore(symbol="BTCUSD", timeframe="1m", max_capacity=10)
        self.freshness = FreshnessTracker(max_staleness_seconds=2.0)
        self.base_time = datetime(2026, 10, 25, 0, 0, 0, tzinfo=timezone.utc)

    def test_candle_store_contiguity_and_capacity(self) -> None:
        """Verify contiguous sequence passes and max capacity evicts oldest candle while preserving ordering."""
        # Add 5 ordered candles
        for i in range(5):
            self.store.add_candle(make_candle(i, self.base_time))

        self.assertEqual(self.store.count, 5)
        self.assertTrue(self.store.is_contiguous())

        # Exceed capacity (max_capacity = 10)
        for i in range(5, 15):
            self.store.add_candle(make_candle(i, self.base_time))

        self.assertEqual(self.store.count, 10)
        self.assertTrue(self.store.is_contiguous())
        # First candle in store should be offset 5
        candles = self.store.get_candles()
        self.assertEqual(candles[0].open_time, self.base_time + timedelta(minutes=5))
        self.assertEqual(candles[-1].open_time, self.base_time + timedelta(minutes=14))

    def test_candle_store_replaces_forming_candle(self) -> None:
        """Adding a candle with identical open_time updates the latest candle in place."""
        initial = make_candle(0, self.base_time, is_closed=False)
        self.store.add_candle(initial)
        self.assertEqual(self.store.count, 1)
        self.assertFalse(self.store.get_candles()[0].is_closed)

        # Updated closed candle for same minute
        final_closed = make_candle(0, self.base_time, is_closed=True)
        self.store.add_candle(final_closed)
        self.assertEqual(self.store.count, 1)
        self.assertTrue(self.store.get_candles()[0].is_closed)

    def test_candle_store_detects_non_contiguous_sequence(self) -> None:
        """Out of order or backwards timestamps violate contiguity."""
        c0 = make_candle(0, self.base_time)
        c2 = make_candle(2, self.base_time)
        c1_late = make_candle(1, self.base_time)

        self.store.add_candle(c0)
        self.store.add_candle(c2)
        # Directly appending backwards timestamp (c1 after c2)
        self.store._candles.append(c1_late)

        self.assertFalse(self.store.is_contiguous())

    def test_freshness_tracker_behavior(self) -> None:
        """Verify freshness flag state and custom thresholding."""
        self.freshness.record_update()
        self.assertTrue(self.freshness.is_fresh())
        self.assertLess(self.freshness.staleness_seconds, 1.0)

        # Check with strict 0.0000001s threshold
        self.assertFalse(self.freshness.is_fresh(custom_threshold_seconds=0.0000001))

    async def test_websocket_stream_reconnect_and_backfill(self) -> None:
        """Simulate WebSocket disconnect, feed gap, and historical backfill via FakeExchange."""
        fake_exchange = FakeExchange()
        store = CandleStore(symbol="BTCUSD", timeframe="1m", max_capacity=100)

        # Ingest initial 3 candles
        for i in range(3):
            store.add_candle(make_candle(i, self.base_time))
        self.assertEqual(store.count, 3)

        # Simulate stream drop: minutes 3, 4, 5 are missed.
        # Now live stream reconnects at minute 6:
        reconnected_candle = make_candle(6, self.base_time)

        # Detect gap between last stored (minute 2) and incoming (minute 6)
        last_stored = store.get_candles()[-1]
        gap_detected = (reconnected_candle.open_time - last_stored.close_time).total_seconds() > 0
        self.assertTrue(gap_detected)

        # Backfill missing candles (minutes 3 to 5) from exchange
        start_ts = int(last_stored.close_time.timestamp())
        end_ts = int(reconnected_candle.open_time.timestamp())
        missing_candles = await fake_exchange.get_candles(
            symbol="BTCUSD",
            resolution="1m",
            start_time_s=start_ts,
            end_time_s=end_ts,
        )

        self.assertGreater(len(missing_candles), 0)

        # Ingest backfilled candles followed by reconnected candle
        for c in missing_candles:
            store.add_candle(c)
        store.add_candle(reconnected_candle)

        # Sequence must now be intact and contiguous
        self.assertTrue(store.is_contiguous())
        self.assertGreaterEqual(store.count, 5)

    def test_candle_builder_tick_aggregation_and_emission(self) -> None:
        """Verify CandleBuilder aggregates ticks within 1m bucket and emits closed candle on boundary."""
        emitted_events = []
        builder = CandleBuilder(
            symbol="BTCUSD",
            timeframe="1m",
            on_candle_closed=lambda evt: emitted_events.append(evt),
            max_age_s=5.0,
        )

        t0 = datetime(2026, 10, 25, 12, 0, 5, tzinfo=timezone.utc)
        t1 = datetime(2026, 10, 25, 12, 0, 25, tzinfo=timezone.utc)
        t2 = datetime(2026, 10, 25, 12, 0, 55, tzinfo=timezone.utc)

        # 3 ticks within 12:00:00 - 12:01:00 bucket
        res0 = builder.push_tick(price=Decimal("65000.0"), volume=Decimal("1.5"), timestamp=t0)
        self.assertIsNone(res0)
        self.assertFalse(builder.is_stale(max_age_s=5.0, now=t0))

        res1 = builder.push_tick(price=Decimal("65050.0"), volume=Decimal("2.0"), timestamp=t1)
        self.assertIsNone(res1)

        res2 = builder.push_tick(price=Decimal("64980.0"), volume=Decimal("0.5"), timestamp=t2)
        self.assertIsNone(res2)

        # Check current forming candle
        curr = builder.current_candle
        self.assertIsNotNone(curr)
        self.assertEqual(curr.open, Decimal("65000.0"))
        self.assertEqual(curr.high, Decimal("65050.0"))
        self.assertEqual(curr.low, Decimal("64980.0"))
        self.assertEqual(curr.close, Decimal("64980.0"))
        self.assertEqual(curr.volume, Decimal("4.0"))
        self.assertFalse(curr.is_closed)
        self.assertEqual(len(emitted_events), 0)

        # Next tick at 12:01:02 crosses into new minute bucket
        t3 = datetime(2026, 10, 25, 12, 1, 2, tzinfo=timezone.utc)
        closed_candle = builder.push_tick(price=Decimal("65010.0"), volume=Decimal("1.0"), timestamp=t3)

        self.assertIsNotNone(closed_candle)
        self.assertTrue(closed_candle.is_closed)
        self.assertEqual(closed_candle.open, Decimal("65000.0"))
        self.assertEqual(closed_candle.close, Decimal("64980.0"))
        self.assertEqual(len(emitted_events), 1)
        self.assertEqual(emitted_events[0].candle.close, Decimal("64980.0"))

    def test_candle_builder_staleness_tracking(self) -> None:
        """Verify is_stale returns True when elapsed time exceeds max_age_s."""
        builder = CandleBuilder(symbol="BTCUSD", timeframe="1m", max_age_s=5.0)
        self.assertTrue(builder.is_stale())

        t0 = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)
        builder.push_tick(price=Decimal("65000.0"), volume=Decimal("1.0"), timestamp=t0)

        # 3 seconds later: fresh
        t_fresh = datetime(2026, 10, 25, 12, 0, 3, tzinfo=timezone.utc)
        self.assertFalse(builder.is_stale(now=t_fresh))

        # 6 seconds later: stale
        t_stale = datetime(2026, 10, 25, 12, 0, 6, tzinfo=timezone.utc)
        self.assertTrue(builder.is_stale(now=t_stale))

    async def test_websocket_client_subscriptions_and_heartbeat(self) -> None:
        """Verify DeltaWebSocketClient constructs correct channels, auth, and processes messages."""
        from app.exchange.websocket import DeltaWebSocketClient

        ws = DeltaWebSocketClient(
            public_url="wss://socket-ind-pub.testnet.deltaex.org",
            private_url="wss://socket-ind.testnet.deltaex.org",
            api_key="test_key",
            api_secret="test_secret",
            target_env="testnet",
        )

        # 1. Check default public subscriptions
        pub_msgs = ws.subscribe_public_default(["BTCUSD"])
        self.assertEqual(len(pub_msgs), 4)
        ch_names = [m["payload"]["channels"][0]["name"] for m in pub_msgs]
        self.assertIn("v2/ticker", ch_names)
        self.assertIn("candlestick_1m", ch_names)
        self.assertIn("l2_orderbook", ch_names)
        self.assertIn("mark_price", ch_names)

        # 2. Check default private subscriptions
        priv_msgs = ws.subscribe_private_default(["BTCUSD"])
        self.assertEqual(len(priv_msgs), 3)
        priv_names = [m["payload"]["channels"][0]["name"] for m in priv_msgs]
        self.assertIn("orders", priv_names)
        self.assertIn("positions", priv_names)
        self.assertIn("user_trades", priv_names)

        # 3. Check auth message structure
        auth = ws.build_auth_message(timestamp_s=1700000000)
        self.assertEqual(auth["type"], "auth")
        self.assertEqual(auth["payload"]["api-key"], "test_key")
        self.assertEqual(auth["payload"]["timestamp"], "1700000000")
        self.assertIsNotNone(auth["payload"]["signature"])

        # 4. Check message dispatch and heartbeat pong handling
        received_messages = []
        ws.add_handler(lambda msg: received_messages.append(msg))

        # Send normal market data message
        await ws.handle_message({"type": "v2/ticker", "symbol": "BTCUSD", "mark_price": "65000.0"})
        self.assertEqual(len(received_messages), 1)

        # Send heartbeat pong message (should update _last_pong_time and not dispatch to user handler)
        init_pong_time = ws._last_pong_time
        await ws.handle_message({"type": "pong"})
        self.assertGreaterEqual(ws._last_pong_time, init_pong_time)
        self.assertEqual(len(received_messages), 1)


if __name__ == "__main__":
    unittest.main()
