import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine

from app.application.automatic_daily import AutomaticDailyService
from app.application.daily import DailyService
from app.application.daily_dto import ClosedDaily, OpenedDaily, PreparedReminder
from app.application.guild_admin import GuildAdminService
from app.domain.enums import AssignmentStatus, NotificationKind, ProjectStatus, SessionStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    DailyAssignment,
    DailyNotification,
    DailySession,
    Guild,
    Project,
    ProjectMembership,
)
from app.infrastructure.scheduler.coordinator import (
    DatabaseScheduleSource,
    SchedulerCoordinator,
)
from app.infrastructure.scheduler.planner import ScheduleStage


@pytest.fixture(scope="module", autouse=True)
def _upgrade_database() -> None:
    command.upgrade(Config("alembic.ini"), "head")


class FakeJob:
    def __init__(self, job_id: str) -> None:
        self.id = job_id


class FakeScheduler:
    def __init__(self) -> None:
        self.jobs: dict[str, FakeJob] = {}

    def add_job(self, func: object, trigger: object, **options: object) -> FakeJob:
        del func, trigger
        job = FakeJob(str(options["id"]))
        self.jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> FakeJob | None:
        return self.jobs.get(job_id)

    def get_jobs(self) -> list[FakeJob]:
        return list(self.jobs.values())

    def remove_job(self, job_id: str) -> None:
        self.jobs.pop(job_id, None)


class PersistingGateway:
    def __init__(self, daily: DailyService, automatic: AutomaticDailyService) -> None:
        self._daily = daily
        self._automatic = automatic
        self.opened: list[OpenedDaily] = []
        self.reminders: list[PreparedReminder] = []
        self.closed: list[ClosedDaily] = []

    async def publish_opened(self, opened: OpenedDaily) -> int:
        self.opened.append(opened)
        message_id = 4_900_000_000_000_000_000 + opened.panel.session_id
        await self._daily.attach_message(
            session_id=opened.panel.session_id,
            message_id=message_id,
        )
        return message_id

    async def publish_reminder(self, reminder: PreparedReminder) -> int:
        self.reminders.append(reminder)
        message_id = 4_910_000_000_000_000_000 + reminder.notification_id
        await self._automatic.attach_notification(reminder.notification_id, message_id)
        return message_id

    async def publish_closed(self, closed: ClosedDaily) -> None:
        self.closed.append(closed)


async def test_scheduler_cycle_opens_reminds_and_closes_with_postgresql() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    database = Database.from_engine(engine)
    suffix = uuid4().int % 1_000_000_000
    discord_guild_id = 8_600_000_000_000_000_000 + suffix
    now = datetime(2026, 8, 19, 13, 0, tzinfo=UTC)

    try:
        await GuildAdminService(database.sessions).ensure_guild(
            discord_guild_id=discord_guild_id,
            guild_name="Guild ciclo scheduler",
        )
        async with database.sessions() as session, session.begin():
            guild = await session.scalar(
                select(Guild).where(Guild.discord_guild_id == discord_guild_id)
            )
            assert guild is not None
            project = Project(
                guild_id=guild.id,
                name="Ciclo",
                slug="ciclo-scheduler",
                discord_channel_id=6_990_000_000_000_000_000 + suffix,
                status=ProjectStatus.ACTIVE,
                daily_enabled=True,
            )
            session.add(project)
            await session.flush()
            session.add(
                ProjectMembership(
                    project_id=project.id,
                    discord_user_id=5_990_000_000_000_000_000 + suffix,
                    display_name="Ada",
                    joined_at=now,
                    left_at=None,
                )
            )

        daily = DailyService(database.sessions, clock=lambda: now)
        automatic = AutomaticDailyService(database.sessions, clock=lambda: now)
        scheduler = FakeScheduler()
        gateway = PersistingGateway(daily, automatic)
        coordinator = SchedulerCoordinator(
            scheduler=scheduler,
            schedule_source=DatabaseScheduleSource(database.sessions),
            automatic_service=automatic,
            gateway=gateway,
            clock=lambda: now,
        )

        await coordinator.reconcile_guild(discord_guild_id)
        await coordinator.run_stage(discord_guild_id, ScheduleStage.FIRST_REMINDER)
        await coordinator.run_stage(discord_guild_id, ScheduleStage.CLOSE)

        assert set(scheduler.jobs) == {
            f"guild:{discord_guild_id}:open",
            f"guild:{discord_guild_id}:reminder1",
            f"guild:{discord_guild_id}:reminder2",
            f"guild:{discord_guild_id}:close",
            f"guild:{discord_guild_id}:daily-report",
            f"guild:{discord_guild_id}:weekly-report",
            f"guild:{discord_guild_id}:monthly-report",
        }
        assert len(gateway.opened) == len(gateway.reminders) == len(gateway.closed) == 1
        assert gateway.reminders[0].kind == NotificationKind.FIRST_REMINDER

        async with database.sessions() as session:
            daily_session = await session.scalar(
                select(DailySession)
                .join(Project, Project.id == DailySession.project_id)
                .where(Project.guild_id == guild.id)
            )
            assert daily_session is not None
            assignment = await session.scalar(
                select(DailyAssignment).where(DailyAssignment.session_id == daily_session.id)
            )
            notification = await session.scalar(
                select(DailyNotification).where(DailyNotification.session_id == daily_session.id)
            )
            assert daily_session.status == SessionStatus.CLOSED
            assert daily_session.message_id is not None
            assert assignment is not None
            assert assignment.status == AssignmentStatus.NOT_ANSWERED
            assert notification is not None
            assert notification.message_id is not None
    finally:
        async with database.sessions() as session, session.begin():
            await session.execute(delete(Guild).where(Guild.discord_guild_id == discord_guild_id))
        await engine.dispose()
