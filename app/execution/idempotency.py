"""Idempotency management and client order ID generation.

Per Section 9.6 of agent.md:
Client order ID composed of: project prefix, strategy code, decision ID, role, attempt.
"""

from __future__ import annotations


def generate_client_order_id(
    strategy_name: str,
    decision_id: str,
    role: str = "ent",
    attempt: int = 1,
    prefix: str = "qp",
) -> str:
    """Construct an idempotent client order ID.

    Format: qp_<strat_3letter>_<decision_8char>_<role>_<attempt>
    Example: qp_trn_a1b2c3d4_ent_1
    """
    strat_code = strategy_name[:3].lower()
    short_decision = decision_id.replace("-", "")[:8]
    role_code = role[:3].lower()
    return f"{prefix}_{strat_code}_{short_decision}_{role_code}_{attempt}"
