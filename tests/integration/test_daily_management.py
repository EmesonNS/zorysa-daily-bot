import os
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.daily import DailyService
from app.application.daily_management import DailyManagementService
from app.application.dto import ActorContext
from app.application.errors import AuthorizationError, NotFoundError
from app.application.guild_admin import GuildAdminService
from app.application.projects import ProjectService
from app.domain.enums import AssignmentStatus, AuditAction, SessionStatus
from app.infrastructure.database.models import AuditEvent

TODAY = date(2026, 8, 21)


def _actor(*, roles: tuple[int, ...] = (), owner: bool = False) -> ActorContext:
    return ActorContext(9_007_000_001, "Guild Daily", 42, roles, owner, owner)


@pytest.fixture
async def daily_management_context():  # type: ignore[no-untyped-def]
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as connection:
        transaction = await connection.begin()
        sessions = async_sessionmaker(
            connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            yield sessions
        finally:
            await transaction.rollback()
    await engine.dispose()


async def test_public_status_and_manual_close_are_private_scoped_and_idempotent(
    daily_management_context,
) -> None:  # type: ignore[no-untyped-def]
    await GuildAdminService(daily_management_context).add_admin_role(
        actor=_actor(owner=True), role_id=10
    )
    actor = _actor(roles=(10,))
    projects = ProjectService(daily_management_context)
    await projects.create_project(actor=actor, name="Zorysa", channel_id=100)
    await projects.add_member(actor=actor, project_slug="zorysa", user_id=200, display_name="Ada")
    opened_at = datetime(2026, 8, 21, 12, tzinfo=UTC)
    opened = await DailyService(daily_management_context, clock=lambda: opened_at).open_daily(
        actor=actor, project_slug="zorysa"
    )

    service = DailyManagementService(daily_management_context, clock=lambda: opened_at)
    panel = await service.status(
        discord_guild_id=actor.guild_id, project_slug="zorysa", local_date=None
    )
    assert panel == opened.panel
    assert "answer" not in repr(panel).casefold()
    assert "reason" not in repr(panel).casefold()
    with pytest.raises(NotFoundError):
        await service.status(
            discord_guild_id=actor.guild_id + 1,
            project_slug="zorysa",
            local_date=TODAY,
        )
    with pytest.raises(AuthorizationError):
        await service.close(actor=_actor(owner=True), project_slug="zorysa", local_date=TODAY)

    closed = await service.close(actor=actor, project_slug="zorysa", local_date=TODAY)
    reclosed = await DailyManagementService(
        daily_management_context, clock=lambda: opened_at + timedelta(hours=1)
    ).close(actor=actor, project_slug="zorysa", local_date=TODAY)

    assert closed.panel.status == SessionStatus.CLOSED
    assert closed.panel.participants[0].status == AssignmentStatus.NOT_ANSWERED
    assert closed.closed_at == reclosed.closed_at == opened_at
    assert reclosed.panel == closed.panel
    async with daily_management_context() as session:
        events = (
            await session.scalars(
                select(AuditEvent).where(AuditEvent.action == AuditAction.DAILY_CLOSED_MANUALLY)
            )
        ).all()
    assert len(events) == 1
    assert events[0].target_id == opened.panel.session_id
    assert events[0].details["session_date"] == TODAY.isoformat()
    assert isinstance(events[0].details["project_id"], int)
