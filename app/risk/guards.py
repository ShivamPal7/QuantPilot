"""Hard rejection rules for the Risk Gate.

Per Section 9.5 of agent.md:
Rules evaluated in fixed order. The first failure immediately rejects the intent.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.contracts import MarketSnapshot, OrderIntent, RuleEvaluationResult
from app.core.state import EngineState


def check_engine_state(state: EngineState) -> RuleEvaluationResult:
    """Rule 1: Engine must be in RUNNING state."""
    passed = (state == EngineState.RUNNING)
    return RuleEvaluationResult(
        rule_name="ENGINE_STATE_RUNNING",
        passed=passed,
        observed_value=state.value,
        threshold_value=EngineState.RUNNING.value,
        message="Engine is not in RUNNING state" if not passed else "Engine running",
    )


def check_data_freshness(staleness_seconds: float, max_staleness: float = 5.0) -> RuleEvaluationResult:
    """Rule 2: Market data must be fresh and within threshold."""
    passed = staleness_seconds <= max_staleness
    return RuleEvaluationResult(
        rule_name="DATA_FRESHNESS",
        passed=passed,
        observed_value=round(staleness_seconds, 2),
        threshold_value=max_staleness,
        message=f"Data staleness ({staleness_seconds:.2f}s) exceeds limit ({max_staleness}s)" if not passed else "Data fresh",
    )


def check_spread(snapshot: MarketSnapshot, max_spread_bps: float = 15.0) -> RuleEvaluationResult:
    """Rule 3: Bid-ask spread must be within acceptable liquidity threshold."""
    spread_bps = float(snapshot.spread_bps)
    passed = spread_bps <= max_spread_bps
    return RuleEvaluationResult(
        rule_name="SPREAD_WITHIN_LIMIT",
        passed=passed,
        observed_value=round(spread_bps, 2),
        threshold_value=max_spread_bps,
        message=f"Spread ({spread_bps:.1f} bps) exceeds limit ({max_spread_bps} bps)" if not passed else "Spread acceptable",
    )


def check_protective_stop(intent: OrderIntent) -> RuleEvaluationResult:
    """Rule 4: Every entry intent must have a valid non-zero protective stop distance."""
    passed = intent.proposed_stop_distance > Decimal("0")
    return RuleEvaluationResult(
        rule_name="PROTECTIVE_STOP_REQUIRED",
        passed=passed,
        observed_value=float(intent.proposed_stop_distance),
        threshold_value=0.0,
        message="Intent lacks a valid non-zero protective stop" if not passed else "Protective stop present",
    )
