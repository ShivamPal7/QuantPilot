"""Deterministic plain-language decision narrative generator.

ZONE: RED (HUMAN-AUTHORED ONLY)
Owner: Team Member C (See docs/ownership.md)
Reference: Section 9.7 of agent.md

Generates 2 to 5 sentences from structured fields using deterministic templates.
No LLM generation is used here, ensuring complete reproducibility and explainability.
"""

from __future__ import annotations

from app.core.contracts import AllocationDecision, RegimeReading, RiskAction, RiskVerdict


class NarrativeGenerator:
    """Produces deterministic plain-language explanations for journal records."""

    @staticmethod
    def generate(
        symbol: str,
        regime: RegimeReading,
        allocation: AllocationDecision,
        verdict: RiskVerdict,
    ) -> str:
        """Construct explanatory narrative sentences."""
        # Sentence 1: Market Regime context
        s1 = f"Market regime for {symbol} was classified as {regime.label.value}."

        # Sentence 2: Allocator verdict
        if allocation.selected_strategy:
            s2 = f"Strategy '{allocation.selected_strategy}' was selected with weight {allocation.weight:.2f} ({allocation.reason})."
        else:
            s2 = f"No strategy was allocated risk ({allocation.reason})."

        # Sentence 3: Risk Gate action
        if verdict.action == RiskAction.APPROVE:
            s3 = f"Risk gate APPROVED execution for {verdict.approved_contracts} contracts with exchange-side bracket protection."
        elif verdict.action == RiskAction.RESIZE:
            s3 = f"Risk gate RESIZED position to {verdict.approved_contracts} contracts due to volatility scaling."
        else:
            reason = verdict.rejection_reason or verdict.binding_rule or "Safety rule triggered"
            s3 = f"Risk gate REJECTED the trade intent: {reason}."

        return f"{s1} {s2} {s3}"
