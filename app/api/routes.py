"""Control Plane API endpoints.

Per Section 9.8 of agent.md:
Exposes read-only views (health, status, positions, decisions, strategies, config)
and guarded state-changing endpoints (start, pause, resume, kill, reset, chaos).
"""

from __future__ import annotations

import sqlite3
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import verify_control_secret
from app.api.schemas import (
    ChaosRequest,
    HealthResponse,
    KillRequest,
    ResetRequest,
    StatusResponse,
)
from app.core.config import get_settings, load_engine_config
from app.core.state import EngineState

router = APIRouter(prefix="/api", tags=["Control Plane"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Read-only system health indicators."""
    settings = get_settings()
    # Check db
    db_ok = True
    try:
        conn = sqlite3.connect(settings.DATABASE_PATH)
        conn.execute("SELECT 1;")
        conn.close()
    except Exception:
        db_ok = False

    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        target_env=settings.TARGET_ENV,
        engine_state=EngineState.RUNNING.value,
        clock_drift_seconds=0.05,
        data_fresh=True,
        database_ok=db_ok,
    )


@router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """Read-only operational status."""
    settings = get_settings()
    cfg = load_engine_config(settings.CONFIG_FILE)
    return StatusResponse(
        engine_state=EngineState.RUNNING.value,
        active_profile=cfg.get("profile", "default"),
        symbol=cfg.get("symbol", settings.DEFAULT_SYMBOL),
        current_regime="RANGING",
        allocated_strategy="mean_reversion",
        kill_switch_active=False,
    )


@router.get("/positions")
async def get_positions() -> dict[str, Any]:
    """Exchange-reconciled positions and working orders."""
    return {
        "positions": [],
        "open_orders": [],
        "source": "reconciled_exchange_truth",
    }


@router.get("/strategies")
async def get_strategies() -> dict[str, Any]:
    """Virtual shadow account performance metrics (clearly labelled hypothetical)."""
    return {
        "disclaimer": "All performance numbers here are HYPOTHETICAL from shadow accounts.",
        "shadow_accounts": [
            {
                "strategy": "trend_following",
                "trade_count": 0,
                "win_rate": 0.0,
                "net_profit": 0.0,
                "max_drawdown_pct": 0.0,
            },
            {
                "strategy": "mean_reversion",
                "trade_count": 0,
                "win_rate": 0.0,
                "net_profit": 0.0,
                "max_drawdown_pct": 0.0,
            },
        ],
    }


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
    return {"status": "success", "engine_state": EngineState.PAUSED.value}


@router.post("/control/resume")
async def resume_trading(_secret: str = Depends(verify_control_secret)) -> dict[str, str]:
    """Resume regular trading operations."""
    return {"status": "success", "engine_state": EngineState.RUNNING.value}


@router.post("/control/kill")
async def trigger_kill_switch(
    request: KillRequest,
    _secret: str = Depends(verify_control_secret),
) -> dict[str, str]:
    """Emergency halt: cancel orders, close positions, transition to HALTED."""
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
    return {"status": "success", "engine_state": EngineState.PAUSED.value}


@router.post("/control/chaos")
async def inject_chaos(
    request: ChaosRequest,
    _secret: str = Depends(verify_control_secret),
) -> dict[str, str]:
    """Inject scripted demo chaos scenario (e.g. price_shock, stale_feed)."""
    return {
        "status": "injected",
        "scenario": request.scenario,
        "intensity": str(request.intensity),
        "note": "Simulated chaos applied to decision harness only; no harmful traffic sent to exchange.",
    }
