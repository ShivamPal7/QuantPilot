"""Unit tests for Centralized Risk Gate: ordered evaluation, hard rejection guards, and drawdown ladder.

Per Section 10 of agent.md:
- Mandatory single checkpoint before any order execution.
- Strict ordered evaluation:
  1. Engine State (RUNNING)
  2. Data Freshness (< 5.0s)
  3. Bid-Ask Spread (< 15 bps)
  4. Protective Stop (non-zero stop distance)
  5. Minimum contract size (>= 1 contract)
- Drawdown ladder scaling and halt protection.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.core.contracts import (
    Direction,
    MarketSnapshot,
    OrderIntent,
    RiskAction,
)
from app.core.state import EngineState, EngineStateMachine
from app.risk.gate import RiskGate
from app.risk.guards import (
    check_data_freshness,
    check_engine_state,
    check_protective_stop,
    check_spread,
)
from app.risk.kill_switch import KillSwitch
from app.risk.sizing import PositionSizer


class TestRiskGate(unittest.TestCase):
    def setUp(self) -> None:
        self.state_machine = EngineStateMachine(initial_state=EngineState.RUNNING)
        self.kill_switch = KillSwitch(state_machine=self.state_machine)
        self.sizer = PositionSizer(default_risk_fraction=0.01, max_leverage=3)
        self.gate = RiskGate(
            state_machine=self.state_machine,
            kill_switch=self.kill_switch,
            sizer=self.sizer,
            max_spread_bps=15.0,
            max_staleness_seconds=5.0,
        )

    def _create_fresh_snapshot(
        self,
        best_bid: Decimal = Decimal("65000.0"),
        best_ask: Decimal = Decimal("65005.0"),
        age_seconds: float = 0.5,
    ) -> MarketSnapshot:
        now = datetime.now(timezone.utc)
        ts = now - timedelta(seconds=age_seconds)
        return MarketSnapshot(
            symbol="BTCUSD",
            timestamp=ts,
            best_bid=best_bid,
            best_ask=best_ask,
            bid_size=Decimal("10.0"),
            ask_size=Decimal("10.0"),
            mark_price=(best_bid + best_ask) / Decimal("2"),
            spot_price=best_bid,
        )

    def _create_intent(
        self,
        stop_dist: Decimal = Decimal("100.0"),
        risk_fraction: float = 0.01,
    ) -> OrderIntent:
        return OrderIntent(
            decision_id="dec-risk-001",
            strategy_name="trend_following",
            symbol="BTCUSD",
            direction=Direction.LONG,
            desired_risk_fraction=risk_fraction,
            proposed_stop_distance=stop_dist,
        )

    def test_guard_unit_functions(self) -> None:
        """Individually test each pure guard check function."""
        # check_engine_state
        self.assertTrue(check_engine_state(EngineState.RUNNING).passed)
        self.assertFalse(check_engine_state(EngineState.PAUSED).passed)
        self.assertFalse(check_engine_state(EngineState.HALTED).passed)

        # check_data_freshness
        self.assertTrue(check_data_freshness(staleness_seconds=1.5, max_staleness=5.0).passed)
        self.assertTrue(check_data_freshness(staleness_seconds=5.0, max_staleness=5.0).passed)
        self.assertFalse(check_data_freshness(staleness_seconds=5.1, max_staleness=5.0).passed)

        # check_spread (65005 - 65000) / 65000 * 10000 = ~0.77 bps (< 15.0 bps)
        snapshot_tight = self._create_fresh_snapshot(best_bid=Decimal("65000.0"), best_ask=Decimal("65005.0"))
        self.assertTrue(check_spread(snapshot_tight, max_spread_bps=15.0).passed)

        # Spread of 150 points on 65000 = ~23.07 bps (> 15.0 bps)
        snapshot_wide = self._create_fresh_snapshot(best_bid=Decimal("65000.0"), best_ask=Decimal("65150.0"))
        self.assertFalse(check_spread(snapshot_wide, max_spread_bps=15.0).passed)

        # check_protective_stop
        valid_stop_intent = self._create_intent(stop_dist=Decimal("50.0"))
        zero_stop_intent = self._create_intent(stop_dist=Decimal("0.0"))
        self.assertTrue(check_protective_stop(valid_stop_intent).passed)
        self.assertFalse(check_protective_stop(zero_stop_intent).passed)

    def test_ordered_evaluation_early_exit_rule1_engine_state(self) -> None:
        """Rule 1: Engine state non-RUNNING halts evaluation immediately."""
        self.state_machine.transition(EngineState.PAUSED, reason="Operator paused")
        snapshot = self._create_fresh_snapshot()
        intent = self._create_intent()

        verdict = self.gate.evaluate_intent(intent, snapshot, Decimal("10000.0"))
        self.assertEqual(verdict.action, RiskAction.REJECT)
        self.assertEqual(verdict.binding_rule, "ENGINE_STATE_RUNNING")
        self.assertEqual(len(verdict.evaluated_rules), 1)

    def test_ordered_evaluation_early_exit_rule2_data_freshness(self) -> None:
        """Rule 2: Stale data (> 5.0s) fails at rule 2 without evaluating spread or stops."""
        snapshot = self._create_fresh_snapshot(age_seconds=10.0)
        intent = self._create_intent()

        verdict = self.gate.evaluate_intent(intent, snapshot, Decimal("10000.0"))
        self.assertEqual(verdict.action, RiskAction.REJECT)
        self.assertEqual(verdict.binding_rule, "DATA_FRESHNESS")
        self.assertEqual(len(verdict.evaluated_rules), 2)
        self.assertTrue(verdict.evaluated_rules[0].passed)  # Engine state passed
        self.assertFalse(verdict.evaluated_rules[1].passed)  # Freshness failed

    def test_ordered_evaluation_early_exit_rule3_spread(self) -> None:
        """Rule 3: Wide spread fails at rule 3 without evaluating stops."""
        # 65000 to 65200 is ~30.7 bps > 15 bps limit
        snapshot = self._create_fresh_snapshot(best_bid=Decimal("65000.0"), best_ask=Decimal("65200.0"))
        intent = self._create_intent()

        verdict = self.gate.evaluate_intent(intent, snapshot, Decimal("10000.0"))
        self.assertEqual(verdict.action, RiskAction.REJECT)
        self.assertEqual(verdict.binding_rule, "SPREAD_WITHIN_LIMIT")
        self.assertEqual(len(verdict.evaluated_rules), 3)

    def test_ordered_evaluation_early_exit_rule4_protective_stop(self) -> None:
        """Rule 4: Missing or zero protective stop fails at rule 4."""
        snapshot = self._create_fresh_snapshot()
        intent = self._create_intent(stop_dist=Decimal("0.0"))

        verdict = self.gate.evaluate_intent(intent, snapshot, Decimal("10000.0"))
        self.assertEqual(verdict.action, RiskAction.REJECT)
        self.assertEqual(verdict.binding_rule, "PROTECTIVE_STOP_REQUIRED")
        self.assertEqual(len(verdict.evaluated_rules), 4)

    def test_rejection_on_sub_contract_size(self) -> None:
        """When all guards pass but equity/stop yields < 1 contract, reject with INSUFFICIENT_CAPITAL_FOR_MIN_SIZE."""
        snapshot = self._create_fresh_snapshot()
        # Equity $10, risk 1% = $0.10, stop distance 500 -> 500 * 0.001 = $0.50 risk per contract -> 0.10 / 0.50 = 0.2 contracts -> floor is 0
        intent = self._create_intent(stop_dist=Decimal("500.0"))
        verdict = self.gate.evaluate_intent(intent, snapshot, current_equity=Decimal("10.0"))

        self.assertEqual(verdict.action, RiskAction.REJECT)
        self.assertEqual(verdict.binding_rule, "INSUFFICIENT_CAPITAL_FOR_MIN_SIZE")
        self.assertEqual(verdict.approved_contracts, 0)

    def test_happy_path_approval(self) -> None:
        """All guards pass and size >= 1 contract -> APPROVE."""
        snapshot = self._create_fresh_snapshot(best_bid=Decimal("1000.0"), best_ask=Decimal("1001.0"))
        # Equity $10,000, risk 1% = $100, stop 25 -> 100 / (25 * 0.001) = 4,000 contracts
        intent = self._create_intent(stop_dist=Decimal("25.0"))
        verdict = self.gate.evaluate_intent(intent, snapshot, current_equity=Decimal("10000.0"))

        self.assertEqual(verdict.action, RiskAction.APPROVE)
        self.assertIsNone(verdict.binding_rule)
        self.assertEqual(verdict.approved_contracts, 4000)
        self.assertAlmostEqual(verdict.approved_risk_fraction, 0.01)

    def test_drawdown_ladder_behavior(self) -> None:
        """Verify drawdown ladder: normal -> scaled down -> halted via kill switch."""
        initial_capital = Decimal("10000.0")
        snapshot = self._create_fresh_snapshot(best_bid=Decimal("1000.0"), best_ask=Decimal("1001.0"))
        intent = self._create_intent(stop_dist=Decimal("20.0"))

        # 1. Normal state (0% drawdown): full weight 1.0 -> 100 / (20 * 0.001) = 5,000 contracts
        v_normal = self.gate.evaluate_intent(
            intent, snapshot, current_equity=initial_capital, allocator_weight=1.0
        )
        self.assertEqual(v_normal.action, RiskAction.APPROVE)
        self.assertEqual(v_normal.approved_contracts, 5000)

        # 2. Drawdown ladder rung 1 (3% drawdown): equity $9,700, allocator halves weight to 0.5
        equity_tier1 = Decimal("9700.0")
        v_tier1 = self.gate.evaluate_intent(
            intent, snapshot, current_equity=equity_tier1, allocator_weight=0.5
        )
        self.assertEqual(v_tier1.action, RiskAction.RESIZE)
        self.assertLess(v_tier1.approved_contracts, v_normal.approved_contracts)
        # Risk capital = 9700 * 0.01 * 0.5 = 48.5; 48.5 / (20 * 0.001) = 2425 contracts
        self.assertEqual(v_tier1.approved_contracts, 2425)

        # 3. Drawdown ladder rung 2 (severe breach, 8% drawdown): triggers kill switch
        equity_tier2 = Decimal("9200.0")
        self.kill_switch.trigger(
            source="drawdown_ladder",
            reason="Cumulative drawdown 8.0% breached maximum safe loss threshold",
            details={"initial_capital": 10000.0, "current_equity": 9200.0},
        )
        self.assertTrue(self.kill_switch.is_active)
        self.assertEqual(self.state_machine.current_state, EngineState.HALTED)

        # Once halted, risk gate rejects any new intents at Rule 1
        v_halted = self.gate.evaluate_intent(intent, snapshot, current_equity=equity_tier2)
        self.assertEqual(v_halted.action, RiskAction.REJECT)
        self.assertEqual(v_halted.binding_rule, "ENGINE_STATE_RUNNING")

    def test_drawdown_ladder_class_rungs(self) -> None:
        """Verify DrawdownLadder evaluates all tiers: NORMAL, COOLING_OFF, REDUCED_50, HALT."""
        from app.risk.drawdown import DrawdownLadder, DrawdownTier

        ladder = DrawdownLadder(
            initial_capital=Decimal("10000.0"),
            cooling_off_pct=0.02,
            reduced_size_pct=0.04,
            halt_pct=0.06,
            kill_switch=self.kill_switch,
        )

        # 1. Normal (1% drawdown < 2%)
        tier, mult, rung = ladder.evaluate_rung(Decimal("9900.0"))
        self.assertEqual(tier, DrawdownTier.NORMAL)
        self.assertEqual(mult, 1.0)
        self.assertEqual(rung, 1)

        # 2. Cooling off (3% drawdown >= 2% and < 4%)
        tier, mult, rung = ladder.evaluate_rung(Decimal("9700.0"))
        self.assertEqual(tier, DrawdownTier.COOLING_OFF)
        self.assertEqual(mult, 0.75)
        self.assertEqual(rung, 2)

        # 3. 50% Size (5% drawdown >= 4% and < 6%)
        tier, mult, rung = ladder.evaluate_rung(Decimal("9500.0"))
        self.assertEqual(tier, DrawdownTier.REDUCED_50)
        self.assertEqual(mult, 0.5)
        self.assertEqual(rung, 3)

        # 4. Halt (7% drawdown >= 6%)
        tier, mult, rung = ladder.evaluate_rung(Decimal("9300.0"))
        self.assertEqual(tier, DrawdownTier.HALT)
        self.assertEqual(mult, 0.0)
        self.assertEqual(rung, 4)
        self.assertTrue(self.kill_switch.is_active)
        self.assertEqual(self.state_machine.current_state, EngineState.HALTED)

    def test_kill_switch_exchange_flattening(self) -> None:
        """Kill switch trigger invokes exchange cancel_all and close_all via reduce-only."""
        from tests.fakes.fake_exchange import FakeExchange
        import asyncio

        async def _test() -> None:
            fake = FakeExchange(initial_balance=Decimal("10000.0"))
            await fake.place_order(
                symbol="BTCUSD",
                size_contracts=3,
                side="buy",
                price=Decimal("65000.0"),
                bracket_stop_loss_price=Decimal("64500.0"),
            )
            self.assertEqual(len(await fake.get_positions()), 1)

            ks = KillSwitch(state_machine=self.state_machine, exchange=fake)
            results = await ks.flatten()

            self.assertTrue(results["positions_closed"])
            self.assertEqual(len(await fake.get_positions()), 0)

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()

