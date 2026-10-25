"""Background task supervisor for QuantPilot application lifespan.

Per Section 7.3 of agent.md, manages background loops, monitors crashes,
restarts with backoff, and signals degraded status when thresholds are breached.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger("supervisor")


@dataclass
class TaskStatus:
    """Supervised task health metadata."""
    name: str
    restarts: int = 0
    last_crash: datetime | None = None
    is_healthy: bool = True
    active_task: asyncio.Task[Any] | None = None


class Supervisor:
    """Oversees background coroutine loops."""

    def __init__(self, max_consecutive_restarts: int = 5, base_backoff_seconds: float = 1.0) -> None:
        self.max_restarts = max_consecutive_restarts
        self.base_backoff = base_backoff_seconds
        self._tasks: dict[str, TaskStatus] = {}
        self._factories: dict[str, Callable[[], Coroutine[Any, Any, None]]] = {}
        self._running = False

    def register(self, name: str, coro_factory: Callable[[], Coroutine[Any, Any, None]]) -> None:
        """Register a background coroutine factory."""
        self._factories[name] = coro_factory
        self._tasks[name] = TaskStatus(name=name)

    async def start(self) -> None:
        """Launch all registered tasks under supervision."""
        self._running = True
        for name in self._factories:
            self._start_task(name)
        logger.info("Supervisor launched %d background tasks.", len(self._tasks))

    def _start_task(self, name: str) -> None:
        if not self._running:
            return
        coro = self._factories[name]()
        task = asyncio.create_task(self._wrap_task(name, coro), name=f"supervised-{name}")
        self._tasks[name].active_task = task

    async def _wrap_task(self, name: str, coro: Coroutine[Any, Any, None]) -> None:
        status = self._tasks[name]
        try:
            await coro
            logger.info("Task %s completed cleanly.", name)
            status.is_healthy = True
        except asyncio.CancelledError:
            logger.info("Task %s cancelled.", name)
            status.is_healthy = False
        except Exception as exc:
            status.restarts += 1
            status.last_crash = datetime.now(timezone.utc)
            status.is_healthy = False
            logger.error("Task %s crashed with error: %s (Restart #%d)", name, exc, status.restarts, exc_info=True)
            if self._running and status.restarts <= self.max_restarts:
                backoff = min(30.0, self.base_backoff * (2 ** (status.restarts - 1)))
                logger.warning("Restarting task %s after %.1fs backoff...", name, backoff)
                await asyncio.sleep(backoff)
                self._start_task(name)
            else:
                logger.critical("Task %s exceeded maximum restart limit. Marked unrecoverable.", name)

    async def stop(self) -> None:
        """Cancel and await all running background tasks."""
        self._running = False
        for status in self._tasks.values():
            if status.active_task and not status.active_task.done():
                status.active_task.cancel()
        # Wait for all to finish
        tasks = [s.active_task for s in self._tasks.values() if s.active_task]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Supervisor stopped all tasks.")

    @property
    def is_healthy(self) -> bool:
        """Return True if all supervised tasks are running and healthy."""
        return all(s.is_healthy for s in self._tasks.values())
