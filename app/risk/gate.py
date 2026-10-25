"""Centralized Risk Gate.

ZONE: RED (HUMAN-AUTHORED POLICY)
Owner: Team Member B (See docs/ownership.md)
Reference: Section 9.5 of agent.md

The single mandatory checkpoint between a chosen signal and any order.
Evaluates rules in fixed order: hard rejections first, sizing second.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.core.contracts import (
    MarketSnapshot,
    OrderIntent,
    RiskAction,
    RiskVerdict,
    RuleEvaluationResult,
)
from app.core.state import EngineStateMachine
from app.risk.drawdown import DrawdownLadder
from app.risk.guards import (
    check_data_freshness,
    check_engine_state,
    check_protective_stop,
    check_spread,
)
from app.risk.kill_switch import KillSwitch
from app.risk.sizing import PositionSizer


class RiskGate:
    """Evaluates OrderIntents against multi-layer safety rules in strict ordered sequence."""

    def __init__(
        self,
        state_machine: EngineStateMachine,
        kill_switch: KillSwitch,
        sizer: PositionSizer | None = None,
        drawdown_ladder: DrawdownLadder | None = None,
        max_spread_bps: float = 15.0,
        max_staleness_seconds: float = 5.0,
    ) -> None:
        self.state_machine = state_machine
        self.kill_switch = kill_switch
        self.sizer = sizer or PositionSizer()
        self.drawdown_ladder = drawdown_ladder
        self.max_spread_bps = max_spread_bps
        self.max_staleness_seconds = max_staleness_seconds

    def evaluate_intent(
        self,
        intent: OrderIntent,
        snapshot: MarketSnapshot,
        current_equity: Decimal,
        allocator_weight: float = 1.0,
        volatility_ratio: float = 1.0,
    ) -> RiskVerdict:
        """Run intent through full risk gate evaluation."""
        eval_results: list[RuleEvaluationResult] = []

        # 1. Hard Rejection: Engine State RUNNING
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

        # 2. Hard Rejection: Data Freshness (< 5.0s)
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

        # 3. Hard Rejection: Bid-Ask Spread (< 15 bps)
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

        # 4. Hard Rejection: Protective Stop Required (> 0)
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

        # 5. Hard Rejection: Drawdown Ladder Halt Check
        effective_weight = allocator_weight
        if self.drawdown_ladder is not None:
            r_dd = self.drawdown_ladder.check_drawdown_guard(current_equity)
            eval_results.append(r_dd)
            if not r_dd.passed:
                # Trigger emergency kill switch if drawdown ladder breached halt rung
                if not self.kill_switch.is_active:
                    self.kill_switch.trigger(
                        source="drawdown_ladder",
                        reason=r_dd.message,
                        details={"current_equity": float(current_equity)},
                    )
                return RiskVerdict(
                    action=RiskAction.REJECT,
                    approved_risk_fraction=0.0,
                    approved_contracts=0,
                    evaluated_rules=eval_results,
                    binding_rule=r_dd.rule_name,
                    rejection_reason=r_dd.message,
                )

            # Apply drawdown ladder sizing multiplier (e.g., 0.5 for 50% size tier)
            _, dd_mult, _ = self.drawdown_ladder.evaluate_rung(current_equity)
            effective_weight *= dd_mult

        # Sizing Calculation: volatility-scaled integer contracts factoring in contract multiplier
        contracts = self.sizer.calculate_contracts(
            intent=intent,
            current_equity=current_equity,
            entry_price=snapshot.mark_price,
            allocator_weight=effective_weight,
            volatility_ratio=volatility_ratio,
        )

        if contracts < 1:
            return RiskVerdict(
                action=RiskAction.REJECT,
                approved_risk_fraction=0.0,
                approved_contracts=0,
                evaluated_rules=eval_results,
                binding_rule="INSUFFICIENT_CAPITAL_FOR_MIN_SIZE",
                rejection_reason="INSUFFICIENT_CAPITAL_FOR_MIN_SIZE: Computed position size is below 1 contract minimum.",
            )

        # Check if size was resized down
        unscaled_contracts = self.sizer.calculate_contracts(
            intent=intent,
            current_equity=current_equity,
            entry_price=snapshot.mark_price,
            allocator_weight=1.0,
            volatility_ratio=1.0,
        )
        action = RiskAction.RESIZE if contracts < unscaled_contracts else RiskAction.APPROVE

        return RiskVerdict(
            action=action,
            approved_risk_fraction=intent.desired_risk_fraction * effective_weight,
            approved_contracts=contracts,
            evaluated_rules=eval_results,
        )
