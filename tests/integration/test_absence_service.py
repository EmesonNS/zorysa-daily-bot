import os
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.absences import AbsenceService
from app.application.automatic_daily import AutomaticDailyService
from app.application.daily import DailyService
from app.application.dto import ActorContext
from app.application.errors import AuthorizationError, ConflictError
from app.application.guild_admin import GuildAdminService
from app.application.projects import ProjectService
from app.domain.enums import AssignmentStatus
from app.infrastructure.database.models import DailyAssignment

TODAY = date(2026, 8, 20)


def _actor(*, roles: tuple[int, ...] = (), owner: bool = False) -> ActorContext:
    return ActorContext(9_006_000_001, "Guild Ausências", 42, roles, owner, owner)


@pytest.fixture
async def absence_context():  # type: ignore[no-untyped-def]
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


async def _seed(context):  # type: ignore[no-untyped-def]
    await GuildAdminService(context).add_admin_role(actor=_actor(owner=True), role_id=10)
    actor = _actor(roles=(10,))
    projects = ProjectService(context)
    await projects.create_project(actor=actor, name="Zorysa", channel_id=100)
    await projects.add_member(
        actor=actor, project_slug="zorysa", user_id=200, display_name="Emeson"
    )
    opened = await DailyService(
        context, clock=lambda: datetime(2026, 8, 20, 12, tzinfo=UTC)
    ).open_daily(actor=actor, project_slug="zorysa")
    return actor, opened.panel.session_id


async def test_justifies_pending_and_keeps_reason_private(absence_context) -> None:  # type: ignore[no-untyped-def]
    actor, session_id = await _seed(absence_context)
    now = datetime(2026, 8, 20, 13, tzinfo=UTC)
    justified = await AbsenceService(absence_context, clock=lambda: now).justify(
        actor=actor, project_slug="zorysa", user_id=200, local_date=TODAY, reason="Consulta"
    )

    assert justified.panel.participants[0].status == AssignmentStatus.EXCUSED
    assert not hasattr(justified.panel.participants[0], "excuse_reason")
    async with absence_context() as session:
        assignment = await session.scalar(
            select(DailyAssignment).where(DailyAssignment.session_id == session_id)
        )
        assert assignment is not None
        assert assignment.excuse_reason == "Consulta"
        assert assignment.excused_by_user_id == actor.user_id
        assert assignment.excused_at == now


async def test_repeated_justification_updates_metadata_idempotently(absence_context) -> None:  # type: ignore[no-untyped-def]
    actor, _ = await _seed(absence_context)
    service = AbsenceService(absence_context)
    await service.justify(
        actor=actor, project_slug="zorysa", user_id=200, local_date=TODAY, reason="Consulta"
    )
    justified = await service.justify(
        actor=actor, project_slug="zorysa", user_id=200, local_date=TODAY, reason="Treinamento"
    )
    assert justified.panel.participants[0].status == AssignmentStatus.EXCUSED


async def test_justifies_not_answered_after_close(absence_context) -> None:  # type: ignore[no-untyped-def]
    actor, _ = await _seed(absence_context)
    await AutomaticDailyService(absence_context).close_guild(actor.guild_id, TODAY)
    justified = await AbsenceService(absence_context).justify(
        actor=actor, project_slug="zorysa", user_id=200, local_date=TODAY, reason="Férias"
    )
    assert justified.panel.participants[0].status == AssignmentStatus.EXCUSED


async def test_rejects_answered_assignment_and_unauthorized_actor(absence_context) -> None:  # type: ignore[no-untyped-def]
    actor, session_id = await _seed(absence_context)
    async with absence_context() as session, session.begin():
        assignment = await session.scalar(
            select(DailyAssignment).where(DailyAssignment.session_id == session_id)
        )
        assert assignment is not None
        assignment.status = AssignmentStatus.ANSWERED
        assignment.answered_at = datetime.now(UTC)

    with pytest.raises(ConflictError, match="respondeu"):
        await AbsenceService(absence_context).justify(
            actor=actor, project_slug="zorysa", user_id=200, local_date=TODAY, reason="Consulta"
        )
    with pytest.raises(AuthorizationError):
        await AbsenceService(absence_context).justify(
            actor=_actor(owner=True),
            project_slug="zorysa",
            user_id=200,
            local_date=TODAY,
            reason="Consulta",
        )
