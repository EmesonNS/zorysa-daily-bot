import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.audit import AuditService, append_audit_event
from app.application.dto import ActorContext, AuditFilters
from app.application.errors import AuthorizationError
from app.domain.enums import AuditAction
from app.infrastructure.database.models import AdminRole, AuditEvent, Guild, GuildSettings

GUILD_ID = 9_007_000_201
OTHER_GUILD_ID = 9_007_000_202
BASE = datetime(2026, 8, 21, 12, tzinfo=UTC)


def _actor(*, roles: tuple[int, ...] = (10,)) -> ActorContext:
    return ActorContext(GUILD_ID, "Guild Auditada", 42, roles, False, False)


@pytest.fixture
async def audit_context():  # type: ignore[no-untyped-def]
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


async def _seed(audit_context) -> None:  # type: ignore[no-untyped-def]
    async with audit_context() as session, session.begin():
        guild = Guild(discord_guild_id=GUILD_ID, name="Guild Auditada")
        other = Guild(discord_guild_id=OTHER_GUILD_ID, name="Outra Guild")
        session.add_all((guild, other))
        await session.flush()
        session.add_all(
            (
                GuildSettings(guild_id=guild.id),
                GuildSettings(guild_id=other.id),
                AdminRole(guild_id=guild.id, discord_role_id=10),
            )
        )
        append_audit_event(
            session,
            guild=guild,
            actor=_actor(),
            action=AuditAction.PROJECT_CREATED,
            target_type="project",
            target_id=100,
            details={"slug": "alpha"},
            occurred_at=BASE,
        )
        append_audit_event(
            session,
            guild=guild,
            actor=ActorContext(GUILD_ID, "Guild Auditada", 77, (10,), False, False),
            action=AuditAction.PROJECT_EDITED,
            target_type="project",
            target_id=101,
            details={"daily_enabled": False},
            occurred_at=BASE + timedelta(minutes=1),
        )
        append_audit_event(
            session,
            guild=other,
            actor=None,
            action=AuditAction.MEMBER_LEFT_GUILD,
            target_type="member",
            target_id=42,
            details={},
            occurred_at=BASE + timedelta(minutes=2),
        )


async def test_list_is_guild_scoped_sorted_and_cursor_paginated(audit_context) -> None:  # type: ignore[no-untyped-def]
    await _seed(audit_context)
    service = AuditService(audit_context)

    first = await service.list_events(actor=_actor(), limit=1)
    second = await service.list_events(actor=_actor(), cursor=first.next_cursor, limit=1)

    assert [event.action for event in first.events] == [AuditAction.PROJECT_EDITED]
    assert [event.action for event in second.events] == [AuditAction.PROJECT_CREATED]
    assert second.next_cursor is None


@pytest.mark.parametrize(
    "filters",
    [
        AuditFilters(action=AuditAction.PROJECT_CREATED),
        AuditFilters(actor_user_id=42),
        AuditFilters(target_type="project"),
        AuditFilters(target_id=100),
        AuditFilters(started_at=BASE - timedelta(seconds=1), ended_at=BASE),
    ],
)
async def test_list_applies_each_supported_filter(audit_context, filters: AuditFilters) -> None:  # type: ignore[no-untyped-def]
    await _seed(audit_context)

    page = await AuditService(audit_context).list_events(actor=_actor(), filters=filters)

    assert len(page.events) >= 1
    assert all(event.guild_id == GUILD_ID for event in page.events)


async def test_rollback_does_not_leave_audit_event(audit_context) -> None:  # type: ignore[no-untyped-def]
    await _seed(audit_context)
    async with audit_context() as session:
        guild = await session.scalar(select(Guild).where(Guild.discord_guild_id == GUILD_ID))
        assert guild is not None
        append_audit_event(
            session,
            guild=guild,
            actor=_actor(),
            action=AuditAction.PROJECT_ARCHIVED,
            target_type="project",
            target_id=100,
            details={},
        )
        await session.flush()
        await session.rollback()
    async with audit_context() as session:
        count = await session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.action == AuditAction.PROJECT_ARCHIVED
            )
        )
    assert count == 0


async def test_list_requires_configured_admin_role(audit_context) -> None:  # type: ignore[no-untyped-def]
    await _seed(audit_context)

    with pytest.raises(AuthorizationError):
        await AuditService(audit_context).list_events(actor=_actor(roles=()))
