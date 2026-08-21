"""Administrative justified-absence workflow."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.audit import append_audit_event
from app.application.daily import DailyService
from app.application.daily_dto import JustifiedDaily
from app.application.dto import ActorContext
from app.application.errors import ConflictError, NotFoundError, ValidationError
from app.application.guild_admin import authorize_admin, ensure_guild_record
from app.domain.enums import AssignmentStatus, AuditAction
from app.infrastructure.database.models import (
    DailyAssignment,
    DailySession,
    Guild,
    GuildSettings,
    Project,
)


class AbsenceService:
    """Justify one snapshotted participant without exposing the private reason."""

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

    async def justify(
        self,
        *,
        actor: ActorContext,
        project_slug: str,
        user_id: int,
        local_date: date | None,
        reason: str,
    ) -> JustifiedDaily:
        """Set or update EXCUSED metadata before or after daily closure."""

        clean_reason = reason.strip()
        if not clean_reason or len(clean_reason) > 1000:
            raise ValidationError("Informe um motivo de ausência com até 1000 caracteres.")
        if user_id <= 0:
            raise ValidationError("O participante informado é inválido.")

        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            if local_date is None:
                timezone = await session.scalar(
                    select(GuildSettings.timezone).where(GuildSettings.guild_id == guild.id)
                )
                local_date = self._now().astimezone(ZoneInfo(timezone or self._timezone)).date()
            row = (
                await session.execute(
                    select(DailyAssignment, DailySession, Project)
                    .join(DailySession, DailySession.id == DailyAssignment.session_id)
                    .join(Project, Project.id == DailySession.project_id)
                    .where(
                        Project.guild_id == guild.id,
                        Project.slug == project_slug.strip().lower(),
                        DailySession.session_date == local_date,
                        DailyAssignment.discord_user_id == user_id,
                    )
                    .with_for_update(of=DailyAssignment)
                )
            ).one_or_none()
            if row is None:
                raise NotFoundError("Participante ou daily não encontrado para a data informada.")
            assignment, daily_session, project = row
            if assignment.status == AssignmentStatus.ANSWERED:
                raise ConflictError("Este participante já respondeu a daily.")
            if assignment.status not in {
                AssignmentStatus.PENDING,
                AssignmentStatus.NOT_ANSWERED,
                AssignmentStatus.EXCUSED,
            }:
                raise ConflictError("O estado deste participante não permite justificativa.")

            assignment.status = AssignmentStatus.EXCUSED
            assignment.excused_at = self._now()
            assignment.excused_by_user_id = actor.user_id
            assignment.excuse_reason = clean_reason
            await session.flush()
            append_audit_event(
                session,
                guild=guild,
                actor=actor,
                action=AuditAction.ABSENCE_JUSTIFIED,
                target_type="daily_assignment",
                target_id=assignment.id,
                details={
                    "project_id": project.id,
                    "session_id": daily_session.id,
                    "user_id": user_id,
                    "session_date": daily_session.session_date.isoformat(),
                },
            )
            return JustifiedDaily(
                panel=await DailyService._panel(session, daily_session, project.name),
                channel_id=project.discord_channel_id,
                message_id=daily_session.message_id,
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

    def _now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
