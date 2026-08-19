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
from app.domain.enums import ProjectStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    DailyAssignment,
    DailyQuestionSnapshot,
    DailySession,
    Guild,
    Project,
    ProjectMembership,
)


@pytest.fixture(scope="module", autouse=True)
def _upgrade_database() -> None:
    command.upgrade(Config("alembic.ini"), "head")


async def test_open_guild_opens_only_eligible_projects_and_is_idempotent() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    database = Database.from_engine(engine)
    suffix = uuid4().int % 1_000_000_000
    discord_guild_id = 8_100_000_000_000_000_000 + suffix
    local_date = date(2026, 8, 19)
    now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)

    try:
        await GuildAdminService(database.sessions).ensure_guild(
            discord_guild_id=discord_guild_id,
            guild_name="Guild automática",
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
                    slug="alpha",
                    discord_channel_id=6_100_000_000_000_000_000 + suffix,
                    status=ProjectStatus.ACTIVE,
                    daily_enabled=True,
                ),
                Project(
                    guild_id=guild.id,
                    name="Beta",
                    slug="beta",
                    discord_channel_id=6_200_000_000_000_000_000 + suffix,
                    status=ProjectStatus.ACTIVE,
                    daily_enabled=True,
                ),
                Project(
                    guild_id=guild.id,
                    name="Sem membros",
                    slug="sem-membros",
                    discord_channel_id=6_300_000_000_000_000_000 + suffix,
                    status=ProjectStatus.ACTIVE,
                    daily_enabled=True,
                ),
                Project(
                    guild_id=guild.id,
                    name="Arquivado",
                    slug="arquivado",
                    discord_channel_id=6_400_000_000_000_000_000 + suffix,
                    status=ProjectStatus.ARCHIVED,
                    daily_enabled=True,
                ),
                Project(
                    guild_id=guild.id,
                    name="Desabilitado",
                    slug="desabilitado",
                    discord_channel_id=6_500_000_000_000_000_000 + suffix,
                    status=ProjectStatus.ACTIVE,
                    daily_enabled=False,
                ),
            ]
            session.add_all(projects)
            await session.flush()
            session.add_all(
                [
                    ProjectMembership(
                        project_id=projects[0].id,
                        discord_user_id=5_100_000_000_000_000_000 + suffix,
                        display_name="Ada",
                        joined_at=now,
                        left_at=None,
                    ),
                    ProjectMembership(
                        project_id=projects[1].id,
                        discord_user_id=5_200_000_000_000_000_000 + suffix,
                        display_name="Grace",
                        joined_at=now,
                        left_at=None,
                    ),
                ]
            )

        service = AutomaticDailyService(database.sessions, clock=lambda: now)
        opened = await service.open_guild(discord_guild_id, local_date)
        reopened = await service.open_guild(discord_guild_id, local_date)

        assert tuple(item.panel.project_name for item in opened) == ("Alpha", "Beta")
        assert tuple(item.panel.session_id for item in reopened) == tuple(
            item.panel.session_id for item in opened
        )
        async with database.sessions() as session:
            session_ids = tuple(item.panel.session_id for item in opened)
            session_count = await session.scalar(
                select(func.count(DailySession.id)).where(
                    DailySession.session_date == local_date,
                    DailySession.project_id.in_(
                        select(Project.id).where(Project.guild_id == guild.id)
                    ),
                )
            )
            assignment_count = await session.scalar(
                select(func.count(DailyAssignment.id)).where(
                    DailyAssignment.session_id.in_(session_ids)
                )
            )
            snapshot_count = await session.scalar(
                select(func.count(DailyQuestionSnapshot.id)).where(
                    DailyQuestionSnapshot.session_id.in_(session_ids)
                )
            )
            assert session_count == 2
            assert assignment_count == 2
            assert snapshot_count == 8
    finally:
        async with database.sessions() as session, session.begin():
            await session.execute(delete(Guild).where(Guild.discord_guild_id == discord_guild_id))
        await engine.dispose()


async def test_open_guild_reuses_session_during_concurrent_execution() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    database = Database.from_engine(engine)
    suffix = uuid4().int % 1_000_000_000
    discord_guild_id = 8_200_000_000_000_000_000 + suffix
    local_date = date(2026, 8, 19)
    now = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)

    try:
        await GuildAdminService(database.sessions).ensure_guild(
            discord_guild_id=discord_guild_id,
            guild_name="Guild concorrente",
        )
        async with database.sessions() as session, session.begin():
            guild = await session.scalar(
                select(Guild).where(Guild.discord_guild_id == discord_guild_id)
            )
            assert guild is not None
            project = Project(
                guild_id=guild.id,
                name="Concorrente",
                slug="concorrente",
                discord_channel_id=6_600_000_000_000_000_000 + suffix,
                status=ProjectStatus.ACTIVE,
                daily_enabled=True,
            )
            session.add(project)
            await session.flush()
            session.add(
                ProjectMembership(
                    project_id=project.id,
                    discord_user_id=5_600_000_000_000_000_000 + suffix,
                    display_name="Linus",
                    joined_at=now,
                    left_at=None,
                )
            )

        service = AutomaticDailyService(database.sessions, clock=lambda: now)
        first, second = await asyncio.gather(
            service.open_guild(discord_guild_id, local_date),
            service.open_guild(discord_guild_id, local_date),
        )

        assert len(first) == len(second) == 1
        assert first[0].panel.session_id == second[0].panel.session_id
        async with database.sessions() as session:
            count = await session.scalar(
                select(func.count(DailySession.id)).where(
                    DailySession.project_id == project.id,
                    DailySession.session_date == local_date,
                )
            )
            assert count == 1
    finally:
        async with database.sessions() as session, session.begin():
            await session.execute(delete(Guild).where(Guild.discord_guild_id == discord_guild_id))
        await engine.dispose()
