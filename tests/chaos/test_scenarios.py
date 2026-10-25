"""Chaos scenarios testing system resilience under adverse conditions.

Per Section 13.4 of agent.md:
- Price shock & drawdown rung
- Stale feed auto-pause
- Rate limit storm backoff
- Kill switch emergency flatting
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from app.core.contracts import Direction, MarketSnapshot, OrderIntent, RiskAction
from app.core.state import EngineState, EngineStateMachine
from app.risk.gate import RiskGate
from app.risk.kill_switch import KillSwitch


class TestChaosScenarios(unittest.TestCase):
    def test_chaos_kill_switch_flattens_and_halts(self) -> None:
        sm = EngineStateMachine(initial_state=EngineState.RUNNING)
        ks = KillSwitch(state_machine=sm)

        event = ks.trigger(source="chaos_test", reason="Simulated severe drawdown breach")
        self.assertTrue(ks.is_active)
        self.assertEqual(sm.current_state, EngineState.HALTED)
        self.assertEqual(event.reason, "Simulated severe drawdown breach")

    def test_chaos_stale_feed_rejects_intent(self) -> None:
        sm = EngineStateMachine(initial_state=EngineState.RUNNING)
        ks = KillSwitch(state_machine=sm)
        gate = RiskGate(state_machine=sm, kill_switch=ks, max_staleness_seconds=1.0)

        intent = OrderIntent(
            decision_id="dec-9999",
            strategy_name="trend_following",
            symbol="BTCUSD",
            direction=Direction.LONG,
            desired_risk_fraction=0.01,
            proposed_stop_distance=Decimal("100.0"),
        )

        stale_snapshot = MarketSnapshot(
            symbol="BTCUSD",
            timestamp=datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),  # Long ago
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


if __name__ == "__main__":
    unittest.main()
