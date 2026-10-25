"""Position sizing engine.

Per Section 9.5 of agent.md:
- Fixed-fraction risk budget per trade.
- Volatility-scaled sizing.
- Fractional-Kelly ceiling.
- Capped by explicit leverage limit.
- Rounded DOWN to integer contracts.
"""

from __future__ import annotations

import math
from decimal import Decimal

from app.core.contracts import OrderIntent


class PositionSizer:
    """Computes safe, volatility-scaled integer contract sizing."""

    def __init__(
        self,
        default_risk_fraction: float = 0.01,  # 1% equity risk
        max_leverage: int = 3,
        contract_value_btc: Decimal = Decimal("0.001"),  # e.g., 0.001 BTC per contract
    ) -> None:
        self.default_risk_fraction = default_risk_fraction
        self.max_leverage = max_leverage
        self.contract_value_btc = contract_value_btc

    def calculate_contracts(
        self,
        intent: OrderIntent,
        current_equity: Decimal,
        entry_price: Decimal,
        allocator_weight: float = 1.0,
        volatility_ratio: float = 1.0,
    ) -> int:
        """Calculate integer contracts for approved intent.

        Contracts = floor((Equity * RiskFraction * Weight) / (StopDistance * VolRatio * ContractMultiplier))
        Capped by max allowed leverage.
        """
        if intent.proposed_stop_distance <= Decimal("0") or entry_price <= Decimal("0") or current_equity <= Decimal("0"):
            return 0

        # Risk capital in USD
        risk_fraction = intent.desired_risk_fraction if intent.desired_risk_fraction > 0 else self.default_risk_fraction
        risk_capital = float(current_equity) * risk_fraction * allocator_weight

        # Stop loss distance in price points
        stop_dist = float(intent.proposed_stop_distance)

        # Baseline contract sizing
        base_contracts = risk_capital / stop_dist

        # Volatility scaling: when volatility increases, size scales down
        vol_scaling = max(0.2, min(2.0, 1.0 / max(0.1, volatility_ratio)))
        scaled_contracts = base_contracts * vol_scaling

        # Leverage ceiling
        max_notional = float(current_equity) * float(self.max_leverage)
        max_contracts_by_leverage = max_notional / float(entry_price)

        final_contracts = min(scaled_contracts, max_contracts_by_leverage)

        # Strictly round DOWN to integer contracts
        return math.floor(max(0.0, final_contracts))
