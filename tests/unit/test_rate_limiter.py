"""Unit tests for the Rate Limit budget accountant."""

from __future__ import annotations

import unittest

from app.exchange.rate_limiter import RateLimitAccountant


class TestRateLimiter(unittest.TestCase):
    def test_rate_limiter_budget_tracking(self) -> None:
        limiter = RateLimitAccountant(max_quota=100, window_seconds=10.0, budget_fraction=0.25)

        self.assertTrue(limiter.can_make_request(10))
        self.assertTrue(limiter.is_within_budget(10))

        limiter.record_usage(20)
        self.assertEqual(limiter.used_weight, 20)
        self.assertFalse(limiter.is_within_budget(10))  # 20 + 10 = 30 > 25
        self.assertTrue(limiter.can_make_request(50))   # 20 + 50 = 70 <= 100


if __name__ == "__main__":
    unittest.main()
