"""Integration test verifying full order placement and bracket attachment on FakeExchange."""

from __future__ import annotations

import unittest
from decimal import Decimal

from app.core.contracts import Direction, OrderIntent, RiskAction, RiskVerdict
from app.execution.manager import ExecutionManager
from tests.fakes.fake_exchange import FakeExchange


class TestFakeExchangeIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_execution_manager_with_fake_exchange(self) -> None:
        fake_exchange = FakeExchange()
        manager = ExecutionManager(exchange=fake_exchange)

        intent = OrderIntent(
            decision_id="dec-12345678",
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
            approved_contracts=5,
        )

        ticker = await fake_exchange.get_ticker("BTCUSD")
        record = await manager.execute_intent(intent=intent, verdict=verdict, snapshot=ticker)

        self.assertIsNotNone(record)
        self.assertEqual(record.size_contracts, 5)
        self.assertEqual(record.side, "buy")
        self.assertTrue(record.client_order_id.startswith("qp_tre_dec12345_ent_"))

        positions = await fake_exchange.get_positions("BTCUSD")
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].contracts, 5)
        self.assertTrue(positions[0].has_active_bracket)

    async def test_unbracketed_position_flip_clears_stale_brackets(self) -> None:
        ex = FakeExchange()
        # Open Long 2 with SL=64000
        await ex.place_order(
            "BTCUSD", 2, "buy", price=Decimal("65000.0"),
            bracket_stop_loss_price=Decimal("64000.0"),
            bracket_take_profit_price=Decimal("66000.0"),
        )
        # Flip position to Short 3 without brackets
        await ex.place_order("BTCUSD", 5, "sell", price=Decimal("65000.0"))

        pos = (await ex.get_positions("BTCUSD"))[0]
        self.assertEqual(pos.side, "short")
        self.assertEqual(pos.contracts, 3)
        self.assertFalse(pos.has_active_bracket)

        # Trigger market price check at 65000 - should not trigger stale long SL
        events = await ex.set_market_price(Decimal("65000.0"))
        self.assertEqual(len(events), 0, "Stale bracket was falsely triggered on flipped position")


if __name__ == "__main__":
    unittest.main()
