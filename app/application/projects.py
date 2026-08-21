"""Guild-scoped project and historical membership application service."""

import re
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.audit import append_audit_event
from app.application.dto import ActorContext, MemberSummary, ProjectDetails, ProjectSummary
from app.application.errors import ConflictError, NotFoundError, ValidationError
from app.application.guild_admin import authorize_admin, ensure_guild_record
from app.domain.enums import AuditAction, ProjectStatus
from app.infrastructure.database.models import DailySession, Guild, Project, ProjectMembership


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

        clean_name = self._validate_project_input(name, channel_id)
        slug = project_slug(clean_name)
        if len(slug) > 100:
            raise ValidationError("O identificador gerado para o projeto é muito longo.")

        try:
            async with self._sessions() as session, session.begin():
                guild = await self._authorized_guild(session, actor)
                existing = await session.scalar(
                    select(Project.id).where(Project.guild_id == guild.id, Project.slug == slug)
                )
                if existing is not None:
                    raise ConflictError("Já existe um projeto com este nome no servidor.")
                project = Project(
                    guild_id=guild.id,
                    name=clean_name,
                    slug=slug,
                    discord_channel_id=channel_id,
                    status=ProjectStatus.ACTIVE,
                    daily_enabled=True,
                )
                session.add(project)
                await session.flush()
                append_audit_event(
                    session,
                    guild=guild,
                    actor=actor,
                    action=AuditAction.PROJECT_CREATED,
                    target_type="project",
                    target_id=project.id,
                    details=self._project_audit_details(project),
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

    async def edit_project(
        self,
        *,
        actor: ActorContext,
        project_slug: str,
        name: str,
        channel_id: int,
        daily_enabled: bool,
    ) -> ProjectSummary:
        """Edit future project operation while preserving its stable slug and history."""

        clean_name = self._validate_project_input(name, channel_id)
        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            project = await self._project_by_slug(session, guild, project_slug, lock=True)
            if project.status == ProjectStatus.ARCHIVED:
                raise ConflictError("Um projeto arquivado não pode ser editado.")
            project.name = clean_name
            project.discord_channel_id = channel_id
            project.daily_enabled = daily_enabled
            await session.flush()
            append_audit_event(
                session,
                guild=guild,
                actor=actor,
                action=AuditAction.PROJECT_EDITED,
                target_type="project",
                target_id=project.id,
                details=self._project_audit_details(project),
            )
            return await self._summary(session, project)

    async def archive_project(self, *, actor: ActorContext, project_slug: str) -> ProjectSummary:
        """Archive a project and end all active memberships atomically."""

        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            project = await self._project_by_slug(session, guild, project_slug, lock=True)
            if project.status == ProjectStatus.ARCHIVED:
                return await self._summary(session, project)
            memberships = (
                await session.scalars(
                    select(ProjectMembership)
                    .where(
                        ProjectMembership.project_id == project.id,
                        ProjectMembership.left_at.is_(None),
                    )
                    .with_for_update()
                )
            ).all()
            archived_at = self._clock()
            for membership in memberships:
                membership.left_at = archived_at
            project.status = ProjectStatus.ARCHIVED
            project.daily_enabled = False
            await session.flush()
            details = self._project_audit_details(project)
            details["memberships_closed"] = len(memberships)
            append_audit_event(
                session,
                guild=guild,
                actor=actor,
                action=AuditAction.PROJECT_ARCHIVED,
                target_type="project",
                target_id=project.id,
                details=details,
            )
            return await self._summary(session, project)

    async def project_details(self, *, actor: ActorContext, project_slug: str) -> ProjectDetails:
        """Return current participants and basic historical project indicators."""

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
            membership_count = await session.scalar(
                select(func.count(ProjectMembership.id)).where(
                    ProjectMembership.project_id == project.id
                )
            )
            session_count = await session.scalar(
                select(func.count(DailySession.id)).where(DailySession.project_id == project.id)
            )
            return ProjectDetails(
                summary=await self._summary(session, project),
                active_members=tuple(self._member_summary(item) for item in memberships),
                membership_count=int(membership_count or 0),
                session_count=int(session_count or 0),
            )

    async def list_member_projects(
        self, *, actor: ActorContext, user_id: int
    ) -> tuple[ProjectSummary, ...]:
        """List active projects currently associated with one guild member."""

        if user_id <= 0:
            raise ValidationError("O membro informado é inválido.")
        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            projects = (
                await session.scalars(
                    select(Project)
                    .join(ProjectMembership)
                    .where(
                        Project.guild_id == guild.id,
                        Project.status == ProjectStatus.ACTIVE,
                        ProjectMembership.discord_user_id == user_id,
                        ProjectMembership.left_at.is_(None),
                    )
                    .order_by(Project.name, Project.id)
                )
            ).all()
            return tuple([await self._summary(session, project) for project in projects])

    async def list_projects(self, *, actor: ActorContext) -> tuple[ProjectSummary, ...]:
        """List guild projects with their current active participant count."""

        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            projects = (
                await session.scalars(
                    select(Project)
                    .where(Project.guild_id == guild.id)
                    .order_by(Project.name, Project.id)
                )
            ).all()
            return tuple([await self._summary(session, project) for project in projects])

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
                if project.status == ProjectStatus.ARCHIVED:
                    raise ConflictError("Não é possível adicionar membros a um projeto arquivado.")
                active = await session.scalar(
                    select(ProjectMembership.id).where(
                        ProjectMembership.project_id == project.id,
                        ProjectMembership.discord_user_id == user_id,
                        ProjectMembership.left_at.is_(None),
                    )
                )
                if active is not None:
                    raise ConflictError("Este membro já participa ativamente do projeto.")
                membership = ProjectMembership(
                    project_id=project.id,
                    discord_user_id=user_id,
                    display_name=clean_display_name,
                    joined_at=now,
                    left_at=None,
                )
                session.add(membership)
                await session.flush()
                append_audit_event(
                    session,
                    guild=guild,
                    actor=actor,
                    action=AuditAction.MEMBER_ADDED,
                    target_type="project_membership",
                    target_id=user_id,
                    details={"project_id": project.id, "user_id": user_id},
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
            append_audit_event(
                session,
                guild=guild,
                actor=actor,
                action=AuditAction.MEMBER_REMOVED,
                target_type="project_membership",
                target_id=user_id,
                details={"project_id": project.id, "user_id": user_id},
            )

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
            return tuple(self._member_summary(membership) for membership in memberships)

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
    async def _project_by_slug(
        session: AsyncSession, guild: Guild, slug: str, *, lock: bool = False
    ) -> Project:
        statement = select(Project).where(
            Project.guild_id == guild.id,
            Project.slug == slug.strip().lower(),
        )
        if lock:
            statement = statement.with_for_update()
        project = await session.scalar(statement)
        if project is None:
            raise NotFoundError("Projeto não encontrado neste servidor.")
        return project

    @staticmethod
    def _validate_project_input(name: str, channel_id: int) -> str:
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 100 or not project_slug(clean_name):
            raise ValidationError("Informe um nome de projeto válido com até 100 caracteres.")
        if channel_id <= 0:
            raise ValidationError("O canal informado é inválido.")
        return clean_name

    @staticmethod
    async def _summary(session: AsyncSession, project: Project) -> ProjectSummary:
        count = await session.scalar(
            select(func.count(ProjectMembership.id)).where(
                ProjectMembership.project_id == project.id,
                ProjectMembership.left_at.is_(None),
            )
        )
        return ProjectSummary(
            name=project.name,
            slug=project.slug,
            channel_id=project.discord_channel_id,
            status=project.status.value,
            daily_enabled=project.daily_enabled,
            participant_count=int(count or 0),
        )

    @staticmethod
    def _member_summary(membership: ProjectMembership) -> MemberSummary:
        return MemberSummary(
            user_id=membership.discord_user_id,
            display_name=membership.display_name,
            joined_at=membership.joined_at,
        )

    @staticmethod
    def _project_audit_details(project: Project) -> dict[str, object]:
        return {
            "name": project.name,
            "slug": project.slug,
            "channel_id": project.discord_channel_id,
            "status": project.status.value,
            "daily_enabled": project.daily_enabled,
        }
