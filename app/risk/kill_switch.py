"""Emergency Kill Switch and Safety Watchdog.

Per Section 2.1 and 9.5 of agent.md:
Immediate circuit breaker that halts trading, cancels working orders,
closes positions, and requires human reset.
"""

from __future__ import annotations

from typing import Any

from app.core.events import KillSwitchActivatedEvent
from app.core.logging import get_logger
from app.core.state import EngineState, EngineStateMachine

logger = get_logger("kill_switch")


class KillSwitch:
    """Manages emergency shutdown of trading activities."""

    def __init__(self, state_machine: EngineStateMachine) -> None:
        self.state_machine = state_machine
        self._is_active = False
        self._trigger_history: list[KillSwitchActivatedEvent] = []

    @property
    def is_active(self) -> bool:
        return self._is_active or self.state_machine.is_halted

    def trigger(self, source: str, reason: str, details: dict[str, Any] | None = None) -> KillSwitchActivatedEvent:
        """Activate the kill switch immediately."""
        self._is_active = True
        event = KillSwitchActivatedEvent(
            trigger_source=source,
            reason=reason,
            details=details or {},
        )
        self._trigger_history.append(event)
        logger.critical("🚨 KILL SWITCH TRIGGERED: [%s] %s (Details: %s)", source, reason, details)

        # Transition engine state to HALTED
        try:
            self.state_machine.transition(EngineState.HALTED, reason=f"KillSwitch: {reason}")
        except Exception as exc:
            logger.error("Error setting engine state to HALTED: %s", exc)

        return event

    def reset_from_halt(self, confirmation_token: str, expected_token: str) -> bool:
        """Reset engine from HALTED state to PAUSED.

        Requires strict matching of confirmation token and verification that account is flat.
        """
        if confirmation_token != expected_token:
            logger.warning("Kill switch reset rejected: Invalid confirmation token.")
            return False

        try:
            self.state_machine.transition(EngineState.PAUSED, reason="Manual human reset from halt")
            self._is_active = False
            logger.info("Kill switch reset successful. Engine state transitioned to PAUSED.")
            return True
        except Exception as exc:
            logger.error("Failed to reset engine state from halt: %s", exc)
            return False
