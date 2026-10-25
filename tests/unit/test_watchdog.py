"""Unit tests for UnprotectedPositionWatchdog.

Per Section 10.6 of agent.md:
Watchdog monitors open positions and halts engine if any position lacks bracket protection.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import unittest

from app.core.contracts import PositionView
from app.core.state import EngineState, EngineStateMachine
from app.risk.kill_switch import KillSwitch
from app.risk.watchdog import UnprotectedPositionWatchdog
from tests.fakes.fake_exchange import FakeExchange


class TestWatchdog(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.state_machine = EngineStateMachine(initial_state=EngineState.RUNNING)
        self.kill_switch = KillSwitch(state_machine=self.state_machine)
        self.fake_exchange = FakeExchange(initial_balance=Decimal("10000.0"))
        self.watchdog = UnprotectedPositionWatchdog(
            exchange=self.fake_exchange,
            kill_switch=self.kill_switch,
            check_interval_seconds=0.01,
        )

    async def test_protected_positions_do_not_trigger_watchdog(self) -> None:
        """When positions have active brackets, watchdog passes without action."""
        pos = PositionView(
            symbol="BTCUSD",
            side="long",
            contracts=2,
            entry_price=Decimal("65000.0"),
            mark_price=Decimal("65000.0"),
            unrealized_pnl=Decimal("0.0"),
            leverage=3,
            liquidation_price=None,
            has_active_bracket=True,
            reconciled_at=datetime.now(timezone.utc),
        )
        self.fake_exchange.positions = [pos]

        unprotected = await self.watchdog.inspect_positions()
        self.assertEqual(len(unprotected), 0)
        self.assertFalse(self.kill_switch.is_active)
        self.assertEqual(self.state_machine.current_state, EngineState.RUNNING)

    async def test_unprotected_position_triggers_kill_switch_and_flattens(self) -> None:
        """Unprotected position triggers kill switch, halts engine, and flattens positions."""
        naked_pos = PositionView(
            symbol="BTCUSD",
            side="long",
            contracts=3,
            entry_price=Decimal("65000.0"),
            mark_price=Decimal("65000.0"),
            unrealized_pnl=Decimal("0.0"),
            leverage=3,
            liquidation_price=None,
            has_active_bracket=False,
            reconciled_at=datetime.now(timezone.utc),
        )
        self.fake_exchange.positions = [naked_pos]

        unprotected = await self.watchdog.inspect_positions()
        self.assertEqual(len(unprotected), 1)
        self.assertEqual(unprotected[0].symbol, "BTCUSD")
        self.assertTrue(self.kill_switch.is_active)
        self.assertEqual(self.state_machine.current_state, EngineState.HALTED)
        self.assertEqual(len(await self.fake_exchange.get_positions()), 0)

    async def test_zero_contracts_position_ignored(self) -> None:
        """Flat positions (0 contracts) do not trigger watchdog."""
        flat_pos = PositionView(
            symbol="BTCUSD",
            side="long",
            contracts=0,
            entry_price=Decimal("65000.0"),
            mark_price=Decimal("65000.0"),
            unrealized_pnl=Decimal("0.0"),
            leverage=3,
            liquidation_price=None,
            has_active_bracket=False,
            reconciled_at=datetime.now(timezone.utc),
        )
        self.fake_exchange.positions = [flat_pos]

        unprotected = await self.watchdog.inspect_positions()
        self.assertEqual(len(unprotected), 0)
        self.assertFalse(self.kill_switch.is_active)

    async def test_watchdog_run_loop_and_clean_stop(self) -> None:
        """Watchdog loop runs as background task and stops cleanly."""
        loop_task = asyncio.create_task(self.watchdog.run())
        await asyncio.sleep(0.03)
        self.assertTrue(self.watchdog._running)
        self.watchdog.stop()
        await asyncio.sleep(0.02)
        self.assertFalse(self.watchdog._running)
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    unittest.main()
