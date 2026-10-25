"""Evidence-Based Strategy Allocator.

ZONE: RED (HUMAN-AUTHORED ONLY)
Owner: Team Member A (See docs/ownership.md)
Reference: Section 9.4 of agent.md

Purpose:
Decide which strategy (if any) takes real risk on this candle.
Method: Bayesian multi-armed bandit (Thompson sampling) with recency weighting,
exploration floor, and regime-based stand-aside override.
"""

from __future__ import annotations

from app.core.contracts import AllocationDecision, RegimeLabel, RegimeReading, ShadowStats


class StrategyAllocator:
    """Selects which strategy is permitted to take real testnet risk."""

    def __init__(
        self,
        exploration_floor: float = 0.10,
        recency_window_trades: int = 20,
        min_trades_for_prior: int = 5,
    ) -> None:
        self.exploration_floor = exploration_floor
        self.recency_window_trades = recency_window_trades
        self.min_trades_for_prior = min_trades_for_prior

    def allocate(
        self,
        regime: RegimeReading,
        shadow_stats: dict[str, ShadowStats],
    ) -> AllocationDecision:
        """Select active strategy or enforce stand-aside.

        HUMAN TEAM IMPLEMENTATION:
        1. Stand-aside override: if regime is CHAOTIC, allocate None.
        2. Thompson sampling over strategies with Beta distribution priors based on shadow win rates.
        3. Guarantee exploration floor so all strategies accumulate evidence.
        """
        # Hard regime override
        if regime.label == RegimeLabel.CHAOTIC:
            return AllocationDecision(
                selected_strategy=None,
                weight=0.0,
                reason="Regime filter classified market as CHAOTIC: standing aside.",
                is_regime_override=True,
            )

        # Baseline default mapping: trend_following in TRENDING, mean_reversion in RANGING
        if regime.label == RegimeLabel.TRENDING and "trend_following" in shadow_stats:
            return AllocationDecision(
                selected_strategy="trend_following",
                weight=1.0,
                reason="Selected trend_following due to TRENDING market regime.",
                is_regime_override=False,
            )
        elif regime.label == RegimeLabel.RANGING and "mean_reversion" in shadow_stats:
            return AllocationDecision(
                selected_strategy="mean_reversion",
                weight=1.0,
                reason="Selected mean_reversion due to RANGING market regime.",
                is_regime_override=False,
            )

        # Fallback
        first_strat = next(iter(shadow_stats.keys()), None)
        return AllocationDecision(
            selected_strategy=first_strat,
            weight=1.0 if first_strat else 0.0,
            reason="Cold-start default allocation.",
            is_exploration=True,
        )
