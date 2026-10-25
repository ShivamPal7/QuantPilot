"""Engine state machine and transitions.

Defined in Section 7.5 of agent.md:
Initialising -> Warming up -> Running -> Paused -> Halted (kill switch) -> Stopped.
"""

from __future__ import annotations

from enum import Enum


class EngineState(str, Enum):
    """Lifecycle states of the QuantPilot trading engine."""

    INITIALISING = "INITIALISING"
    WARMING_UP = "WARMING_UP"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    HALTED = "HALTED"  # Reached by kill switch; requires manual reset
    STOPPED = "STOPPED"


class StateTransitionError(Exception):
    """Raised when an illegal engine state transition is attempted."""
    pass


class EngineStateMachine:
    """Manages and validates transitions between engine states."""

    ALLOWED_TRANSITIONS: dict[EngineState, set[EngineState]] = {
        EngineState.INITIALISING: {EngineState.WARMING_UP, EngineState.HALTED, EngineState.STOPPED},
        EngineState.WARMING_UP: {EngineState.RUNNING, EngineState.PAUSED, EngineState.HALTED, EngineState.STOPPED},
        EngineState.RUNNING: {EngineState.PAUSED, EngineState.HALTED, EngineState.STOPPED},
        EngineState.PAUSED: {EngineState.RUNNING, EngineState.HALTED, EngineState.STOPPED},
        EngineState.HALTED: {EngineState.PAUSED, EngineState.STOPPED},  # Reset from halt goes to PAUSED
        EngineState.STOPPED: set(),  # Terminal state
    }

    def __init__(self, initial_state: EngineState = EngineState.INITIALISING) -> None:
        self._state = initial_state
        self._transition_history: list[tuple[EngineState, EngineState, str]] = []

    @property
    def current_state(self) -> EngineState:
        return self._state

    def can_transition_to(self, target: EngineState) -> bool:
        """Check if transition to target state is legally permissible."""
        # Any state can transition to HALTED in an emergency
        if target == EngineState.HALTED:
            return True
        return target in self.ALLOWED_TRANSITIONS.get(self._state, set())

    def transition(self, target: EngineState, reason: str = "") -> EngineState:
        """Execute state transition if permissible, otherwise raise StateTransitionError."""
        if not self.can_transition_to(target):
            raise StateTransitionError(
                f"Illegal state transition from {self._state.value} to {target.value}. Reason: {reason}"
            )
        previous = self._state
        self._state = target
        self._transition_history.append((previous, target, reason))
        return self._state

    @property
    def is_trading_allowed(self) -> bool:
        """Only RUNNING state allows new real trading intents to execute."""
        return self._state == EngineState.RUNNING

    @property
    def is_halted(self) -> bool:
        return self._state == EngineState.HALTED
