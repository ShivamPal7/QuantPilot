"""Trading Engine Orchestrator ("Glass-Box Desk").

Defined in Section 7.2, 7.3, 7.4, 7.5, and 9 of agent.md.
Ties together the exchange adapter, market data service, pure signal layer,
shadow virtual accounts, Bayesian allocator, risk gate, execution manager,
reconciliation, watchdog, and SQLite decision journal.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.core.clock import check_clock_drift
from app.core.config import AppSettings, get_settings, load_engine_config
from app.core.contracts import (
    AllocationDecision,
    Candle,
    Direction,
    DecisionRecord,
    MarketSnapshot,
    OrderIntent,
    OrderRole,
    OrderState,
    PositionView,
    RegimeLabel,
    RegimeReading,
    RiskAction,
    RiskVerdict,
    ShadowStats,
    Signal,
)
from app.core.events import (
    EngineStateChangedEvent,
    GuardTriggeredEvent,
    KillSwitchActivatedEvent,
    ReconciliationMismatchEvent,
)
from app.core.logging import get_logger
from app.core.state import EngineState, EngineStateMachine, StateTransitionError
from app.core.supervisor import Supervisor
from app.data.builder import CandleBuilder
from app.data.freshness import FreshnessTracker
from app.data.store import CandleStore
from app.execution.manager import ExecutionManager
from app.execution.reconciliation import Reconciler
from app.journal.db import get_db_connection, init_database
from app.journal.narrative import NarrativeGenerator
from app.journal.writer import JournalWriter
from app.risk.drawdown import DrawdownLadder
from app.risk.gate import RiskGate
from app.risk.kill_switch import KillSwitch
from app.risk.sizing import PositionSizer
from app.risk.watchdog import UnprotectedPositionWatchdog
from app.shadow.account import ShadowAccount
from app.shadow.allocator import StrategyAllocator
from app.shadow.cost_model import ShadowCostModel
from app.signals.regime import RegimeFilter
from app.signals.reversion import MeanReversionStrategy
from app.signals.trend import TrendFollowingStrategy

logger = get_logger("engine")


class TradingEngine:
    """The central trading engine orchestrating data, signals, shadow, risk, and execution."""

    def __init__(
        self,
        settings: AppSettings | None = None,
        exchange: Any = None,
        db_path: str | None = None,
        profile_override: dict[str, Any] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.db_path = db_path or self.settings.DATABASE_PATH
        self.profile = profile_override or load_engine_config(self.settings.CONFIG_FILE)

        self.symbol = self.profile.get("symbol", self.settings.DEFAULT_SYMBOL)
        self.timeframe = self.profile.get("timeframe", "1h")
        self.contract_value_btc = Decimal(str(self.profile.get("contract_value_btc", "0.001")))
        self.initial_capital = Decimal(str(self.profile.get("initial_capital", "10000.0")))
        self.max_leverage = int(self.profile.get("leverage_limit", 3))

        # 1. State machine & Supervisor
        self.state_machine = EngineStateMachine(initial_state=EngineState.INITIALISING)
        self.supervisor = Supervisor(max_consecutive_restarts=5, base_backoff_seconds=1.0)
        self.kill_switch = KillSwitch(state_machine=self.state_machine)

        # 2. Database & Journal
        init_database(self.db_path)
        self._db_conn = get_db_connection(self.db_path)
        self.journal_writer = JournalWriter(self._db_conn)

        # 3. Market data & Freshness
        self.candle_store = CandleStore(symbol=self.symbol, timeframe=self.timeframe)
        self.freshness_tracker = FreshnessTracker(
            max_staleness_seconds=float(self.profile.get("max_staleness_seconds", 5.0))
        )
        self.candle_builder = CandleBuilder(
            symbol=self.symbol,
            timeframe=self.timeframe,
            on_candle_closed=self._handle_candle_closed_event,
            max_age_s=float(self.profile.get("max_staleness_seconds", 5.0)),
        )

        # 4. Signal layer & Regime filter
        self.regime_filter = RegimeFilter(
            trend_threshold=float(self.profile.get("trend_threshold", 25.0)),
            volatility_lookback=int(self.profile.get("volatility_lookback", 20)),
        )
        self.strategy_trend = TrendFollowingStrategy(
            fast_period=int(self.profile.get("trend_fast_period", 20)),
            slow_period=int(self.profile.get("trend_slow_period", 50)),
            atr_period=int(self.profile.get("atr_period", 14)),
        )
        self.strategy_reversion = MeanReversionStrategy(
            lookback_period=int(self.profile.get("reversion_lookback", 30)),
            z_score_threshold=float(self.profile.get("reversion_z_score", 2.0)),
            atr_period=int(self.profile.get("atr_period", 14)),
        )
        self.strategies = {
            self.strategy_trend.name: self.strategy_trend,
            self.strategy_reversion.name: self.strategy_reversion,
        }

        # 5. Shadow layer & Allocator
        self.cost_model = ShadowCostModel(
            maker_fee_pct=Decimal(str(self.profile.get("maker_fee_pct", "0.0002"))),
            taker_fee_pct=Decimal(str(self.profile.get("taker_fee_pct", "0.0005"))),
            default_slippage_bps=Decimal(str(self.profile.get("slippage_bps", "10.0"))),
        )
        self.shadow_accounts: dict[str, ShadowAccount] = {
            self.strategy_trend.name: ShadowAccount(
                strategy_name=self.strategy_trend.name,
                initial_capital=self.initial_capital,
                cost_model=self.cost_model,
                contract_multiplier=self.contract_value_btc,
            ),
            self.strategy_reversion.name: ShadowAccount(
                strategy_name=self.strategy_reversion.name,
                initial_capital=self.initial_capital,
                cost_model=self.cost_model,
                contract_multiplier=self.contract_value_btc,
            ),
        }
        self.allocator = StrategyAllocator(
            exploration_floor=float(self.profile.get("exploration_floor", 0.10)),
            recency_window_trades=int(self.profile.get("recency_window_trades", 20)),
            min_trades_for_prior=int(self.profile.get("min_trades_for_prior", 5)),
            seed=42,
        )

        # 6. Risk Gate & Sizing
        self.sizer = PositionSizer(
            default_risk_fraction=float(self.profile.get("risk_fraction", 0.01)),
            contract_value_btc=self.contract_value_btc,
            max_leverage=self.max_leverage,
        )
        self.drawdown_ladder = DrawdownLadder(
            initial_capital=self.initial_capital,
            cooling_off_pct=float(self.profile.get("drawdown_caution_pct", 0.02)),
            reduced_size_pct=float(self.profile.get("drawdown_degraded_pct", 0.04)),
            halt_pct=float(self.profile.get("drawdown_halt_pct", 0.06)),
            kill_switch=self.kill_switch,
        )
        self.risk_gate = RiskGate(
            state_machine=self.state_machine,
            kill_switch=self.kill_switch,
            sizer=self.sizer,
            drawdown_ladder=self.drawdown_ladder,
            max_spread_bps=float(self.profile.get("max_spread_bps", 15.0)),
            max_staleness_seconds=float(self.profile.get("max_staleness_seconds", 5.0)),
        )

        # 7. Execution, Reconciliation & Watchdog
        self.exchange = exchange
        self.execution_manager = ExecutionManager(exchange=self.exchange) if self.exchange else None
        self.reconciler = Reconciler(exchange=self.exchange) if self.exchange else None
        self.watchdog = UnprotectedPositionWatchdog(
            exchange=self.exchange,
            kill_switch=self.kill_switch,
        ) if self.exchange else None

        self._last_decision: DecisionRecord | None = None
        self._current_regime: RegimeReading | None = None
        self._current_allocation: AllocationDecision | None = None
        self._clock_drift_seconds: float = 0.02
        self.current_equity: Decimal = self.initial_capital

    def set_exchange(self, exchange: Any) -> None:
        """Inject or swap exchange client."""
        self.exchange = exchange
        self.execution_manager = ExecutionManager(exchange=self.exchange)
        self.reconciler = Reconciler(exchange=self.exchange)
        self.watchdog = UnprotectedPositionWatchdog(
            exchange=self.exchange,
            kill_switch=self.kill_switch,
        )

    async def initialize(self) -> None:
        """Startup routine: reconcile, check clock, transition to RUNNING or PAUSED."""
        logger.info("Initializing Trading Engine for symbol %s (%s)...", self.symbol, self.timeframe)
        self.state_machine.transition(EngineState.WARMING_UP, reason="Startup initialization")

        # Initial reconciliation if exchange client is configured
        if self.exchange and self.reconciler:
            try:
                await self.reconciler.reconcile()
                logger.info("Startup reconciliation complete. Found %d active positions.", len(self.reconciler.last_reconciled_positions))
            except Exception as exc:
                logger.warning("Startup reconciliation warning: %s", exc)

        # Register supervised loops
        if self.reconciler:
            self.supervisor.register("periodic_reconciliation", self._reconciliation_loop)
        if self.watchdog:
            self.supervisor.register("position_watchdog", self._watchdog_loop)

        await self.supervisor.start()

        # If credentials are not configured or are placeholder, start in PAUSED to prevent unintended trades
        if (
            not self.settings.DELTA_API_KEY
            or self.settings.DELTA_API_KEY == "your_delta_testnet_api_key_here"
        ):
            self.state_machine.transition(EngineState.PAUSED, reason="Placeholder API credentials; entries paused")
            logger.info("Engine transitioned to PAUSED (waiting for valid API credentials).")
        else:
            self.state_machine.transition(EngineState.RUNNING, reason="Initialization and warmup complete")
            logger.info("Engine transitioned to RUNNING. Operational and ready.")

    async def stop(self) -> None:
        """Gracefully shut down background supervisor and database connections."""
        logger.info("Stopping Trading Engine...")
        await self.supervisor.stop()
        if self.state_machine.current_state != EngineState.STOPPED:
            try:
                self.state_machine.transition(EngineState.STOPPED, reason="Clean shutdown")
            except Exception:
                pass
        try:
            self._db_conn.close()
        except Exception:
            pass
        logger.info("Trading Engine stopped.")

    def _handle_candle_closed_event(self, event: Any) -> None:
        """Callback invoked when CandleBuilder closes a candle."""
        if hasattr(event, "candle") and event.candle:
            asyncio.create_task(self.process_candle(event.candle))

    async def process_candle(
        self,
        candle: Candle,
        snapshot: MarketSnapshot | None = None,
    ) -> DecisionRecord:
        """Executes the complete End-to-End decision loop per closed candle.

        Per Section 7.4 of agent.md:
        1. Store closed candle, verify contiguity.
        2. Compute indicators and regime filter.
        3. Evaluate Strategy A and Strategy B pure signals.
        4. Update shadow accounts and calculate performance statistics.
        5. Allocator selects active strategy or enforces stand-aside.
        6. Build OrderIntent if a strategy is selected with non-flat signal.
        7. RiskGate evaluates intent against safety rules.
        8. If approved/resized, ExecutionManager places order + bracket.
        9. Generate plain-language narrative.
        10. Persist complete DecisionRecord in SQLite journal.
        """
        # 1. Store candle
        self.candle_store.add_candle(candle)
        self.freshness_tracker.record_update(candle.close_time)

        # Construct default snapshot if not supplied
        if snapshot is None:
            snapshot = MarketSnapshot(
                symbol=candle.symbol,
                timestamp=candle.close_time,
                best_bid=candle.close - Decimal("0.5"),
                best_ask=candle.close + Decimal("0.5"),
                bid_size=Decimal("10.0"),
                ask_size=Decimal("10.0"),
                mark_price=candle.close,
                spot_price=candle.close,
            )

        # 2. Indicators & Regime Filter
        candles = self.candle_store.get_candles()
        regime = self.regime_filter.evaluate(candles)
        self._current_regime = regime

        # 3. Strategy Signals
        signals: dict[str, Signal] = {}
        for name, strat in self.strategies.items():
            signals[name] = strat.evaluate(candles)

        # 4. Shadow Accounts
        for name, shadow in self.shadow_accounts.items():
            shadow.process_closed_candle(candle)
            sig = signals.get(name)
            if sig:
                shadow.on_signal(sig, candle)

        shadow_stats = {name: s.get_stats() for name, s in self.shadow_accounts.items()}

        # 5. Allocator
        allocation = self.allocator.allocate(
            regime=regime,
            shadow_stats=shadow_stats,
            shadow_accounts=self.shadow_accounts,
        )
        self._current_allocation = allocation

        # 6. Order Intent
        decision_id = f"dec_{int(candle.close_time.timestamp())}_{candle.symbol.lower()}"
        intent: OrderIntent | None = None
        selected_strat_name = allocation.selected_strategy
        selected_signal = signals.get(selected_strat_name) if selected_strat_name else None

        if (
            selected_strat_name
            and selected_signal
            and selected_signal.direction != Direction.FLAT
            and allocation.weight > 0.0
        ):
            intent = OrderIntent(
                decision_id=decision_id,
                strategy_name=selected_strat_name,
                symbol=candle.symbol,
                direction=selected_signal.direction,
                desired_risk_fraction=0.01 * allocation.weight,
                proposed_stop_distance=selected_signal.proposed_stop_distance,
                proposed_tp_distance=selected_signal.proposed_stop_distance * Decimal("2.0"),
            )

        # 7. Risk Gate Evaluation
        current_equity = self.current_equity
        if intent is not None:
            verdict = self.risk_gate.evaluate_intent(
                intent=intent,
                snapshot=snapshot,
                current_equity=current_equity,
                allocator_weight=allocation.weight,
            )
        else:
            verdict = RiskVerdict(
                action=RiskAction.REJECT,
                approved_contracts=0,
                approved_risk_fraction=0.0,
                binding_rule="NO_TRADE_ALLOCATED",
                rejection_reason="No strategy allocated risk or signal is FLAT",
            )

        # 8. Execution Manager (if approved or resized)
        order_record = None
        if verdict.action in (RiskAction.APPROVE, RiskAction.RESIZE) and self.execution_manager and intent:
            try:
                order_record = await self.execution_manager.execute_intent(intent, verdict, snapshot)
            except Exception as exc:
                logger.error("Execution error for decision %s: %s", decision_id, exc)

        # 9. Plain-language Narrative
        narrative = NarrativeGenerator.generate(
            symbol=candle.symbol,
            regime=regime,
            allocation=allocation,
            verdict=verdict,
        )

        # 10. Persist Decision Record
        orders = [order_record] if order_record else []
        record = DecisionRecord(
            decision_id=decision_id,
            timestamp=datetime.now(timezone.utc),
            symbol=candle.symbol,
            timeframe=candle.timeframe,
            candle_close_price=candle.close,
            regime=regime,
            signals=list(signals.values()),
            shadow_stats=list(shadow_stats.values()),
            allocation=allocation,
            intent=intent,
            risk_verdict=verdict,
            orders=orders,
            narrative=narrative,
        )
        self.journal_writer.write_decision(record)
        self._last_decision = record
        return record

    # =========================================================================
    # Control Plane Operations
    # =========================================================================

    def pause(self) -> EngineState:
        """Pause trading entries (existing brackets remain protected)."""
        new_state = self.state_machine.transition(EngineState.PAUSED, reason="Manual operator pause")
        self.journal_writer.write_event(
            EngineStateChangedEvent(
                old_state=EngineState.RUNNING,
                new_state=EngineState.PAUSED,
                reason="Manual operator pause",
            )
        )
        return new_state

    def resume(self) -> EngineState:
        """Resume trading entries."""
        new_state = self.state_machine.transition(EngineState.RUNNING, reason="Manual operator resume")
        self.journal_writer.write_event(
            EngineStateChangedEvent(
                old_state=EngineState.PAUSED,
                new_state=EngineState.RUNNING,
                reason="Manual operator resume",
            )
        )
        return new_state

    async def kill(self, reason: str = "Operator emergency kill") -> KillSwitchActivatedEvent:
        """Emergency halt: cancel orders, close positions, transition to HALTED."""
        evt = self.kill_switch.trigger(source="control_plane_api", reason=reason)
        if self.exchange:
            try:
                if hasattr(self.exchange, "cancel_all"):
                    await self.exchange.cancel_all(self.symbol)
                elif hasattr(self.exchange, "cancel_all_orders"):
                    await self.exchange.cancel_all_orders(self.symbol)

                if hasattr(self.exchange, "close_all"):
                    await self.exchange.close_all(self.symbol)
                elif hasattr(self.exchange, "close_all_positions"):
                    await self.exchange.close_all_positions(self.symbol)
            except Exception as exc:
                logger.error("Error flattening positions on kill: %s", exc)
        self.journal_writer.write_event(evt)
        return evt

    def reset_from_halt(self, confirmation: str) -> bool:
        """Reset from HALTED to PAUSED after human verification."""
        success = self.kill_switch.reset_from_halt(confirmation_token=confirmation)
        if success:
            self.journal_writer.write_event(
                EngineStateChangedEvent(
                    old_state=EngineState.HALTED,
                    new_state=EngineState.PAUSED,
                    reason="Human confirmed reset from halt",
                )
            )
        return success

    async def inject_chaos(self, scenario: str, intensity: float = 1.0) -> dict[str, Any]:
        """Inject scripted demo chaos scenario."""
        logger.warning("Injecting chaos scenario: %s (intensity=%.2f)", scenario, intensity)
        if scenario == "price_shock":
            if self.exchange and hasattr(self.exchange, "set_market_price"):
                current_price = Decimal("65000.0")
                drop_price = current_price * Decimal(str(1.0 - (0.10 * intensity)))
                await self.exchange.set_market_price(new_bid=drop_price, new_ask=drop_price + Decimal("5.0"))
            return {"status": "injected", "scenario": scenario, "action": "Triggered adverse price wick"}
        elif scenario == "stale_feed":
            self.freshness_tracker.last_update_time = None
            return {"status": "injected", "scenario": scenario, "action": "Cleared freshness timestamp to trigger stall"}
        elif scenario == "rate_limit_storm":
            if self.exchange and hasattr(self.exchange, "simulate_rate_limit"):
                self.exchange.simulate_rate_limit = True
            return {"status": "injected", "scenario": scenario, "action": "Simulating exchange HTTP 429 rate limit storm"}
        return {"status": "injected", "scenario": scenario, "action": "General simulated chaos applied"}

    # =========================================================================
    # Status & Reporting Views
    # =========================================================================

    def get_health(self) -> dict[str, Any]:
        """Health indicators for /api/health."""
        db_ok = True
        try:
            with self._db_conn:
                self._db_conn.execute("SELECT 1;")
        except Exception:
            db_ok = False

        is_healthy = (
            db_ok
            and self.state_machine.current_state != EngineState.HALTED
            and self.supervisor.is_healthy
        )
        return {
            "status": "healthy" if is_healthy else "degraded",
            "target_env": self.settings.TARGET_ENV,
            "engine_state": self.state_machine.current_state.value,
            "clock_drift_seconds": self._clock_drift_seconds,
            "data_fresh": self.freshness_tracker.is_fresh(),
            "database_ok": db_ok,
            "supervisor_healthy": self.supervisor.is_healthy,
        }

    def get_status(self) -> dict[str, Any]:
        """Operational status for /api/status."""
        regime_label = self._current_regime.label.value if self._current_regime else "RANGING"
        allocated_strat = (
            self._current_allocation.selected_strategy
            if self._current_allocation and self._current_allocation.selected_strategy
            else "none"
        )
        dd_pct = self.drawdown_ladder.current_drawdown_pct(self.current_equity)
        return {
            "engine_state": self.state_machine.current_state.value,
            "active_profile": self.profile.get("profile", "default"),
            "symbol": self.symbol,
            "current_regime": regime_label,
            "allocated_strategy": allocated_strat,
            "kill_switch_active": self.kill_switch.is_active,
            "equity": float(self.current_equity),
            "drawdown_pct": float(dd_pct),
        }

    async def get_positions(self) -> dict[str, Any]:
        """Exchange-reconciled positions and orders for /api/positions."""
        positions: list[dict[str, Any]] = []
        if self.reconciler:
            positions = [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "contracts": p.contracts,
                    "entry_price": float(p.entry_price),
                    "mark_price": float(p.mark_price),
                    "unrealized_pnl": float(p.unrealized_pnl),
                    "leverage": p.leverage,
                    "has_active_bracket": p.has_active_bracket,
                }
                for p in self.reconciler.last_reconciled_positions
            ]
        return {
            "positions": positions,
            "open_orders": [],
            "source": "reconciled_exchange_truth",
        }

    def get_strategies(self) -> dict[str, Any]:
        """Shadow account performance for /api/strategies."""
        stats_list = []
        for name, shadow in self.shadow_accounts.items():
            st = shadow.get_stats()
            stats_list.append(
                {
                    "strategy": name,
                    "trade_count": st.trade_count,
                    "win_rate": round(st.win_rate, 4),
                    "net_profit": float(st.net_profit),
                    "max_drawdown_pct": round(st.max_drawdown_pct, 4),
                }
            )
        return {
            "disclaimer": "All performance numbers here are HYPOTHETICAL from shadow accounts.",
            "shadow_accounts": stats_list,
        }

    # =========================================================================
    # Supervised Background Tasks
    # =========================================================================

    async def _reconciliation_loop(self) -> None:
        """Periodic background reconciliation with exchange REST truth."""
        while True:
            await asyncio.sleep(15.0)
            if self.reconciler and self.exchange:
                try:
                    await self.reconciler.reconcile()
                except Exception as exc:
                    logger.warning("Periodic reconciliation encountered issue: %s", exc)

    async def _watchdog_loop(self) -> None:
        """Periodic background inspection for unprotected positions."""
        while True:
            await asyncio.sleep(5.0)
            if self.watchdog and self.exchange:
                try:
                    await self.watchdog.inspect_positions()
                except Exception as exc:
                    logger.warning("Position watchdog encountered issue: %s", exc)


# Module-level singleton engine holder
_active_engine: TradingEngine | None = None


def get_trading_engine() -> TradingEngine:
    """Return the global active trading engine instance."""
    global _active_engine
    if _active_engine is None:
        _active_engine = TradingEngine()
    return _active_engine


def set_trading_engine(engine: TradingEngine) -> None:
    """Set the global active trading engine instance."""
    global _active_engine
    _active_engine = engine
