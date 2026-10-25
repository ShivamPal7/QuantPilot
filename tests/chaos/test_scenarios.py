"""Chaos scenarios testing system resilience under adverse conditions.

Per Section 13.4 of agent.md and PROJECT.md:
All 7 required chaos and resiliency scenarios:
1. Scenario 1: Price shock (sudden 10% wick against position).
2. Scenario 2: Stale market data feed (> 5.0s elapsed).
3. Scenario 3: WebSocket stream loss.
4. Scenario 4: Order uncertainty (timeout/in-flight resolution).
5. Scenario 5: Unprotected position watchdog.
6. Scenario 6: Rate limit storm (429 backoff).
7. Scenario 7: Engine restart with open position.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.core.contracts import (
    Direction,
    MarketSnapshot,
    OrderIntent,
    OrderRecord,
    OrderState,
    PositionView,
    RiskAction,
    RiskVerdict,
)
from app.core.state import EngineState, EngineStateMachine
from app.data.freshness import FreshnessTracker
from app.exchange.errors import RateLimitExceededError
from app.exchange.rate_limiter import RateLimitAccountant
from app.execution.manager import ExecutionManager
from app.execution.reconciliation import Reconciler
from app.risk.gate import RiskGate
from app.risk.kill_switch import KillSwitch
from app.risk.sizing import PositionSizer
from app.risk.watchdog import UnprotectedPositionWatchdog
from tests.fakes.fake_exchange import FakeExchange


class TestChaosScenarios(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.state_machine = EngineStateMachine(initial_state=EngineState.RUNNING)
        self.kill_switch = KillSwitch(state_machine=self.state_machine)
        self.fake_exchange = FakeExchange(initial_balance=Decimal("10000.0"))

    # =========================================================================
    # Scenario 1: Price Shock (sudden 10% wick against position)
    # =========================================================================
    async def test_chaos_scenario_1_price_shock_triggers_bracket_stop(self) -> None:
        """Inject sudden 10% adverse price drop; verify bracket stop-loss executes on FakeExchange and limits loss."""
        # 1. Establish long position at 65000 with stop-loss at 63500 (1500 points distance)
        order = await self.fake_exchange.place_order(
            symbol="BTCUSD",
            size_contracts=2,
            side="buy",
            price=Decimal("65000.0"),
            bracket_stop_loss_price=Decimal("63500.0"),
            bracket_take_profit_price=Decimal("68000.0"),
        )
        self.assertEqual(order["state"], "filled")
        positions = await self.fake_exchange.get_positions("BTCUSD")
        self.assertEqual(len(positions), 1)
        self.assertTrue(positions[0].has_active_bracket)

        # 2. Sudden 10% flash crash wick down to 58,500 (well below stop-loss of 63,500)
        triggered = await self.fake_exchange.set_market_price(new_bid=Decimal("58500.0"))

        # 3. Verify stop-loss triggered and closed position
        self.assertEqual(len(triggered), 1)
        self.assertEqual(triggered[0]["role"], "BRACKET_STOP")
        self.assertEqual(triggered[0]["reason"], "STOP_LOSS_TRIGGERED")

        # Position must be flat on exchange
        positions_after = await self.fake_exchange.get_positions("BTCUSD")
        self.assertEqual(len(positions_after), 0)

        # Drawdown occurred but was bounded by stop exit
        # Realized PnL is (58500 - 65000) * 2 contracts * 0.001 = -13.0 USDT
        expected_pnl = (Decimal("58500.0") - Decimal("65000.0")) * 2 * Decimal("0.001")
        self.assertEqual(Decimal(triggered[0]["realized_pnl"]), expected_pnl)
        self.assertEqual(self.fake_exchange.balance, Decimal("10000.0") + expected_pnl)
        self.assertEqual(self.fake_exchange.balance, Decimal("9987.0"))

    # =========================================================================
    # Scenario 2: Stale Market Data Feed (> 5.0s elapsed)
    # =========================================================================
    async def test_chaos_scenario_2_stale_feed_rejects_intent(self) -> None:
        """Market data timestamp older than 5.0s must be rejected by Risk Gate with DATA_FRESHNESS."""
        gate = RiskGate(
            state_machine=self.state_machine,
            kill_switch=self.kill_switch,
            max_staleness_seconds=5.0,
        )

        intent = OrderIntent(
            decision_id="dec-stale-002",
            strategy_name="trend_following",
            symbol="BTCUSD",
            direction=Direction.LONG,
            desired_risk_fraction=0.01,
            proposed_stop_distance=Decimal("100.0"),
        )

        stale_time = datetime.now(timezone.utc) - timedelta(seconds=12.0)  # 12s old (> 5.0s)
        stale_snapshot = MarketSnapshot(
            symbol="BTCUSD",
            timestamp=stale_time,
            best_bid=Decimal("65000.0"),
            best_ask=Decimal("65005.0"),
            bid_size=Decimal("10.0"),
            ask_size=Decimal("10.0"),
            mark_price=Decimal("65002.5"),
            spot_price=Decimal("65001.0"),
        )

        verdict = gate.evaluate_intent(
            intent=intent,
            snapshot=stale_snapshot,
            current_equity=Decimal("10000.0"),
        )

        self.assertEqual(verdict.action, RiskAction.REJECT)
        self.assertEqual(verdict.binding_rule, "DATA_FRESHNESS")

    # =========================================================================
    # Scenario 3: WebSocket Stream Loss
    # =========================================================================
    async def test_chaos_scenario_3_websocket_stream_loss_detection(self) -> None:
        """Simulate WebSocket disconnect; FreshnessTracker flags feed stall and pauses entries."""
        tracker = FreshnessTracker(max_staleness_seconds=0.05)
        tracker.record_update()
        self.assertTrue(tracker.is_fresh())

        # Stream drops: sleep past timeout without updates
        await asyncio.sleep(0.08)

        self.assertFalse(tracker.is_fresh())
        self.assertGreater(tracker.staleness_seconds, 0.05)

        # If data is stale, risk gate must reject new entries
        gate = RiskGate(
            state_machine=self.state_machine,
            kill_switch=self.kill_switch,
            max_staleness_seconds=0.05,
        )
        snapshot = await self.fake_exchange.get_ticker("BTCUSD")
        # Simulate stalled snapshot timestamp
        stalled_snapshot = MarketSnapshot(
            symbol=snapshot.symbol,
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=1.0),
            best_bid=snapshot.best_bid,
            best_ask=snapshot.best_ask,
            bid_size=snapshot.bid_size,
            ask_size=snapshot.ask_size,
            mark_price=snapshot.mark_price,
            spot_price=snapshot.spot_price,
        )

        intent = OrderIntent(
            decision_id="dec-ws-loss",
            strategy_name="trend_following",
            symbol="BTCUSD",
            direction=Direction.LONG,
            desired_risk_fraction=0.01,
            proposed_stop_distance=Decimal("100.0"),
        )
        verdict = gate.evaluate_intent(intent, stalled_snapshot, Decimal("10000.0"))
        self.assertEqual(verdict.action, RiskAction.REJECT)
        self.assertEqual(verdict.binding_rule, "DATA_FRESHNESS")

    # =========================================================================
    # Scenario 4: Order Uncertainty (timeout / in-flight resolution)
    # =========================================================================
    async def test_chaos_scenario_4_order_uncertainty_resolution(self) -> None:
        """Simulate network timeout during order submission; verify in-flight resolution and no double placement."""
        manager = ExecutionManager(exchange=self.fake_exchange)
        verdict = RiskVerdict(
            action=RiskAction.APPROVE,
            approved_risk_fraction=0.01,
            approved_contracts=1,
        )
        ticker = await self.fake_exchange.get_ticker("BTCUSD")

        # Case A: Network timeout before order reaches exchange matching engine
        self.fake_exchange.simulate_timeout = True
        intent_dropped = OrderIntent(
            decision_id="dec-timeout-004",
            strategy_name="trend_following",
            symbol="BTCUSD",
            direction=Direction.LONG,
            desired_risk_fraction=0.01,
            proposed_stop_distance=Decimal("100.0"),
        )
        record_dropped = await manager.execute_intent(intent_dropped, verdict, ticker)
        # ExecutionManager queried in-flight status and confirmed order never reached exchange
        self.assertIsNone(record_dropped)
        self.assertIsNone(await self.fake_exchange.get_order_by_client_id("qp_tre_dectimeo_ent_1"))

        # Case B: Order reaches exchange matching engine, but response drops on network return
        self.fake_exchange.simulate_timeout = False
        self.fake_exchange.simulate_timeout_post_placement = True
        intent_reached = OrderIntent(
            decision_id="dec2-timeout-hit",
            strategy_name="trend_following",
            symbol="BTCUSD",
            direction=Direction.LONG,
            desired_risk_fraction=0.01,
            proposed_stop_distance=Decimal("100.0"),
        )
        # Submission encounters timeout on response; ExecutionManager reconciles in-flight by client_order_id
        record_adopted = await manager.execute_intent(intent_reached, verdict, ticker)
        self.assertIsNotNone(record_adopted)
        self.assertEqual(record_adopted.client_order_id, "qp_tre_dec2time_ent_1")
        self.assertEqual(record_adopted.state, OrderState.FILLED)

        # Verify idempotency prevents double placement on subsequent retry
        self.fake_exchange.simulate_timeout_post_placement = False
        retry_record = await manager.execute_intent(intent_reached, verdict, ticker)
        self.assertIsNotNone(retry_record)
        self.assertEqual(retry_record.client_order_id, "qp_tre_dec2time_ent_1")
        # Position count remains exactly 1 contract without double placement
        positions = await self.fake_exchange.get_positions("BTCUSD")
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].contracts, 1)

    # =========================================================================
    # Scenario 5: Unprotected Position Watchdog
    # =========================================================================
    async def test_chaos_scenario_5_unprotected_position_watchdog(self) -> None:
        """Inject open position without bracket protection; watchdog detects missing bracket and triggers kill switch."""
        watchdog = UnprotectedPositionWatchdog(
            exchange=self.fake_exchange,
            kill_switch=self.kill_switch,
        )

        # Inject naked/unprotected position directly on exchange
        unprotected_pos = PositionView(
            symbol="BTCUSD",
            side="long",
            contracts=4,
            entry_price=Decimal("65000.0"),
            mark_price=Decimal("65000.0"),
            unrealized_pnl=Decimal("0.0"),
            leverage=3,
            liquidation_price=None,
            has_active_bracket=False,  # UNPROTECTED!
        )
        self.fake_exchange.positions = [unprotected_pos]

        # Watchdog inspection routine runs genuine production class
        unprotected = await watchdog.inspect_positions()
        self.assertEqual(len(unprotected), 1)
        self.assertEqual(unprotected[0].symbol, "BTCUSD")

        # Safety safeguards verified
        self.assertTrue(self.kill_switch.is_active)
        self.assertEqual(self.state_machine.current_state, EngineState.HALTED)
        # Position closed and flattened on exchange
        self.assertEqual(len(await self.fake_exchange.get_positions()), 0)

    # =========================================================================
    # Scenario 6: Rate Limit Storm (429 backoff)
    # =========================================================================
    async def test_chaos_scenario_6_rate_limit_storm_backoff(self) -> None:
        """Simulate HTTP 429 rate limit storm; verify exchange raises RateLimitExceededError and RateLimitAccountant backs off."""
        rate_limiter = RateLimitAccountant(max_quota=20000, window_seconds=300.0)
        self.assertTrue(rate_limiter.can_make_request())
        self.assertFalse(rate_limiter.is_in_backoff())

        self.fake_exchange.simulate_rate_limit = True

        # 1. Direct operations fail with RateLimitExceededError
        with self.assertRaises(RateLimitExceededError):
            await self.fake_exchange.place_order(
                symbol="BTCUSD",
                size_contracts=1,
                side="buy",
            )

        with self.assertRaises(RateLimitExceededError):
            await self.fake_exchange.get_positions()

        # 2. Reconciler encounters 429, triggers backoff on RateLimitAccountant
        reconciler = Reconciler(exchange=self.fake_exchange, rate_limiter=rate_limiter)
        mismatches = await reconciler.reconcile()
        self.assertEqual(len(mismatches), 0)

        # 3. Explicitly verify rate limiter entered backoff state and suppresses calls
        self.assertTrue(rate_limiter.is_in_backoff())
        self.assertFalse(rate_limiter.can_make_request())
        self.assertFalse(rate_limiter.is_within_budget())
        self.assertGreater(rate_limiter.backoff_remaining_seconds(), 0.0)

    # =========================================================================
    # Scenario 7: Engine Restart with Open Position
    # =========================================================================
    async def test_chaos_scenario_7_engine_restart_with_open_position(self) -> None:
        """Engine restarts while exchange holds open position; startup reconciliation adopts and validates bracket."""
        # Exchange already holds open 2-contract long position from prior session
        await self.fake_exchange.place_order(
            symbol="BTCUSD",
            size_contracts=2,
            side="buy",
            price=Decimal("65000.0"),
            bracket_stop_loss_price=Decimal("64800.0"),
            bracket_take_profit_price=Decimal("66000.0"),
        )

        # Brand new engine instance cold-starts
        fresh_state_machine = EngineStateMachine(initial_state=EngineState.INITIALISING)
        fresh_reconciler = Reconciler(exchange=self.fake_exchange)

        # Cold-start reconciliation pass
        self.assertFalse(fresh_reconciler.is_initial_sync_done)
        await fresh_reconciler.reconcile()
        self.assertTrue(fresh_reconciler.is_initial_sync_done)

        # Adopted position verified
        self.assertEqual(len(fresh_reconciler.last_reconciled_positions), 1)
        adopted = fresh_reconciler.last_reconciled_positions[0]
        self.assertEqual(adopted.symbol, "BTCUSD")
        self.assertEqual(adopted.contracts, 2)
        self.assertEqual(adopted.side, "long")
        self.assertTrue(adopted.has_active_bracket)

        # Engine safely transitions from INITIALISING -> WARMING_UP -> RUNNING with state aligned
        fresh_state_machine.transition(EngineState.WARMING_UP, reason="Startup reconciliation complete")
        fresh_state_machine.transition(EngineState.RUNNING, reason="All systems aligned with exchange")
        self.assertEqual(fresh_state_machine.current_state, EngineState.RUNNING)


if __name__ == "__main__":
    unittest.main()
