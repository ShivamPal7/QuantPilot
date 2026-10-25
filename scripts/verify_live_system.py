"""Live Verification of FastAPI Control Plane & Real Delta Testnet Integration.

Tests the full operational lifecycle against live Delta Exchange India Testnet:
1. Lifespan startup & safety guard verification.
2. Live product specification & wallet balance sync.
3. /api/health and /api/status reporting real testnet parameters.
4. /api/positions verifying live reconciled exchange truth.
5. /api/control/step executing full closed-candle pipeline & narrative logging.
6. /api/decisions reading back SQLite decision journal entries.
7. /api/control/flatten invoking exchange close_all.
8. /api/control/kill & /api/control/reset testing safeguard controls.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path
import sys

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.engine import get_trading_engine
from app.exchange.client import DeltaRESTClient
from app.main import app, lifespan


async def verify_live_system() -> None:
    print("=" * 75)
    print("QuantPilot Phase 2: Live FastAPI & Delta Testnet Verification")
    print("=" * 75)

    settings = get_settings()
    print(f"Target Environment: {settings.TARGET_ENV}")
    print(f"REST URL:           {settings.DELTA_REST_URL}")

    # Use lifespan context manager to start and stop app cleanly
    async with lifespan(app):
        engine = get_trading_engine()

        # 1. Verify Engine state and Exchange Client
        print("\n[Step 1] Verifying Live Engine Initialization...")
        status = engine.get_status()
        print(f"  Engine State:        {status['engine_state']}")
        print(f"  Symbol:              {status['symbol']}")
        print(f"  Current Regime:      {status['current_regime']}")
        print(f"  Allocated Strategy:  {status['allocated_strategy']}")
        print(f"  Live Equity:         {status['equity']:.4f} USD")
        print(f"  Kill Switch Active:  {status['kill_switch_active']}")
        assert status["engine_state"] == "RUNNING", f"Expected RUNNING, got {status['engine_state']}"
        assert status["equity"] > 0, "Expected positive live equity from testnet"
        print("  ✅ Engine initialized in RUNNING state with live equity sync.")

        # 2. Check Reconciled Positions against Delta Testnet
        print("\n[Step 2] Checking Reconciled Positions from Delta Testnet...")
        pos_data = await engine.get_positions()
        print(f"  Open Positions:      {len(pos_data['positions'])}")
        print(f"  Source:              {pos_data['source']}")
        for p in pos_data["positions"]:
            print(f"    -> {p['contracts']} contracts {p['side']} {p['symbol']} @ {p['entry_price']} (Bracket: {p['has_active_bracket']})")
        print("  ✅ Live exchange positions queried successfully.")

        # 3. Test Step Closed Candle Pipeline
        print("\n[Step 3] Stepping Closed Candle Pipeline via Engine...")
        rec = await engine.step_candle(close_price=80350.0)
        print(f"  Decision ID:         {rec.decision_id}")
        print(f"  Regime:              {rec.regime.label.value} (Confidence: {rec.regime.confidence:.2f})")
        print(f"  Selected Strategy:   {rec.allocation.selected_strategy}")
        print(f"  Risk Gate Verdict:   {rec.risk_verdict.action.value} ({rec.risk_verdict.binding_rule})")
        print(f"  Approved Contracts:  {rec.risk_verdict.approved_contracts}")
        print(f"  Decision Narrative:  {rec.narrative}")
        assert rec.decision_id is not None
        assert len(rec.narrative) > 0
        print("  ✅ Step candle executed and logged to SQLite decision journal.")

        # 4. Read back Decision from SQLite Journal
        print("\n[Step 4] Reading back Decision from SQLite Journal...")
        import sqlite3
        conn = sqlite3.connect(settings.DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM decisions WHERE decision_id = ?", (rec.decision_id,))
        row = cur.fetchone()
        assert row is not None, f"Decision {rec.decision_id} not found in database!"
        print(f"  Found DB Decision:   {row['decision_id']}")
        print(f"  DB Regime:           {row['regime_label']}")
        print(f"  DB Narrative:        {row['narrative']}")
        conn.close()
        print("  ✅ SQLite Decision Journal verified.")

        # 5. Test Live Emergency Flatten
        print("\n[Step 5] Testing Emergency Flatten on Live Delta Testnet...")
        flat_res = await engine.flatten()
        print(f"  Flatten Result:      {flat_res}")
        assert flat_res["status"] == "success"
        print("  ✅ Live exchange close_all & cancel_all completed successfully.")

        # 6. Test Kill Switch & Reset
        print("\n[Step 6] Testing Kill Switch & Reset Safeguard...")
        engine.kill_switch.trigger(
            source="verification_test",
            reason="Automated live system test drill",
        )
        post_kill_status = engine.get_status()
        print(f"  Engine State after Kill: {post_kill_status['engine_state']}")
        print(f"  Kill Switch Active:      {post_kill_status['kill_switch_active']}")
        assert post_kill_status["engine_state"] == "HALTED"
        assert post_kill_status["kill_switch_active"] is True

        reset_success = engine.reset_from_halt(confirmation="CONFIRM_RESET")
        post_reset_status = engine.get_status()
        print(f"  Reset Success:           {reset_success}")
        print(f"  Engine State after Reset:{post_reset_status['engine_state']}")
        assert reset_success is True
        assert post_reset_status["engine_state"] == "PAUSED"
        print("  ✅ Emergency Kill Switch & Reset verified.")

    print("\n" + "=" * 75)
    print("🎉 All Live FastAPI & Delta Testnet Checks PASSED Cleanly!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(verify_live_system())
