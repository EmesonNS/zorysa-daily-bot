import os
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.member_lifecycle import MemberLifecycleService
from app.domain.enums import AssignmentStatus, AuditAction, ProjectStatus, SessionStatus
from app.infrastructure.database.models import (
    AuditEvent,
    DailyAssignment,
    DailySession,
    Guild,
    Project,
    ProjectMembership,
)

JOINED_AT = datetime(2026, 8, 1, 12, tzinfo=UTC)
LEFT_AT = datetime(2026, 8, 21, 15, tzinfo=UTC)


@pytest.fixture
async def lifecycle_context():  # type: ignore[no-untyped-def]
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as connection:
        transaction = await connection.begin()
        sessions = async_sessionmaker(
            connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        async with sessions() as session, session.begin():
            first_guild = Guild(discord_guild_id=9_008_000_001, name="Primeira")
            second_guild = Guild(discord_guild_id=9_008_000_002, name="Segunda")
            session.add_all([first_guild, second_guild])
            await session.flush()
            first_project = Project(
                guild_id=first_guild.id,
                name="Primeiro",
                slug="primeiro",
                discord_channel_id=100,
                status=ProjectStatus.ACTIVE,
                daily_enabled=True,
            )
            second_project = Project(
                guild_id=first_guild.id,
                name="Segundo",
                slug="segundo",
                discord_channel_id=200,
                status=ProjectStatus.ACTIVE,
                daily_enabled=True,
            )
            other_project = Project(
                guild_id=second_guild.id,
                name="Outro",
                slug="outro",
                discord_channel_id=300,
                status=ProjectStatus.ACTIVE,
                daily_enabled=True,
            )
            session.add_all([first_project, second_project, other_project])
            await session.flush()
            session.add_all(
                [
                    ProjectMembership(
                        project_id=first_project.id,
                        discord_user_id=77,
                        display_name="Ada",
                        joined_at=JOINED_AT,
                        left_at=None,
                    ),
                    ProjectMembership(
                        project_id=second_project.id,
                        discord_user_id=77,
                        display_name="Ada",
                        joined_at=JOINED_AT,
                        left_at=None,
                    ),
                    ProjectMembership(
                        project_id=first_project.id,
                        discord_user_id=77,
                        display_name="Ada antiga",
                        joined_at=JOINED_AT - timedelta(days=30),
                        left_at=JOINED_AT - timedelta(days=1),
                    ),
                    ProjectMembership(
                        project_id=first_project.id,
                        discord_user_id=88,
                        display_name="Grace",
                        joined_at=JOINED_AT,
                        left_at=None,
                    ),
                    ProjectMembership(
                        project_id=other_project.id,
                        discord_user_id=77,
                        display_name="Ada",
                        joined_at=JOINED_AT,
                        left_at=None,
                    ),
                ]
            )
            daily = DailySession(
                project_id=first_project.id,
                session_date=date(2026, 8, 21),
                status=SessionStatus.OPEN,
                opened_at=JOINED_AT,
                closed_at=None,
                message_id=500,
            )
            session.add(daily)
            await session.flush()
            session.add(
                DailyAssignment(
                    session_id=daily.id,
                    discord_user_id=77,
                    display_name="Ada",
                    status=AssignmentStatus.PENDING,
                    answered_at=None,
                )
            )
        try:
            yield sessions
        finally:
            await transaction.rollback()
    await engine.dispose()


async def test_leave_guild_closes_only_active_memberships_and_preserves_assignment(
    lifecycle_context,
) -> None:  # type: ignore[no-untyped-def]
    changed = await MemberLifecycleService(lifecycle_context, clock=lambda: LEFT_AT).leave_guild(
        9_008_000_001, 77
    )

    assert changed == 2
    async with lifecycle_context() as session:
        first_values = (
            await session.scalars(
                select(ProjectMembership.left_at)
                .join(Project)
                .join(Guild)
                .where(
                    Guild.discord_guild_id == 9_008_000_001,
                    ProjectMembership.discord_user_id == 77,
                )
                .order_by(ProjectMembership.id)
            )
        ).all()
        other_left_at = await session.scalar(
            select(ProjectMembership.left_at)
            .join(Project)
            .join(Guild)
            .where(
                Guild.discord_guild_id == 9_008_000_002,
                ProjectMembership.discord_user_id == 77,
            )
        )
        unaffected = await session.scalar(
            select(ProjectMembership.left_at).where(ProjectMembership.discord_user_id == 88)
        )
        assignment = await session.scalar(select(DailyAssignment))
        event = await session.scalar(
            select(AuditEvent).where(AuditEvent.action == AuditAction.MEMBER_LEFT_GUILD)
        )

    assert first_values.count(LEFT_AT) == 2
    assert JOINED_AT - timedelta(days=1) in first_values
    assert other_left_at is None and unaffected is None
    assert assignment.status == AssignmentStatus.PENDING
    assert event.actor_user_id is None and event.target_id == 77
    assert event.details == {"membership_count": 2}


async def test_leave_guild_is_idempotent_and_audits_only_first_change(
    lifecycle_context,
) -> None:  # type: ignore[no-untyped-def]
    service = MemberLifecycleService(lifecycle_context, clock=lambda: LEFT_AT)

    assert await service.leave_guild(9_008_000_001, 77) == 2
    assert await service.leave_guild(9_008_000_001, 77) == 0
    async with lifecycle_context() as session:
        count = await session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.action == AuditAction.MEMBER_LEFT_GUILD
            )
        )
    assert count == 1


async def test_leave_guild_ignores_unknown_guild_or_member(
    lifecycle_context,
) -> None:  # type: ignore[no-untyped-def]
    service = MemberLifecycleService(lifecycle_context)

    assert await service.leave_guild(9_008_000_099, 77) == 0
    assert await service.leave_guild(9_008_000_001, 999) == 0
    async with lifecycle_context() as session:
        active_count = await session.scalar(
            select(func.count(ProjectMembership.id)).where(ProjectMembership.left_at.is_(None))
        )
        audit_count = await session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.action == AuditAction.MEMBER_LEFT_GUILD
            )
        )
    assert active_count == 4
    assert audit_count == 0
