"""Position safety watchdog.

Per Section 10.6 of agent.md and PROJECT.md:
Monitors open positions on the exchange. If any open position lacks
an active exchange-side protective bracket, triggers the emergency kill switch
and immediately flattens open positions to prevent catastrophic naked exposure.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.contracts import PositionView
from app.core.logging import get_logger
from app.exchange.client import ExchangeClientProtocol
from app.risk.kill_switch import KillSwitch

logger = get_logger("watchdog")


class UnprotectedPositionWatchdog:
    """Monitors exchange positions to ensure every open position is bracketed."""

    def __init__(
        self,
        exchange: ExchangeClientProtocol,
        kill_switch: KillSwitch,
        check_interval_seconds: float = 1.0,
    ) -> None:
        self.exchange = exchange
        self.kill_switch = kill_switch
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def inspect_positions(self) -> list[PositionView]:
        """Inspect open positions. If any position lacks an active bracket, trigger kill switch and flatten."""
        positions = await self.exchange.get_positions()
        unprotected = [p for p in positions if not p.has_active_bracket and p.contracts > 0]

        if unprotected:
            for pos in unprotected:
                logger.critical(
                    "WATCHDOG ALERT: Position in %s (%d contracts) lacks exchange-side bracket protection!",
                    pos.symbol,
                    pos.contracts,
                )
                self.kill_switch.trigger(
                    source="unprotected_position_watchdog",
                    reason=f"Position in {pos.symbol} lacks exchange-side bracket protection",
                    details={"symbol": pos.symbol, "contracts": pos.contracts},
                )
            # Emergency flatten all positions
            await self.exchange.close_all()

        return unprotected

    async def run(self) -> None:
        """Continuous inspection loop for supervisor execution."""
        self._running = True
        while self._running:
            try:
                await self.inspect_positions()
            except Exception as exc:
                logger.error("Watchdog inspection error: %s", exc)
            await asyncio.sleep(self.check_interval_seconds)

    def stop(self) -> None:
        """Stop the watchdog loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
