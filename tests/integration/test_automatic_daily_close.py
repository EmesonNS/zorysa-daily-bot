import os
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine

from app.application.automatic_daily import AutomaticDailyService
from app.application.daily import DailyService
from app.application.errors import ConflictError
from app.application.guild_admin import GuildAdminService
from app.domain.enums import AssignmentStatus, ProjectStatus, SessionStatus
from app.infrastructure.database import Database
from app.infrastructure.database.models import (
    DailyAssignment,
    DailySession,
    Guild,
    Project,
    ProjectMembership,
)


@pytest.fixture(scope="module", autouse=True)
def _upgrade_database() -> None:
    command.upgrade(Config("alembic.ini"), "head")


async def test_close_guild_finalizes_pending_and_rejects_late_responses_idempotently() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    database = Database.from_engine(engine)
    suffix = uuid4().int % 1_000_000_000
    discord_guild_id = 8_500_000_000_000_000_000 + suffix
    local_date = date(2026, 8, 19)
    now = datetime(2026, 8, 19, 15, 0, tzinfo=UTC)
    user_ids = (
        5_960_000_000_000_000_000 + suffix,
        5_970_000_000_000_000_000 + suffix,
    )

    try:
        await GuildAdminService(database.sessions).ensure_guild(
            discord_guild_id=discord_guild_id,
            guild_name="Guild de fechamento",
        )
        async with database.sessions() as session, session.begin():
            guild = await session.scalar(
                select(Guild).where(Guild.discord_guild_id == discord_guild_id)
            )
            assert guild is not None
            project = Project(
                guild_id=guild.id,
                name="Fechamento",
                slug="fechamento",
                discord_channel_id=6_950_000_000_000_000_000 + suffix,
                status=ProjectStatus.ACTIVE,
                daily_enabled=True,
            )
            session.add(project)
            await session.flush()
            session.add_all(
                [
                    ProjectMembership(
                        project_id=project.id,
                        discord_user_id=user_ids[0],
                        display_name="Ada",
                        joined_at=now,
                        left_at=None,
                    ),
                    ProjectMembership(
                        project_id=project.id,
                        discord_user_id=user_ids[1],
                        display_name="Grace",
                        joined_at=now,
                        left_at=None,
                    ),
                ]
            )

        automatic = AutomaticDailyService(database.sessions, clock=lambda: now)
        daily = DailyService(database.sessions, clock=lambda: now)
        opened = await automatic.open_guild(discord_guild_id, local_date)
        message_id = 4_800_000_000_000_000_000 + suffix
        await daily.attach_message(
            session_id=opened[0].panel.session_id,
            message_id=message_id,
        )
        form = await daily.prepare_response(message_id=message_id, user_id=user_ids[0])
        private_answers = {
            question.id: f"Implementei a API secreta {question.position}"
            for question in form.questions
        }
        await daily.submit_response(
            message_id=message_id,
            user_id=user_ids[0],
            answers=private_answers,
        )

        closed = await automatic.close_guild(discord_guild_id, local_date)
        reclosed = await AutomaticDailyService(
            database.sessions,
            clock=lambda: now + timedelta(hours=1),
        ).close_guild(discord_guild_id, local_date)

        assert len(closed) == len(reclosed) == 1
        assert closed[0].closed_at == reclosed[0].closed_at == now
        assert closed[0].panel.status == SessionStatus.CLOSED
        assert tuple(participant.status for participant in closed[0].panel.participants) == (
            AssignmentStatus.ANSWERED,
            AssignmentStatus.NOT_ANSWERED,
        )
        assert closed[0].message_id == message_id
        assert not hasattr(closed[0], "view")
        assert "Implementei a API secreta" not in repr(closed[0].panel)

        with pytest.raises(ConflictError, match="encerrada"):
            await daily.prepare_response(message_id=message_id, user_id=user_ids[1])
        with pytest.raises(ConflictError, match="encerrada"):
            await daily.submit_response(
                message_id=message_id,
                user_id=user_ids[1],
                answers={},
            )

        async with database.sessions() as session:
            daily_session = await session.get(DailySession, opened[0].panel.session_id)
            assignments = (
                await session.scalars(
                    select(DailyAssignment)
                    .where(DailyAssignment.session_id == opened[0].panel.session_id)
                    .order_by(DailyAssignment.display_name)
                )
            ).all()
            assert daily_session is not None
            assert daily_session.status == SessionStatus.CLOSED
            assert daily_session.closed_at == now
            assert tuple(item.status for item in assignments) == (
                AssignmentStatus.ANSWERED,
                AssignmentStatus.NOT_ANSWERED,
            )
    finally:
        async with database.sessions() as session, session.begin():
            await session.execute(delete(Guild).where(Guild.discord_guild_id == discord_guild_id))
        await engine.dispose()
