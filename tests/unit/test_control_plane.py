"""Unit tests for Control Plane: supervisor lifecycle, state machine transitions, and control endpoints.

Per Section 7.3, 9.8, and 13.1 of agent.md:
- Background task supervisor manages coroutines, restarts on failure with backoff, and halts on excessive crashes.
- Engine state machine enforces strict state transition guards.
- Control operations (pause, resume, kill, reset) require shared secret validation.
- Reset from halt strictly requires "CONFIRM_RESET" confirmation token.
"""

from __future__ import annotations

import asyncio
from typing import Any
import unittest

from app.core.config import get_settings
from app.core.state import (
    EngineState,
    EngineStateMachine,
    StateTransitionError,
)
from app.core.supervisor import Supervisor
from app.risk.kill_switch import KillSwitch


class TestControlPlane(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.state_machine = EngineStateMachine(initial_state=EngineState.RUNNING)
        self.kill_switch = KillSwitch(state_machine=self.state_machine)
        self.settings = get_settings()

    async def test_supervisor_task_lifecycle_and_clean_stop(self) -> None:
        """Verify supervisor launches tasks, reports health, and cleanly stops on demand."""
        supervisor = Supervisor(max_consecutive_restarts=3, base_backoff_seconds=0.01)
        run_count = 0

        async def healthy_loop() -> None:
            nonlocal run_count
            while True:
                run_count += 1
                await asyncio.sleep(0.01)

        supervisor.register("loop_task", healthy_loop)
        await supervisor.start()

        # Let the loop execute briefly
        await asyncio.sleep(0.03)
        self.assertTrue(supervisor.is_healthy)
        self.assertGreater(run_count, 0)

        # Clean shutdown
        await supervisor.stop()
        self.assertFalse(supervisor._running)

    async def test_supervisor_crash_restart_and_max_retry_limit(self) -> None:
        """Supervisor catches task exceptions, increments restart counter, and stops restarting past limit."""
        supervisor = Supervisor(max_consecutive_restarts=2, base_backoff_seconds=0.01)
        crash_count = 0

        async def crashing_task() -> None:
            nonlocal crash_count
            crash_count += 1
            raise RuntimeError(f"Simulated crash #{crash_count}")

        supervisor.register("crashing_task", crashing_task)
        await supervisor.start()

        # Wait for restarts and backoff
        await asyncio.sleep(0.08)

        # Status inspection
        task_status = supervisor._tasks["crashing_task"]
        self.assertFalse(task_status.is_healthy)
        self.assertGreaterEqual(task_status.restarts, 2)
        self.assertFalse(supervisor.is_healthy)

        await supervisor.stop()

    def test_state_machine_valid_and_invalid_transitions(self) -> None:
        """Verify strict engine state transition rules."""
        sm = EngineStateMachine(initial_state=EngineState.INITIALISING)

        # INITIALISING -> WARMING_UP
        sm.transition(EngineState.WARMING_UP, reason="Loading candles")
        self.assertEqual(sm.current_state, EngineState.WARMING_UP)

        # WARMING_UP -> RUNNING
        sm.transition(EngineState.RUNNING, reason="Warmup complete")
        self.assertEqual(sm.current_state, EngineState.RUNNING)

        # RUNNING -> PAUSED
        sm.transition(EngineState.PAUSED, reason="User pause")
        self.assertEqual(sm.current_state, EngineState.PAUSED)

        # PAUSED -> RUNNING
        sm.transition(EngineState.RUNNING, reason="User resume")
        self.assertEqual(sm.current_state, EngineState.RUNNING)

        # RUNNING -> HALTED
        sm.transition(EngineState.HALTED, reason="Emergency halt")
        self.assertEqual(sm.current_state, EngineState.HALTED)
        self.assertTrue(sm.is_halted)

        # HALTED -> RUNNING directly is STRICTLY ILLEGAL
        with self.assertRaises(StateTransitionError):
            sm.transition(EngineState.RUNNING, reason="Attempted illegal direct resume")

        # HALTED -> PAUSED via human reset
        sm.transition(EngineState.PAUSED, reason="Reset to paused")
        self.assertEqual(sm.current_state, EngineState.PAUSED)

    def test_kill_switch_trigger_and_reset_token_validation(self) -> None:
        """Kill switch halts engine; reset strictly enforces 'CONFIRM_RESET' token."""
        self.assertEqual(self.state_machine.current_state, EngineState.RUNNING)
        self.assertFalse(self.kill_switch.is_active)

        # Trigger kill switch
        event = self.kill_switch.trigger(
            source="control_plane_api",
            reason="Operator hit emergency button",
        )
        self.assertTrue(self.kill_switch.is_active)
        self.assertEqual(self.state_machine.current_state, EngineState.HALTED)
        self.assertEqual(event.trigger_source, "control_plane_api")

        # Invalid confirmation token must be rejected
        reset_rejected = self.kill_switch.reset_from_halt(
            confirmation_token="WRONG_TOKEN",
            expected_token="CONFIRM_RESET",
        )
        self.assertFalse(reset_rejected)
        self.assertEqual(self.state_machine.current_state, EngineState.HALTED)
        self.assertTrue(self.kill_switch.is_active)

        # Valid confirmation token resets engine state to PAUSED
        reset_ok = self.kill_switch.reset_from_halt(
            confirmation_token="CONFIRM_RESET",
            expected_token="CONFIRM_RESET",
        )
        self.assertTrue(reset_ok)
        self.assertEqual(self.state_machine.current_state, EngineState.PAUSED)
        self.assertFalse(self.kill_switch.is_active)

    async def test_control_secret_authorization_logic(self) -> None:
        """State-changing operations must require matching control plane shared secret."""
        try:
            from fastapi import HTTPException
        except ImportError:
            from app.api.deps import HTTPException  # type: ignore[assignment]
        from app.api.deps import verify_control_secret

        configured_secret = self.settings.CONTROL_PLANE_SECRET

        # Valid secret returns the secret
        authorized = await verify_control_secret(x_control_secret=configured_secret)
        self.assertEqual(authorized, configured_secret)

        # Empty secret raises HTTP 401
        with self.assertRaises(HTTPException) as ctx_empty:
            await verify_control_secret(x_control_secret="")
        self.assertEqual(ctx_empty.exception.status_code, 401)
        self.assertIn("Invalid or missing X-Control-Secret", ctx_empty.exception.detail)

        # Wrong secret raises HTTP 401
        with self.assertRaises(HTTPException) as ctx_wrong:
            await verify_control_secret(x_control_secret="invalid_password_123")
        self.assertEqual(ctx_wrong.exception.status_code, 401)

        # Unauthorized admin attempt raises HTTP 401
        with self.assertRaises(HTTPException) as ctx_admin:
            await verify_control_secret(x_control_secret="admin")
        self.assertEqual(ctx_admin.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
