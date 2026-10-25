"""Data normalizers for the Delta Exchange boundary.

Per Section 6.4 of agent.md:
- Prices and monetary amounts become Decimal (never floats).
- Contract sizes and product IDs become integers.
- Timestamps (microseconds or ISO 8601) become timezone-aware UTC datetime.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any


def to_decimal(value: Any, default: str = "0.0") -> Decimal:
    """Safely convert a string, int, or numeric representation to Decimal."""
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return Decimal(default)


def to_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to integer."""
    if value is None:
        return default
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return default


def parse_exchange_timestamp(ts: Any) -> datetime:
    """Convert microsecond timestamps, second timestamps, or ISO strings to timezone-aware UTC datetime."""
    if ts is None:
        return datetime.now(timezone.utc)

    if isinstance(ts, (int, float)):
        # If timestamp is in microseconds (16 digits)
        if ts > 1e14:
            return datetime.fromtimestamp(ts / 1_000_000.0, tz=timezone.utc)
        # If timestamp is in milliseconds (13 digits)
        elif ts > 1e11:
            return datetime.fromtimestamp(ts / 1_000.0, tz=timezone.utc)
        # If timestamp is in seconds (10 digits)
        else:
            return datetime.fromtimestamp(ts, tz=timezone.utc)

    if isinstance(ts, str):
        ts_str = ts.strip()
        # Try numeric string
        try:
            val = float(ts_str)
            return parse_exchange_timestamp(val)
        except ValueError:
            pass
        # Try ISO 8601
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass

    return datetime.now(timezone.utc)
