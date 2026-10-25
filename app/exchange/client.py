"""Internal exchange interface and Delta Exchange REST implementation.

Defined in Section 9.1 of agent.md.
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any, Protocol

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

from app.core.contracts import Candle, PositionView, MarketSnapshot
from app.core.logging import get_logger
from app.exchange.errors import (
    ExchangeError,
    RateLimitExceededError,
    InvalidKeyError,
    SignatureMismatchError,
    IPNotWhitelistedError,
)
from app.exchange.guard import assert_testnet_environment
from app.exchange.normalizers import parse_exchange_timestamp, to_decimal, to_int
from app.exchange.rate_limiter import (
    RateLimitAccountant,
    WEIGHT_ORDER_ACTION,
    WEIGHT_PUBLIC_READ,
)
from app.exchange.signing import build_auth_headers

logger = get_logger("exchange_client")


class ExchangeClientProtocol(Protocol):
    """Internal contract all exchange adapters (real and fake) must satisfy."""

    async def get_server_time(self) -> float: ...
    async def get_product(self, symbol: str) -> dict[str, Any]: ...
    async def get_balances(self) -> dict[str, Decimal]: ...
    async def get_positions(self, symbol: str | None = None) -> list[PositionView]: ...
    async def get_active_orders(self, symbol: str | None = None) -> list[dict[str, Any]]: ...
    async def get_order_by_client_id(self, client_order_id: str) -> dict[str, Any] | None: ...
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
    ) -> dict[str, Any]: ...
    async def cancel_order(self, order_id: str) -> bool: ...
    async def cancel_all(self, symbol: str | None = None) -> int: ...
    async def close_all(self, symbol: str | None = None) -> bool: ...
    async def get_ticker(self, symbol: str) -> MarketSnapshot: ...
    async def get_candles(
        self, symbol: str, resolution: str, start_time_s: int, end_time_s: int
    ) -> list[Candle]: ...


class DeltaRESTClient:
    """Async HTTP client for Delta Exchange India Testnet."""

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        api_secret: str = "",
        target_env: str = "testnet",
        rate_limiter: RateLimitAccountant | None = None,
    ) -> None:
        if httpx is None:
            raise ImportError("httpx is required to use DeltaRESTClient. Run 'pip install httpx'.")
        # Enforce startup testnet-only security guard
        assert_testnet_environment(target_env=target_env, rest_url=base_url)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.rate_limiter = rate_limiter or RateLimitAccountant()
        self._http_client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        await self._http_client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        weight: int = WEIGHT_PUBLIC_READ,
        auth_required: bool = False,
    ) -> dict[str, Any]:
        """Send authenticated or public HTTP request to Delta REST API."""
        if not self.rate_limiter.can_make_request(weight):
            logger.warning("Rate limit quota nearly exhausted. Backing off...")
            raise RateLimitExceededError()

        self.rate_limiter.record_usage(weight)
        url = f"{self.base_url}{path}"
        query_string = httpx.QueryParams(params or {}).raw.decode("utf-8") if params else ""
        body_str = httpx._content.encode_json(payload)[1].decode("utf-8") if payload else ""

        headers = {}
        if auth_required:
            headers = build_auth_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                method=method,
                path=path,
                query_string=query_string,
                body=body_str,
            )

        response = await self._http_client.request(
            method=method,
            url=url,
            params=params,
            json=payload,
            headers=headers,
        )

        if response.status_code == 429:
            retry_ms = int(response.headers.get("retry-after", "1")) * 1000
            raise RateLimitExceededError(retry_after_ms=retry_ms)
        elif response.status_code == 401:
            raise InvalidKeyError("Unauthorized (401) on Delta Exchange REST")
        elif response.status_code == 403:
            raise IPNotWhitelistedError("Forbidden (403): Verify IP whitelist and User-Agent")

        try:
            data = response.json()
        except Exception:
            raise ExchangeError(f"HTTP {response.status_code}: Non-JSON response")

        if not response.is_success or (isinstance(data, dict) and data.get("success") is False):
            err_msg = data.get("error", {}).get("message", response.text) if isinstance(data, dict) else response.text
            raise ExchangeError(f"Exchange error: {err_msg}")

        return data

    async def get_server_time(self) -> float:
        """Fetch exchange server time for clock-drift check."""
        # Fallback to local time if endpoint unavailable on testnet
        try:
            res = await self._request("GET", "/v2/server_time", weight=WEIGHT_PUBLIC_READ)
            return float(res.get("result", {}).get("server_time", time.time()))
        except Exception:
            return time.time()

    async def get_product(self, symbol: str) -> dict[str, Any]:
        """Look up live product specification by symbol."""
        res = await self._request("GET", f"/v2/products/{symbol}", weight=WEIGHT_PUBLIC_READ)
        return res.get("result", {})

    async def get_balances(self) -> dict[str, Decimal]:
        """Fetch wallet balances."""
        res = await self._request("GET", "/v2/wallet/balances", auth_required=True, weight=WEIGHT_PUBLIC_READ)
        result = {}
        for item in res.get("result", []):
            asset = item.get("asset_symbol", "UNKNOWN")
            result[asset] = to_decimal(item.get("balance", "0"))
        return result

    async def get_positions(self, symbol: str | None = None) -> list[PositionView]:
        """Fetch open margined positions."""
        params = {"symbol": symbol} if symbol else None
        res = await self._request("GET", "/v2/positions", params=params, auth_required=True, weight=WEIGHT_PUBLIC_READ)
        views = []
        for pos in res.get("result", []):
            size = to_int(pos.get("size", 0))
            if size == 0:
                continue
            views.append(
                PositionView(
                    symbol=pos.get("product_symbol", symbol or ""),
                    side="long" if size > 0 else "short",
                    contracts=abs(size),
                    entry_price=to_decimal(pos.get("entry_price", "0")),
                    mark_price=to_decimal(pos.get("mark_price", "0")),
                    unrealized_pnl=to_decimal(pos.get("unrealized_pnl", "0")),
                    leverage=to_int(pos.get("leverage", 1)),
                    liquidation_price=to_decimal(pos.get("liquidation_price")),
                    has_active_bracket=bool(pos.get("bracket_orders")),
                )
            )
        return views

    async def get_active_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params = {"symbol": symbol} if symbol else None
        res = await self._request("GET", "/v2/orders", params=params, auth_required=True, weight=WEIGHT_PUBLIC_READ)
        return res.get("result", [])

    async def get_order_by_client_id(self, client_order_id: str) -> dict[str, Any] | None:
        """Query order by client order ID for idempotency checking."""
        try:
            res = await self._request(
                "GET", f"/v2/orders/{client_order_id}", auth_required=True, weight=WEIGHT_PUBLIC_READ
            )
            return res.get("result")
        except ExchangeError:
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
        """Place order with optional bracket protections."""
        payload: dict[str, Any] = {
            "product_symbol": symbol,
            "size": size_contracts,
            "side": side.lower(),
            "order_type": order_type.lower(),
        }
        if price is not None:
            payload["limit_price"] = str(price)
        if client_order_id:
            payload["client_order_id"] = client_order_id

        # Bracket orders if provided
        if bracket_stop_loss_price is not None:
            payload["stop_loss_price"] = str(bracket_stop_loss_price)
        if bracket_take_profit_price is not None:
            payload["take_profit_price"] = str(bracket_take_profit_price)

        res = await self._request(
            "POST", "/v2/orders", payload=payload, auth_required=True, weight=WEIGHT_ORDER_ACTION
        )
        return res.get("result", {})

    async def cancel_order(self, order_id: str) -> bool:
        res = await self._request("DELETE", f"/v2/orders/{order_id}", auth_required=True, weight=WEIGHT_ORDER_ACTION)
        return bool(res.get("success", False))

    async def cancel_all(self, symbol: str | None = None) -> int:
        payload = {"product_symbol": symbol} if symbol else {}
        res = await self._request("DELETE", "/v2/orders/all", payload=payload, auth_required=True, weight=WEIGHT_ORDER_ACTION)
        return len(res.get("result", []))

    async def close_all(self, symbol: str | None = None) -> bool:
        payload = {"product_symbol": symbol} if symbol else {}
        res = await self._request("POST", "/v2/positions/close_all", payload=payload, auth_required=True, weight=WEIGHT_ORDER_ACTION)
        return bool(res.get("success", False))

    async def get_ticker(self, symbol: str) -> MarketSnapshot:
        res = await self._request("GET", f"/v2/tickers/{symbol}", weight=WEIGHT_PUBLIC_READ)
        data = res.get("result", {})
        quotes = data.get("quotes", {})
        return MarketSnapshot(
            symbol=symbol,
            timestamp=parse_exchange_timestamp(data.get("timestamp")),
            best_bid=to_decimal(quotes.get("best_bid")),
            best_ask=to_decimal(quotes.get("best_ask")),
            bid_size=to_decimal(quotes.get("bid_size")),
            ask_size=to_decimal(quotes.get("ask_size")),
            mark_price=to_decimal(data.get("mark_price")),
            spot_price=to_decimal(data.get("spot_price")),
        )

    async def get_candles(
        self, symbol: str, resolution: str, start_time_s: int, end_time_s: int
    ) -> list[Candle]:
        params = {
            "symbol": symbol,
            "resolution": resolution,
            "start": start_time_s,
            "end": end_time_s,
        }
        res = await self._request("GET", "/v2/chart/history", params=params, weight=WEIGHT_PUBLIC_READ)
        candles = []
        for item in res.get("result", []):
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=resolution,
                    open_time=parse_exchange_timestamp(item.get("time")),
                    close_time=parse_exchange_timestamp(item.get("time")),
                    open=to_decimal(item.get("open")),
                    high=to_decimal(item.get("high")),
                    low=to_decimal(item.get("low")),
                    close=to_decimal(item.get("close")),
                    volume=to_decimal(item.get("volume")),
                    is_closed=True,
                    source="delta_rest",
                )
            )
        return candles
