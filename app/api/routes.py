"""Control Plane API endpoints.

Per Section 9.8 of agent.md:
Exposes read-only views (health, status, positions, decisions, strategies, config)
and guarded state-changing endpoints (start, pause, resume, kill, reset, chaos).
All endpoints connect to the live TradingEngine.
"""

from __future__ import annotations

import sqlite3
from typing import Any

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, status
except ImportError:
    class APIRouter:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def get(self, *args: Any, **kwargs: Any) -> Any:
            def decorator(f: Any) -> Any:
                return f
            return decorator

        def post(self, *args: Any, **kwargs: Any) -> Any:
            def decorator(f: Any) -> Any:
                return f
            return decorator

    def Depends(dependency: Any = None) -> Any:  # type: ignore[no-redef]
        return dependency

    def Query(default: Any = ..., **kwargs: Any) -> Any:  # type: ignore[no-redef]
        return default

    from app.api.deps import HTTPException, status  # type: ignore[assignment]


from app.api.deps import verify_control_secret
from app.api.schemas import (
    ChaosRequest,
    HealthResponse,
    KillRequest,
    ResetRequest,
    StatusResponse,
)
from app.core.config import get_settings, load_engine_config
from app.core.engine import get_trading_engine
from app.core.state import EngineState

router = APIRouter(prefix="/api", tags=["Control Plane"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Read-only system health indicators from live trading engine."""
    engine = get_trading_engine()
    health_data = engine.get_health()
    return HealthResponse(
        status=health_data["status"],
        target_env=health_data["target_env"],
        engine_state=health_data["engine_state"],
        clock_drift_seconds=health_data["clock_drift_seconds"],
        data_fresh=health_data["data_fresh"],
        database_ok=health_data["database_ok"],
    )


@router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """Read-only operational status from live trading engine."""
    engine = get_trading_engine()
    status_data = engine.get_status()
    return StatusResponse(
        engine_state=status_data["engine_state"],
        active_profile=status_data["active_profile"],
        symbol=status_data["symbol"],
        current_regime=status_data["current_regime"],
        allocated_strategy=status_data["allocated_strategy"],
        kill_switch_active=status_data["kill_switch_active"],
        equity=status_data.get("equity"),
        drawdown_pct=status_data.get("drawdown_pct"),
    )


@router.get("/positions")
async def get_positions() -> dict[str, Any]:
    """Exchange-reconciled positions, working orders, and recent fills."""
    engine = get_trading_engine()
    pos_data = await engine.get_positions()

    settings = get_settings()
    fills: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    try:
        conn = sqlite3.connect(settings.DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM fills ORDER BY filled_at DESC LIMIT 10;")
        fills = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT * FROM orders WHERE state = 'OPEN' ORDER BY created_at DESC LIMIT 10;")
        orders = [dict(r) for r in cursor.fetchall()]
        conn.close()
    except Exception:
        pass

    pos_data["fills"] = fills
    if not pos_data.get("open_orders"):
        pos_data["open_orders"] = orders
    return pos_data


@router.get("/strategies")
async def get_strategies() -> dict[str, Any]:
    """Virtual shadow account performance metrics (clearly labelled hypothetical)."""
    engine = get_trading_engine()
    return engine.get_strategies()


@router.get("/decisions")
async def get_decisions(
    limit: int = Query(20, ge=1, le=100),
    decision_id: str | None = None,
) -> dict[str, Any]:
    """Decision journal log and explanation view."""
    settings = get_settings()
    records = []
    try:
        conn = sqlite3.connect(settings.DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if decision_id:
            cursor.execute("SELECT * FROM decisions WHERE decision_id = ?", (decision_id,))
        else:
            cursor.execute("SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        for r in rows:
            records.append(dict(r))
        conn.close()
    except Exception:
        pass

    return {
        "count": len(records),
        "decisions": records,
    }


@router.get("/config")
async def get_config() -> dict[str, Any]:
    """Read-only view of active configuration with secrets redacted."""
    settings = get_settings()
    cfg = load_engine_config(settings.CONFIG_FILE)
    return {
        "target_env": settings.TARGET_ENV,
        "delta_rest_url": settings.DELTA_REST_URL,
        "parameters": cfg,
    }


# ==============================================================================
# State-Changing Endpoints (Guarded by X-Control-Secret)
# ==============================================================================

@router.post("/control/pause")
async def pause_trading(_secret: str = Depends(verify_control_secret)) -> dict[str, str]:
    """Pause new entries; existing brackets remain active."""
    engine = get_trading_engine()
    new_state = engine.pause()
    return {"status": "success", "engine_state": new_state.value}


@router.post("/control/resume")
async def resume_trading(_secret: str = Depends(verify_control_secret)) -> dict[str, str]:
    """Resume regular trading operations."""
    engine = get_trading_engine()
    new_state = engine.resume()
    return {"status": "success", "engine_state": new_state.value}


@router.post("/control/kill")
async def trigger_kill_switch(
    request: KillRequest,
    _secret: str = Depends(verify_control_secret),
) -> dict[str, str]:
    """Emergency halt: cancel orders, close positions, transition to HALTED."""
    engine = get_trading_engine()
    await engine.kill(reason=request.reason)
    return {
        "status": "HALTED",
        "action": "Working orders cancelled, positions closing via reduce-only",
        "reason": request.reason,
    }


@router.post("/control/reset")
async def reset_from_halt(
    request: ResetRequest,
    _secret: str = Depends(verify_control_secret),
) -> dict[str, str]:
    """Reset engine from HALTED to PAUSED after human verification."""
    if request.confirmation != "CONFIRM_RESET":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset rejected. 'confirmation' must equal 'CONFIRM_RESET'",
        )
    engine = get_trading_engine()
    success = engine.reset_from_halt(request.confirmation)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset rejected. Engine is not halted or verification failed.",
        )
    return {"status": "success", "engine_state": EngineState.PAUSED.value}


@router.post("/control/chaos")
async def inject_chaos(
    request: ChaosRequest,
    _secret: str = Depends(verify_control_secret),
) -> dict[str, str]:
    """Inject scripted demo chaos scenario (e.g. price_shock, stale_feed)."""
    engine = get_trading_engine()
    res = await engine.inject_chaos(scenario=request.scenario, intensity=request.intensity)
    return {
        "status": "injected",
        "scenario": request.scenario,
        "intensity": str(request.intensity),
        "note": res.get("action", "Simulated chaos applied to decision harness"),
    }


@router.post("/control/flatten")
async def flatten_positions(
    _secret: str = Depends(verify_control_secret),
) -> dict[str, Any]:
    """Manual emergency flatten: cancel all orders and close positions."""
    engine = get_trading_engine()
    return await engine.flatten()


@router.post("/control/step")
async def step_candle(
    close_price: float | None = Query(None),
) -> dict[str, Any]:
    """Trigger or simulate immediate closed-candle evaluation on the engine."""
    engine = get_trading_engine()
    rec = await engine.step_candle(close_price=close_price)
    return {
        "status": "success",
        "decision_id": rec.decision_id,
        "narrative": rec.narrative,
        "action": rec.risk_verdict.action.value,
        "symbol": rec.symbol,
        "timeframe": rec.timeframe,
    }

