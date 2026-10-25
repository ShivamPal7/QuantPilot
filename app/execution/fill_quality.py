"""Fill quality analytics and feedback.

Per Section 9.6 of agent.md:
Measures slippage, execution latency, fees, and fill ratio.
Feeds median realized slippage back into the shadow cost model.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.shadow.cost_model import ShadowCostModel


@dataclass
class FillReport:
    client_order_id: str
    expected_price: Decimal
    actual_fill_price: Decimal
    slippage_bps: Decimal
    fees: Decimal
    latency_ms: float


class FillQualityTracker:
    """Tracks execution performance and calibration metrics."""

    def __init__(self, max_history: int = 100) -> None:
        self.max_history = max_history
        self._reports: list[FillReport] = []
        self._total_submitted_orders: int = 0
        self._total_filled_orders: int = 0

    def record_submission(self) -> None:
        """Increment count of submitted intents."""
        self._total_submitted_orders += 1

    def record_fill(
        self,
        client_order_id: str,
        expected_price: Decimal,
        actual_price: Decimal,
        fees: Decimal,
        latency_ms: float,
        is_buy: bool,
    ) -> FillReport:
        """Calculate slippage and record fill metrics."""
        self._total_filled_orders += 1
        if expected_price > Decimal("0"):
            if is_buy:
                # Paid higher than expected -> positive slippage (adverse)
                diff = actual_price - expected_price
            else:
                # Sold lower than expected -> positive slippage (adverse)
                diff = expected_price - actual_price
            slippage_bps = (diff / expected_price) * Decimal("10000")
        else:
            slippage_bps = Decimal("0")

        report = FillReport(
            client_order_id=client_order_id,
            expected_price=expected_price,
            actual_fill_price=actual_price,
            slippage_bps=slippage_bps,
            fees=fees,
            latency_ms=latency_ms,
        )
        self._reports.append(report)
        if len(self._reports) > self.max_history:
            self._reports.pop(0)

        return report

    def get_median_slippage_bps(self) -> Decimal:
        """Return median slippage across recorded fills."""
        if not self._reports:
            return Decimal("10.0")  # Default conservative fallback
        values = [float(r.slippage_bps) for r in self._reports]
        med = statistics.median(values)
        return Decimal(str(round(med, 2)))

    def get_average_latency_ms(self) -> float:
        """Return average execution latency in milliseconds."""
        if not self._reports:
            return 0.0
        return statistics.mean([r.latency_ms for r in self._reports])

    def get_fill_ratio(self) -> float:
        """Return ratio of filled orders relative to submitted orders."""
        if self._total_submitted_orders == 0:
            return 1.0 if self._total_filled_orders > 0 else 0.0
        return min(1.0, float(self._total_filled_orders / self._total_submitted_orders))

    def feed_to_cost_model(self, cost_model: ShadowCostModel) -> Decimal:
        """Feed median realized slippage into shadow cost model for calibration."""
        median_slippage = self.get_median_slippage_bps()
        cost_model.calibrate_slippage(median_slippage)
        return median_slippage
