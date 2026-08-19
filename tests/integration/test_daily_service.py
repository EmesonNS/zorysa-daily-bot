import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import create_async_engine

from app.application.daily import DailyService
from app.application.dto import ActorContext
from app.application.errors import AuthorizationError, ConflictError
from app.application.guild_admin import GuildAdminService
from app.application.projects import ProjectService
from app.infrastructure.database import Database
from app.infrastructure.database.models import DailyAnswer, Guild


@pytest.fixture(scope="module", autouse=True)
def _upgrade_database() -> None:
    command.upgrade(Config("alembic.ini"), "head")


async def test_manual_daily_snapshots_members_and_persists_private_answers() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    database = Database.from_engine(engine)
    suffix = uuid4().int % 1_000_000_000
    guild_id = 8_000_000_000_000_000_000 + suffix
    role_id = 7_000_000_000_000_000_000 + suffix
    channel_id = 6_000_000_000_000_000_000 + suffix
    user_id = 5_000_000_000_000_000_000 + suffix
    now = datetime(2026, 8, 19, 15, 0, tzinfo=UTC)
    owner = ActorContext(
        guild_id=guild_id,
        guild_name="Guild de integração",
        user_id=user_id,
        role_ids=(),
        is_guild_owner=True,
        can_manage_guild=True,
    )
    admin = ActorContext(
        guild_id=guild_id,
        guild_name="Guild de integração",
        user_id=user_id,
        role_ids=(role_id,),
        is_guild_owner=True,
        can_manage_guild=True,
    )

    try:
        guild_service = GuildAdminService(database.sessions)
        project_service = ProjectService(database.sessions, clock=lambda: now)
        daily_service = DailyService(database.sessions, clock=lambda: now)
        await guild_service.add_admin_role(actor=owner, role_id=role_id)
        await project_service.create_project(actor=admin, name="AmazHealth", channel_id=channel_id)
        await project_service.add_member(
            actor=admin,
            project_slug="amazhealth",
            user_id=user_id,
            display_name="Ada",
        )

        opened = await daily_service.open_daily(actor=admin, project_slug="amazhealth")
        reopened = await daily_service.open_daily(actor=admin, project_slug="amazhealth")
        assert reopened.panel.session_id == opened.panel.session_id
        assert len(opened.panel.participants) == 1
        assert opened.message_id is None

        message_id = 4_000_000_000_000_000_000 + suffix
        await daily_service.attach_message(
            session_id=opened.panel.session_id, message_id=message_id
        )
        form = await daily_service.prepare_response(message_id=message_id, user_id=user_id)
        assert len(form.questions) == 4

        with pytest.raises(AuthorizationError):
            await daily_service.prepare_response(message_id=message_id, user_id=user_id + 1)

        answers = {question.id: f"Resposta {question.position}" for question in form.questions}
        panel = await daily_service.submit_response(
            message_id=message_id, user_id=user_id, answers=answers
        )
        assert panel.participants[0].answered is True
        with pytest.raises(ConflictError):
            await daily_service.submit_response(
                message_id=message_id, user_id=user_id, answers=answers
            )

        async with database.sessions() as session:
            answer_count = await session.scalar(select(func.count(DailyAnswer.id)))
            assert answer_count is not None and answer_count >= 4
    finally:
        async with database.sessions() as session, session.begin():
            await session.execute(delete(Guild).where(Guild.discord_guild_id == guild_id))
        await engine.dispose()
