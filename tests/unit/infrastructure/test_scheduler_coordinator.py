from dataclasses import replace
from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.application.dto import ScheduleSummary
from app.domain.enums import NotificationKind
from app.infrastructure.scheduler.coordinator import (
    GuildSchedule,
    SchedulerCoordinator,
)
from app.infrastructure.scheduler.planner import ScheduleStage


def _schedule(*, enabled: bool = True) -> ScheduleSummary:
    return ScheduleSummary(
        timezone="America/Belem",
        daily_enabled=enabled,
        execution_days=(0, 1, 2, 3, 4),
        opening=time(9),
        first_reminder=time(10, 30),
        last_reminder=time(11, 30),
        closing=time(12),
        reporting=time(12, 10),
    )


class FakeJob:
    def __init__(self, job_id: str) -> None:
        self.id = job_id


class FakeScheduler:
    def __init__(self, *job_ids: str) -> None:
        self.jobs = {job_id: FakeJob(job_id) for job_id in job_ids}
        self.added: list[dict[str, object]] = []
        self.removed: list[str] = []

    def add_job(self, func: object, trigger: object, **options: object) -> FakeJob:
        record = {"func": func, "trigger": trigger, **options}
        self.added.append(record)
        job_id = str(options["id"])
        job = FakeJob(job_id)
        self.jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> FakeJob | None:
        return self.jobs.get(job_id)

    def get_jobs(self) -> list[FakeJob]:
        return list(self.jobs.values())

    def remove_job(self, job_id: str) -> None:
        self.removed.append(job_id)
        self.jobs.pop(job_id)


class FakeScheduleSource:
    def __init__(self, schedules: dict[int, ScheduleSummary]) -> None:
        self.schedules = schedules
        self.open_dates: dict[int, tuple[date, ...] | Exception] = {}

    async def get_guild_schedule(self, guild_id: int) -> ScheduleSummary | None:
        return self.schedules.get(guild_id)

    async def list_guild_schedules(self) -> tuple[GuildSchedule, ...]:
        return tuple(
            GuildSchedule(discord_guild_id=guild_id, schedule=schedule)
            for guild_id, schedule in self.schedules.items()
        )

    async def list_open_session_dates(self, guild_id: int) -> tuple[date, ...]:
        result = self.open_dates.get(guild_id, ())
        if isinstance(result, Exception):
            raise result
        return result


def _coordinator(
    *,
    now: datetime,
    source: FakeScheduleSource | None = None,
    scheduler: FakeScheduler | None = None,
) -> tuple[SchedulerCoordinator, FakeScheduler, FakeScheduleSource, AsyncMock, AsyncMock]:
    actual_scheduler = scheduler or FakeScheduler()
    actual_source = source or FakeScheduleSource({81: _schedule()})
    service = AsyncMock()
    service.open_guild.return_value = ()
    service.prepare_reminders.return_value = ()
    service.close_guild.return_value = ()
    gateway = AsyncMock()
    coordinator = SchedulerCoordinator(
        scheduler=actual_scheduler,
        schedule_source=actual_source,
        automatic_service=service,
        gateway=gateway,
        clock=lambda: now,
    )
    return coordinator, actual_scheduler, actual_source, service, gateway


async def test_reconcile_guild_adds_or_replaces_four_stable_jobs() -> None:
    coordinator, scheduler, _, _, _ = _coordinator(now=datetime(2026, 8, 19, 11, 0, tzinfo=UTC))

    await coordinator.reconcile_guild(81)

    assert [call["id"] for call in scheduler.added] == [
        "guild:81:open",
        "guild:81:reminder1",
        "guild:81:reminder2",
        "guild:81:close",
    ]
    for call, stage in zip(scheduler.added, ScheduleStage, strict=True):
        assert call["func"] == coordinator.run_stage
        assert call["args"] == (81, stage)
        assert call["replace_existing"] is True
        assert call["coalesce"] is True
        assert call["max_instances"] == 1
        assert call["misfire_grace_time"] == 60

    await coordinator.reconcile_guild(81)

    assert len(scheduler.added) == 8
    assert len(scheduler.jobs) == 4


async def test_reconcile_removes_disabled_and_obsolete_scheduler_jobs() -> None:
    scheduler = FakeScheduler(
        "guild:81:open",
        "guild:81:reminder1",
        "guild:81:reminder2",
        "guild:81:close",
        "guild:999:open",
        "unrelated:job",
    )
    source = FakeScheduleSource({81: _schedule(enabled=False)})
    coordinator, _, _, _, _ = _coordinator(
        now=datetime(2026, 8, 19, 11, 0, tzinfo=UTC),
        source=source,
        scheduler=scheduler,
    )

    await coordinator.reconcile_all()

    assert set(scheduler.removed) == {
        "guild:81:open",
        "guild:81:reminder1",
        "guild:81:reminder2",
        "guild:81:close",
        "guild:999:open",
    }
    assert set(scheduler.jobs) == {"unrelated:job"}


