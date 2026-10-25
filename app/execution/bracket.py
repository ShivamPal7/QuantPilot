"""Exchange-side bracket order manager and validation.

Per Section 6.6, 9.6, and 11.2 of agent.md:
Constructs server-side stop-loss and take-profit exit brackets attached to entry orders.
Enforces tick-size rounding, strict boundary checks, and ensures no naked position opens.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_UP

from app.core.contracts import Direction


@dataclass(frozen=True)
class BracketOrder:
    """Calculated exchange-side exit bracket parameters."""

    stop_loss_price: Decimal
    take_profit_price: Decimal | None = None


class BracketManager:
    """Calculates, rounds, and validates server-side bracket order prices."""

    @staticmethod
    def round_to_tick(price: Decimal, tick_size: Decimal = Decimal("0.5"), round_up: bool = False) -> Decimal:
        """Round price to the product's tick size."""
        if tick_size <= Decimal("0"):
            return price
        # Number of ticks
        ticks = price / tick_size
        rounded_ticks = Decimal(str(int(ticks.to_integral_value(rounding=ROUND_UP if round_up else ROUND_DOWN))))
        return rounded_ticks * tick_size

    @classmethod
    def compute_brackets(
        cls,
        entry_price: Decimal,
        direction: Direction,
        stop_distance: Decimal,
        tp_distance: Decimal | None = None,
        tick_size: Decimal = Decimal("0.5"),
    ) -> BracketOrder:
        """Calculate and validate SL and TP bracket prices."""
        if entry_price <= Decimal("0"):
            raise ValueError(f"Entry price must be positive, got {entry_price}")
        if stop_distance <= Decimal("0"):
            raise ValueError(f"Protective stop distance must be positive, got {stop_distance}")

        if direction == Direction.LONG:
            raw_sl = entry_price - stop_distance
            sl_price = cls.round_to_tick(raw_sl, tick_size, round_up=False)
            if sl_price >= entry_price:
                sl_price = entry_price - tick_size

            tp_price = None
            if tp_distance is not None and tp_distance > Decimal("0"):
                raw_tp = entry_price + tp_distance
                tp_price = cls.round_to_tick(raw_tp, tick_size, round_up=True)
                if tp_price <= entry_price:
                    tp_price = entry_price + tick_size

        elif direction == Direction.SHORT:
            raw_sl = entry_price + stop_distance
            sl_price = cls.round_to_tick(raw_sl, tick_size, round_up=True)
            if sl_price <= entry_price:
                sl_price = entry_price + tick_size

            tp_price = None
            if tp_distance is not None and tp_distance > Decimal("0"):
                raw_tp = entry_price - tp_distance
                tp_price = cls.round_to_tick(raw_tp, tick_size, round_up=False)
                if tp_price >= entry_price:
                    tp_price = entry_price - tick_size
        else:
            raise ValueError(f"Unsupported direction: {direction}")

        return BracketOrder(
            stop_loss_price=sl_price,
            take_profit_price=tp_price,
        )
