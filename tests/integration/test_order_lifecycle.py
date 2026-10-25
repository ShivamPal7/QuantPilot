"""Integration tests for order lifecycle: marketable limit orders, bracket attachment, fill tracking, and idempotency.

Per Section 11 of agent.md:
- Translates approved intents into marketable limit orders bounded by the touch.
- Attaches server-side bracket exits (stop-loss and take-profit).
- Enforces deterministic client order IDs for idempotency.
- Tracks order states and verifies position creation with bracket safeguards.
"""

from __future__ import annotations

from decimal import Decimal
import unittest

from app.core.contracts import (
    Direction,
    MarketSnapshot,
    OrderIntent,
    OrderRole,
    OrderState,
    RiskAction,
    RiskVerdict,
)
from app.execution.manager import ExecutionManager
from tests.fakes.fake_exchange import FakeExchange


class TestOrderLifecycle(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.fake_exchange = FakeExchange(initial_balance=Decimal("10000.0"))
        self.manager = ExecutionManager(exchange=self.fake_exchange)
        self.ticker = await self.fake_exchange.get_ticker("BTCUSD")

    async def test_marketable_limit_long_order_with_brackets(self) -> None:
        """Verify LONG entry order uses best_ask for limit price and computes correct SL/TP bracket prices."""
        intent = OrderIntent(
            decision_id="dec-long-001",
            strategy_name="trend_following",
            symbol="BTCUSD",
            direction=Direction.LONG,
            desired_risk_fraction=0.01,
            proposed_stop_distance=Decimal("150.0"),
            proposed_tp_distance=Decimal("300.0"),
        )
        verdict = RiskVerdict(
            action=RiskAction.APPROVE,
            approved_risk_fraction=0.01,
            approved_contracts=3,
        )

        record = await self.manager.execute_intent(intent, verdict, self.ticker)

        self.assertIsNotNone(record)
        self.assertEqual(record.symbol, "BTCUSD")
        self.assertEqual(record.role, OrderRole.ENTRY)
        self.assertEqual(record.side, "buy")
        self.assertEqual(record.size_contracts, 3)
        self.assertEqual(record.price, self.ticker.best_ask)
        self.assertEqual(record.state, OrderState.SUBMITTED)
        self.assertTrue(record.client_order_id.startswith("qp_tre_declong0_ent_"))

        # Verify position on FakeExchange
        positions = await self.fake_exchange.get_positions("BTCUSD")
        self.assertEqual(len(positions), 1)
        pos = positions[0]
        self.assertEqual(pos.side, "long")
        self.assertEqual(pos.contracts, 3)
        self.assertTrue(pos.has_active_bracket)

        # Verify bracket levels in FakeExchange
        brackets = self.fake_exchange.bracket_orders.get("BTCUSD")
        self.assertIsNotNone(brackets)
        expected_sl = self.ticker.best_ask - Decimal("150.0")
        expected_tp = self.ticker.best_ask + Decimal("300.0")
        self.assertEqual(brackets["stop_loss"], expected_sl)
        self.assertEqual(brackets["take_profit"], expected_tp)

    async def test_marketable_limit_short_order_with_brackets(self) -> None:
        """Verify SHORT entry order uses best_bid for limit price and computes correct SL/TP bracket prices."""
        intent = OrderIntent(
            decision_id="dec-short-002",
            strategy_name="mean_reversion",
            symbol="BTCUSD",
            direction=Direction.SHORT,
            desired_risk_fraction=0.01,
            proposed_stop_distance=Decimal("120.0"),
            proposed_tp_distance=Decimal("240.0"),
        )
        verdict = RiskVerdict(
            action=RiskAction.APPROVE,
            approved_risk_fraction=0.01,
            approved_contracts=2,
        )

        record = await self.manager.execute_intent(intent, verdict, self.ticker)

        self.assertIsNotNone(record)
        self.assertEqual(record.side, "sell")
        self.assertEqual(record.size_contracts, 2)
        self.assertEqual(record.price, self.ticker.best_bid)

        # Verify position on FakeExchange
        positions = await self.fake_exchange.get_positions("BTCUSD")
        self.assertEqual(len(positions), 1)
        pos = positions[0]
        self.assertEqual(pos.side, "short")
        self.assertEqual(pos.contracts, 2)
        self.assertTrue(pos.has_active_bracket)

        # Verify short bracket levels (SL above entry, TP below entry)
        brackets = self.fake_exchange.bracket_orders.get("BTCUSD")
        self.assertIsNotNone(brackets)
        expected_sl = self.ticker.best_bid + Decimal("120.0")
        expected_tp = self.ticker.best_bid - Decimal("240.0")
        self.assertEqual(brackets["stop_loss"], expected_sl)
        self.assertEqual(brackets["take_profit"], expected_tp)

    async def test_zero_approved_contracts_skipped(self) -> None:
        """When risk gate approves 0 contracts, manager returns None without submitting to exchange."""
        intent = OrderIntent(
            decision_id="dec-zero-003",
            strategy_name="trend_following",
            symbol="BTCUSD",
            direction=Direction.LONG,
            desired_risk_fraction=0.0,
            proposed_stop_distance=Decimal("100.0"),
        )
        verdict = RiskVerdict(
            action=RiskAction.REJECT,
            approved_risk_fraction=0.0,
            approved_contracts=0,
        )

        record = await self.manager.execute_intent(intent, verdict, self.ticker)
        self.assertIsNone(record)
        positions = await self.fake_exchange.get_positions()
        self.assertEqual(len(positions), 0)

    async def test_client_order_id_idempotency_prevents_duplicate_exchange_orders(self) -> None:
        """Duplicate execution of same intent with identical client order ID returns existing order."""
        intent = OrderIntent(
            decision_id="dec-idem-004",
            strategy_name="trend_following",
            symbol="BTCUSD",
            direction=Direction.LONG,
            desired_risk_fraction=0.01,
            proposed_stop_distance=Decimal("100.0"),
        )
        verdict = RiskVerdict(
            action=RiskAction.APPROVE,
            approved_risk_fraction=0.01,
            approved_contracts=1,
        )

        record1 = await self.manager.execute_intent(intent, verdict, self.ticker)
        self.assertIsNotNone(record1)

        # Submit duplicate order with same client_order_id
        duplicate_res = await self.fake_exchange.place_order(
            symbol=intent.symbol,
            size_contracts=verdict.approved_contracts,
            side="buy",
            price=self.ticker.best_ask,
            client_order_id=record1.client_order_id,
        )

        # Exchange returns existing order id rather than creating new order
        self.assertEqual(duplicate_res["id"], record1.exchange_order_id)
        # Order history count should remain 1 (no duplicate order added)
        matching_orders = [o for o in self.fake_exchange.order_history if o.get("client_order_id") == record1.client_order_id]
        self.assertEqual(len(matching_orders), 1)


if __name__ == "__main__":
    unittest.main()
