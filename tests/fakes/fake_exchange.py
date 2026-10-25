"""In-memory Fake Exchange for integration and chaos tests.

Per Section 9.1 of agent.md:
Implements ExchangeClientProtocol. Can simulate fills, rejects,
rate limit errors, and clock drift.
"""

from __future__ import annotations

import time
import uuid
from decimal import Decimal
from typing import Any

from app.core.contracts import Candle, MarketSnapshot, PositionView
from app.exchange.client import ExchangeClientProtocol
from app.exchange.errors import InsufficientMarginError, RateLimitExceededError


class FakeExchange(ExchangeClientProtocol):
    """In-memory simulation of Delta Exchange."""

    def __init__(self, initial_balance: Decimal = Decimal("10000.0")) -> None:
        self.balance = initial_balance
        self.positions: list[PositionView] = []
        self.active_orders: list[dict[str, Any]] = []
        self.order_history: list[dict[str, Any]] = []

        # Chaos flags
        self.simulate_rate_limit = False
        self.simulate_rejection = False
        self.simulated_drift_seconds = 0.0

        # Current market price
        self.current_bid = Decimal("65000.0")
        self.current_ask = Decimal("65005.0")

    async def get_server_time(self) -> float:
        return time.time() + self.simulated_drift_seconds

    async def get_product(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "contract_value": "0.001",
            "tick_size": "0.5",
            "trading_status": "operational",
            "max_leverage": 100,
        }

    async def get_balances(self) -> dict[str, Decimal]:
        return {"USDT": self.balance}

    async def get_positions(self, symbol: str | None = None) -> list[PositionView]:
        if symbol:
            return [p for p in self.positions if p.symbol == symbol]
        return list(self.positions)

    async def get_active_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        return list(self.active_orders)

    async def get_order_by_client_id(self, client_order_id: str) -> dict[str, Any] | None:
        for o in self.active_orders + self.order_history:
            if o.get("client_order_id") == client_order_id:
                return o
        return None

    async def place_order(
        self,
        symbol: str,
        size_contracts: int,
        side: str,
        order_type: str = "limit",
        price: Decimal | None = None,
        client_order_id: str | None = None,
        bracket_stop_loss_price: Decimal | None = None,
        bracket_take_profit_price: Decimal | None = None,
    ) -> dict[str, Any]:
        if self.simulate_rate_limit:
            raise RateLimitExceededError()
        if self.simulate_rejection:
            raise InsufficientMarginError("Simulated rejection in chaos test")

        order_id = str(uuid.uuid4())
        order_obj = {
            "id": order_id,
            "product_symbol": symbol,
            "size": size_contracts,
            "side": side.lower(),
            "price": str(price) if price else str(self.current_ask if side == "buy" else self.current_bid),
            "client_order_id": client_order_id or f"fake_{order_id[:8]}",
            "bracket_orders": {
                "stop_loss": str(bracket_stop_loss_price) if bracket_stop_loss_price else None,
                "take_profit": str(bracket_take_profit_price) if bracket_take_profit_price else None,
            },
            "state": "filled",
        }
        self.order_history.append(order_obj)

        # Update position
        pos_side = "long" if side.lower() == "buy" else "short"
        self.positions = [
            PositionView(
                symbol=symbol,
                side=pos_side,
                contracts=size_contracts,
                entry_price=price or self.current_bid,
                mark_price=price or self.current_bid,
                unrealized_pnl=Decimal("0"),
                leverage=3,
                liquidation_price=None,
                has_active_bracket=bool(bracket_stop_loss_price),
            )
        ]
        return order_obj

    async def cancel_order(self, order_id: str) -> bool:
        self.active_orders = [o for o in self.active_orders if o["id"] != order_id]
        return True

    async def cancel_all(self, symbol: str | None = None) -> int:
        count = len(self.active_orders)
        self.active_orders.clear()
        return count

    async def close_all(self, symbol: str | None = None) -> bool:
        self.positions.clear()
        self.active_orders.clear()
        return True

    async def get_ticker(self, symbol: str) -> MarketSnapshot:
        return MarketSnapshot(
            symbol=symbol,
            timestamp=Candle(
                symbol=symbol,
                timeframe="1m",
                open_time=time.time(),
                close_time=time.time(),
                open=self.current_bid,
                high=self.current_ask,
                low=self.current_bid,
                close=self.current_bid,
                volume=Decimal("100"),
            ).close_time,
            best_bid=self.current_bid,
            best_ask=self.current_ask,
            bid_size=Decimal("10.0"),
            ask_size=Decimal("10.0"),
            mark_price=(self.current_bid + self.current_ask) / Decimal("2"),
            spot_price=self.current_bid,
        )

    async def get_candles(
        self, symbol: str, resolution: str, start_time_s: int, end_time_s: int
    ) -> list[Candle]:
        return []
