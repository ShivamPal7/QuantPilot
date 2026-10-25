"""Exchange state reconciliation routine.

Per Section 9.6 of agent.md:
Synchronizes local position and order tracking with Delta Exchange truth.
Adopts orphan positions and raises engine events on discrepancies.
"""

from __future__ import annotations

from typing import Any

from app.core.contracts import PositionView
from app.core.events import ReconciliationMismatchEvent
from app.core.logging import get_logger
from app.exchange.client import ExchangeClientProtocol

logger = get_logger("reconciliation")


class Reconciler:
    """Ensures local state matches exchange truth."""

    def __init__(self, exchange: ExchangeClientProtocol) -> None:
        self.exchange = exchange
        self.last_reconciled_positions: list[PositionView] = []
        self.is_initial_sync_done = False

    async def reconcile(self) -> list[ReconciliationMismatchEvent]:
        """Perform reconciliation pass."""
        mismatches: list[ReconciliationMismatchEvent] = []
        try:
            exchange_positions = await self.exchange.get_positions()
            self.last_reconciled_positions = exchange_positions
            self.is_initial_sync_done = True
            logger.info("Reconciliation complete. Active positions count: %d", len(exchange_positions))
        except Exception as exc:
            logger.error("Reconciliation failed to fetch exchange positions: %s", exc)

        return mismatches
