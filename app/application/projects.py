"""Guild-scoped project and historical membership application service."""

import re
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto import ActorContext, MemberSummary, ProjectSummary
from app.application.errors import ConflictError, NotFoundError, ValidationError
from app.application.guild_admin import authorize_admin, ensure_guild_record
from app.domain.enums import ProjectStatus
from app.infrastructure.database.models import Guild, Project, ProjectMembership


def project_slug(name: str) -> str:
    """Create a stable, command-friendly ASCII slug from a project name."""

    normalized = unicodedata.normalize("NFKD", name.strip())
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")


class ProjectService:
    """Maintain projects and append-only membership history."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        timezone: str = "America/Belem",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = sessions
        self._timezone = timezone
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create_project(
        self, *, actor: ActorContext, name: str, channel_id: int
    ) -> ProjectSummary:
        """Create an active project with daily enabled by default."""

        clean_name = name.strip()
        slug = project_slug(clean_name)
        if not clean_name or len(clean_name) > 100 or not slug:
            raise ValidationError("Informe um nome de projeto válido com até 100 caracteres.")
        if len(slug) > 100:
            raise ValidationError("O identificador gerado para o projeto é muito longo.")
        if channel_id <= 0:
            raise ValidationError("O canal informado é inválido.")

        try:
            async with self._sessions() as session, session.begin():
                guild = await self._authorized_guild(session, actor)
                existing = await session.scalar(
                    select(Project.id).where(Project.guild_id == guild.id, Project.slug == slug)
                )
                if existing is not None:
                    raise ConflictError("Já existe um projeto com este nome no servidor.")
                session.add(
                    Project(
                        guild_id=guild.id,
                        name=clean_name,
                        slug=slug,
                        discord_channel_id=channel_id,
                        status=ProjectStatus.ACTIVE,
                        daily_enabled=True,
                    )
                )
        except IntegrityError as error:
            raise ConflictError("Já existe um projeto com este nome no servidor.") from error

        return ProjectSummary(
            name=clean_name,
            slug=slug,
            channel_id=channel_id,
            status=ProjectStatus.ACTIVE.value,
            daily_enabled=True,
            participant_count=0,
        )

    async def list_projects(self, *, actor: ActorContext) -> tuple[ProjectSummary, ...]:
        """List guild projects with their current active participant count."""

        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            participant_count = (
                select(func.count(ProjectMembership.id))
                .where(
                    ProjectMembership.project_id == Project.id,
                    ProjectMembership.left_at.is_(None),
                )
                .correlate(Project)
                .scalar_subquery()
            )
            rows = (
                await session.execute(
                    select(Project, participant_count.label("participant_count"))
                    .where(Project.guild_id == guild.id)
                    .order_by(Project.name, Project.id)
                )
            ).all()
            return tuple(
                ProjectSummary(
                    name=project.name,
                    slug=project.slug,
                    channel_id=project.discord_channel_id,
                    status=project.status.value,
                    daily_enabled=project.daily_enabled,
                    participant_count=int(count),
                )
                for project, count in rows
            )

    async def add_member(
        self,
        *,
        actor: ActorContext,
        project_slug: str,
        user_id: int,
        display_name: str,
    ) -> MemberSummary:
        """Append an active membership, allowing re-entry after a prior departure."""

        clean_display_name = display_name.strip()
        if user_id <= 0 or not clean_display_name or len(clean_display_name) > 100:
            raise ValidationError("O membro informado é inválido.")
        now = self._clock()
        try:
            async with self._sessions() as session, session.begin():
                guild = await self._authorized_guild(session, actor)
                project = await self._project_by_slug(session, guild, project_slug)
                active = await session.scalar(
                    select(ProjectMembership.id).where(
                        ProjectMembership.project_id == project.id,
                        ProjectMembership.discord_user_id == user_id,
                        ProjectMembership.left_at.is_(None),
                    )
                )
                if active is not None:
                    raise ConflictError("Este membro já participa ativamente do projeto.")
                session.add(
                    ProjectMembership(
                        project_id=project.id,
                        discord_user_id=user_id,
                        display_name=clean_display_name,
                        joined_at=now,
                        left_at=None,
                    )
                )
        except IntegrityError as error:
            raise ConflictError("Este membro já participa ativamente do projeto.") from error
        return MemberSummary(user_id=user_id, display_name=clean_display_name, joined_at=now)

    async def remove_member(self, *, actor: ActorContext, project_slug: str, user_id: int) -> None:
        """End an active membership without deleting its history."""

        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            project = await self._project_by_slug(session, guild, project_slug)
            membership = await session.scalar(
                select(ProjectMembership).where(
                    ProjectMembership.project_id == project.id,
                    ProjectMembership.discord_user_id == user_id,
                    ProjectMembership.left_at.is_(None),
                )
            )
            if membership is None:
                raise NotFoundError("Este membro não participa ativamente do projeto.")
            membership.left_at = self._clock()

    async def list_members(
        self, *, actor: ActorContext, project_slug: str
    ) -> tuple[MemberSummary, ...]:
        """List only active memberships while history remains stored."""

        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            project = await self._project_by_slug(session, guild, project_slug)
            memberships = (
                await session.scalars(
                    select(ProjectMembership)
                    .where(
                        ProjectMembership.project_id == project.id,
                        ProjectMembership.left_at.is_(None),
                    )
                    .order_by(ProjectMembership.display_name, ProjectMembership.id)
                )
            ).all()
            return tuple(
                MemberSummary(
                    user_id=membership.discord_user_id,
                    display_name=membership.display_name,
                    joined_at=membership.joined_at,
                )
                for membership in memberships
            )

    async def _authorized_guild(self, session: AsyncSession, actor: ActorContext) -> Guild:
        guild = await ensure_guild_record(
            session,
            discord_guild_id=actor.guild_id,
            guild_name=actor.guild_name,
            timezone=self._timezone,
        )
        await authorize_admin(session, guild=guild, actor=actor)
        return guild

    @staticmethod
    async def _project_by_slug(session: AsyncSession, guild: Guild, slug: str) -> Project:
        project = await session.scalar(
            select(Project).where(
                Project.guild_id == guild.id,
                Project.slug == slug.strip().lower(),
            )
        )
        if project is None:
            raise NotFoundError("Projeto não encontrado neste servidor.")
        return project
