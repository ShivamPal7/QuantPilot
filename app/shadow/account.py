"""Virtual shadow account for zero-risk paper trade tracking.

Per Section 9.4 of agent.md:
One virtual account per strategy running continuously.
Trades evaluated against next candle's prices (never same candle close).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.core.contracts import Candle, Direction, ShadowStats, ShadowTrade
from app.shadow.cost_model import ShadowCostModel


class ShadowAccount:
    """Simulates realistic execution and metrics for a specific strategy."""

    def __init__(
        self,
        strategy_name: str,
        initial_capital: Decimal = Decimal("10000.0"),
        cost_model: ShadowCostModel | None = None,
    ) -> None:
        self.strategy_name = strategy_name
        self.initial_capital = initial_capital
        self.current_equity = initial_capital
        self.cost_model = cost_model or ShadowCostModel()

        self._trades: list[ShadowTrade] = []
        self._open_trade: dict[str, Any] | None = None
        self._peak_equity = initial_capital

    def process_closed_candle(self, candle: Candle) -> None:
        """Mark open position or process stops on candle close."""
        # Scaffolding logic: evaluate paper positions
        if self.current_equity > self._peak_equity:
            self._peak_equity = self.current_equity

    def get_stats(self) -> ShadowStats:
        """Compute summary statistics."""
        wins = sum(1 for t in self._trades if t.is_win)
        losses = sum(1 for t in self._trades if not t.is_win)
        total = len(self._trades)
        win_rate = (wins / total) if total > 0 else 0.0
        drawdown_pct = float((self._peak_equity - self.current_equity) / self._peak_equity) if self._peak_equity > 0 else 0.0

        return ShadowStats(
            strategy_name=self.strategy_name,
            trade_count=total,
            win_count=wins,
            loss_count=losses,
            win_rate=win_rate,
            net_profit=self.current_equity - self.initial_capital,
            max_drawdown_pct=drawdown_pct,
            updated_at=datetime.now(timezone.utc),
        )
