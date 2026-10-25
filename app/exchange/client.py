"""Internal exchange interface and Delta Exchange REST implementation.

Defined in Section 9.1 of agent.md.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
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
        # Enforce startup testnet-only security guard
        assert_testnet_environment(target_env=target_env, rest_url=base_url)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.rate_limiter = rate_limiter or RateLimitAccountant()
        self._http_client = httpx.AsyncClient(timeout=10.0) if httpx is not None else None
        self._product_cache: dict[str, dict[str, Any]] = {}

    async def close(self) -> None:
        if self._http_client is not None:
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

        if params:
            query_string = urllib.parse.urlencode(params)
            full_url = f"{url}?{query_string}"
        else:
            query_string = ""
            full_url = url

        body_str = json.dumps(payload, separators=(',', ':')) if payload else ""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "QuantPilot-GlassBoxDesk/1.0",
        }
        if auth_required:
            auth_hdrs = build_auth_headers(
                api_key=self.api_key,
                api_secret=self.api_secret,
                method=method,
                path=path,
                query_string=query_string,
                body=body_str,
            )
            headers.update(auth_hdrs)

        if self._http_client is not None:
            response = await self._http_client.request(
                method=method,
                url=url,
                params=params,
                json=payload,
                headers=headers,
            )
            status_code = response.status_code
            resp_headers = dict(response.headers)
            resp_text = response.text
            try:
                data = response.json()
            except Exception:
                data = None
        else:
            def _send_urllib() -> tuple[int, dict[str, str], str]:
                body_bytes = body_str.encode("utf-8") if body_str else None
                req = urllib.request.Request(full_url, data=body_bytes, headers=headers, method=method)
                try:
                    with urllib.request.urlopen(req, timeout=10.0) as resp:
                        s_code = resp.status
                        h_dict = {k.lower(): v for k, v in resp.headers.items()}
                        t_body = resp.read().decode("utf-8")
                        return s_code, h_dict, t_body
                except urllib.error.HTTPError as h_err:
                    s_code = h_err.code
                    h_dict = {k.lower(): v for k, v in h_err.headers.items()}
                    t_body = h_err.read().decode("utf-8")
                    return s_code, h_dict, t_body
                except Exception as exc:
                    raise ExchangeError(f"HTTP request failed: {exc}")

            status_code, resp_headers, resp_text = await asyncio.to_thread(_send_urllib)
            try:
                data = json.loads(resp_text)
            except Exception:
                data = None

        if status_code == 429:
            retry_ms = int(resp_headers.get("retry-after", "1")) * 1000
            raise RateLimitExceededError(retry_after_ms=retry_ms)
        elif status_code == 401:
            raise InvalidKeyError("Unauthorized (401) on Delta Exchange REST")
        elif status_code == 403:
            raise IPNotWhitelistedError("Forbidden (403): Verify IP whitelist and User-Agent")

        if data is None:
            raise ExchangeError(f"HTTP {status_code}: Non-JSON response ({resp_text})")

        if status_code >= 400 or (isinstance(data, dict) and data.get("success") is False):
            err_msg = data.get("error", {}).get("message", resp_text) if isinstance(data, dict) else resp_text
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
        """Look up live product specification by symbol with in-memory caching."""
        if symbol in self._product_cache:
            return self._product_cache[symbol]
        res = await self._request("GET", f"/v2/products/{symbol}", weight=WEIGHT_PUBLIC_READ)
        prod = res.get("result", {})
        if prod:
            self._product_cache[symbol] = prod
        return prod

    async def get_balances(self) -> dict[str, Decimal]:
        """Fetch wallet balances."""
        res = await self._request("GET", "/v2/wallet/balances", auth_required=True, weight=WEIGHT_PUBLIC_READ)
        result = {}
        for item in res.get("result", []):
            asset = item.get("asset_symbol", "UNKNOWN")
            result[asset] = to_decimal(item.get("balance", "0"))
        return result

    async def get_positions(self, symbol: str | None = None) -> list[PositionView]:
        """Fetch open margined positions, cross-referencing active orders for bracket protection."""
        res = await self._request("GET", "/v2/positions/margined", auth_required=True, weight=WEIGHT_PUBLIC_READ)
        views = []
        raw_items = res.get("result", [])
        if isinstance(raw_items, dict):
            raw_items = [raw_items]

        # If any open positions exist, query active orders to verify bracket stop orders on exchange
        active_orders: list[dict[str, Any]] = []
        if any(to_int(p.get("size", 0)) != 0 for p in raw_items):
            try:
                active_orders = await self.get_active_orders(symbol)
            except Exception:
                active_orders = []

        for pos in raw_items:
            prod_symbol = pos.get("product_symbol") or pos.get("product", {}).get("symbol") or ""
            if symbol and prod_symbol and prod_symbol != symbol:
                continue
            size = to_int(pos.get("size", 0))
            if size == 0:
                continue

            p_id = pos.get("product_id") or pos.get("product", {}).get("id")
            has_bracket = bool(pos.get("bracket_orders") or pos.get("bracket_order"))
            if not has_bracket and active_orders:
                has_bracket = any(
                    (o.get("product_id") == p_id or o.get("product_symbol") == prod_symbol)
                    and (
                        o.get("bracket_order") is True
                        or o.get("stop_order_type") in ("stop_loss_order", "bracket_stop_loss")
                        or (o.get("reduce_only") is True and o.get("stop_price") is not None)
                    )
                    and o.get("state") in ("open", "pending")
                    for o in active_orders
                )

            views.append(
                PositionView(
                    symbol=prod_symbol or (symbol or ""),
                    side="long" if size > 0 else "short",
                    contracts=abs(size),
                    entry_price=to_decimal(pos.get("entry_price", "0")),
                    mark_price=to_decimal(pos.get("mark_price", "0")),
                    unrealized_pnl=to_decimal(pos.get("unrealized_pnl", "0")),
                    leverage=to_int(pos.get("leverage", pos.get("product", {}).get("default_leverage", 3))),
                    liquidation_price=to_decimal(pos.get("liquidation_price")),
                    has_active_bracket=has_bracket,
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
        prod = await self.get_product(symbol)
        product_id = prod.get("id")

        norm_type = "limit_order" if "limit" in order_type.lower() else "market_order"

        payload: dict[str, Any] = {
            "size": size_contracts,
            "side": side.lower(),
            "order_type": norm_type,
        }
        if product_id is not None:
            payload["product_id"] = product_id
        else:
            payload["product_symbol"] = symbol

        if price is not None:
            payload["limit_price"] = str(price)
        if client_order_id:
            payload["client_order_id"] = client_order_id

        # Bracket orders if provided
        if bracket_stop_loss_price is not None:
            payload["bracket_stop_loss_price"] = str(bracket_stop_loss_price)
        if bracket_take_profit_price is not None:
            payload["bracket_take_profit_price"] = str(bracket_take_profit_price)

        res = await self._request(
            "POST", "/v2/orders", payload=payload, auth_required=True, weight=WEIGHT_ORDER_ACTION
        )
        return res.get("result", {})

    async def cancel_order(
        self,
        order_id: str | int,
        symbol: str | None = None,
        product_id: int | None = None,
    ) -> bool:
        """Cancel an open order by ID."""
        p_id = product_id
        if p_id is None and symbol:
            prod = await self.get_product(symbol)
            p_id = prod.get("id")
        if p_id is None:
            prod = await self.get_product("BTCUSD")
            p_id = prod.get("id", 84)

        payload: dict[str, Any] = {
            "id": int(order_id) if str(order_id).isdigit() else order_id,
        }
        if p_id:
            payload["product_id"] = p_id

        res = await self._request(
            "DELETE", "/v2/orders", payload=payload, auth_required=True, weight=WEIGHT_ORDER_ACTION
        )
        return bool(res.get("success", False))

    async def cancel_all(self, symbol: str | None = None) -> int:
        """Cancel all open orders, optionally for a specific symbol."""
        payload: dict[str, Any] = {}
        if symbol:
            prod = await self.get_product(symbol)
            if prod.get("id"):
                payload["product_id"] = prod["id"]
        res = await self._request("DELETE", "/v2/orders/all", payload=payload, auth_required=True, weight=WEIGHT_ORDER_ACTION)
        return len(res.get("result", []))

    async def close_all(self, symbol: str | None = None) -> bool:
        """Close all positions via reduce-only, optionally for a specific symbol."""
        payload: dict[str, Any] = {}
        if symbol:
            prod = await self.get_product(symbol)
            if prod.get("id"):
                payload["product_id"] = prod["id"]
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
        resolution_map = {
            "1m": "1",
            "3m": "3",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "2h": "120",
            "4h": "240",
            "6h": "360",
            "1d": "D",
            "1w": "1W",
        }
        res_str = resolution_map.get(resolution.lower(), resolution)
        params = {
            "symbol": symbol,
            "resolution": res_str,
            "from": start_time_s,
            "to": end_time_s,
            "start": start_time_s,
            "end": end_time_s,
        }
        res = await self._request("GET", "/v2/chart/history", params=params, weight=WEIGHT_PUBLIC_READ)
        candles = []
        raw = res.get("result", {})
        if isinstance(raw, dict) and "t" in raw:
            times = raw.get("t", [])
            opens = raw.get("o", [])
            highs = raw.get("h", [])
            lows = raw.get("l", [])
            closes = raw.get("c", [])
            volumes = raw.get("v", [])
            for i in range(len(times)):
                t_val = times[i]
                open_dt = parse_exchange_timestamp(t_val)
                candles.append(
                    Candle(
                        symbol=symbol,
                        timeframe=resolution,
                        open_time=open_dt,
                        close_time=open_dt,
                        open=to_decimal(opens[i]),
                        high=to_decimal(highs[i]),
                        low=to_decimal(lows[i]),
                        close=to_decimal(closes[i]),
                        volume=to_decimal(volumes[i]) if i < len(volumes) else Decimal("0"),
                        is_closed=True,
                        source="delta_rest",
                    )
                )
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    t_val = item.get("time") or item.get("t")
                    open_dt = parse_exchange_timestamp(t_val)
                    candles.append(
                        Candle(
                            symbol=symbol,
                            timeframe=resolution,
                            open_time=open_dt,
                            close_time=open_dt,
                            open=to_decimal(item.get("open") or item.get("o")),
                            high=to_decimal(item.get("high") or item.get("h")),
                            low=to_decimal(item.get("low") or item.get("l")),
                            close=to_decimal(item.get("close") or item.get("c")),
                            volume=to_decimal(item.get("volume") or item.get("v", "0")),
                            is_closed=True,
                            source="delta_rest",
                        )
                    )
        return candles
