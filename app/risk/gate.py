"""Centralized Risk Gate.

ZONE: RED (HUMAN-AUTHORED POLICY)
Owner: Team Member B (See docs/ownership.md)
Reference: Section 9.5 of agent.md

The single mandatory checkpoint between a chosen signal and any order.
Evaluates rules in fixed order: hard rejections first, sizing second.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.contracts import (
    MarketSnapshot,
    OrderIntent,
    RiskAction,
    RiskVerdict,
    RuleEvaluationResult,
)
from app.core.state import EngineStateMachine
from app.risk.guards import (
    check_data_freshness,
    check_engine_state,
    check_protective_stop,
    check_spread,
)
from app.risk.kill_switch import KillSwitch
from app.risk.sizing import PositionSizer


class RiskGate:
    """Evaluates OrderIntents against multi-layer safety rules."""

    def __init__(
        self,
        state_machine: EngineStateMachine,
        kill_switch: KillSwitch,
        sizer: PositionSizer | None = None,
        max_spread_bps: float = 15.0,
        max_staleness_seconds: float = 5.0,
    ) -> None:
        self.state_machine = state_machine
        self.kill_switch = kill_switch
        self.sizer = sizer or PositionSizer()
        self.max_spread_bps = max_spread_bps
        self.max_staleness_seconds = max_staleness_seconds

    def evaluate_intent(
        self,
        intent: OrderIntent,
        snapshot: MarketSnapshot,
        current_equity: Decimal,
        allocator_weight: float = 1.0,
    ) -> RiskVerdict:
        """Run intent through full risk gate evaluation."""
        eval_results: list[RuleEvaluationResult] = []

        # 1. Hard Rejection: Engine State
        r_state = check_engine_state(self.state_machine.current_state)
        eval_results.append(r_state)
        if not r_state.passed:
            return RiskVerdict(
                action=RiskAction.REJECT,
                approved_risk_fraction=0.0,
                approved_contracts=0,
                evaluated_rules=eval_results,
                binding_rule=r_state.rule_name,
                rejection_reason=r_state.message,
            )

        # 2. Hard Rejection: Data Freshness
        from datetime import datetime, timezone
        staleness = snapshot.freshness_age_seconds(datetime.now(timezone.utc))
        r_freshness = check_data_freshness(staleness, self.max_staleness_seconds)
        eval_results.append(r_freshness)
        if not r_freshness.passed:
            return RiskVerdict(
                action=RiskAction.REJECT,
                approved_risk_fraction=0.0,
                approved_contracts=0,
                evaluated_rules=eval_results,
                binding_rule=r_freshness.rule_name,
                rejection_reason=r_freshness.message,
            )

        # 3. Hard Rejection: Spread
        r_spread = check_spread(snapshot, self.max_spread_bps)
        eval_results.append(r_spread)
        if not r_spread.passed:
            return RiskVerdict(
                action=RiskAction.REJECT,
                approved_risk_fraction=0.0,
                approved_contracts=0,
                evaluated_rules=eval_results,
                binding_rule=r_spread.rule_name,
                rejection_reason=r_spread.message,
            )

        # 4. Hard Rejection: Protective Stop Required
        r_stop = check_protective_stop(intent)
        eval_results.append(r_stop)
        if not r_stop.passed:
            return RiskVerdict(
                action=RiskAction.REJECT,
                approved_risk_fraction=0.0,
                approved_contracts=0,
                evaluated_rules=eval_results,
                binding_rule=r_stop.rule_name,
                rejection_reason=r_stop.message,
            )

        # Sizing Calculation
        contracts = self.sizer.calculate_contracts(
            intent=intent,
            current_equity=current_equity,
            entry_price=snapshot.mark_price,
            allocator_weight=allocator_weight,
        )

        if contracts < 1:
            return RiskVerdict(
                action=RiskAction.REJECT,
                approved_risk_fraction=0.0,
                approved_contracts=0,
                evaluated_rules=eval_results,
                binding_rule="MIN_CONTRACT_SIZE",
                rejection_reason="Computed position size is below 1 contract minimum.",
            )

        return RiskVerdict(
            action=RiskAction.APPROVE,
            approved_risk_fraction=intent.desired_risk_fraction * allocator_weight,
            approved_contracts=contracts,
            evaluated_rules=eval_results,
        )