async def test_reconcile_in_open_window_runs_recovery_without_replaying_reminders() -> None:
    coordinator, _, _, service, gateway = _coordinator(
        now=datetime(2026, 8, 19, 12, 30, tzinfo=UTC)
    )
    opened = (SimpleNamespace(name="one"), SimpleNamespace(name="two"))
    service.open_guild.return_value = opened
    gateway.publish_opened.side_effect = [RuntimeError("canal removido"), None]

    await coordinator.reconcile_guild(81)

    service.open_guild.assert_awaited_once_with(81, date(2026, 8, 19))
    assert gateway.publish_opened.await_count == 2
    service.prepare_reminders.assert_not_awaited()


async def test_recovery_always_closes_historical_sessions_past_local_deadline() -> None:
    source = FakeScheduleSource({81: _schedule()})
    source.open_dates[81] = (date(2026, 8, 18), date(2026, 8, 19))
    coordinator, _, _, service, gateway = _coordinator(
        now=datetime(2026, 8, 19, 11, 0, tzinfo=UTC),
        source=source,
    )
    closed = (SimpleNamespace(name="one"), SimpleNamespace(name="two"))
    service.close_guild.return_value = closed
    gateway.publish_closed.side_effect = [RuntimeError("mensagem ausente"), None]

    await coordinator.reconcile_guild(81)

    service.close_guild.assert_awaited_once_with(81, date(2026, 8, 18))
    assert gateway.publish_closed.await_count == 2
    service.open_guild.assert_not_awaited()
    service.prepare_reminders.assert_not_awaited()


async def test_run_stage_maps_each_job_to_application_service_and_gateway() -> None:
    coordinator, _, _, service, gateway = _coordinator(
        now=datetime(2026, 8, 19, 12, 30, tzinfo=UTC)
    )
    opened = SimpleNamespace(name="opened")
    first = SimpleNamespace(name="first")
    last = SimpleNamespace(name="last")
    closed = SimpleNamespace(name="closed")
    service.open_guild.return_value = (opened,)
    service.prepare_reminders.side_effect = [(first,), (last,)]
    service.close_guild.return_value = (closed,)

    await coordinator.run_stage(81, ScheduleStage.OPEN)
    await coordinator.run_stage(81, ScheduleStage.FIRST_REMINDER)
    await coordinator.run_stage(81, ScheduleStage.LAST_REMINDER)
    await coordinator.run_stage(81, ScheduleStage.CLOSE)

    service.open_guild.assert_awaited_once_with(81, date(2026, 8, 19))
    assert service.prepare_reminders.await_args_list[0].args == (
        81,
        date(2026, 8, 19),
        NotificationKind.FIRST_REMINDER,
    )
    assert service.prepare_reminders.await_args_list[1].args == (
        81,
        date(2026, 8, 19),
        NotificationKind.LAST_REMINDER,
    )
    service.close_guild.assert_awaited_once_with(81, date(2026, 8, 19))
    gateway.publish_opened.assert_awaited_once_with(opened)
    gateway.publish_reminder.assert_any_await(first)
    gateway.publish_reminder.assert_any_await(last)
    gateway.publish_closed.assert_awaited_once_with(closed)


async def test_reconcile_all_isolates_one_guild_recovery_failure() -> None:
    source = FakeScheduleSource({81: _schedule(), 82: replace(_schedule(), timezone="UTC")})
    source.open_dates[81] = RuntimeError("database unavailable")
    coordinator, scheduler, _, service, _ = _coordinator(
        now=datetime(2026, 8, 19, 9, 30, tzinfo=UTC),
        source=source,
    )

    await coordinator.reconcile_all()

    assert len(scheduler.added) == 8
    service.open_guild.assert_awaited_once_with(82, date(2026, 8, 19))


async def test_run_stage_contains_service_failure_inside_its_guild_job() -> None:
    coordinator, _, _, service, gateway = _coordinator(
        now=datetime(2026, 8, 19, 12, 30, tzinfo=UTC)
    )
    service.open_guild.side_effect = RuntimeError("project failure")

    await coordinator.run_stage(81, ScheduleStage.OPEN)

    gateway.publish_opened.assert_not_awaited()
