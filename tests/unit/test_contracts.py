"""Unit tests for domain contracts and state machine."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from app.core.contracts import Direction, MarketSnapshot, OrderIntent, RiskAction
from app.core.state import EngineState, EngineStateMachine, StateTransitionError


class TestContractsAndState(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_snapshot = MarketSnapshot(
            symbol="BTCUSD",
            timestamp=datetime.now(timezone.utc),
            best_bid=Decimal("65000.0"),
            best_ask=Decimal("65005.0"),
            bid_size=Decimal("10.0"),
            ask_size=Decimal("10.0"),
            mark_price=Decimal("65002.5"),
            spot_price=Decimal("65001.0"),
        )
        self.engine_state_machine = EngineStateMachine()

    def test_market_snapshot_spread_calculation(self) -> None:
        self.assertEqual(self.sample_snapshot.spread, Decimal("5.0"))
        self.assertGreater(float(self.sample_snapshot.spread_bps), 0.7)
        self.assertLess(float(self.sample_snapshot.spread_bps), 0.8)

    def test_engine_state_transitions(self) -> None:
        self.assertEqual(self.engine_state_machine.current_state, EngineState.INITIALISING)
        self.assertFalse(self.engine_state_machine.is_trading_allowed)

        self.engine_state_machine.transition(EngineState.WARMING_UP)
        self.assertEqual(self.engine_state_machine.current_state, EngineState.WARMING_UP)
        self.assertFalse(self.engine_state_machine.is_trading_allowed)

        self.engine_state_machine.transition(EngineState.RUNNING)
        self.assertEqual(self.engine_state_machine.current_state, EngineState.RUNNING)
        self.assertTrue(self.engine_state_machine.is_trading_allowed)

        # Emergency halt allowed from RUNNING
        self.engine_state_machine.transition(EngineState.HALTED)
        self.assertEqual(self.engine_state_machine.current_state, EngineState.HALTED)
        self.assertFalse(self.engine_state_machine.is_trading_allowed)

        # Cannot transition directly from HALTED to RUNNING (must reset to PAUSED first)
        with self.assertRaises(StateTransitionError):
            self.engine_state_machine.transition(EngineState.RUNNING)


if __name__ == "__main__":
    unittest.main()
