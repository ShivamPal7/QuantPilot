"""Shadow cost model for realistic paper fills.

Per Section 9.4 of agent.md:
Accounts for exchange taker/maker fees and realistic slippage.
Can update slippage allowance based on median realized fills from real testnet orders.
"""

from __future__ import annotations

from decimal import Decimal


class ShadowCostModel:
    """Calculates transaction friction (fees + slippage) for virtual accounts."""

    def __init__(
        self,
        taker_fee_pct: Decimal | float = Decimal("0.0005"),  # 0.05%
        maker_fee_pct: Decimal | float = Decimal("0.0002"),  # 0.02%
        default_slippage_bps: Decimal | float = Decimal("10.0"),  # 10 bps
    ) -> None:
        self.taker_fee_pct = Decimal(str(taker_fee_pct)) if not isinstance(taker_fee_pct, Decimal) else taker_fee_pct
        self.maker_fee_pct = Decimal(str(maker_fee_pct)) if not isinstance(maker_fee_pct, Decimal) else maker_fee_pct
        self.slippage_bps = Decimal(str(default_slippage_bps)) if not isinstance(default_slippage_bps, Decimal) else default_slippage_bps

    def calibrate_slippage(self, median_realized_bps: Decimal) -> None:
        """Update slippage model using feedback from real testnet execution."""
        self.slippage_bps = max(Decimal("5.0"), median_realized_bps)

    def calculate_entry_cost(self, notional: Decimal, is_taker: bool = True) -> tuple[Decimal, Decimal]:
        """Calculate (fee, slippage_amount) for entry."""
        fee_rate = self.taker_fee_pct if is_taker else self.maker_fee_pct
        fee = notional * fee_rate
        slippage = notional * (self.slippage_bps / Decimal("10000"))
        return (fee, slippage)

    def calculate_exit_cost(self, notional: Decimal, is_taker: bool = True) -> tuple[Decimal, Decimal]:
        """Calculate (fee, slippage_amount) for exit."""
        fee_rate = self.taker_fee_pct if is_taker else self.maker_fee_pct
        fee = notional * fee_rate
        slippage = notional * (self.slippage_bps / Decimal("10000"))
        return (fee, slippage)

    def apply_entry_slippage(self, price: Decimal, is_long: bool) -> Decimal:
        """Adjust entry fill price for slippage friction."""
        slippage_fraction = self.slippage_bps / Decimal("10000")
        if is_long:
            return price * (Decimal("1") + slippage_fraction)
        else:
            return price * (Decimal("1") - slippage_fraction)

    def apply_exit_slippage(self, price: Decimal, is_long: bool) -> Decimal:
        """Adjust exit fill price for slippage friction."""
        slippage_fraction = self.slippage_bps / Decimal("10000")
        if is_long:
            # Exiting long by selling: lower price
            return price * (Decimal("1") - slippage_fraction)
        else:
            # Exiting short by buying: higher price
            return price * (Decimal("1") + slippage_fraction)
