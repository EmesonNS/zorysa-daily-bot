from unittest.mock import AsyncMock

from app.infrastructure.scheduler.lifecycle import SchedulerLifecycle


class FakeScheduler:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def start(self, *, paused: bool = False) -> None:
        self.calls.append(("start", paused))

    def pause(self) -> None:
        self.calls.append(("pause", None))

    def resume(self) -> None:
        self.calls.append(("resume", None))

    def shutdown(self, *, wait: bool = True) -> None:
        self.calls.append(("shutdown", wait))


async def test_lifecycle_starts_once_paused_and_guards_duplicate_ready() -> None:
    scheduler = FakeScheduler()
    coordinator = AsyncMock()
    lifecycle = SchedulerLifecycle(scheduler, coordinator)

    await lifecycle.setup()
    await lifecycle.setup()
    await lifecycle.ready()
    await lifecycle.ready()

    assert scheduler.calls == [("start", True), ("resume", None)]
    coordinator.reconcile_all.assert_awaited_once_with()


async def test_disconnect_pauses_and_reconnect_runs_recovery_again() -> None:
    scheduler = FakeScheduler()
    coordinator = AsyncMock()
    lifecycle = SchedulerLifecycle(scheduler, coordinator)

    await lifecycle.ready()
    await lifecycle.disconnect()
    await lifecycle.disconnect()
    await lifecycle.ready()

    assert scheduler.calls == [
        ("start", True),
        ("resume", None),
        ("pause", None),
        ("resume", None),
    ]
    assert coordinator.reconcile_all.await_count == 2


async def test_shutdown_drains_jobs_before_stopping_scheduler_idempotently() -> None:
    events: list[str] = []
    scheduler = FakeScheduler()
    coordinator = AsyncMock()
    coordinator.wait_for_idle.side_effect = lambda timeout: events.append(f"drain:{timeout}")
    lifecycle = SchedulerLifecycle(scheduler, coordinator, drain_timeout=3.0)

    await lifecycle.ready()
    scheduler.calls.clear()
    await lifecycle.shutdown()
    await lifecycle.shutdown()

    assert scheduler.calls == [
        ("pause", None),
        ("shutdown", False),
    ]
    assert events == ["drain:3.0"]
