"""Evidence-Based Strategy Allocator.

Reference: Section 9.4 of agent.md
Owner: Team Member A (See docs/ownership.md)

Purpose:
Decide which strategy (if any) takes real risk on this candle.
Method: Bayesian multi-armed bandit using Thompson sampling (Beta distribution over shadow performance)
with recency window, exploration floor, regime bias, and hard stand-aside override.
"""

from __future__ import annotations

import random
from typing import Any

from app.core.contracts import AllocationDecision, RegimeLabel, RegimeReading, ShadowStats
from app.shadow.account import ShadowAccount


class StrategyAllocator:
    """Selects which strategy is permitted to take real testnet risk using Thompson sampling."""

    def __init__(
        self,
        exploration_floor: float = 0.10,
        recency_window_trades: int = 20,
        min_trades_for_prior: int = 5,
        seed: int | None = None,
    ) -> None:
        self.exploration_floor = exploration_floor
        self.recency_window_trades = recency_window_trades
        self.min_trades_for_prior = min_trades_for_prior
        self._random = random.Random(seed)

    def set_seed(self, seed: int) -> None:
        """Set deterministic seed for reproducible testing."""
        self._random = random.Random(seed)

    def allocate(
        self,
        regime: RegimeReading,
        shadow_stats: dict[str, ShadowStats],
        shadow_accounts: dict[str, ShadowAccount] | None = None,
    ) -> AllocationDecision:
        """Select active strategy or enforce stand-aside."""
        # 1. Hard regime override: CHAOTIC strictly forces stand-aside
        if regime.label == RegimeLabel.CHAOTIC:
            return AllocationDecision(
                selected_strategy=None,
                weight=0.0,
                reason="Regime filter classified market as CHAOTIC: standing aside.",
                sampled_values={},
                is_exploration=False,
                is_regime_override=True,
            )

        if not shadow_stats:
            return AllocationDecision(
                selected_strategy=None,
                weight=0.0,
                reason="No active strategies registered in shadow stats.",
                sampled_values={},
                is_exploration=False,
                is_regime_override=False,
            )

        # 2. Cold-start check
        total_trades = sum(stats.trade_count for stats in shadow_stats.values())
        if total_trades < self.min_trades_for_prior:
            # Use regime-based default mapping
            if regime.label == RegimeLabel.TRENDING and "trend_following" in shadow_stats:
                return AllocationDecision(
                    selected_strategy="trend_following",
                    weight=1.0,
                    reason="Cold start (< 5 trades): Selected trend_following based on TRENDING market regime prior.",
                    sampled_values={"trend_following": 0.5, "mean_reversion": 0.5},
                    is_exploration=False,
                    is_regime_override=False,
                )
            elif regime.label == RegimeLabel.RANGING and "mean_reversion" in shadow_stats:
                return AllocationDecision(
                    selected_strategy="mean_reversion",
                    weight=1.0,
                    reason="Cold start (< 5 trades): Selected mean_reversion based on RANGING market regime prior.",
                    sampled_values={"trend_following": 0.5, "mean_reversion": 0.5},
                    is_exploration=False,
                    is_regime_override=False,
                )
            else:
                first_strat = next(iter(shadow_stats.keys()))
                return AllocationDecision(
                    selected_strategy=first_strat,
                    weight=1.0,
                    reason="Cold start default fallback.",
                    sampled_values={first_strat: 0.5},
                    is_exploration=True,
                    is_regime_override=False,
                )

        # 3. Calculate Beta priors with recency window and regime bias
        sampled_values: dict[str, float] = {}

        for name, stats in shadow_stats.items():
            wins = 0
            losses = 0

            if shadow_accounts and name in shadow_accounts:
                recent_trades = shadow_accounts[name].trades[-self.recency_window_trades :]
                wins = sum(1 for t in recent_trades if t.is_win)
                losses = len(recent_trades) - wins
            else:
                wins = stats.win_count
                losses = stats.loss_count

            # Beta prior parameters: alpha = 1 + wins, beta = 1 + losses
            alpha = 1.0 + float(wins)
            beta = 1.0 + float(losses)

            # Apply regime bias modifier
            if regime.label == RegimeLabel.TRENDING and name == "trend_following":
                alpha += 1.0
            elif regime.label == RegimeLabel.RANGING and name == "mean_reversion":
                alpha += 1.0

            # Thompson sample from Beta(alpha, beta)
            sample = self._random.betavariate(alpha, beta)
            sampled_values[name] = round(sample, 4)

        # 4. Exploration floor check
        if self._random.random() < self.exploration_floor:
            # Random exploration among available strategies
            strat_list = list(shadow_stats.keys())
            chosen = self._random.choice(strat_list)
            return AllocationDecision(
                selected_strategy=chosen,
                weight=1.0,
                reason=(
                    f"Exploration floor ({int(self.exploration_floor * 100)}%) active: "
                    f"selected '{chosen}' to accumulate evidence (Thompson sample: {sampled_values.get(chosen, 0.0)})."
                ),
                sampled_values=sampled_values,
                is_exploration=True,
                is_regime_override=False,
            )

        # 5. Exploitation: select strategy with highest sampled score
        best_strategy = max(sampled_values, key=sampled_values.get)
        best_score = sampled_values[best_strategy]

        reason = (
            f"Thompson sampling selected '{best_strategy}' (score: {best_score}) "
            f"in {regime.label.value} market regime."
        )

        return AllocationDecision(
            selected_strategy=best_strategy,
            weight=1.0,
            reason=reason,
            sampled_values=sampled_values,
            is_exploration=False,
            is_regime_override=False,
        )
