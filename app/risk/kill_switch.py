"""Emergency Kill Switch and Safety Watchdog.

Per Section 2.1 and 9.5 of agent.md:
Immediate circuit breaker that halts trading, cancels working orders,
flattens exchange positions via reduce-only orders, and requires authenticated human reset.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.events import KillSwitchActivatedEvent
from app.core.logging import get_logger
from app.core.state import EngineState, EngineStateMachine
from app.exchange.client import ExchangeClientProtocol

logger = get_logger("kill_switch")


class KillSwitch:
    """Manages emergency shutdown of trading activities and exchange flattening."""

    def __init__(
        self,
        state_machine: EngineStateMachine,
        exchange: ExchangeClientProtocol | None = None,
        reset_token: str = "CONFIRM_RESET",
    ) -> None:
        self.state_machine = state_machine
        self.exchange = exchange
        self.reset_token = reset_token
        self._is_active = False
        self._trigger_history: list[KillSwitchActivatedEvent] = []

    def set_exchange(self, exchange: ExchangeClientProtocol) -> None:
        """Attach or update exchange client instance for flattening operations."""
        self.exchange = exchange

    @property
    def is_active(self) -> bool:
        return self._is_active or self.state_machine.is_halted

    def trigger(
        self,
        source: str,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> KillSwitchActivatedEvent:
        """Activate the kill switch immediately, halt engine, and flatten exchange positions."""
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

        # Genuine exchange flattening: cancel orders and close open positions
        if self.exchange is not None:
            self._schedule_flatten()

        return event

    def _schedule_flatten(self) -> None:
        """Schedule or execute exchange flattening."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.flatten())
        except RuntimeError:
            try:
                asyncio.run(self.flatten())
            except Exception as exc:
                logger.error("Failed to execute exchange flattening: %s", exc)

    async def flatten(self) -> dict[str, Any]:
        """Cancel working orders and close all positions via reduce-only orders."""
        results: dict[str, Any] = {"cancelled_orders": 0, "positions_closed": False}
        if self.exchange is None:
            logger.warning("Kill switch flatten requested but no exchange client configured.")
            return results

        try:
            cancelled = await self.exchange.cancel_all()
            results["cancelled_orders"] = cancelled
            logger.info("KillSwitch: Cancelled %d working orders on exchange.", cancelled)
        except Exception as exc:
            logger.error("KillSwitch: Failed to cancel orders during flattening: %s", exc)

        try:
            closed = await self.exchange.close_all()
            results["positions_closed"] = closed
            logger.info("KillSwitch: Closed all open positions on exchange: %s", closed)
        except Exception as exc:
            logger.error("KillSwitch: Failed to close positions during flattening: %s", exc)

        return results

    def reset_from_halt(self, confirmation_token: str, expected_token: str = "CONFIRM_RESET") -> bool:
        """Reset engine from HALTED state to PAUSED.

        Requires strict matching of confirmation token ("CONFIRM_RESET").
        """
        target = expected_token or self.reset_token
        if confirmation_token != target:
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
