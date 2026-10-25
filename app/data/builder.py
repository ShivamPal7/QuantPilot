"""Live candle aggregator.

Per Section 7.4 and 9.2 of agent.md:
Constructs timeframe candles from tick/trade streams and emits CandleClosedEvent.
Provides tick-level freshness tracking.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.contracts import Candle
from app.core.events import CandleClosedEvent
from app.core.logging import get_logger
from app.data.store import parse_timeframe_seconds

logger = get_logger("candle_builder")


class CandleBuilder:
    """Builds candles from incoming prices and ticks."""

    def __init__(
        self,
        symbol: str,
        timeframe: str = "1m",
        on_candle_closed: Callable[[CandleClosedEvent], None] | None = None,
        max_age_s: float = 5.0,
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.on_candle_closed = on_candle_closed
        self.max_age_s = max_age_s
        self._current_candle: Candle | None = None
        self._last_tick_time: datetime | None = None

    @property
    def current_candle(self) -> Candle | None:
        return self._current_candle

    @property
    def last_tick_time(self) -> datetime | None:
        return self._last_tick_time

    def _get_bucket_times(self, timestamp: datetime) -> tuple[datetime, datetime]:
        """Compute aligned open and close times for the tick timestamp."""
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        step_sec = parse_timeframe_seconds(self.timeframe)
        ts = int(timestamp.timestamp())
        bucket_ts = (ts // step_sec) * step_sec
        bucket_open = datetime.fromtimestamp(bucket_ts, tz=timezone.utc)
        bucket_close = bucket_open + timedelta(seconds=step_sec)
        return bucket_open, bucket_close

    def push_tick(self, price: Decimal, volume: Decimal, timestamp: datetime) -> Candle | None:
        """Process an incoming tick (price, volume, timestamp).

        If the tick falls in a new timeframe bucket, the previous candle is closed,
        emitted via on_candle_closed (if registered), and returned.
        Otherwise, updates the current forming candle and returns None.
        """
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        self._last_tick_time = timestamp

        bucket_open, bucket_close = self._get_bucket_times(timestamp)

        if self._current_candle is None:
            self._current_candle = Candle(
                symbol=self.symbol,
                timeframe=self.timeframe,
                open_time=bucket_open,
                close_time=bucket_close,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
                is_closed=False,
                source="live_ticks",
            )
            return None

        # Same bucket: update OHLCV
        if bucket_open == self._current_candle.open_time:
            self._current_candle = Candle(
                symbol=self.symbol,
                timeframe=self.timeframe,
                open_time=bucket_open,
                close_time=bucket_close,
                open=self._current_candle.open,
                high=max(self._current_candle.high, price),
                low=min(self._current_candle.low, price),
                close=price,
                volume=self._current_candle.volume + volume,
                is_closed=False,
                source="live_ticks",
            )
            return None

        # New bucket: close previous candle
        closed_candle = Candle(
            symbol=self.symbol,
            timeframe=self.timeframe,
            open_time=self._current_candle.open_time,
            close_time=self._current_candle.close_time,
            open=self._current_candle.open,
            high=self._current_candle.high,
            low=self._current_candle.low,
            close=self._current_candle.close,
            volume=self._current_candle.volume,
            is_closed=True,
            source="live_ticks",
        )

        # Notify listener
        if self.on_candle_closed:
            try:
                self.on_candle_closed(
                    CandleClosedEvent(
                        symbol=closed_candle.symbol,
                        timeframe=closed_candle.timeframe,
                        close_time=closed_candle.close_time,
                        close_price=float(closed_candle.close),
                        candle=closed_candle,
                    )
                )
            except Exception as e:
                logger.error("Error in on_candle_closed callback: %s", e)

        # Initialize new forming candle for this tick
        self._current_candle = Candle(
            symbol=self.symbol,
            timeframe=self.timeframe,
            open_time=bucket_open,
            close_time=bucket_close,
            open=price,
            high=price,
            low=price,
            close=price,
            volume=volume,
            is_closed=False,
            source="live_ticks",
        )

        return closed_candle

    def is_stale(self, max_age_s: float | None = None, now: datetime | None = None) -> bool:
        """Return True if no ticks received or elapsed time exceeds threshold."""
        if self._last_tick_time is None:
            return True
        threshold = max_age_s if max_age_s is not None else self.max_age_s
        current_time = now if now is not None else datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        elapsed = (current_time - self._last_tick_time).total_seconds()
        return elapsed > threshold
