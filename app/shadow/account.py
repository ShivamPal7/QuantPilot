"""Virtual shadow account for zero-risk paper trade tracking.

Per Section 9.4 of agent.md:
One virtual account per strategy running continuously.
Trades evaluated against next candle's open price (never same candle close).
Models exchange fees, slippage, and tracks real-time hypothetical statistics.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.core.contracts import Candle, Direction, ShadowStats, ShadowTrade, Signal
from app.shadow.cost_model import ShadowCostModel


class ShadowAccount:
    """Simulates realistic execution and metrics for a specific strategy."""

    def __init__(
        self,
        strategy_name: str,
        initial_capital: Decimal = Decimal("10000.0"),
        cost_model: ShadowCostModel | None = None,
        contract_multiplier: Decimal = Decimal("0.001"),
        risk_fraction: float = 0.01,
    ) -> None:
        self.strategy_name = strategy_name
        self.initial_capital = initial_capital
        self.current_cash = initial_capital
        self.current_equity = initial_capital
        self.cost_model = cost_model or ShadowCostModel()
        self.contract_multiplier = contract_multiplier
        self.risk_fraction = risk_fraction

        self._trades: list[ShadowTrade] = []
        self._pending_intent: dict[str, Any] | None = None
        self._open_position: dict[str, Any] | None = None
        self._peak_equity = initial_capital

    @property
    def peak_equity(self) -> Decimal:
        return self._peak_equity

    @property
    def trades(self) -> list[ShadowTrade]:
        return list(self._trades)

    @property
    def has_open_position(self) -> bool:
        return self._open_position is not None

    @property
    def open_position(self) -> dict[str, Any] | None:
        return dict(self._open_position) if self._open_position is not None else None

    def on_signal(self, signal: Signal, candle: Candle) -> None:
        """Register strategy signal on closed candle; queues order for next candle execution."""
        if signal.direction == Direction.FLAT:
            if self._open_position is not None:
                # Signal says FLAT: close open position on next candle
                self._pending_intent = {
                    "action": "CLOSE",
                    "reason": "SIGNAL_FLAT",
                    "signal_time": candle.close_time,
                }
            else:
                self._pending_intent = None
            return

        # Directional signal: LONG or SHORT
        if self._open_position is not None:
            if self._open_position["direction"] == signal.direction:
                # Same direction: hold existing position
                self._pending_intent = None
                return
            else:
                # Opposite direction: close current position and open opposite
                self._pending_intent = {
                    "action": "FLIP",
                    "direction": signal.direction,
                    "stop_dist": signal.proposed_stop_distance,
                    "tp_dist": signal.proposed_tp_distance,
                    "signal_time": candle.close_time,
                }
                return

        # Currently flat: queue new entry
        self._pending_intent = {
            "action": "OPEN",
            "direction": signal.direction,
            "stop_dist": signal.proposed_stop_distance,
            "tp_dist": signal.proposed_tp_distance,
            "signal_time": candle.close_time,
        }

    def process_closed_candle(self, candle: Candle) -> None:
        """Process price action on incoming candle: fills pending orders and checks bracket triggers."""
        # Step 1: Execute any pending orders on candle open
        if self._pending_intent is not None:
            intent = self._pending_intent
            self._pending_intent = None
            action = intent["action"]

            if action in ("CLOSE", "FLIP") and self._open_position is not None:
                self._close_position(
                    exit_price=candle.open,
                    exit_time=candle.open_time,
                    exit_reason=intent.get("reason", "SIGNAL_REVERSAL"),
                )

            if action in ("OPEN", "FLIP"):
                self._open_new_position(
                    direction=intent["direction"],
                    raw_price=candle.open,
                    entry_time=candle.open_time,
                    stop_dist=intent["stop_dist"],
                    tp_dist=intent["tp_dist"],
                )

        # Step 2: Check stop-loss and take-profit triggers on open position
        if self._open_position is not None:
            pos = self._open_position
            direction = pos["direction"]
            sl = pos["stop_loss"]
            tp = pos["take_profit"]

            if direction == Direction.LONG:
                if sl is not None and candle.low <= sl:
                    # Stop loss triggered
                    fill_p = min(candle.open, sl)
                    self._close_position(exit_price=fill_p, exit_time=candle.close_time, exit_reason="STOP_LOSS")
                elif tp is not None and candle.high >= tp:
                    # Take profit triggered
                    fill_p = max(candle.open, tp)
                    self._close_position(exit_price=fill_p, exit_time=candle.close_time, exit_reason="TAKE_PROFIT")
                else:
                    # Position remains open; mark to market
                    pos["holding_candles"] += 1
                    unrealized_pnl = (candle.close - pos["entry_price"]) * pos["contracts"] * self.contract_multiplier
                    self.current_equity = self.current_cash + unrealized_pnl
            else:  # SHORT
                if sl is not None and candle.high >= sl:
                    # Stop loss triggered
                    fill_p = max(candle.open, sl)
                    self._close_position(exit_price=fill_p, exit_time=candle.close_time, exit_reason="STOP_LOSS")
                elif tp is not None and candle.low <= tp:
                    # Take profit triggered
                    fill_p = min(candle.open, tp)
                    self._close_position(exit_price=fill_p, exit_time=candle.close_time, exit_reason="TAKE_PROFIT")
                else:
                    # Position remains open; mark to market
                    pos["holding_candles"] += 1
                    unrealized_pnl = (pos["entry_price"] - candle.close) * pos["contracts"] * self.contract_multiplier
                    self.current_equity = self.current_cash + unrealized_pnl

        # Step 3: Update peak equity
        if self.current_equity > self._peak_equity:
            self._peak_equity = self.current_equity

    def _open_new_position(
        self,
        direction: Direction,
        raw_price: Decimal,
        entry_time: datetime,
        stop_dist: Decimal,
        tp_dist: Decimal | None,
    ) -> None:
        is_long = direction == Direction.LONG
        fill_price = self.cost_model.apply_entry_slippage(raw_price, is_long=is_long)

        # Sizing: risk budget = risk_fraction * current_equity
        risk_dollars = self.current_equity * Decimal(str(self.risk_fraction))
        denom = (stop_dist * self.contract_multiplier) if stop_dist > 0 else Decimal("100.0")
        calc_contracts = int(risk_dollars / denom) if denom > 0 else 1
        contracts = max(1, calc_contracts)

        notional = Decimal(str(contracts)) * self.contract_multiplier * fill_price
        entry_fee, entry_slippage = self.cost_model.calculate_entry_cost(notional, is_taker=True)

        if is_long:
            stop_loss = fill_price - stop_dist if stop_dist > 0 else None
            take_profit = fill_price + tp_dist if (tp_dist and tp_dist > 0) else None
        else:
            stop_loss = fill_price + stop_dist if stop_dist > 0 else None
            take_profit = fill_price - tp_dist if (tp_dist and tp_dist > 0) else None

        self._open_position = {
            "trade_id": str(uuid.uuid4()),
            "direction": direction,
            "entry_time": entry_time,
            "entry_price": fill_price,
            "contracts": contracts,
            "notional": notional,
            "entry_fee": entry_fee,
            "entry_slippage": entry_slippage,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "holding_candles": 0,
        }

    def _close_position(self, exit_price: Decimal, exit_time: datetime, exit_reason: str) -> None:
        if self._open_position is None:
            return

        pos = self._open_position
        direction = pos["direction"]
        contracts = pos["contracts"]
        is_long = direction == Direction.LONG

        fill_exit_price = self.cost_model.apply_exit_slippage(exit_price, is_long=is_long)
        exit_notional = Decimal(str(contracts)) * self.contract_multiplier * fill_exit_price
        exit_fee, exit_slippage = self.cost_model.calculate_exit_cost(exit_notional, is_taker=True)

        if is_long:
            gross_pnl = (fill_exit_price - pos["entry_price"]) * contracts * self.contract_multiplier
        else:
            gross_pnl = (pos["entry_price"] - fill_exit_price) * contracts * self.contract_multiplier

        total_fees = pos["entry_fee"] + exit_fee
        total_slippage = pos["entry_slippage"] + exit_slippage
        # gross_pnl is already computed using slipped entry/exit prices.
        # Do not double-subtract total_slippage; keep it for tracking in ShadowTrade.
        net_pnl = gross_pnl - total_fees

        self.current_cash += net_pnl
        self.current_equity = self.current_cash

        trade = ShadowTrade(
            trade_id=pos["trade_id"],
            strategy_name=self.strategy_name,
            direction=direction,
            entry_time=pos["entry_time"],
            entry_price=pos["entry_price"],
            exit_time=exit_time,
            exit_price=fill_exit_price,
            exit_reason=exit_reason,
            gross_pnl=gross_pnl,
            fees=total_fees,
            slippage=total_slippage,
            net_pnl=net_pnl,
            holding_candles=pos["holding_candles"],
            is_win=net_pnl > Decimal("0"),
        )
        self._trades.append(trade)
        self._open_position = None

    def get_stats(self) -> ShadowStats:
        """Compute summary statistics."""
        wins = sum(1 for t in self._trades if t.is_win)
        losses = sum(1 for t in self._trades if not t.is_win)
        total = len(self._trades)
        win_rate = (wins / total) if total > 0 else 0.0
        drawdown_pct = float((self._peak_equity - self.current_equity) / self._peak_equity) if self._peak_equity > 0 else 0.0

        return ShadowStats(
            strategy_name=self.strategy_name,
            trade_count=total,
            win_count=wins,
            loss_count=losses,
            win_rate=win_rate,
            net_profit=self.current_equity - self.initial_capital,
            max_drawdown_pct=max(0.0, drawdown_pct),
            updated_at=datetime.now(timezone.utc),
        )
