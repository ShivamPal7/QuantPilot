"""In-memory Fake Exchange for integration and chaos tests.

Per Section 9.1 of agent.md:
Implements ExchangeClientProtocol. Can simulate fills, rejects,
rate limit errors, clock drift, synthetic candles, and price-triggered brackets.
"""

from __future__ import annotations

import math
import time
import uuid
from datetime import datetime, timezone
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
        self.bracket_orders: dict[str, dict[str, Decimal]] = {}
        self.custom_candles: list[Candle] = []

        # Chaos flags
        self.simulate_rate_limit = False
        self.simulate_rejection = False
        self.simulated_drift_seconds = 0.0
        self.simulate_timeout = False
        self.simulate_timeout_post_placement = False

        # Current market price
        self.current_bid = Decimal("65000.0")
        self.current_ask = Decimal("65005.0")
        self.contract_multiplier = Decimal("0.001")

    @property
    def wallet_balance(self) -> Decimal:
        return self.balance

    @wallet_balance.setter
    def wallet_balance(self, value: Decimal) -> None:
        self.balance = value

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
        if self.simulate_rate_limit:
            raise RateLimitExceededError()
        if symbol:
            return [p for p in self.positions if p.symbol == symbol]
        return list(self.positions)

    async def get_active_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        if symbol:
            return [o for o in self.active_orders if o.get("product_symbol") == symbol]
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
        if self.simulate_timeout:
            raise TimeoutError("Simulated exchange timeout on order placement")
        if self.simulate_rate_limit:
            raise RateLimitExceededError()
        if self.simulate_rejection:
            rej_id = str(uuid.uuid4())
            rej_order = {
                "id": rej_id,
                "product_symbol": symbol,
                "size": size_contracts,
                "side": side.lower(),
                "price": str(price or self.current_bid),
                "client_order_id": client_order_id or f"fake_{rej_id[:8]}",
                "state": "rejected",
                "rejection_reason": "Insufficient margin",
            }
            self.order_history.append(rej_order)
            raise InsufficientMarginError("Simulated rejection in chaos test")

        # Idempotency check: if client_order_id exists, return existing order
        if client_order_id:
            existing = await self.get_order_by_client_id(client_order_id)
            if existing is not None:
                return existing

        order_id = str(uuid.uuid4())
        fill_price = price if price is not None else (self.current_ask if side.lower() == "buy" else self.current_bid)
        order_obj = {
            "id": order_id,
            "product_symbol": symbol,
            "size": size_contracts,
            "side": side.lower(),
            "price": str(fill_price),
            "client_order_id": client_order_id or f"fake_{order_id[:8]}",
            "bracket_orders": {
                "stop_loss": str(bracket_stop_loss_price) if bracket_stop_loss_price else None,
                "take_profit": str(bracket_take_profit_price) if bracket_take_profit_price else None,
            },
            "state": "filled",
        }
        self.order_history.append(order_obj)

        # Store bracket parameters for price-triggered bracket execution
        if bracket_stop_loss_price or bracket_take_profit_price:
            self.bracket_orders[symbol] = {
                "stop_loss": bracket_stop_loss_price,
                "take_profit": bracket_take_profit_price,
            }

        # Update position
        pos_side = "long" if side.lower() == "buy" else "short"
        has_bracket = bool(bracket_stop_loss_price or bracket_take_profit_price)

        existing_pos_idx = next((i for i, p in enumerate(self.positions) if p.symbol == symbol), None)
        if existing_pos_idx is None:
            self.positions.append(
                PositionView(
                    symbol=symbol,
                    side=pos_side,
                    contracts=size_contracts,
                    entry_price=fill_price,
                    mark_price=fill_price,
                    unrealized_pnl=Decimal("0"),
                    leverage=3,
                    liquidation_price=None,
                    has_active_bracket=has_bracket,
                    reconciled_at=datetime.now(timezone.utc),
                )
            )
        else:
            existing = self.positions[existing_pos_idx]
            if existing.side == pos_side:
                total_contracts = existing.contracts + size_contracts
                weighted_entry = (
                    (existing.entry_price * existing.contracts) + (fill_price * size_contracts)
                ) / total_contracts
                self.positions[existing_pos_idx] = PositionView(
                    symbol=symbol,
                    side=pos_side,
                    contracts=total_contracts,
                    entry_price=weighted_entry,
                    mark_price=fill_price,
                    unrealized_pnl=Decimal("0"),
                    leverage=3,
                    liquidation_price=None,
                    has_active_bracket=has_bracket or existing.has_active_bracket,
                    reconciled_at=datetime.now(timezone.utc),
                )
            else:
                # Opposite side order: reduce, close, or flip
                if size_contracts < existing.contracts:
                    remaining_contracts = existing.contracts - size_contracts
                    if existing.side == "long":
                        pnl = (fill_price - existing.entry_price) * size_contracts * self.contract_multiplier
                    else:
                        pnl = (existing.entry_price - fill_price) * size_contracts * self.contract_multiplier
                    self.balance += pnl
                    self.positions[existing_pos_idx] = PositionView(
                        symbol=symbol,
                        side=existing.side,
                        contracts=remaining_contracts,
                        entry_price=existing.entry_price,
                        mark_price=fill_price,
                        unrealized_pnl=Decimal("0"),
                        leverage=3,
                        liquidation_price=None,
                        has_active_bracket=has_bracket or existing.has_active_bracket,
                        reconciled_at=datetime.now(timezone.utc),
                    )
                elif size_contracts == existing.contracts:
                    if existing.side == "long":
                        pnl = (fill_price - existing.entry_price) * size_contracts * self.contract_multiplier
                    else:
                        pnl = (existing.entry_price - fill_price) * size_contracts * self.contract_multiplier
                    self.balance += pnl
                    self.positions.pop(existing_pos_idx)
                    self.bracket_orders.pop(symbol, None)
                else:
                    if existing.side == "long":
                        pnl = (fill_price - existing.entry_price) * existing.contracts * self.contract_multiplier
                    else:
                        pnl = (existing.entry_price - fill_price) * existing.contracts * self.contract_multiplier
                    self.balance += pnl
                    flipped_contracts = size_contracts - existing.contracts
                    if not has_bracket:
                        self.bracket_orders.pop(symbol, None)
                    self.positions[existing_pos_idx] = PositionView(
                        symbol=symbol,
                        side=pos_side,
                        contracts=flipped_contracts,
                        entry_price=fill_price,
                        mark_price=fill_price,
                        unrealized_pnl=Decimal("0"),
                        leverage=3,
                        liquidation_price=None,
                        has_active_bracket=has_bracket,
                        reconciled_at=datetime.now(timezone.utc),
                    )

        if self.simulate_timeout_post_placement:
            raise TimeoutError("Simulated exchange timeout on order response")

        return order_obj

    async def cancel_order(self, order_id: str) -> bool:
        for idx, o in enumerate(self.active_orders):
            if o["id"] == order_id:
                o["state"] = "cancelled"
                self.order_history.append(self.active_orders.pop(idx))
                return True
        return False

    async def cancel_all(self, symbol: str | None = None) -> int:
        count = 0
        remaining = []
        for o in self.active_orders:
            if symbol is None or o.get("product_symbol") == symbol:
                o["state"] = "cancelled"
                self.order_history.append(o)
                count += 1
            else:
                remaining.append(o)
        self.active_orders = remaining
        return count

    async def close_all(self, symbol: str | None = None) -> bool:
        for pos in list(self.positions):
            if symbol is None or pos.symbol == symbol:
                exit_side = "sell" if pos.side == "long" else "buy"
                exit_price = self.current_bid if exit_side == "sell" else self.current_ask
                if pos.side == "long":
                    pnl = (exit_price - pos.entry_price) * pos.contracts * self.contract_multiplier
                else:
                    pnl = (pos.entry_price - exit_price) * pos.contracts * self.contract_multiplier
                self.balance += pnl
                self.order_history.append({
                    "id": str(uuid.uuid4()),
                    "product_symbol": pos.symbol,
                    "size": pos.contracts,
                    "side": exit_side,
                    "price": str(exit_price),
                    "client_order_id": f"close_{uuid.uuid4().hex[:8]}",
                    "state": "filled",
                    "role": "close_all",
                    "realized_pnl": str(pnl),
                })
        if symbol:
            self.positions = [p for p in self.positions if p.symbol != symbol]
            self.bracket_orders.pop(symbol, None)
        else:
            self.positions.clear()
            self.bracket_orders.clear()
        await self.cancel_all(symbol)
        return True

    async def get_ticker(self, symbol: str) -> MarketSnapshot:
        now = datetime.fromtimestamp(time.time() + self.simulated_drift_seconds, tz=timezone.utc)
        mark = (self.current_bid + self.current_ask) / Decimal("2")
        return MarketSnapshot(
            symbol=symbol,
            timestamp=now,
            best_bid=self.current_bid,
            best_ask=self.current_ask,
            bid_size=Decimal("10.0"),
            ask_size=Decimal("10.0"),
            mark_price=mark,
            spot_price=self.current_bid,
        )

    async def get_candles(
        self, symbol: str, resolution: str, start_time_s: int, end_time_s: int
    ) -> list[Candle]:
        if end_time_s <= start_time_s or start_time_s < 0 or end_time_s < 0:
            return []

        interval = 60
        if resolution in ("1m", "60"):
            interval = 60
        elif resolution in ("5m", "300"):
            interval = 300
        elif resolution in ("15m", "900"):
            interval = 900
        elif resolution in ("1h", "3600"):
            interval = 3600
        else:
            try:
                interval = int(resolution)
                if interval <= 0:
                    return []
            except ValueError:
                return []

        if self.custom_candles:
            return [
                c for c in self.custom_candles
                if c.symbol == symbol and start_time_s <= int(c.open_time.timestamp()) < end_time_s
            ]

        candles: list[Candle] = []
        cur_t = start_time_s
        idx = 0
        while cur_t < end_time_s:
            cycle = (cur_t // interval) % 60
            wave = math.sin(cycle / 5.0) * 80.0
            base_p = self.current_bid + Decimal(str(round(wave, 2)))
            open_p = base_p
            high_p = base_p + Decimal("25.0")
            low_p = base_p - Decimal("25.0")
            close_p = base_p + Decimal("10.0") if cycle % 2 == 0 else base_p - Decimal("10.0")

            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=resolution,
                    open_time=datetime.fromtimestamp(cur_t, tz=timezone.utc),
                    close_time=datetime.fromtimestamp(cur_t + interval, tz=timezone.utc),
                    open=open_p,
                    high=high_p,
                    low=low_p,
                    close=close_p,
                    volume=Decimal("150.0"),
                    is_closed=True,
                    source="fake_exchange",
                )
            )
            cur_t += interval
            idx += 1
            if idx >= 500:
                break

        return candles

    async def set_market_price(
        self, new_bid: Decimal, new_ask: Decimal | None = None
    ) -> list[dict[str, Any]]:
        """Update market price and trigger any stop-loss or take-profit bracket executions."""
        self.current_bid = new_bid
        self.current_ask = new_ask if new_ask is not None else (new_bid + Decimal("5.0"))
        return await self._check_bracket_triggers()

    async def _check_bracket_triggers(self) -> list[dict[str, Any]]:
        """Evaluate open positions against bracket triggers."""
        triggered: list[dict[str, Any]] = []
        for pos in list(self.positions):
            if not pos.has_active_bracket:
                continue
            brackets = self.bracket_orders.get(pos.symbol)
            if not brackets:
                continue

            sl = brackets.get("stop_loss")
            tp = brackets.get("take_profit")

            if pos.side == "long":
                # Long SL: price falls to or below stop_loss
                if sl is not None and self.current_bid <= sl:
                    exit_price = self.current_bid
                    pnl = (exit_price - pos.entry_price) * pos.contracts * self.contract_multiplier
                    self.balance += pnl
                    evt = {
                        "id": str(uuid.uuid4()),
                        "product_symbol": pos.symbol,
                        "size": pos.contracts,
                        "side": "sell",
                        "price": str(exit_price),
                        "state": "filled",
                        "role": "BRACKET_STOP",
                        "reason": "STOP_LOSS_TRIGGERED",
                        "realized_pnl": str(pnl),
                    }
                    self.order_history.append(evt)
                    self.positions.remove(pos)
                    self.bracket_orders.pop(pos.symbol, None)
                    triggered.append(evt)
                # Long TP: price rises to or above take_profit
                elif tp is not None and self.current_bid >= tp:
                    exit_price = self.current_bid
                    pnl = (exit_price - pos.entry_price) * pos.contracts * self.contract_multiplier
                    self.balance += pnl
                    evt = {
                        "id": str(uuid.uuid4()),
                        "product_symbol": pos.symbol,
                        "size": pos.contracts,
                        "side": "sell",
                        "price": str(exit_price),
                        "state": "filled",
                        "role": "BRACKET_TAKE_PROFIT",
                        "reason": "TAKE_PROFIT_TRIGGERED",
                        "realized_pnl": str(pnl),
                    }
                    self.order_history.append(evt)
                    self.positions.remove(pos)
                    self.bracket_orders.pop(pos.symbol, None)
                    triggered.append(evt)

            elif pos.side == "short":
                # Short SL: price rises to or above stop_loss
                if sl is not None and self.current_ask >= sl:
                    exit_price = self.current_ask
                    pnl = (pos.entry_price - exit_price) * pos.contracts * self.contract_multiplier
                    self.balance += pnl
                    evt = {
                        "id": str(uuid.uuid4()),
                        "product_symbol": pos.symbol,
                        "size": pos.contracts,
                        "side": "buy",
                        "price": str(exit_price),
                        "state": "filled",
                        "role": "BRACKET_STOP",
                        "reason": "STOP_LOSS_TRIGGERED",
                        "realized_pnl": str(pnl),
                    }
                    self.order_history.append(evt)
                    self.positions.remove(pos)
                    self.bracket_orders.pop(pos.symbol, None)
                    triggered.append(evt)
                # Short TP: price falls to or below take_profit
                elif tp is not None and self.current_ask <= tp:
                    exit_price = self.current_ask
                    pnl = (pos.entry_price - exit_price) * pos.contracts * self.contract_multiplier
                    self.balance += pnl
                    evt = {
                        "id": str(uuid.uuid4()),
                        "product_symbol": pos.symbol,
                        "size": pos.contracts,
                        "side": "buy",
                        "price": str(exit_price),
                        "state": "filled",
                        "role": "BRACKET_TAKE_PROFIT",
                        "reason": "TAKE_PROFIT_TRIGGERED",
                        "realized_pnl": str(pnl),
                    }
                    self.order_history.append(evt)
                    self.positions.remove(pos)
                    self.bracket_orders.pop(pos.symbol, None)
                    triggered.append(evt)

        return triggered
