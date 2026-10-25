"""Pytest shared fixtures with conditional pytest guard.

Allows clean test execution under both pytest and Python standard library unittest.
"""

from __future__ import annotations

from decimal import Decimal

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

from app.core.contracts import MarketSnapshot
from app.core.clock import SimulatedClock
from app.core.state import EngineStateMachine


if HAS_PYTEST:
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
