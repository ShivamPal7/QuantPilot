"""Domain contracts and typed data structures.

Defined in Section 8 of agent.md.
All modules share these immutable contracts to ensure separation of concerns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any


class Direction(str, Enum):
    """Trading direction."""
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class RegimeLabel(str, Enum):
    """Market regime classification."""
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    CHAOTIC = "CHAOTIC"  # Stand-aside


class RiskAction(str, Enum):
    """Verdict returned by the Risk Gate."""
    APPROVE = "APPROVE"
    RESIZE = "RESIZE"
    REJECT = "REJECT"


class OrderRole(str, Enum):
    """Role played by an order in the execution lifecycle."""
    ENTRY = "ENTRY"
    BRACKET_STOP = "BRACKET_STOP"
    BRACKET_TAKE_PROFIT = "BRACKET_TAKE_PROFIT"
    FORCED_EXIT = "FORCED_EXIT"
    MANUAL_EXIT = "MANUAL_EXIT"


class OrderState(str, Enum):
    """Lifecycle states of an order."""
    INTENT_CREATED = "INTENT_CREATED"
    RISK_APPROVED = "RISK_APPROVED"
    SUBMITTED = "SUBMITTED"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"  # Triggers immediate reconciliation


@dataclass(frozen=True)
class Candle:
    """Represents a single OHLCV candlestick."""
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    is_closed: bool = True
    source: str = "delta_rest"


@dataclass(frozen=True)
class MarketSnapshot:
    """Point-in-time order book touch and price snapshot."""
    symbol: str
    timestamp: datetime
    best_bid: Decimal
    best_ask: Decimal
    bid_size: Decimal
    ask_size: Decimal
    mark_price: Decimal
    spot_price: Decimal

    @property
    def spread(self) -> Decimal:
        return self.best_ask - self.best_bid

    @property
    def spread_bps(self) -> Decimal:
        if self.best_bid <= Decimal("0"):
            return Decimal("0")
        return (self.spread / self.best_bid) * Decimal("10000")

    def freshness_age_seconds(self, now: datetime) -> float:
        return max(0.0, (now - self.timestamp).total_seconds())


@dataclass(frozen=True)
class Signal:
    """Strategy proposed trade signal."""
    strategy_name: str
    symbol: str
    direction: Direction
    strength: float  # In range [0.0, 1.0]
    proposed_stop_distance: Decimal  # In price units
    proposed_tp_distance: Decimal | None = None
    time_stop_candles: int = 0
    reason_codes: list[str] = field(default_factory=list)
    numeric_values: dict[str, float] = field(default_factory=dict)
    indicators_snapshot: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RegimeReading:
    """Regime filter evaluation."""
    label: RegimeLabel
    metrics: dict[str, float]
    previous_label: RegimeLabel
    confidence: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ShadowTrade:
    """Completed virtual trade in a shadow account."""
    trade_id: str
    strategy_name: str
    direction: Direction
    entry_time: datetime
    entry_price: Decimal
    exit_time: datetime
    exit_price: Decimal
    exit_reason: str
    gross_pnl: Decimal
    fees: Decimal
    slippage: Decimal
    net_pnl: Decimal
    holding_candles: int
    is_win: bool


@dataclass(frozen=True)
class ShadowStats:
    """Performance statistics for a shadow account."""
    strategy_name: str
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    net_profit: Decimal
    max_drawdown_pct: float
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class AllocationDecision:
    """Verdict on which strategy takes real risk."""
    selected_strategy: str | None  # Strategy name or None for stand-aside
    weight: float  # Weight in [0.0, 1.0]
    reason: str
    sampled_values: dict[str, float] = field(default_factory=dict)
    is_exploration: bool = False
    is_regime_override: bool = False


@dataclass(frozen=True)
class OrderIntent:
    """Intent ready for risk assessment."""
    decision_id: str
    strategy_name: str
    symbol: str
    direction: Direction
    desired_risk_fraction: float
    proposed_stop_distance: Decimal
    proposed_tp_distance: Decimal | None = None
    entry_style: str = "marketable_limit"
    urgency: str = "normal"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class RuleEvaluationResult:
    """Outcome of a single risk gate rule check."""
    rule_name: str
    passed: bool
    observed_value: Any
    threshold_value: Any
    message: str = ""


@dataclass(frozen=True)
class RiskVerdict:
    """Final decision of the Risk Gate."""
    action: RiskAction
    approved_risk_fraction: float
    approved_contracts: int  # Must be integer contracts
    evaluated_rules: list[RuleEvaluationResult] = field(default_factory=list)
    binding_rule: str | None = None
    rejection_reason: str | None = None


@dataclass(frozen=True)
class OrderRecord:
    """State record of an exchange order."""
    internal_id: str
    client_order_id: str
    parent_decision_id: str
    symbol: str
    role: OrderRole
    state: OrderState
    side: str  # 'buy' or 'sell'
    size_contracts: int
    price: Decimal | None
    exchange_order_id: str | None = None
    average_fill_price: Decimal | None = None
    filled_contracts: int = 0
    fees_paid: Decimal = Decimal("0")
    realized_slippage_bps: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class PositionView:
    """Reconciled position snapshot from exchange truth."""
    symbol: str
    side: str  # 'long', 'short', 'flat'
    contracts: int
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    leverage: int
    liquidation_price: Decimal | None
    has_active_bracket: bool
    reconciled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class DecisionRecord:
    """Comprehensive decision journal row for auditability."""
    decision_id: str
    timestamp: datetime
    symbol: str
    timeframe: str
    candle_close_price: Decimal
    regime: RegimeReading
    signals: list[Signal]
    shadow_stats: list[ShadowStats]
    allocation: AllocationDecision
    intent: OrderIntent | None
    risk_verdict: RiskVerdict
    orders: list[OrderRecord]
    narrative: str
