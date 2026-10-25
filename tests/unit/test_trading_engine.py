"""Unit and integration tests for TradingEngine orchestrator and connected API routes.

Per Section 7, 9, 13 of agent.md:
- Tests end-to-end candle processing pipeline.
- Tests regime classification, strategy evaluation, shadow accounts, allocator, risk gate, execution with brackets.
- Tests journal persistence with plain-language narrative.
- Tests control operations: pause, resume, kill, reset from halt, chaos injection.
- Tests connected control-plane API route handlers.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
import tempfile
import unittest

from app.api.routes import (
    get_config,
    get_decisions,
    get_health,
    get_positions,
    get_status,
    get_strategies,
    inject_chaos,
    pause_trading,
    resume_trading,
    reset_from_halt,
    trigger_kill_switch,
)
from app.api.schemas import ChaosRequest, KillRequest, ResetRequest
from app.core.config import AppSettings
from app.core.contracts import (
    Candle,
    Direction,
    MarketSnapshot,
    RiskAction,
)
from app.core.state import EngineState
from app.core.engine import TradingEngine, get_trading_engine, set_trading_engine
from tests.fakes.fake_exchange import FakeExchange


class TestTradingEngine(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_engine.db")

        self.fake_exchange = FakeExchange(initial_balance=Decimal("10000.0"))
        self.settings = AppSettings(
            TARGET_ENV="testnet",
            DELTA_REST_URL="https://cdn-ind.testnet.deltaex.org",
            DELTA_WS_PUBLIC_URL="wss://socket-ind-pub.testnet.deltaex.org",
            DELTA_WS_PRIVATE_URL="wss://socket-ind.testnet.deltaex.org",
            DELTA_API_KEY="test_key_abc",
            DELTA_API_SECRET="test_secret_xyz",
            DATABASE_PATH=self.db_path,
        )

        self.engine = TradingEngine(
            settings=self.settings,
            exchange=self.fake_exchange,
            db_path=self.db_path,
        )
        set_trading_engine(self.engine)

    async def asyncTearDown(self) -> None:
        await self.engine.stop()
        self.tmp_dir.cleanup()

    async def test_engine_lifecycle_initialize_and_stop(self) -> None:
        """Verify engine initializes, transitions state machine, and shuts down cleanly."""
        self.assertEqual(self.engine.state_machine.current_state, EngineState.INITIALISING)
        await self.engine.initialize()
        self.assertEqual(self.engine.state_machine.current_state, EngineState.RUNNING)
        self.assertTrue(self.engine.supervisor.is_healthy)

        health = self.engine.get_health()
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(health["target_env"], "testnet")
        self.assertTrue(health["database_ok"])

    async def test_engine_control_operations_pause_resume_kill_reset(self) -> None:
        """Verify pause, resume, kill, and reset operations."""
        await self.engine.initialize()
        self.assertEqual(self.engine.state_machine.current_state, EngineState.RUNNING)

        # 1. Pause
        new_state = self.engine.pause()
        self.assertEqual(new_state, EngineState.PAUSED)
        self.assertEqual(self.engine.state_machine.current_state, EngineState.PAUSED)

        # 2. Resume
        new_state = self.engine.resume()
        self.assertEqual(new_state, EngineState.RUNNING)
        self.assertEqual(self.engine.state_machine.current_state, EngineState.RUNNING)

        # 3. Emergency Kill
        evt = await self.engine.kill(reason="Test emergency halt")
        self.assertEqual(self.engine.state_machine.current_state, EngineState.HALTED)
        self.assertTrue(self.engine.kill_switch.is_active)
        self.assertEqual(evt.reason, "Test emergency halt")

        # 4. Reset with wrong token fails
        fail_reset = self.engine.reset_from_halt("WRONG_TOKEN")
        self.assertFalse(fail_reset)
        self.assertEqual(self.engine.state_machine.current_state, EngineState.HALTED)

        # 5. Reset with correct token succeeds and enters PAUSED
        ok_reset = self.engine.reset_from_halt("CONFIRM_RESET")
        self.assertTrue(ok_reset)
        self.assertEqual(self.engine.state_machine.current_state, EngineState.PAUSED)
        self.assertFalse(self.engine.kill_switch.is_active)

    async def test_process_candle_end_to_end_decision_flow(self) -> None:
        """Feed candles to engine and verify end-to-end evaluation and journal record creation."""
        await self.engine.initialize()

        base_time = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        record = None

        # Feed 60 candles to satisfy minimum history requirements
        for i in range(60):
            candle_time = base_time + timedelta(hours=i)
            # Create a trending price series (rising steadily)
            close_price = Decimal("60000.0") + Decimal(str(i * 50.0))
            c = Candle(
                symbol="BTCUSD",
                timeframe="1h",
                open_time=candle_time,
                close_time=candle_time + timedelta(hours=1),
                open=close_price - Decimal("10.0"),
                high=close_price + Decimal("40.0"),
                low=close_price - Decimal("20.0"),
                close=close_price,
                volume=Decimal("150.0"),
                is_closed=True,
                source="test",
            )
            snapshot = MarketSnapshot(
                symbol="BTCUSD",
                timestamp=candle_time + timedelta(hours=1),
                best_bid=close_price - Decimal("1.0"),
                best_ask=close_price + Decimal("1.0"),
                bid_size=Decimal("10.0"),
                ask_size=Decimal("10.0"),
                mark_price=close_price,
                spot_price=close_price,
            )
            record = await self.engine.process_candle(c, snapshot)

        self.assertIsNotNone(record)
        self.assertEqual(record.symbol, "BTCUSD")
        self.assertIsNotNone(record.regime)
        strat_names = [s.strategy_name for s in record.signals]
        self.assertIn("trend_following", strat_names)
        self.assertIn("mean_reversion", strat_names)
        self.assertIsNotNone(record.allocation)
        self.assertIsNotNone(record.risk_verdict)
        self.assertIsInstance(record.narrative, str)
        self.assertGreater(len(record.narrative), 10)

        # Verify narrative contains regime and verdict
        self.assertIn("Market regime", record.narrative)
        self.assertIn("Risk gate", record.narrative)

    async def test_connected_api_routes(self) -> None:
        """Verify API endpoints query and mutate the active TradingEngine."""
        await self.engine.initialize()

        # 1. Health endpoint
        health = await get_health()
        self.assertEqual(health.status, "healthy")
        self.assertEqual(health.target_env, "testnet")
        self.assertEqual(health.engine_state, EngineState.RUNNING.value)

        # 2. Status endpoint
        status_resp = await get_status()
        self.assertEqual(status_resp.engine_state, EngineState.RUNNING.value)
        self.assertEqual(status_resp.symbol, "BTCUSD")
        self.assertFalse(status_resp.kill_switch_active)

        # 3. Positions endpoint
        positions_resp = await get_positions()
        self.assertIn("positions", positions_resp)
        self.assertEqual(positions_resp["source"], "reconciled_exchange_truth")

        # 4. Strategies endpoint
        strat_resp = await get_strategies()
        self.assertIn("HYPOTHETICAL", strat_resp["disclaimer"])
        self.assertEqual(len(strat_resp["shadow_accounts"]), 2)

        # 5. Config endpoint
        config_resp = await get_config()
        self.assertEqual(config_resp["target_env"], "testnet")

        # 6. Guarded Pause
        pause_resp = await pause_trading(_secret="dev_secret_change_me")
        self.assertEqual(pause_resp["status"], "success")
        self.assertEqual(pause_resp["engine_state"], EngineState.PAUSED.value)

        # 7. Guarded Resume
        resume_resp = await resume_trading(_secret="dev_secret_change_me")
        self.assertEqual(resume_resp["status"], "success")
        self.assertEqual(resume_resp["engine_state"], EngineState.RUNNING.value)

        # 8. Guarded Kill
        kill_req = KillRequest(reason="Operator test drill")
        kill_resp = await trigger_kill_switch(kill_req, _secret="dev_secret_change_me")
        self.assertEqual(kill_resp["status"], "HALTED")
        self.assertEqual(kill_resp["reason"], "Operator test drill")
        self.assertEqual(self.engine.state_machine.current_state, EngineState.HALTED)

        # 9. Guarded Reset
        reset_req = ResetRequest(confirmation="CONFIRM_RESET")
        reset_resp = await reset_from_halt(reset_req, _secret="dev_secret_change_me")
        self.assertEqual(reset_resp["status"], "success")
        self.assertEqual(reset_resp["engine_state"], EngineState.PAUSED.value)

        # 10. Guarded Chaos injection
        chaos_req = ChaosRequest(scenario="price_shock", intensity=1.5)
        chaos_resp = await inject_chaos(chaos_req, _secret="dev_secret_change_me")
        self.assertEqual(chaos_resp["status"], "injected")
        self.assertEqual(chaos_resp["scenario"], "price_shock")


if __name__ == "__main__":
    unittest.main()
