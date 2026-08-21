"""System workflow for Discord member departures."""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.audit import append_audit_event
from app.application.errors import ValidationError
from app.domain.enums import AuditAction
from app.infrastructure.database.models import Guild, Project, ProjectMembership


class MemberLifecycleService:
    """End current memberships when Discord reports that a member left a guild."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = sessions
        self._clock = clock or (lambda: datetime.now(UTC))

    async def leave_guild(self, discord_guild_id: int, discord_user_id: int) -> int:
        """Close every active membership in one guild and return the changed count."""

        if discord_guild_id <= 0 or discord_user_id <= 0:
            raise ValidationError("O servidor ou membro informado é inválido.")
        async with self._sessions() as session, session.begin():
            guild = await session.scalar(
                select(Guild).where(Guild.discord_guild_id == discord_guild_id)
            )
            if guild is None:
                return 0
            memberships = (
                await session.scalars(
                    select(ProjectMembership)
                    .join(Project, Project.id == ProjectMembership.project_id)
                    .where(
                        Project.guild_id == guild.id,
                        ProjectMembership.discord_user_id == discord_user_id,
                        ProjectMembership.left_at.is_(None),
                    )
                    .with_for_update(of=ProjectMembership)
                )
            ).all()
            if not memberships:
                return 0
            left_at = self._now()
            for membership in memberships:
                membership.left_at = left_at
            append_audit_event(
                session,
                guild=guild,
                actor=None,
                action=AuditAction.MEMBER_LEFT_GUILD,
                target_type="member",
                target_id=discord_user_id,
                details={"membership_count": len(memberships)},
            )
            return len(memberships)

    def _now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
