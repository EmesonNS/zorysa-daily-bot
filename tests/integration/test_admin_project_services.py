import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.daily import DailyService
from app.application.dto import ActorContext
from app.application.errors import AuthorizationError, ConflictError
from app.application.guild_admin import DEFAULT_DAILY_QUESTIONS, GuildAdminService
from app.application.projects import ProjectService
from app.domain.enums import AuditAction
from app.infrastructure.database.models import (
    AuditEvent,
    DailyQuestion,
    DailySession,
    Guild,
    Project,
    ProjectMembership,
)


def _actor(
    *,
    guild_id: int = 9_001_000_001,
    roles: tuple[int, ...] = (),
    owner: bool = False,
    manage: bool = False,
) -> ActorContext:
    return ActorContext(
        guild_id=guild_id,
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


async def test_project_management_preserves_history_and_audits_mutations(
    service_context,
) -> None:  # type: ignore[no-untyped-def]
    await GuildAdminService(service_context).add_admin_role(actor=_actor(owner=True), role_id=10)
    actor = _actor(roles=(10,))
    instant = datetime(2026, 8, 19, 12, tzinfo=UTC)
    projects = ProjectService(service_context, clock=lambda: instant)

    created = await projects.create_project(actor=actor, name="Projeto Original", channel_id=55)
    with pytest.raises(ConflictError):
        await projects.create_project(actor=actor, name="Projeto Original", channel_id=99)
    await projects.add_member(
        actor=actor, project_slug=created.slug, user_id=77, display_name="Nome privado"
    )
    await projects.remove_member(actor=actor, project_slug=created.slug, user_id=77)
    await projects.add_member(
        actor=actor, project_slug=created.slug, user_id=77, display_name="Nome atualizado"
    )
    opened = await DailyService(service_context, clock=lambda: instant).open_daily(
        actor=actor, project_slug=created.slug
    )

    edited = await projects.edit_project(
        actor=actor,
        project_slug=created.slug,
        name="Projeto Renomeado",
        channel_id=66,
        daily_enabled=False,
    )
    details = await projects.project_details(actor=actor, project_slug=created.slug)

    assert edited.slug == created.slug
    assert (edited.name, edited.channel_id, edited.daily_enabled) == (
        "Projeto Renomeado",
        66,
        False,
    )
    assert details.summary == edited
    assert [member.user_id for member in details.active_members] == [77]
    assert details.membership_count == 2
    assert details.session_count == 1
    assert [item.slug for item in await projects.list_member_projects(actor=actor, user_id=77)] == [
        created.slug
    ]

    archived = await projects.archive_project(actor=actor, project_slug=created.slug)
    repeated = await projects.archive_project(actor=actor, project_slug=created.slug)
    assert archived.status == "ARCHIVED" and archived.daily_enabled is False
    assert repeated == archived
    assert repeated.participant_count == 0
    assert await projects.list_member_projects(actor=actor, user_id=77) == ()
    with pytest.raises(ConflictError, match="arquivado"):
        await projects.add_member(
            actor=actor, project_slug=created.slug, user_id=88, display_name="Grace"
        )
    with pytest.raises(ConflictError, match="não está habilitada"):
        await DailyService(service_context, clock=lambda: instant).open_daily(
            actor=actor, project_slug=created.slug
        )

    async with service_context() as session:
        project = await session.scalar(select(Project).where(Project.slug == created.slug))
        memberships = (
            await session.scalars(
                select(ProjectMembership)
                .where(ProjectMembership.project_id == project.id)
                .order_by(ProjectMembership.id)
            )
        ).all()
        session_count = await session.scalar(
            select(func.count(DailySession.id)).where(DailySession.project_id == project.id)
        )
        events = (
            await session.scalars(
                select(AuditEvent)
                .where(AuditEvent.target_type.in_(("project", "project_membership")))
                .order_by(AuditEvent.id)
            )
        ).all()

    assert project.slug == created.slug
    assert session_count == 1 and opened.panel.session_id > 0
    assert len(memberships) == 2
    assert all(membership.left_at == instant for membership in memberships)
    assert [AuditAction(event.action) for event in events] == [
        AuditAction.PROJECT_CREATED,
        AuditAction.MEMBER_ADDED,
        AuditAction.MEMBER_REMOVED,
        AuditAction.MEMBER_ADDED,
        AuditAction.PROJECT_EDITED,
        AuditAction.PROJECT_ARCHIVED,
    ]
    assert all("display_name" not in event.details for event in events)


async def test_member_projects_are_isolated_by_guild(service_context) -> None:  # type: ignore[no-untyped-def]
    first_owner = _actor(owner=True)
    second_owner = _actor(guild_id=9_001_000_002, owner=True)
    admin = GuildAdminService(service_context)
    await admin.add_admin_role(actor=first_owner, role_id=10)
    await admin.add_admin_role(actor=second_owner, role_id=20)
    first = _actor(roles=(10,))
    second = _actor(guild_id=second_owner.guild_id, roles=(20,))
    projects = ProjectService(service_context)
    first_project = await projects.create_project(actor=first, name="Compartilhado", channel_id=100)
    second_project = await projects.create_project(
        actor=second, name="Compartilhado", channel_id=200
    )
    await projects.add_member(
        actor=first, project_slug=first_project.slug, user_id=77, display_name="Ada"
    )
    await projects.add_member(
        actor=second, project_slug=second_project.slug, user_id=77, display_name="Ada"
    )

    first_items = await projects.list_member_projects(actor=first, user_id=77)
    second_items = await projects.list_member_projects(actor=second, user_id=77)
    first_details = await projects.project_details(actor=first, project_slug="compartilhado")
    second_details = await projects.project_details(actor=second, project_slug="compartilhado")

    assert [(item.slug, item.channel_id) for item in first_items] == [("compartilhado", 100)]
    assert [(item.slug, item.channel_id) for item in second_items] == [("compartilhado", 200)]
    assert first_details.summary.channel_id == 100
    assert second_details.summary.channel_id == 200
