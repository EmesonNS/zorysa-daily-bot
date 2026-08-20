"""In-memory scheduler reconciliation and automatic daily job orchestration."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.daily_dto import ClosedDaily, OpenedDaily, PreparedReminder
from app.application.dto import ScheduleSummary
from app.domain.enums import NotificationKind, SessionStatus
from app.infrastructure.database.models import (
    DailySession,
    Guild,
    GuildExecutionDay,
    GuildSettings,
    Project,
)
from app.infrastructure.scheduler.planner import (
    RecoveryAction,
    SchedulePlan,
    ScheduleStage,
    plan_schedule,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GuildSchedule:
    """One Discord guild and its persisted automatic daily schedule."""

    discord_guild_id: int
    schedule: ScheduleSummary


class SchedulerJob(Protocol):
    """Minimum APScheduler job metadata used during reconciliation."""

    id: str


class SchedulerAdapter(Protocol):
    """Synchronous APScheduler operations used by the coordinator."""

    def add_job(
        self,
        func: Callable[[int, ScheduleStage], Awaitable[None]],
        trigger: object,
        *,
        args: tuple[int, ScheduleStage],
        id: str,
        replace_existing: bool,
        coalesce: bool,
        max_instances: int,
        misfire_grace_time: int,
    ) -> object: ...

    def get_job(self, job_id: str) -> SchedulerJob | None: ...

    def get_jobs(self) -> list[SchedulerJob]: ...

    def remove_job(self, job_id: str) -> None: ...


class ScheduleSource(Protocol):
    """Persisted schedules and open session dates required for recovery."""

    async def get_guild_schedule(self, guild_id: int) -> ScheduleSummary | None: ...

    async def list_guild_schedules(self) -> tuple[GuildSchedule, ...]: ...

    async def list_open_session_dates(self, guild_id: int) -> tuple[date, ...]: ...


class AutomaticDailyOperations(Protocol):
    """Application operations executed by scheduler stages."""

    async def open_guild(self, guild_id: int, local_date: date) -> tuple[OpenedDaily, ...]: ...

    async def prepare_reminders(
        self,
        guild_id: int,
        local_date: date,
        kind: NotificationKind,
    ) -> tuple[PreparedReminder, ...]: ...

    async def close_guild(self, guild_id: int, local_date: date) -> tuple[ClosedDaily, ...]: ...


class DailyGateway(Protocol):
    """Discord publications required by automatic stages."""

    async def publish_opened(self, opened: OpenedDaily) -> int: ...

    async def publish_reminder(self, reminder: PreparedReminder) -> int: ...

    async def publish_closed(self, closed: ClosedDaily) -> None: ...


class DatabaseScheduleSource:
    """Load scheduler inputs from the application PostgreSQL schema."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_guild_schedule(self, guild_id: int) -> ScheduleSummary | None:
        """Load one guild schedule by its Discord identifier."""

        records = await self._load_schedules(discord_guild_id=guild_id)
        return records[0].schedule if records else None

    async def list_guild_schedules(self) -> tuple[GuildSchedule, ...]:
        """Load every persisted guild schedule in stable order."""

        return await self._load_schedules()

    async def list_open_session_dates(self, guild_id: int) -> tuple[date, ...]:
        """Return distinct dates that still have open sessions for a guild."""

        async with self._sessions() as session:
            values = (
                await session.scalars(
                    select(DailySession.session_date)
                    .join(Project, Project.id == DailySession.project_id)
                    .join(Guild, Guild.id == Project.guild_id)
                    .where(
                        Guild.discord_guild_id == guild_id,
                        DailySession.status == SessionStatus.OPEN,
                    )
                    .distinct()
                    .order_by(DailySession.session_date)
                )
            ).all()
            return tuple(values)

    async def _load_schedules(
        self,
        *,
        discord_guild_id: int | None = None,
    ) -> tuple[GuildSchedule, ...]:
        async with self._sessions() as session:
            statement = (
                select(
                    Guild.id,
                    Guild.discord_guild_id,
                    GuildSettings.timezone,
                    GuildSettings.daily_enabled,
                    GuildSettings.daily_open_time,
                    GuildSettings.first_reminder_time,
                    GuildSettings.last_reminder_time,
                    GuildSettings.daily_close_time,
                    GuildSettings.daily_report_time,
                )
                .join(GuildSettings, GuildSettings.guild_id == Guild.id)
                .order_by(Guild.discord_guild_id)
            )
            if discord_guild_id is not None:
                statement = statement.where(Guild.discord_guild_id == discord_guild_id)
            rows = (await session.execute(statement)).all()
            records: list[GuildSchedule] = []
            for row in rows:
                days = tuple(
                    (
                        await session.scalars(
                            select(GuildExecutionDay.weekday)
                            .where(GuildExecutionDay.guild_id == row.id)
                            .order_by(GuildExecutionDay.weekday)
                        )
                    ).all()
                )
                records.append(
                    GuildSchedule(
                        discord_guild_id=row.discord_guild_id,
                        schedule=ScheduleSummary(
                            timezone=row.timezone,
                            daily_enabled=row.daily_enabled,
                            execution_days=days,
                            opening=row.daily_open_time,
                            first_reminder=row.first_reminder_time,
                            last_reminder=row.last_reminder_time,
                            closing=row.daily_close_time,
                            reporting=row.daily_report_time,
                        ),
                    )
                )
            return tuple(records)


