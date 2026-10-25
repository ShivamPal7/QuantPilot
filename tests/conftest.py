"""Pytest shared fixtures."""

from __future__ import annotations

from decimal import Decimal
import pytest

from app.core.contracts import MarketSnapshot
from app.core.clock import SimulatedClock
from app.core.state import EngineStateMachine


@pytest.fixture
def simulated_clock() -> SimulatedClock:
    return SimulatedClock()


@pytest.fixture
def engine_state_machine() -> EngineStateMachine:
    return EngineStateMachine()


@pytest.fixture
def sample_snapshot(simulated_clock: SimulatedClock) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="BTCUSD",
        timestamp=simulated_clock.now_utc(),
        best_bid=Decimal("65000.0"),
        best_ask=Decimal("65005.0"),
        bid_size=Decimal("10.0"),
        ask_size=Decimal("10.0"),
        mark_price=Decimal("65002.5"),
        spot_price=Decimal("65001.0"),
    )
