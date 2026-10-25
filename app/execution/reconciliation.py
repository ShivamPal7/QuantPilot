"""Exchange state reconciliation routine.

Per Section 9.6 and 11.4 of agent.md:
Synchronizes local position and order tracking with Delta Exchange truth.
Adopts orphan positions, alerts on discrepancies, and updates cache.
"""

from __future__ import annotations

from typing import Any

from app.core.contracts import PositionView
from app.core.events import ReconciliationMismatchEvent
from app.core.logging import get_logger
from app.exchange.client import ExchangeClientProtocol
from app.exchange.errors import RateLimitExceededError
from app.exchange.rate_limiter import RateLimitAccountant

logger = get_logger("reconciliation")


class Reconciler:
    """Ensures local state matches exchange truth."""

    def __init__(
        self,
        exchange: ExchangeClientProtocol,
        rate_limiter: RateLimitAccountant | None = None,
    ) -> None:
        self.exchange = exchange
        self.rate_limiter = rate_limiter
        self.last_reconciled_positions: list[PositionView] = []
        self.last_reconciled_orders: list[dict[str, Any]] = []
        self.is_initial_sync_done = False

    async def reconcile(self) -> list[ReconciliationMismatchEvent]:
        """Perform reconciliation pass comparing local cache against exchange REST source of truth."""
        mismatches: list[ReconciliationMismatchEvent] = []
        try:
            exchange_positions = await self.exchange.get_positions()

            # Compare against existing cache if already initialized
            if self.is_initial_sync_done:
                old_map = {p.symbol: p for p in self.last_reconciled_positions if p.contracts > 0}
                new_map = {p.symbol: p for p in exchange_positions if p.contracts > 0}

                # 1. Detect position closures or reductions
                for sym, old_pos in old_map.items():
                    if sym not in new_map:
                        logger.info("Reconciliation detected position closure on exchange: %s", sym)
                        mismatches.append(
                            ReconciliationMismatchEvent(
                                mismatch_type="position_closed",
                                internal_val=old_pos.contracts,
                                exchange_val=0,
                            )
                        )
                    elif new_map[sym].contracts != old_pos.contracts:
                        logger.warning(
                            "Reconciliation detected size mismatch on %s: local=%d, exchange=%d",
                            sym,
                            old_pos.contracts,
                            new_map[sym].contracts,
                        )
                        mismatches.append(
                            ReconciliationMismatchEvent(
                                mismatch_type="position_size",
                                internal_val=old_pos.contracts,
                                exchange_val=new_map[sym].contracts,
                            )
                        )

                # 2. Detect orphan positions opened on exchange
                for sym, new_pos in new_map.items():
                    if sym not in old_map:
                        logger.warning(
                            "Reconciliation detected orphan exchange position in %s: %d contracts",
                            sym,
                            new_pos.contracts,
                        )
                        mismatches.append(
                            ReconciliationMismatchEvent(
                                mismatch_type="orphan_position",
                                internal_val=0,
                                exchange_val=new_pos.contracts,
                            )
                        )

            # Update position cache with exchange truth
            self.last_reconciled_positions = exchange_positions

            # Also reconcile open orders
            try:
                self.last_reconciled_orders = await self.exchange.get_active_orders()
            except Exception as o_exc:
                logger.debug("Active orders sync skipped: %s", o_exc)

            self.is_initial_sync_done = True
            logger.info("Reconciliation complete. Active positions count: %d", len(exchange_positions))

        except RateLimitExceededError as exc:
            logger.warning("Reconciliation encountered HTTP 429 rate limit: %s", exc)
            if self.rate_limiter:
                self.rate_limiter.handle_429(retry_after_seconds=5.0)
        except Exception as exc:
            logger.error("Reconciliation failed to fetch exchange positions: %s", exc)

        return mismatches
