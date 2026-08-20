"""Safe APScheduler lifecycle coordinated with Discord connectivity."""

import asyncio
from typing import Protocol


class LifecycleScheduler(Protocol):
    def start(self, *, paused: bool = False) -> None: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def shutdown(self, *, wait: bool = True) -> None: ...


class LifecycleCoordinator(Protocol):
    async def reconcile_all(self) -> None: ...

    async def wait_for_idle(self, max_wait: float) -> None: ...


class SchedulerLifecycle:
    """Start once, recover on readiness, and stop before Discord shutdown."""

    def __init__(
        self,
        scheduler: LifecycleScheduler,
        coordinator: LifecycleCoordinator,
        *,
        drain_timeout: float = 5.0,
    ) -> None:
        self._scheduler = scheduler
        self._coordinator = coordinator
        self._drain_timeout = drain_timeout
        self._lock = asyncio.Lock()
        self._started = False
        self._ready = False

    async def setup(self) -> None:
        async with self._lock:
            if self._started:
                return
            self._scheduler.start(paused=True)
            self._started = True

    async def ready(self) -> None:
        await self.setup()
        async with self._lock:
            if self._ready:
                return
            await self._coordinator.reconcile_all()
            self._scheduler.resume()
            self._ready = True

    async def disconnect(self) -> None:
        async with self._lock:
            if not self._started or not self._ready:
                return
            self._scheduler.pause()
            self._ready = False

    async def shutdown(self) -> None:
        async with self._lock:
            if not self._started:
                return
            if self._ready:
                self._scheduler.pause()
                self._ready = False
            await self._coordinator.wait_for_idle(self._drain_timeout)
            self._scheduler.shutdown(wait=False)
            await asyncio.sleep(0)
            self._started = False
