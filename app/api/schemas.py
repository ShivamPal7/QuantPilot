"""Pydantic schemas for the Control Plane API."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    target_env: str
    engine_state: str
    clock_drift_seconds: float
    data_fresh: bool
    database_ok: bool


class StatusResponse(BaseModel):
    engine_state: str
    active_profile: str
    symbol: str
    current_regime: str
    allocated_strategy: str | None
    kill_switch_active: bool


class KillRequest(BaseModel):
    reason: str = Field(default="Manual operator kill switch trigger")


class ResetRequest(BaseModel):
    confirmation: str = Field(description="Must match 'CONFIRM_RESET'")


class ChaosRequest(BaseModel):
    scenario: str = Field(description="Chaos scenario name (e.g. 'price_shock', 'stale_feed')")
    intensity: float = Field(default=1.0)
