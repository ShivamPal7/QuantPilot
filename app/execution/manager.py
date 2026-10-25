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

        # Calculate bracket prices
        bracket_sl = None
        if intent.proposed_stop_distance > Decimal("0"):
            if intent.direction == Direction.LONG:
                bracket_sl = limit_price - intent.proposed_stop_distance
            else:
                bracket_sl = limit_price + intent.proposed_stop_distance

        bracket_tp = None
        if intent.proposed_tp_distance and intent.proposed_tp_distance > Decimal("0"):
            if intent.direction == Direction.LONG:
                bracket_tp = limit_price + intent.proposed_tp_distance
            else:
                bracket_tp = limit_price - intent.proposed_tp_distance

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

        except Exception as exc:
            logger.error("Failed to place order: %s", exc)
            return None
