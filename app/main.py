"""Main FastAPI entrypoint for QuantPilot.

Per Section 5, 7.3, and 9.8 of agent.md.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.exchange.guard import assert_testnet_environment
from app.journal.db import init_database

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context: startup validation & background task management."""
    settings = get_settings()
    setup_logging(level=settings.LOG_LEVEL)
    logger.info("Initializing QuantPilot Trading System...")

    # 1. Non-negotiable Startup Guard: Strictly enforce testnet endpoints
    assert_testnet_environment(
        target_env=settings.TARGET_ENV,
        rest_url=settings.DELTA_REST_URL,
        ws_public_url=settings.DELTA_WS_PUBLIC_URL,
        ws_private_url=settings.DELTA_WS_PRIVATE_URL,
    )
    logger.info("Testnet Safety Guard PASSED: Target host '%s' verified.", settings.DELTA_REST_URL)

    # 2. Initialize Database tables
    init_database(settings.DATABASE_PATH)
    logger.info("Decision Journal database initialized at: %s", settings.DATABASE_PATH)

    yield

    logger.info("Shutting down QuantPilot Trading System cleanly...")


app = FastAPI(
    title="QuantPilot: Glass-Box Desk",
    description="Delta Exchange Testnet Algorithmic Trading System with explainable decision journal and multi-layered risk gates.",
    version="0.1.0",
    lifespan=lifespan,
)

# Include Control Plane API router
app.include_router(api_router)

# Mount Dashboard static assets
dashboard_dir = Path(__file__).parent / "dashboard"
if dashboard_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(dashboard_dir)), name="static")

    @app.get("/dashboard")
    async def get_dashboard() -> FileResponse:
        return FileResponse(dashboard_dir / "index.html")

    @app.get("/")
    async def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/dashboard")
