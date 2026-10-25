"""Delta Exchange WebSocket streamer.

Per Section 6.8 of agent.md:
Handles public channels (candlestick, order book, mark price) and private channels.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from typing import Any

from app.core.logging import get_logger
from app.exchange.guard import assert_testnet_environment

logger = get_logger("websocket")


class DeltaWebSocketClient:
    """Manages WebSocket connections to Delta Exchange testnet."""

    def __init__(
        self,
        public_url: str,
        private_url: str = "",
        api_key: str = "",
        api_secret: str = "",
        target_env: str = "testnet",
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
        self._running = False
        self._handlers: list[Callable[[dict[str, Any]], Coroutine[Any, Any, None]]] = []

    def add_handler(self, handler: Callable[[dict[str, Any]], Coroutine[Any, Any, None]]) -> None:
        """Register an async callback for incoming messages."""
        self._handlers.append(handler)

    async def connect_and_listen(self) -> None:
        """Connect to WebSocket stream and dispatch messages."""
        self._running = True
        logger.info("Connecting to Delta WebSocket: %s", self.public_url)
        # Note: in Phase 0 / early scaffolding, websockets connection shell
        while self._running:
            try:
                # Simulated stream loop or placeholder connection
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("WebSocket error: %s. Reconnecting in 2s...", e)
                await asyncio.sleep(2.0)

    async def stop(self) -> None:
        """Stop listening and cleanly disconnect."""
        self._running = False
