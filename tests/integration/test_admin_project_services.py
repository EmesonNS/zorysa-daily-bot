import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.dto import ActorContext
from app.application.errors import AuthorizationError, ConflictError
from app.application.guild_admin import DEFAULT_DAILY_QUESTIONS, GuildAdminService
from app.application.projects import ProjectService
from app.domain.enums import AuditAction
from app.infrastructure.database.models import (
    AuditEvent,
    DailyQuestion,
    Guild,
    ProjectMembership,
)


def _actor(
    *, roles: tuple[int, ...] = (), owner: bool = False, manage: bool = False
) -> ActorContext:
    return ActorContext(
        guild_id=9_001_000_001,
        guild_name="Guild de teste",
        user_id=42,
        role_ids=roles,
        is_guild_owner=owner,
        can_manage_guild=manage,
    )


@pytest.fixture
async def service_context():  # type: ignore[no-untyped-def]
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as connection:
        transaction = await connection.begin()
        sessions = async_sessionmaker(
            connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield sessions
        finally:
            await transaction.rollback()
    await engine.dispose()


async def test_admin_bootstrap_defaults_and_last_role_guard(service_context) -> None:  # type: ignore[no-untyped-def]
    service = GuildAdminService(service_context)

    with pytest.raises(AuthorizationError):
        await service.add_admin_role(actor=_actor(), role_id=10)

    await service.add_admin_role(actor=_actor(owner=True), role_id=10)

    async with service_context() as session:
        guild_id = await session.scalar(
            select(Guild.id).where(Guild.discord_guild_id == _actor().guild_id)
        )
        questions = (
            await session.scalars(
                select(DailyQuestion.text)
                .where(DailyQuestion.guild_id == guild_id)
                .order_by(DailyQuestion.position)
            )
        ).all()
    assert tuple(questions) == DEFAULT_DAILY_QUESTIONS

    with pytest.raises(AuthorizationError):
        await service.add_admin_role(actor=_actor(owner=True, manage=True), role_id=20)

    configured_actor = _actor(roles=(10,))
    await service.add_admin_role(actor=configured_actor, role_id=20)
    with pytest.raises(ConflictError):
        await service.add_admin_role(actor=configured_actor, role_id=20)
    assert [role.role_id for role in await service.list_admin_roles(actor=configured_actor)] == [
        10,
        20,
    ]

    await service.remove_admin_role(actor=configured_actor, role_id=20)
    with pytest.raises(ConflictError, match="último cargo"):
        await service.remove_admin_role(actor=configured_actor, role_id=10)

    async with service_context() as session:
        events = (await session.scalars(select(AuditEvent).order_by(AuditEvent.id))).all()
    assert [(event.action, event.actor_user_id, event.target_id) for event in events] == [
        (AuditAction.ADMIN_ROLE_ADDED, 42, 10),
        (AuditAction.ADMIN_ROLE_ADDED, 42, 20),
        (AuditAction.ADMIN_ROLE_REMOVED, 42, 20),
    ]


async def test_project_membership_exit_and_reentry_preserve_history(service_context) -> None:  # type: ignore[no-untyped-def]
    admin = GuildAdminService(service_context)
    await admin.add_admin_role(actor=_actor(owner=True), role_id=10)
    actor = _actor(roles=(10,))
    instant = datetime(2026, 8, 19, 12, tzinfo=UTC)
    projects = ProjectService(service_context, clock=lambda: instant)

    project = await projects.create_project(actor=actor, name="Saúde & Inovação", channel_id=55)
    assert project.slug == "saude-inovacao"
    with pytest.raises(ConflictError):
        await projects.create_project(actor=actor, name="Saude Inovacao", channel_id=56)

    await projects.add_member(
        actor=actor,
        project_slug=project.slug,
        user_id=77,
        display_name="Ada",
    )
    with pytest.raises(ConflictError):
        await projects.add_member(
            actor=actor,
            project_slug=project.slug,
            user_id=77,
            display_name="Ada",
        )

    listed = await projects.list_projects(actor=actor)
    assert listed[0].participant_count == 1
    assert (await projects.list_members(actor=actor, project_slug=project.slug))[
        0
    ].display_name == "Ada"

    await projects.remove_member(actor=actor, project_slug=project.slug, user_id=77)
    assert await projects.list_members(actor=actor, project_slug=project.slug) == ()
    await projects.add_member(
        actor=actor,
        project_slug=project.slug,
        user_id=77,
        display_name="Ada Lovelace",
    )

    async with service_context() as session:
        history_count = await session.scalar(
            select(func.count(ProjectMembership.id)).where(ProjectMembership.discord_user_id == 77)
        )
        active_count = await session.scalar(
            select(func.count(ProjectMembership.id)).where(
                ProjectMembership.discord_user_id == 77,
                ProjectMembership.left_at.is_(None),
            )
        )
    assert history_count == 2
    assert active_count == 1
