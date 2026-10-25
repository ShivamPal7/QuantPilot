"""Live candle aggregator.

Constructs timeframe candles from tick/trade streams and emits CandleClosedEvent.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal

from app.core.contracts import Candle
from app.core.events import CandleClosedEvent
from app.core.logging import get_logger

logger = get_logger("candle_builder")


class CandleBuilder:
    """Builds candles from incoming prices."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        on_candle_closed: Callable[[CandleClosedEvent], None] | None = None,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.on_candle_closed = on_candle_closed
        self._current_candle: Candle | None = None

    def push_tick(self, price: Decimal, volume: Decimal, timestamp: datetime) -> None:
        """Process an incoming tick (price and volume)."""
        # Scaffolding stub for candle aggregation
        pass
