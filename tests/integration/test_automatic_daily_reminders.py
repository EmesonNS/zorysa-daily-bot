import asyncio
import os
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import create_async_engine

from app.application.automatic_daily import AutomaticDailyService
from app.application.guild_admin import GuildAdminService
from app.domain.enums import AssignmentStatus, NotificationKind, ProjectStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    DailyAssignment,
    DailyNotification,
    Guild,
    Project,
    ProjectMembership,
)


@pytest.fixture(scope="module", autouse=True)
def _upgrade_database() -> None:
    command.upgrade(Config("alembic.ini"), "head")


async def test_prepare_reminders_recalculates_pending_and_confirms_delivery() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    database = Database.from_engine(engine)
    suffix = uuid4().int % 1_000_000_000
    discord_guild_id = 8_300_000_000_000_000_000 + suffix
    local_date = date(2026, 8, 19)
    now = datetime(2026, 8, 19, 13, 30, tzinfo=UTC)

    try:
        await GuildAdminService(database.sessions).ensure_guild(
            discord_guild_id=discord_guild_id,
            guild_name="Guild de lembretes",
        )
        async with database.sessions() as session, session.begin():
            guild = await session.scalar(
                select(Guild).where(Guild.discord_guild_id == discord_guild_id)
            )
            assert guild is not None
            projects = [
                Project(
                    guild_id=guild.id,
                    name="Alpha",
                    slug="alpha-reminders",
                    discord_channel_id=6_700_000_000_000_000_000 + suffix,
                    status=ProjectStatus.ACTIVE,
                    daily_enabled=True,
                ),
                Project(
                    guild_id=guild.id,
                    name="Respondido",
                    slug="respondido-reminders",
                    discord_channel_id=6_800_000_000_000_000_000 + suffix,
                    status=ProjectStatus.ACTIVE,
                    daily_enabled=True,
                ),
            ]
            session.add_all(projects)
            await session.flush()
            user_ids = (
                5_700_000_000_000_000_000 + suffix,
                5_800_000_000_000_000_000 + suffix,
                5_900_000_000_000_000_000 + suffix,
            )
            session.add_all(
                [
                    ProjectMembership(
                        project_id=projects[0].id,
                        discord_user_id=user_ids[0],
                        display_name="Ada",
                        joined_at=now,
                        left_at=None,
                    ),
                    ProjectMembership(
                        project_id=projects[0].id,
                        discord_user_id=user_ids[1],
                        display_name="Grace",
                        joined_at=now,
                        left_at=None,
                    ),
                    ProjectMembership(
                        project_id=projects[1].id,
                        discord_user_id=user_ids[2],
                        display_name="Linus",
                        joined_at=now,
                        left_at=None,
                    ),
                ]
            )

        service = AutomaticDailyService(database.sessions, clock=lambda: now)
        opened = await service.open_guild(discord_guild_id, local_date)
        alpha_session_id = next(
            item.panel.session_id for item in opened if item.panel.project_name == "Alpha"
        )
        answered_session_id = next(
            item.panel.session_id for item in opened if item.panel.project_name == "Respondido"
        )
        async with database.sessions() as session, session.begin():
            already_answered = await session.scalar(
                select(DailyAssignment).where(DailyAssignment.session_id == answered_session_id)
            )
            assert already_answered is not None
            already_answered.status = AssignmentStatus.ANSWERED
            already_answered.answered_at = now

        first = await service.prepare_reminders(
            discord_guild_id,
            local_date,
            NotificationKind.FIRST_REMINDER,
        )
        repeated = await service.prepare_reminders(
            discord_guild_id,
            local_date,
            NotificationKind.FIRST_REMINDER,
        )

        assert len(first) == 1
        assert first[0].session_id == alpha_session_id
        assert first[0].kind == NotificationKind.FIRST_REMINDER
        assert tuple(recipient.user_id for recipient in first[0].recipients) == user_ids[:2]
        assert repeated == ()
        message_id = 4_700_000_000_000_000_000 + suffix
        await service.attach_notification(first[0].notification_id, message_id)
        await service.attach_notification(first[0].notification_id, message_id)

        async with database.sessions() as session, session.begin():
            ada = await session.scalar(
                select(DailyAssignment).where(
                    DailyAssignment.session_id == alpha_session_id,
                    DailyAssignment.discord_user_id == user_ids[0],
                )
            )
            assert ada is not None
            ada.status = AssignmentStatus.ANSWERED
            ada.answered_at = now

        last = await service.prepare_reminders(
            discord_guild_id,
            local_date,
            NotificationKind.LAST_REMINDER,
        )

        assert len(last) == 1
        assert tuple(recipient.user_id for recipient in last[0].recipients) == (user_ids[1],)
        async with database.sessions() as session:
            notifications = (
                await session.scalars(select(DailyNotification).order_by(DailyNotification.id))
            ).all()
            own_notifications = [
                item
                for item in notifications
                if item.session_id in (alpha_session_id, answered_session_id)
            ]
            assert len(own_notifications) == 2
            assert all(item.session_id == alpha_session_id for item in own_notifications)
            assert own_notifications[0].message_id == message_id
            assert own_notifications[0].sent_at == now
    finally:
        async with database.sessions() as session, session.begin():
            await session.execute(delete(Guild).where(Guild.discord_guild_id == discord_guild_id))
        await engine.dispose()


async def test_prepare_reminders_reserves_once_during_concurrent_execution() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    database = Database.from_engine(engine)
    suffix = uuid4().int % 1_000_000_000
    discord_guild_id = 8_400_000_000_000_000_000 + suffix
    local_date = date(2026, 8, 19)
    now = datetime(2026, 8, 19, 13, 30, tzinfo=UTC)

    try:
        await GuildAdminService(database.sessions).ensure_guild(
            discord_guild_id=discord_guild_id,
            guild_name="Guild de lembrete concorrente",
        )
        async with database.sessions() as session, session.begin():
            guild = await session.scalar(
                select(Guild).where(Guild.discord_guild_id == discord_guild_id)
            )
            assert guild is not None
            project = Project(
                guild_id=guild.id,
                name="Concorrente",
                slug="concorrente-reminder",
                discord_channel_id=6_900_000_000_000_000_000 + suffix,
                status=ProjectStatus.ACTIVE,
                daily_enabled=True,
            )
            session.add(project)
            await session.flush()
            session.add(
                ProjectMembership(
                    project_id=project.id,
                    discord_user_id=5_950_000_000_000_000_000 + suffix,
                    display_name="Margaret",
                    joined_at=now,
                    left_at=None,
                )
            )

        service = AutomaticDailyService(database.sessions, clock=lambda: now)
        opened = await service.open_guild(discord_guild_id, local_date)
        session_id = opened[0].panel.session_id
        first, second = await asyncio.gather(
            service.prepare_reminders(
                discord_guild_id,
                local_date,
                NotificationKind.FIRST_REMINDER,
            ),
            service.prepare_reminders(
                discord_guild_id,
                local_date,
                NotificationKind.FIRST_REMINDER,
            ),
        )

        assert sorted((len(first), len(second))) == [0, 1]
        async with database.sessions() as session:
            count = await session.scalar(
                select(func.count(DailyNotification.id)).where(
                    DailyNotification.session_id == session_id,
                    DailyNotification.kind == NotificationKind.FIRST_REMINDER,
                )
            )
            assert count == 1
    finally:
        async with database.sessions() as session, session.begin():
            await session.execute(delete(Guild).where(Guild.discord_guild_id == discord_guild_id))
        await engine.dispose()
