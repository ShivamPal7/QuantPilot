"""Rate limit budget accountant for Delta Exchange.

Per Section 6.5 of agent.md:
- 20,000 weight quota per 5-minute fixed window.
- Steady-state target: stay under ~25% of quota.
- Degrades gracefully before hitting limits.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


# Defined endpoint weight costs
WEIGHT_PUBLIC_READ = 3
WEIGHT_ORDER_ACTION = 5
WEIGHT_HISTORY_FILLS = 10
WEIGHT_BATCH_ORDER = 25
WEIGHT_DEFAULT = 1


@dataclass
class RateLimitStatus:
    window_start: float
    used_weight: int
    max_weight: int = 20000
    target_budget_weight: int = 5000  # 25% of 20,000


class RateLimitAccountant:
    """Tracks and throttles Delta API consumption."""

    def __init__(
        self,
        max_quota: int = 20000,
        window_seconds: float = 300.0,
        budget_fraction: float = 0.25,
    ) -> None:
        self.max_quota = max_quota
        self.window_seconds = window_seconds
        self.budget_target = int(max_quota * budget_fraction)
        self.window_start = time.time()
        self.used_weight = 0
        self._backoff_until = 0.0

    def _refresh_window_if_needed(self, now: float) -> None:
        if now - self.window_start >= self.window_seconds:
            self.window_start = now
            self.used_weight = 0

    def handle_429(self, retry_after_seconds: float = 1.0) -> None:
        """Trigger backoff cooldown upon receiving HTTP 429 RateLimitExceeded."""
        self._backoff_until = time.time() + retry_after_seconds

    def is_in_backoff(self) -> bool:
        """Returns True if system is in rate limit backoff cooldown."""
        return time.time() < self._backoff_until

    def backoff_remaining_seconds(self) -> float:
        """Seconds remaining in current backoff window."""
        return max(0.0, self._backoff_until - time.time())

    def record_usage(self, weight: int) -> None:
        """Record consumed weight."""
        now = time.time()
        self._refresh_window_if_needed(now)
        self.used_weight += weight

    def can_make_request(self, weight: int = WEIGHT_DEFAULT) -> bool:
        """Check if request weight fits within total quota and not in backoff."""
        if self.is_in_backoff():
            return False
        now = time.time()
        self._refresh_window_if_needed(now)
        return (self.used_weight + weight) <= self.max_quota

    def is_within_budget(self, weight: int = WEIGHT_DEFAULT) -> bool:
        """Check if request stays within conservative steady-state target (25%) and not in backoff."""
        if self.is_in_backoff():
            return False
        now = time.time()
        self._refresh_window_if_needed(now)
        return (self.used_weight + weight) <= self.budget_target

    def get_status(self) -> RateLimitStatus:
        now = time.time()
        self._refresh_window_if_needed(now)
        return RateLimitStatus(
            window_start=self.window_start,
            used_weight=self.used_weight,
            max_weight=self.max_quota,
            target_budget_weight=self.budget_target,
        )

    def time_to_reset(self) -> float:
        now = time.time()
        return max(0.0, self.window_seconds - (now - self.window_start))
