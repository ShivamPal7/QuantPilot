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


def parse_client_order_id(client_order_id: str) -> dict[str, str | int]:
    """Parse a client order ID into its components."""
    parts = client_order_id.split("_")
    if len(parts) >= 5:
        return {
            "prefix": parts[0],
            "strat_code": parts[1],
            "short_decision": parts[2],
            "role": parts[3],
            "attempt": int(parts[4]) if parts[4].isdigit() else 1,
        }
    return {"raw": client_order_id}
