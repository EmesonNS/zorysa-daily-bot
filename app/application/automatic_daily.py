"""Automatic daily orchestration backed by persisted guild and project data."""

from collections.abc import Callable
from datetime import UTC, date, datetime

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.daily import DailyService, _open_project_session
from app.application.daily_dto import OpenedDaily
from app.application.errors import ValidationError
from app.domain.enums import ProjectStatus
from app.infrastructure.database.models import (
    DailySession,
    Guild,
    Project,
    ProjectMembership,
)


class AutomaticDailyService:
    """Open eligible project sessions without an administrative actor."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = sessions
        self._clock = clock or (lambda: datetime.now(UTC))

    async def open_guild(self, discord_guild_id: int, local_date: date) -> tuple[OpenedDaily, ...]:
        """Open or reuse every eligible project session for one guild and date."""

        project_ids = await self._eligible_project_ids(discord_guild_id)
        opened: list[OpenedDaily] = []
        for project_id in project_ids:
            result = await self._open_project(discord_guild_id, project_id, local_date)
            if result is not None:
                opened.append(result)
        return tuple(opened)

    async def _eligible_project_ids(self, discord_guild_id: int) -> tuple[int, ...]:
        has_active_member = exists(
            select(ProjectMembership.id).where(
                ProjectMembership.project_id == Project.id,
                ProjectMembership.left_at.is_(None),
            )
        )
        async with self._sessions() as session:
            values = (
                await session.scalars(
                    select(Project.id)
                    .join(Guild, Guild.id == Project.guild_id)
                    .where(
                        Guild.discord_guild_id == discord_guild_id,
                        Project.status == ProjectStatus.ACTIVE,
                        Project.daily_enabled.is_(True),
                        has_active_member,
                    )
                    .order_by(Project.name, Project.id)
                )
            ).all()
            return tuple(values)

    async def _open_project(
        self, discord_guild_id: int, project_id: int, local_date: date
    ) -> OpenedDaily | None:
        try:
            async with self._sessions() as session, session.begin():
                row = (
                    await session.execute(
                        select(Guild, Project)
                        .join(Project, Project.guild_id == Guild.id)
                        .where(
                            Guild.discord_guild_id == discord_guild_id,
                            Project.id == project_id,
                            Project.status == ProjectStatus.ACTIVE,
                            Project.daily_enabled.is_(True),
                        )
                    )
                ).one_or_none()
                if row is None:
                    return None
                guild, project = row
                return await _open_project_session(
                    session,
                    guild=guild,
                    project=project,
                    local_date=local_date,
                    opened_at=self._now(),
                )
        except ValidationError:
            return None
        except IntegrityError:
            return await self._persisted_session(discord_guild_id, project_id, local_date)

    async def _persisted_session(
        self, discord_guild_id: int, project_id: int, local_date: date
    ) -> OpenedDaily:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(DailySession, Project)
                    .join(Project, Project.id == DailySession.project_id)
                    .join(Guild, Guild.id == Project.guild_id)
                    .where(
                        Guild.discord_guild_id == discord_guild_id,
                        Project.id == project_id,
                        DailySession.session_date == local_date,
                    )
                )
            ).one()
            daily_session, project = row
            return OpenedDaily(
                panel=await DailyService._panel(session, daily_session, project.name),
                channel_id=project.discord_channel_id,
                message_id=daily_session.message_id,
            )

    def _now(self) -> datetime:
        value = self._clock()
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
