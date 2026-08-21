"""Public daily status and authorized manual closure workflows."""

from collections.abc import Callable
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.audit import append_audit_event
from app.application.daily import DailyService, _close_daily_session
from app.application.daily_dto import ClosedDaily, DailyPanel
from app.application.dto import ActorContext
from app.application.errors import NotFoundError, ValidationError
from app.application.guild_admin import authorize_admin, ensure_guild_record
from app.domain.enums import AuditAction
from app.infrastructure.database.models import DailySession, Guild, Project


class DailyManagementService:
    """Read public state and close one guild-scoped daily manually."""

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

    async def status(
        self,
        *,
        discord_guild_id: int,
        project_slug: str,
        local_date: date,
    ) -> DailyPanel:
        """Return the answer-free panel without requiring administrative access."""

        slug = self._validate_scope(discord_guild_id, project_slug)
        async with self._sessions() as session:
            row = await self._daily_row(
                session,
                discord_guild_id=discord_guild_id,
                project_slug=slug,
                local_date=local_date,
            )
            if row is None:
                raise NotFoundError("Daily não encontrada para o projeto e a data informados.")
            daily_session, project = row
            return await DailyService._panel(session, daily_session, project.name)

    async def close(
        self,
        *,
        actor: ActorContext,
        project_slug: str,
        local_date: date,
    ) -> ClosedDaily:
        """Close one daily idempotently and audit only its first state transition."""

        slug = self._validate_scope(actor.guild_id, project_slug)
        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            row = await self._daily_row(
                session,
                discord_guild_id=actor.guild_id,
                project_slug=slug,
                local_date=local_date,
                lock=True,
            )
            if row is None:
                raise NotFoundError("Daily não encontrada para o projeto e a data informados.")
            daily_session, project = row
            closed, transitioned = await _close_daily_session(
                session,
                daily_session=daily_session,
                project=project,
                closed_at=self._now(),
            )
            if transitioned:
                append_audit_event(
                    session,
                    guild=guild,
                    actor=actor,
                    action=AuditAction.DAILY_CLOSED_MANUALLY,
                    target_type="daily_session",
                    target_id=daily_session.id,
                    details={
                        "project_id": project.id,
                        "session_date": daily_session.session_date.isoformat(),
                    },
                )
            return closed

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
    async def _daily_row(
        session: AsyncSession,
        *,
        discord_guild_id: int,
        project_slug: str,
        local_date: date,
        lock: bool = False,
    ) -> tuple[DailySession, Project] | None:
        statement = (
            select(DailySession, Project)
            .join(Project, Project.id == DailySession.project_id)
            .join(Guild, Guild.id == Project.guild_id)
            .where(
                Guild.discord_guild_id == discord_guild_id,
                Project.slug == project_slug,
                DailySession.session_date == local_date,
            )
        )
        if lock:
            statement = statement.with_for_update(of=DailySession)
        row = (await session.execute(statement)).one_or_none()
        return None if row is None else (row[0], row[1])

    @staticmethod
    def _validate_scope(discord_guild_id: int, project_slug: str) -> str:
        slug = project_slug.strip().lower()
        if discord_guild_id <= 0 or not slug:
            raise ValidationError("Informe um servidor e um projeto válidos.")
        return slug

    def _now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
