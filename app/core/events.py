"""Internal engine event definitions.

Per Section 8 of agent.md, engine events capture state transitions,
guard triggers, kill-switch events, and reconciliation discrepancies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.state import EngineState


@dataclass(frozen=True)
class BaseEngineEvent:
    """Base class for all internal events."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = "base"


@dataclass(frozen=True)
class EngineStateChangedEvent(BaseEngineEvent):
    """Fired when engine state transitions."""

    event_type: str = "engine_state_changed"
    old_state: EngineState = EngineState.INITIALISING
    new_state: EngineState = EngineState.INITIALISING
    reason: str = ""


@dataclass(frozen=True)
class CandleClosedEvent(BaseEngineEvent):
    """Fired when a candle is finalized and closed."""

    event_type: str = "candle_closed"
    symbol: str = "BTCUSD"
    timeframe: str = "1h"
    close_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    close_price: float = 0.0
    candle: Any = None


@dataclass(frozen=True)
class GuardTriggeredEvent(BaseEngineEvent):
    """Fired when a safety guard rejects an intent or pauses operation."""

    event_type: str = "guard_triggered"
    guard_name: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KillSwitchActivatedEvent(BaseEngineEvent):
    """Fired when the kill switch triggers."""

    event_type: str = "kill_switch_activated"
    trigger_source: str = ""  # 'api', 'daily_loss', 'drawdown', 'watchdog'
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReconciliationMismatchEvent(BaseEngineEvent):
    """Fired when internal cache differs from exchange REST source of truth."""

    event_type: str = "reconciliation_mismatch"
    mismatch_type: str = ""  # 'position', 'order_status', 'balance'
    internal_val: Any = None
    exchange_val: Any = None
