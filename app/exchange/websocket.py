"""Delta Exchange WebSocket streamer.

Per Section 6.8 of agent.md:
Handles public channels (v2/ticker, candlestick_1m, l2_orderbook, mark_price)
and authenticated private channels (orders, positions, user_trades).
Includes automatic reconnect with exponential backoff and heartbeat watchdog.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable, Coroutine
from typing import Any

from app.core.logging import get_logger
from app.exchange.guard import assert_testnet_environment
from app.exchange.signing import generate_delta_signature

logger = get_logger("websocket")

DEFAULT_PUBLIC_WS = "wss://socket-ind-pub.testnet.deltaex.org"
DEFAULT_PRIVATE_WS = "wss://socket-ind.testnet.deltaex.org"

PUBLIC_CHANNELS: set[str] = {
    "v2/ticker",
    "candlestick_1m",
    "l2_orderbook",
    "mark_price",
    "spot_price",
    "all_ticker",
}

PRIVATE_CHANNELS: set[str] = {
    "orders",
    "positions",
    "user_trades",
    "margins",
    "portfolio_margins",
    "mmp_trigger",
}


class DeltaWebSocketClient:
    """Manages WebSocket connections to Delta Exchange testnet with automatic reconnection and heartbeat watchdog."""

    def __init__(
        self,
        public_url: str = DEFAULT_PUBLIC_WS,
        private_url: str = DEFAULT_PRIVATE_WS,
        api_key: str = "",
        api_secret: str = "",
        target_env: str = "testnet",
        ping_interval_s: float = 15.0,
        pong_timeout_s: float = 30.0,
        initial_retry_delay_s: float = 1.0,
        max_retry_delay_s: float = 30.0,
        backoff_factor: float = 2.0,
    ) -> None:
        assert_testnet_environment(
            target_env=target_env,
            rest_url=public_url,
            ws_public_url=public_url,
            ws_private_url=private_url,
        )
        self.public_url = public_url
        self.private_url = private_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.target_env = target_env

        self.ping_interval_s = ping_interval_s
        self.pong_timeout_s = pong_timeout_s
        self.initial_retry_delay_s = initial_retry_delay_s
        self.max_retry_delay_s = max_retry_delay_s
        self.backoff_factor = backoff_factor

        self._running = False
        self._connected = False
        self._handlers: list[Callable[[dict[str, Any]], Coroutine[Any, Any, None] | None]] = []
        self._subscriptions: list[dict[str, Any]] = []
        self._last_ping_time: float = 0.0
        self._last_pong_time: float = 0.0
        self._current_retry_delay = initial_retry_delay_s
        self._active_socket: Any = None
        self._active_sockets: set[Any] = set()
        self._send_queue: asyncio.Queue[str] = asyncio.Queue()
        self._pub_send_queue: asyncio.Queue[str] = asyncio.Queue()
        self._priv_send_queue: asyncio.Queue[str] = asyncio.Queue()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_running(self) -> bool:
        return self._running

    def add_handler(self, handler: Callable[[dict[str, Any]], Coroutine[Any, Any, None] | None]) -> None:
        """Register an async or sync callback for incoming messages."""
        self._handlers.append(handler)

    def subscribe(self, channel: str, symbols: list[str]) -> dict[str, Any]:
        """Register channel subscription and queue subscription payload."""
        sub = {"name": channel, "symbols": symbols}
        if sub not in self._subscriptions:
            self._subscriptions.append(sub)
        msg = self.build_subscribe_message([sub])
        if self._connected:
            self.send(msg)
        return msg

    def subscribe_public_default(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Subscribe to required public channels: v2/ticker, candlestick_1m, l2_orderbook, mark_price."""
        public_channels = ["v2/ticker", "candlestick_1m", "l2_orderbook", "mark_price"]
        messages = []
        for ch in public_channels:
            messages.append(self.subscribe(ch, symbols))
        return messages

    def subscribe_private_default(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Subscribe to required private channels: orders, positions, user_trades."""
        private_channels = ["orders", "positions", "user_trades"]
        messages = []
        for ch in private_channels:
            messages.append(self.subscribe(ch, symbols))
        return messages

    def build_auth_message(self, timestamp_s: int | None = None) -> dict[str, Any]:
        """Construct HMAC-SHA256 authenticated payload for private WebSocket stream."""
        ts = str(timestamp_s if timestamp_s is not None else int(time.time()))
        signature = generate_delta_signature(
            secret=self.api_secret,
            method="GET",
            timestamp=ts,
            path="/live",
        )
        return {
            "type": "auth",
            "payload": {
                "api-key": self.api_key,
                "signature": signature,
                "timestamp": ts,
            },
        }

    def build_subscribe_message(self, channels: list[dict[str, Any]]) -> dict[str, Any]:
        """Construct channel subscription message for Delta WebSocket."""
        return {
            "type": "subscribe",
            "payload": {
                "channels": channels,
            },
        }

    def build_ping_message(self) -> dict[str, Any]:
        """Construct standard heartbeat ping message."""
        return {"type": "ping"}

    def get_endpoint_for_channel(self, channel: str) -> str:
        """Route private channels to private_url and public channels to public_url."""
        if channel in PRIVATE_CHANNELS:
            return self.private_url
        return self.public_url

    def partition_subscriptions(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Partition registered subscriptions into (public_subscriptions, private_subscriptions)."""
        pub_subs = [s for s in self._subscriptions if s.get("name") not in PRIVATE_CHANNELS]
        priv_subs = [s for s in self._subscriptions if s.get("name") in PRIVATE_CHANNELS]
        return pub_subs, priv_subs

    def send(self, message: dict[str, Any] | str) -> None:
        """Queue message for sending over active WebSocket with channel-aware routing."""
        payload_str = message if isinstance(message, str) else json.dumps(message)
        self._send_queue.put_nowait(payload_str)

        parsed = message if isinstance(message, dict) else None
        if parsed is None:
            try:
                parsed = json.loads(payload_str)
            except Exception:
                pass

        is_private = False
        is_ping = False
        if isinstance(parsed, dict):
            mtype = parsed.get("type")
            if mtype == "auth":
                is_private = True
            elif mtype == "ping":
                is_ping = True
            elif mtype == "subscribe":
                channels = parsed.get("payload", {}).get("channels", [])
                if any(c.get("name") in PRIVATE_CHANNELS for c in channels):
                    is_private = True

        if is_ping:
            self._pub_send_queue.put_nowait(payload_str)
            self._priv_send_queue.put_nowait(payload_str)
        elif is_private:
            self._priv_send_queue.put_nowait(payload_str)
        else:
            self._pub_send_queue.put_nowait(payload_str)

    async def handle_message(self, raw_msg: str | dict[str, Any]) -> None:
        """Process incoming message, manage heartbeat pong, and notify handlers."""
        try:
            msg = json.loads(raw_msg) if isinstance(raw_msg, str) else raw_msg
        except Exception as e:
            logger.warning("Failed to decode WebSocket message: %s (raw: %s)", e, raw_msg)
            return

        msg_type = msg.get("type")
        if msg_type == "pong":
            self._last_pong_time = time.monotonic()
            logger.debug("Received WebSocket pong")
            return

        for handler in self._handlers:
            try:
                res = handler(msg)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error("Error in WebSocket handler callback: %s", e)

    async def _heartbeat_watchdog(self) -> None:
        """Periodically emit ping frames and monitor pong responses."""
        while self._running and self._connected:
            try:
                await asyncio.sleep(self.ping_interval_s)
                if not self._connected:
                    break

                self.send(self.build_ping_message())
                self._last_ping_time = time.monotonic()

                # Check if pong is stale
                if self._last_pong_time > 0:
                    time_since_pong = time.monotonic() - self._last_pong_time
                    if time_since_pong > self.pong_timeout_s:
                        logger.warning(
                            "WebSocket pong timeout (%.1fs > %.1fs). Forcing reconnect...",
                            time_since_pong,
                            self.pong_timeout_s,
                        )
                        self._connected = False
                        # Explicitly close active socket so the listening loop breaks and triggers reconnect
                        if self._active_socket is not None:
                            try:
                                res = self._active_socket.close()
                                if asyncio.iscoroutine(res):
                                    await res
                            except Exception as ex:
                                logger.warning("Error closing active socket on watchdog timeout: %s", ex)
                        for s in list(self._active_sockets):
                            try:
                                res = s.close()
                                if asyncio.iscoroutine(res):
                                    await res
                            except Exception:
                                pass
                        break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat error: %s", e)
                break

    async def _listen_single_endpoint(
        self,
        url: str,
        subscriptions: list[dict[str, Any]],
        is_private: bool,
    ) -> None:
        """Manage a single WebSocket connection loop (public or private) with retries."""
        try:
            import websockets  # type: ignore
        except ImportError:
            logger.warning("websockets package not installed. Running simulated loop.")
            self._connected = True
            self._last_pong_time = time.monotonic()
            while self._running:
                await asyncio.sleep(1.0)
            return

        send_queue = self._priv_send_queue if is_private else self._pub_send_queue
        retry_delay = self.initial_retry_delay_s

        while self._running:
            try:
                logger.info("Connecting to WebSocket [%s]: %s", "private" if is_private else "public", url)
                async with websockets.connect(url, ping_interval=None) as ws:
                    self._active_socket = ws
                    self._active_sockets.add(ws)
                    self._connected = True
                    self._last_pong_time = time.monotonic()
                    retry_delay = self.initial_retry_delay_s

                    # Authenticate if private connection and credentials available
                    if is_private and self.api_key and self.api_secret:
                        await ws.send(json.dumps(self.build_auth_message()))

                    # Subscribe to assigned channels
                    if subscriptions:
                        await ws.send(json.dumps(self.build_subscribe_message(subscriptions)))

                    watchdog_task = asyncio.create_task(self._heartbeat_watchdog())

                    async def _sender():
                        while self._running and self._connected:
                            msg = await send_queue.get()
                            await ws.send(msg)
                            send_queue.task_done()

                    sender_task = asyncio.create_task(_sender())

                    try:
                        async for raw in ws:
                            if not self._running:
                                break
                            await self.handle_message(raw)
                    finally:
                        watchdog_task.cancel()
                        sender_task.cancel()
                        self._active_sockets.discard(ws)
                        if not self._active_sockets:
                            self._connected = False
                            self._active_socket = None

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                logger.warning(
                    "WebSocket [%s] dropped (%s). Reconnecting in %.1fs...",
                    "private" if is_private else "public",
                    e,
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(
                    self.max_retry_delay_s,
                    retry_delay * self.backoff_factor,
                )

    async def connect_and_listen(self, custom_stream: Any = None) -> None:
        """Main listening loop with exponential backoff on disconnect.

        Args:
            custom_stream: Optional mock/pre-connected async stream for testing.
        """
        self._running = True
        logger.info("Starting Delta WebSocket client: public=%s, private=%s", self.public_url, self.private_url)

        if custom_stream is not None:
            # Injected stream for testing
            self._connected = True
            self._last_pong_time = time.monotonic()
            self._current_retry_delay = self.initial_retry_delay_s

            # Send auth if credentials configured
            if self.api_key and self.api_secret:
                self.send(self.build_auth_message())

            # Send all pending subscriptions
            if self._subscriptions:
                self.send(self.build_subscribe_message(self._subscriptions))

            watchdog_task = asyncio.create_task(self._heartbeat_watchdog())
            try:
                async for raw in custom_stream:
                    if not self._running:
                        break
                    await self.handle_message(raw)
            finally:
                watchdog_task.cancel()
                self._connected = False
            return

        pub_subs, priv_subs = self.partition_subscriptions()
        tasks = []

        # Connect to public WebSocket if there are public subs or if no specific private subs
        if pub_subs or not priv_subs:
            tasks.append(self._listen_single_endpoint(self.public_url, pub_subs, is_private=False))

        # Connect to private WebSocket if there are private subs or authenticated credentials
        if priv_subs or (self.api_key and self.api_secret and priv_subs):
            tasks.append(self._listen_single_endpoint(self.private_url, priv_subs, is_private=True))

        if tasks:
            await asyncio.gather(*tasks)

    async def stop(self) -> None:
        """Stop listening and cleanly disconnect all active sockets."""
        self._running = False
        self._connected = False
        if self._active_socket is not None:
            try:
                res = self._active_socket.close()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
            self._active_socket = None
        for s in list(self._active_sockets):
            try:
                res = s.close()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
        self._active_sockets.clear()
