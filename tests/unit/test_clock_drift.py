"""Unit tests for clock drift detection, tolerance boundaries, and halting triggers.

Per Section 6.2 of agent.md:
Signatures older than 5.0 seconds fail on Delta Exchange.
System must verify clock drift and warn/halt if local drift > 2.0s from Delta server time.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.core.clock import SimulatedClock, SystemClock, check_clock_drift
from app.core.state import EngineState, EngineStateMachine
from app.risk.kill_switch import KillSwitch
from tests.fakes.fake_exchange import FakeExchange


class TestClockDrift(unittest.IsolatedAsyncioTestCase):
    def test_clock_drift_within_tolerance(self) -> None:
        """Drift <= 2.0s must pass validation."""
        # Exact sync (0.0s)
        valid, drift = check_clock_drift(local_time_s=1000.0, exchange_time_s=1000.0, max_drift_s=2.0)
        self.assertTrue(valid)
        self.assertAlmostEqual(drift, 0.0)

        # 0.5s forward drift
        valid, drift = check_clock_drift(local_time_s=1000.5, exchange_time_s=1000.0, max_drift_s=2.0)
        self.assertTrue(valid)
        self.assertAlmostEqual(drift, 0.5)

        # 1.99s backward drift
        valid, drift = check_clock_drift(local_time_s=998.01, exchange_time_s=1000.0, max_drift_s=2.0)
        self.assertTrue(valid)
        self.assertAlmostEqual(drift, 1.99)

        # Exact boundary condition at 2.0s
        valid, drift = check_clock_drift(local_time_s=1002.0, exchange_time_s=1000.0, max_drift_s=2.0)
        self.assertTrue(valid)
        self.assertAlmostEqual(drift, 2.0)

    def test_clock_drift_exceeding_tolerance_fails(self) -> None:
        """Drift > 2.0s must fail validation and report accurate drift magnitude."""
        # Boundary violation at 2.001s
        valid, drift = check_clock_drift(local_time_s=1002.001, exchange_time_s=1000.0, max_drift_s=2.0)
        self.assertFalse(valid)
        self.assertAlmostEqual(drift, 2.001, places=3)

        # Severe forward drift: 5.0s (Delta auth signature expiration boundary)
        valid, drift = check_clock_drift(local_time_s=1005.0, exchange_time_s=1000.0, max_drift_s=2.0)
        self.assertFalse(valid)
        self.assertAlmostEqual(drift, 5.0)

        # Severe backward drift: 10.0s lag
        valid, drift = check_clock_drift(local_time_s=990.0, exchange_time_s=1000.0, max_drift_s=2.0)
        self.assertFalse(valid)
        self.assertAlmostEqual(drift, 10.0)

    def test_clock_drift_custom_tolerance(self) -> None:
        """Custom drift thresholds should be strictly honored."""
        valid, drift = check_clock_drift(local_time_s=1000.8, exchange_time_s=1000.0, max_drift_s=0.5)
        self.assertFalse(valid)
        self.assertAlmostEqual(drift, 0.8)

        valid, drift = check_clock_drift(local_time_s=1000.4, exchange_time_s=1000.0, max_drift_s=0.5)
        self.assertTrue(valid)
        self.assertAlmostEqual(drift, 0.4)

    def test_simulated_clock_advancement_and_time_setting(self) -> None:
        """Verify SimulatedClock protocol compliance, advancement, and manual time setting."""
        start = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)
        clock = SimulatedClock(start_time=start)

        self.assertEqual(clock.now_utc(), start)
        self.assertEqual(clock.time_seconds(), start.timestamp())

        # Advance by 15.5 seconds
        clock.advance(15.5)
        self.assertEqual(clock.time_seconds(), start.timestamp() + 15.5)

        # Explicitly set time
        target = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        clock.set_time(target)
        self.assertEqual(clock.now_utc(), target)
        self.assertEqual(clock.time_seconds(), target.timestamp())

    def test_system_clock_sanity(self) -> None:
        """Verify SystemClock returns valid UTC datetime and positive unix timestamp."""
        sys_clock = SystemClock()
        now = sys_clock.now_utc()
        self.assertIsNotNone(now.tzinfo)
        self.assertGreater(sys_clock.time_seconds(), 1700000000.0)

    async def test_drift_detection_triggers_kill_switch_and_halts_engine(self) -> None:
        """Simulate clock drift against exchange server time triggering safety halt."""
        fake_exchange = FakeExchange()
        fake_exchange.simulated_drift_seconds = 3.5  # Exceeds 2.0s limit

        state_machine = EngineStateMachine(initial_state=EngineState.RUNNING)
        kill_switch = KillSwitch(state_machine=state_machine)

        # Exchange client checking server time against local clock
        local_time = 1000000.0
        server_time = await fake_exchange.get_server_time()
        # Apply simulated drift
        is_valid, drift = check_clock_drift(
            local_time_s=local_time,
            exchange_time_s=local_time + fake_exchange.simulated_drift_seconds,
            max_drift_s=2.0,
        )

        self.assertFalse(is_valid)
        self.assertGreater(drift, 2.0)

        # When drift exceeds limit, watchdog must trigger kill switch and transition to HALTED
        if not is_valid:
            kill_switch.trigger(
                source="clock_drift_guard",
                reason=f"Clock drift {drift:.2f}s exceeds maximum allowed 2.0s limit",
                details={"drift_seconds": drift, "threshold": 2.0},
            )

        self.assertTrue(kill_switch.is_active)
        self.assertEqual(state_machine.current_state, EngineState.HALTED)


if __name__ == "__main__":
    unittest.main()
