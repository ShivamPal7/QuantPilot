"""Integration tests for state reconciliation comparing exchange truth against local state.

Per Section 11.4 of agent.md:
The exchange is the ultimate source of truth for positions and orders.
Local state is a cache that is continuously reconciled.
Orphan positions and external closures must be accurately synchronized.
"""

from __future__ import annotations

from decimal import Decimal
import unittest

from app.execution.reconciliation import Reconciler
from tests.fakes.fake_exchange import FakeExchange


class TestReconciliation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.fake_exchange = FakeExchange(initial_balance=Decimal("10000.0"))
        self.reconciler = Reconciler(exchange=self.fake_exchange)

    async def test_initial_sync_flat_account(self) -> None:
        """Initial reconciliation on startup establishes baseline truth with zero active positions."""
        self.assertFalse(self.reconciler.is_initial_sync_done)
        self.assertEqual(len(self.reconciler.last_reconciled_positions), 0)

        mismatches = await self.reconciler.reconcile()

        self.assertTrue(self.reconciler.is_initial_sync_done)
        self.assertEqual(len(self.reconciler.last_reconciled_positions), 0)
        self.assertEqual(len(mismatches), 0)

    async def test_reconciliation_discovers_and_adopts_exchange_positions(self) -> None:
        """Positions existing or opened on exchange are discovered and synchronized into local state."""
        # Open position directly on exchange
        await self.fake_exchange.place_order(
            symbol="BTCUSD",
            size_contracts=5,
            side="buy",
            price=Decimal("65000.0"),
            bracket_stop_loss_price=Decimal("64800.0"),
        )

        mismatches = await self.reconciler.reconcile()

        self.assertEqual(len(self.reconciler.last_reconciled_positions), 1)
        pos = self.reconciler.last_reconciled_positions[0]
        self.assertEqual(pos.symbol, "BTCUSD")
        self.assertEqual(pos.contracts, 5)
        self.assertEqual(pos.side, "long")
        self.assertTrue(pos.has_active_bracket)

    async def test_reconciliation_detects_position_closure_after_bracket_trigger(self) -> None:
        """When an exchange bracket triggers and flattens a position, reconciliation syncs the flat state."""
        # Open 3 contracts with stop loss at 64800
        await self.fake_exchange.place_order(
            symbol="BTCUSD",
            size_contracts=3,
            side="buy",
            price=Decimal("65000.0"),
            bracket_stop_loss_price=Decimal("64800.0"),
        )
        await self.reconciler.reconcile()
        self.assertEqual(len(self.reconciler.last_reconciled_positions), 1)

        # Market price drops to 64700, triggering stop-loss on exchange
        await self.fake_exchange.set_market_price(new_bid=Decimal("64700.0"))
        exchange_positions = await self.fake_exchange.get_positions()
        self.assertEqual(len(exchange_positions), 0)

        # Next reconciliation pass syncs the closed position
        await self.reconciler.reconcile()
        self.assertEqual(len(self.reconciler.last_reconciled_positions), 0)

    async def test_reconciliation_handles_exchange_error_gracefully(self) -> None:
        """Network or rate-limit error during reconciliation does not crash the loop."""
        self.fake_exchange.simulate_rate_limit = True

        # Reconcile attempt should handle exception gracefully
        mismatches = await self.reconciler.reconcile()
        self.assertEqual(len(mismatches), 0)
        # Prior state is preserved
        self.assertFalse(self.reconciler.is_initial_sync_done)


if __name__ == "__main__":
    unittest.main()