class SchedulerCoordinator:
    """Reconcile guild jobs and execute idempotent automatic daily stages."""

    def __init__(
        self,
        *,
        scheduler: SchedulerAdapter,
        schedule_source: ScheduleSource,
        automatic_service: AutomaticDailyOperations,
        gateway: DailyGateway,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._schedule_source = schedule_source
        self._automatic_service = automatic_service
        self._gateway = gateway
        self._clock = clock or (lambda: datetime.now(UTC))
        self._active_tasks: set[asyncio.Task[object]] = set()

    async def reconcile_guild(self, discord_guild_id: int) -> None:
        """Replace one guild's jobs and immediately apply startup recovery rules."""

        schedule = await self._schedule_source.get_guild_schedule(discord_guild_id)
        if schedule is None:
            self._remove_guild_jobs(discord_guild_id)
            return
        await self._reconcile_record(
            GuildSchedule(discord_guild_id=discord_guild_id, schedule=schedule),
            self._now(),
        )

    async def reconcile_all(self) -> None:
        """Rebuild all managed jobs, remove stale ones and isolate guild failures."""

        records = await self._schedule_source.list_guild_schedules()
        now = self._now()
        plans = {record.discord_guild_id: plan_schedule(record.schedule, now) for record in records}
        desired_ids = {
            self._job_id(guild_id, job.stage)
            for guild_id, plan in plans.items()
            for job in plan.jobs
        }
        for job in tuple(self._scheduler.get_jobs()):
            if self._is_managed_job(job.id) and job.id not in desired_ids:
                self._scheduler.remove_job(job.id)

        for record in records:
            try:
                await self._apply_plan(record, plans[record.discord_guild_id])
                await self._recover(record, plans[record.discord_guild_id], now)
            except Exception:
                logger.exception(
                    "Failed to reconcile automatic daily for guild %s",
                    record.discord_guild_id,
                )

    async def run_stage(self, discord_guild_id: int, stage: ScheduleStage) -> None:
        """Execute one scheduled guild stage without leaking failures to other jobs."""

        current_task = asyncio.current_task()
        if current_task is not None:
            self._active_tasks.add(current_task)
        try:
            schedule = await self._schedule_source.get_guild_schedule(discord_guild_id)
            if schedule is None or not schedule.daily_enabled:
                return
            plan = plan_schedule(schedule, self._now())
            if stage == ScheduleStage.OPEN:
                opened = await self._automatic_service.open_guild(discord_guild_id, plan.local_date)
                await self._publish_opened(discord_guild_id, opened)
            elif stage == ScheduleStage.FIRST_REMINDER:
                reminders = await self._automatic_service.prepare_reminders(
                    discord_guild_id,
                    plan.local_date,
                    NotificationKind.FIRST_REMINDER,
                )
                await self._publish_reminders(discord_guild_id, reminders)
            elif stage == ScheduleStage.LAST_REMINDER:
                reminders = await self._automatic_service.prepare_reminders(
                    discord_guild_id,
                    plan.local_date,
                    NotificationKind.LAST_REMINDER,
                )
                await self._publish_reminders(discord_guild_id, reminders)
            else:
                closed = await self._automatic_service.close_guild(
                    discord_guild_id, plan.local_date
                )
                await self._publish_closed(discord_guild_id, closed)
        except Exception:
            logger.exception(
                "Automatic daily stage %s failed for guild %s",
                stage.value,
                discord_guild_id,
            )
        finally:
            if current_task is not None:
                self._active_tasks.discard(current_task)

    async def wait_for_idle(self, max_wait: float) -> None:
        """Wait briefly for active scheduler jobs without cancelling application tasks."""

        current_task = asyncio.current_task()
        pending = tuple(task for task in self._active_tasks if task is not current_task)
        if pending:
            await asyncio.wait(pending, timeout=max_wait)

    async def _reconcile_record(self, record: GuildSchedule, now: datetime) -> None:
        plan = plan_schedule(record.schedule, now)
        await self._apply_plan(record, plan)
        await self._recover(record, plan, now)

    async def _apply_plan(self, record: GuildSchedule, plan: SchedulePlan) -> None:
        desired_ids = {self._job_id(record.discord_guild_id, job.stage) for job in plan.jobs}
        for existing_job in tuple(self._scheduler.get_jobs()):
            if (
                existing_job.id.startswith(f"guild:{record.discord_guild_id}:")
                and self._is_managed_job(existing_job.id)
                and existing_job.id not in desired_ids
            ):
                self._scheduler.remove_job(existing_job.id)

        for planned_job in plan.jobs:
            self._scheduler.add_job(
                self.run_stage,
                planned_job.trigger,
                args=(record.discord_guild_id, planned_job.stage),
                id=self._job_id(record.discord_guild_id, planned_job.stage),
                replace_existing=True,
                coalesce=True,
                max_instances=1,
                misfire_grace_time=60,
            )

    async def _recover(
        self,
        record: GuildSchedule,
        plan: SchedulePlan,
        now: datetime,
    ) -> None:
        timezone = ZoneInfo(record.schedule.timezone)
        local_now = now.astimezone(timezone)
        open_dates = await self._schedule_source.list_open_session_dates(record.discord_guild_id)
        for session_date in open_dates:
            deadline = datetime.combine(
                session_date,
                record.schedule.closing,
                tzinfo=timezone,
            )
            if deadline <= local_now:
                closed = await self._automatic_service.close_guild(
                    record.discord_guild_id,
                    session_date,
                )
                await self._publish_closed(record.discord_guild_id, closed)

        if RecoveryAction.ENSURE_OPEN in plan.recovery_actions:
            opened = await self._automatic_service.open_guild(
                record.discord_guild_id,
                plan.local_date,
            )
            await self._publish_opened(record.discord_guild_id, opened)

    async def _publish_opened(self, guild_id: int, opened: tuple[OpenedDaily, ...]) -> None:
        for item in opened:
            try:
                await self._gateway.publish_opened(item)
            except Exception:
                logger.exception("Failed to publish opened daily for guild %s", guild_id)

    async def _publish_reminders(
        self, guild_id: int, reminders: tuple[PreparedReminder, ...]
    ) -> None:
        for item in reminders:
            try:
                await self._gateway.publish_reminder(item)
            except Exception:
                logger.exception("Failed to publish daily reminder for guild %s", guild_id)

    async def _publish_closed(self, guild_id: int, closed: tuple[ClosedDaily, ...]) -> None:
        for item in closed:
            try:
                await self._gateway.publish_closed(item)
            except Exception:
                logger.exception("Failed to publish closed daily for guild %s", guild_id)

    def _remove_guild_jobs(self, guild_id: int) -> None:
        for stage in ScheduleStage:
            job_id = self._job_id(guild_id, stage)
            if self._scheduler.get_job(job_id) is not None:
                self._scheduler.remove_job(job_id)

    @staticmethod
    def _job_id(guild_id: int, stage: ScheduleStage) -> str:
        return f"guild:{guild_id}:{stage.value}"

    @staticmethod
    def _is_managed_job(job_id: str) -> bool:
        parts = job_id.split(":")
        return (
            len(parts) == 3
            and parts[0] == "guild"
            and parts[1].isdigit()
            and parts[2] in ScheduleStage
        )

    def _now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
