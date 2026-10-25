"""Drawdown Ladder and Multi-Tier Capital Protection.

Per Section 9.5 and 10.4 of agent.md:
Multi-tier capital protection ladder:
- Normal (Rung 1): Drawdown < cooling threshold -> 100% sizing multiplier (1.0).
- Cooling Off (Rung 2): Drawdown >= cooling threshold -> reduced sizing / cooldown.
- 50% Size (Rung 3): Drawdown >= reduced size threshold -> 50% sizing multiplier (0.5).
- Halt (Rung 4): Drawdown >= halt threshold -> triggers Kill Switch and halts engine.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any

from app.core.contracts import RuleEvaluationResult
from app.core.logging import get_logger
from app.risk.guards import check_drawdown
from app.risk.kill_switch import KillSwitch

logger = get_logger("drawdown_ladder")


class DrawdownTier(str, Enum):
    """Drawdown ladder protection rungs."""

    NORMAL = "NORMAL"
    COOLING_OFF = "COOLING_OFF"
    REDUCED_50 = "REDUCED_50"
    HALT = "HALT"


class DrawdownLadder:
    """Monitors equity and enforces tiered risk reduction and kill-switch halts."""

    def __init__(
        self,
        initial_capital: Decimal = Decimal("10000.0"),
        cooling_off_pct: float = 0.02,   # 2% drawdown -> cooling off
        reduced_size_pct: float = 0.04,  # 4% drawdown -> 50% sizing
        halt_pct: float = 0.06,          # 6% drawdown -> halt & trigger kill switch
        kill_switch: KillSwitch | None = None,
    ) -> None:
        self.initial_capital = initial_capital
        self.peak_equity = initial_capital
        self.cooling_off_pct = cooling_off_pct
        self.reduced_size_pct = reduced_size_pct
        self.halt_pct = halt_pct
        self.kill_switch = kill_switch

    def update_equity(self, current_equity: Decimal) -> None:
        """Update peak equity high-water mark."""
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

    def current_drawdown_pct(self, current_equity: Decimal) -> float:
        """Calculate current percentage drawdown from peak equity."""
        if self.peak_equity <= Decimal("0"):
            return 0.0
        dd = float((self.peak_equity - current_equity) / self.peak_equity)
        return max(0.0, dd)

    def evaluate_rung(self, current_equity: Decimal) -> tuple[DrawdownTier, float, int]:
        """Determine current drawdown tier, sizing multiplier, and rung index (1-4).

        Returns:
            (tier, sizing_multiplier, rung_index)
        """
        self.update_equity(current_equity)
        dd = self.current_drawdown_pct(current_equity)

        if dd >= self.halt_pct:
            tier = DrawdownTier.HALT
            multiplier = 0.0
            rung = 4
            if self.kill_switch and not self.kill_switch.is_active:
                logger.critical(
                    "Drawdown ladder HALT rung breached: %.2f%% >= %.2f%% threshold!",
                    dd * 100.0,
                    self.halt_pct * 100.0,
                )
                self.kill_switch.trigger(
                    source="drawdown_ladder",
                    reason=f"Cumulative drawdown {dd * 100.0:.1f}% breached maximum safe loss threshold",
                    details={
                        "initial_capital": float(self.initial_capital),
                        "current_equity": float(current_equity),
                        "peak_equity": float(self.peak_equity),
                        "drawdown_pct": round(dd, 4),
                    },
                )
        elif dd >= self.reduced_size_pct:
            tier = DrawdownTier.REDUCED_50
            multiplier = 0.5
            rung = 3
        elif dd >= self.cooling_off_pct:
            tier = DrawdownTier.COOLING_OFF
            multiplier = 0.75
            rung = 2
        else:
            tier = DrawdownTier.NORMAL
            multiplier = 1.0
            rung = 1

        return tier, multiplier, rung

    def check_drawdown_guard(self, current_equity: Decimal) -> RuleEvaluationResult:
        """Evaluate drawdown guard for RiskGate."""
        self.update_equity(current_equity)
        return check_drawdown(
            current_equity=current_equity,
            peak_equity=self.peak_equity,
            halt_threshold_pct=self.halt_pct,
        )
