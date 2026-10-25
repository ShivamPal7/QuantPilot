"""Order execution manager.

Per Section 9.6 of agent.md:
Converts approved intents into marketable limit orders, attaches brackets,
and manages the order lifecycle.
"""

from __future__ import annotations

from decimal import Decimal
import uuid

from app.core.contracts import (
    Direction,
    MarketSnapshot,
    OrderIntent,
    OrderRecord,
    OrderRole,
    OrderState,
    RiskVerdict,
)
from app.core.logging import get_logger
from app.execution.idempotency import generate_client_order_id
from app.exchange.client import ExchangeClientProtocol

logger = get_logger("execution_manager")


class ExecutionManager:
    """Oversees order placement, bracket attachment, and state tracking."""

    def __init__(self, exchange: ExchangeClientProtocol) -> None:
        self.exchange = exchange
        self._orders: dict[str, OrderRecord] = {}

    async def execute_intent(
        self,
        intent: OrderIntent,
        verdict: RiskVerdict,
        snapshot: MarketSnapshot,
    ) -> OrderRecord | None:
        """Submit approved order with server-side brackets."""
        if verdict.approved_contracts < 1:
            logger.warning("ExecutionManager: No approved contracts to execute.")
            return None

        client_order_id = generate_client_order_id(
            strategy_name=intent.strategy_name,
            decision_id=intent.decision_id,
            role="ent",
        )

        side = "buy" if intent.direction == Direction.LONG else "sell"
        # Marketable limit bounded by touch
        limit_price = snapshot.best_ask if intent.direction == Direction.LONG else snapshot.best_bid

        # Calculate bracket prices using BracketManager
        bracket_sl = None
        bracket_tp = None
        if intent.proposed_stop_distance > Decimal("0"):
            from app.execution.bracket import BracketManager
            brackets = BracketManager.compute_brackets(
                entry_price=limit_price,
                direction=intent.direction,
                stop_distance=intent.proposed_stop_distance,
                tp_distance=intent.proposed_tp_distance,
                tick_size=Decimal("0.5"),
            )
            bracket_sl = brackets.stop_loss_price
            bracket_tp = brackets.take_profit_price

        logger.info(
            "Placing %s order for %d contracts of %s (Price: %s, SL: %s, TP: %s, ClOrdID: %s)",
            side.upper(),
            verdict.approved_contracts,
            intent.symbol,
            limit_price,
            bracket_sl,
            bracket_tp,
            client_order_id,
        )

        try:
            res = await self.exchange.place_order(
                symbol=intent.symbol,
                size_contracts=verdict.approved_contracts,
                side=side,
                order_type="limit",
                price=limit_price,
                client_order_id=client_order_id,
                bracket_stop_loss_price=bracket_sl,
                bracket_take_profit_price=bracket_tp,
            )

            record = OrderRecord(
                internal_id=str(uuid.uuid4()),
                client_order_id=client_order_id,
                parent_decision_id=intent.decision_id,
                symbol=intent.symbol,
                role=OrderRole.ENTRY,
                state=OrderState.SUBMITTED,
                side=side,
                size_contracts=verdict.approved_contracts,
                price=limit_price,
                exchange_order_id=str(res.get("id")) if res.get("id") else None,
            )
            self._orders[client_order_id] = record
            return record

        except TimeoutError as exc:
            logger.warning(
                "Timeout placing order %s: %s. Querying exchange by client_order_id to resolve in-flight state...",
                client_order_id,
                exc,
            )
            resolved = await self.resolve_in_flight_order(
                client_order_id=client_order_id,
                parent_decision_id=intent.decision_id,
                symbol=intent.symbol,
                side=side,
                size_contracts=verdict.approved_contracts,
                price=limit_price,
            )
            return resolved

        except Exception as exc:
            logger.error("Failed to place order: %s", exc)
            return None

    async def resolve_in_flight_order(
        self,
        client_order_id: str,
        parent_decision_id: str = "in_flight_resolution",
        symbol: str = "",
        side: str = "",
        size_contracts: int = 0,
        price: Decimal = Decimal("0"),
    ) -> OrderRecord | None:
        """Query exchange by client_order_id to determine order state following a timeout or network drop."""
        try:
            existing = await self.exchange.get_order_by_client_id(client_order_id)
            if existing is not None:
                order_state = OrderState.FILLED if existing.get("state") == "filled" else OrderState.SUBMITTED
                record = OrderRecord(
                    internal_id=str(uuid.uuid4()),
                    client_order_id=client_order_id,
                    parent_decision_id=parent_decision_id,
                    symbol=existing.get("product_symbol", symbol),
                    role=OrderRole.ENTRY,
                    state=order_state,
                    side=existing.get("side", side),
                    size_contracts=int(existing.get("size", size_contracts)),
                    price=Decimal(str(existing.get("price", price))),
                    exchange_order_id=str(existing.get("id")) if existing.get("id") else None,
                )
                self._orders[client_order_id] = record
                logger.info("Successfully resolved in-flight order %s: state=%s", client_order_id, order_state)
                return record
            else:
                logger.info("In-flight order %s not found on exchange.", client_order_id)
                return None
        except Exception as exc:
            logger.error("Failed to resolve in-flight order %s: %s", client_order_id, exc)
            return None
