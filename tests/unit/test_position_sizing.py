"""Unit tests for PositionSizer: volatility scaling, integer rounding, leverage limits, and boundary cases.

Per Section 10.3 of agent.md and PROJECT.md:
- Strict floor integer rounding (no fractional contracts).
- Volatility scaling reduces risk capital during elevated volatility.
- Hard leverage cap <= 3x.
- Safe rejection (0 contracts) on invalid boundary inputs.
"""

from __future__ import annotations

from decimal import Decimal
import unittest

from app.core.contracts import Direction, OrderIntent
from app.risk.sizing import PositionSizer


class TestPositionSizing(unittest.TestCase):
    def setUp(self) -> None:
        self.sizer = PositionSizer(
            default_risk_fraction=0.01,
            max_leverage=3,
            contract_value_btc=Decimal("0.001"),
        )

    def _create_intent(
        self,
        stop_dist: Decimal = Decimal("100.0"),
        risk_fraction: float = 0.01,
    ) -> OrderIntent:
        return OrderIntent(
            decision_id="test-dec-01",
            strategy_name="trend_following",
            symbol="BTCUSD",
            direction=Direction.LONG,
            desired_risk_fraction=risk_fraction,
            proposed_stop_distance=stop_dist,
        )

    def test_floor_integer_rounding(self) -> None:
        """Position size must always strictly round DOWN to integer contracts."""
        intent = self._create_intent(stop_dist=Decimal("70.0"))
        # Equity = $10,000, Risk = 1% ($100), Stop = 70, Multiplier = 0.001 -> 100 / (70 * 0.001) = 1428.57 contracts -> floor is 1428
        contracts = self.sizer.calculate_contracts(
            intent=intent,
            current_equity=Decimal("10000.0"),
            entry_price=Decimal("1000.0"),
            volatility_ratio=1.0,
        )
        self.assertIsInstance(contracts, int)
        self.assertEqual(contracts, 1428)

        # Equity = $10,000, Risk = 1% ($100), Stop = 22, Multiplier = 0.001 -> 100 / (22 * 0.001) = 4545.45 -> floor is 4545
        intent2 = self._create_intent(stop_dist=Decimal("22.0"))
        contracts2 = self.sizer.calculate_contracts(
            intent=intent2,
            current_equity=Decimal("10000.0"),
            entry_price=Decimal("1000.0"),
            volatility_ratio=1.0,
        )
        self.assertEqual(contracts2, 4545)

        # Sub-unit result: 100 / (150000 * 0.001) = 0.666 -> floor is 0
        intent3 = self._create_intent(stop_dist=Decimal("150000.0"))
        contracts3 = self.sizer.calculate_contracts(
            intent=intent3,
            current_equity=Decimal("10000.0"),
            entry_price=Decimal("1000.0"),
            volatility_ratio=1.0,
        )
        self.assertEqual(contracts3, 0)

    def test_volatility_scaling_reduces_size(self) -> None:
        """Elevated volatility ratio must strictly scale down position size."""
        intent = self._create_intent(stop_dist=Decimal("10.0"))
        equity = Decimal("20000.0")  # Risk = $200, Base = 200 / (10 * 0.001) = 20,000 contracts
        entry = Decimal("500.0")     # Max leverage 3x notional = 60000. Contract val = 0.5. Max = 120,000 contracts (unconstrained)

        # Normal volatility (ratio 1.0) -> vol_scaling = 1.0 -> 20,000 contracts
        c_normal = self.sizer.calculate_contracts(
            intent=intent,
            current_equity=equity,
            entry_price=entry,
            volatility_ratio=1.0,
        )

        # High volatility (ratio 2.0) -> vol_scaling = 0.5 -> 10,000 contracts
        c_high_vol = self.sizer.calculate_contracts(
            intent=intent,
            current_equity=equity,
            entry_price=entry,
            volatility_ratio=2.0,
        )

        # Extreme volatility (ratio 5.0) -> vol_scaling = 0.2 (clamp min) -> 4,000 contracts
        c_extreme_vol = self.sizer.calculate_contracts(
            intent=intent,
            current_equity=equity,
            entry_price=entry,
            volatility_ratio=5.0,
        )

        self.assertEqual(c_normal, 20000)
        self.assertEqual(c_high_vol, 10000)
        self.assertEqual(c_extreme_vol, 4000)
        self.assertLess(c_high_vol, c_normal)
        self.assertLess(c_extreme_vol, c_high_vol)

    def test_leverage_capping_3x(self) -> None:
        """Position size must be capped by max_leverage (default 3x) notional ceiling."""
        # Tight stop distance of 1.0 would mathematically request 100 / (1 * 0.001) = 100,000 contracts
        intent = self._create_intent(stop_dist=Decimal("1.0"))
        equity = Decimal("10000.0")
        entry = Decimal("2000.0")

        # Max notional = 10000 * 3 = 30,000. Contract notional = 2000 * 0.001 = 2.0 -> max contracts = 30000 / 2.0 = 15,000
        contracts = self.sizer.calculate_contracts(
            intent=intent,
            current_equity=equity,
            entry_price=entry,
            volatility_ratio=1.0,
        )
        self.assertEqual(contracts, 15000)

        # Notional value of position must not exceed Equity * max_leverage
        notional = Decimal(str(contracts)) * entry * self.sizer.contract_value_btc
        max_allowed_notional = equity * Decimal(str(self.sizer.max_leverage))
        self.assertLessEqual(notional, max_allowed_notional)

    def test_invalid_and_boundary_conditions_return_zero(self) -> None:
        """Zero or negative equity, stop distance, or price must return 0 contracts."""
        valid_intent = self._create_intent(stop_dist=Decimal("50.0"))
        zero_stop_intent = self._create_intent(stop_dist=Decimal("0.0"))
        neg_stop_intent = self._create_intent(stop_dist=Decimal("-10.0"))

        equity = Decimal("10000.0")
        price = Decimal("1000.0")

        # Zero stop distance
        self.assertEqual(self.sizer.calculate_contracts(zero_stop_intent, equity, price), 0)
        # Negative stop distance
        self.assertEqual(self.sizer.calculate_contracts(neg_stop_intent, equity, price), 0)
        # Zero equity
        self.assertEqual(self.sizer.calculate_contracts(valid_intent, Decimal("0.0"), price), 0)
        # Negative equity (in drawdown)
        self.assertEqual(self.sizer.calculate_contracts(valid_intent, Decimal("-500.0"), price), 0)
        # Zero entry price
        self.assertEqual(self.sizer.calculate_contracts(valid_intent, equity, Decimal("0.0")), 0)
        # Negative entry price
        self.assertEqual(self.sizer.calculate_contracts(valid_intent, equity, Decimal("-100.0")), 0)
        # Zero allocator weight
        self.assertEqual(
            self.sizer.calculate_contracts(valid_intent, equity, price, allocator_weight=0.0),
            0,
        )

    def test_contract_multiplier_attribute(self) -> None:
        """Verify contract_value_btc is configured and retrievable."""
        self.assertEqual(self.sizer.contract_value_btc, Decimal("0.001"))
        self.assertEqual(self.sizer.max_leverage, 3)


if __name__ == "__main__":
    unittest.main()
