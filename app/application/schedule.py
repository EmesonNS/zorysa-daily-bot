"""Guild schedule configuration with post-commit reconciliation."""

import re
from datetime import time
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto import ActorContext, ScheduleSummary
from app.application.errors import ConflictError, ValidationError
from app.application.guild_admin import authorize_admin, ensure_guild_record
from app.infrastructure.database.models import Guild, GuildExecutionDay, GuildSettings

_TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


class ScheduleReloader(Protocol):
    """Refresh in-memory jobs after a schedule is committed."""

    async def reconcile_guild(self, discord_guild_id: int) -> None: ...


class ScheduleService:
    """Read and mutate one guild's automatic daily schedule."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        timezone: str = "America/Belem",
        reloader: ScheduleReloader | None = None,
    ) -> None:
        self._sessions = sessions
        self._default_timezone = timezone
        self._reloader = reloader

    def bind_reloader(self, reloader: ScheduleReloader) -> None:
        """Bind the scheduler after the Discord client composition is complete."""

        if self._reloader is not None:
            raise ValueError("Schedule reloader is already configured")
        self._reloader = reloader

    async def get_schedule(self, *, actor: ActorContext) -> ScheduleSummary:
        """Return the authorized guild schedule."""

        async with self._sessions() as session, session.begin():
            guild, settings, days = await self._authorized_schedule(session, actor)
            del guild
            return self._summary(settings, days)

    async def update_times(
        self,
        *,
        actor: ActorContext,
        opening: str,
        first_reminder: str,
        last_reminder: str,
        closing: str,
        reporting: str,
    ) -> ScheduleSummary:
        """Change all stages atomically after validating their strict order."""

        parsed = tuple(
            self._parse_time(value)
            for value in (opening, first_reminder, last_reminder, closing, reporting)
        )
        if not parsed[0] < parsed[1] < parsed[2] < parsed[3] < parsed[4]:
            raise ValidationError(
                "Os horários devem seguir abertura < primeiro lembrete < "
                "último lembrete < fechamento < relatório."
            )

        async with self._sessions() as session, session.begin():
            guild, settings, days = await self._authorized_schedule(session, actor)
            (
                settings.daily_open_time,
                settings.first_reminder_time,
                settings.last_reminder_time,
                settings.daily_close_time,
                settings.daily_report_time,
            ) = parsed
            result = self._summary(settings, days)
            discord_guild_id = guild.discord_guild_id
        await self._reload(discord_guild_id)
        return result

    async def update_timezone(self, *, actor: ActorContext, timezone: str) -> ScheduleSummary:
        """Change the guild timezone after validating an IANA identifier."""

        clean_timezone = timezone.strip()
        try:
            ZoneInfo(clean_timezone)
        except (ValueError, ZoneInfoNotFoundError) as error:
            raise ValidationError("Informe um timezone IANA válido, como America/Belem.") from error

        async with self._sessions() as session, session.begin():
            guild, settings, days = await self._authorized_schedule(session, actor)
            settings.timezone = clean_timezone
            result = self._summary(settings, days)
            discord_guild_id = guild.discord_guild_id
        await self._reload(discord_guild_id)
        return result

    async def add_execution_day(self, *, actor: ActorContext, weekday: int) -> ScheduleSummary:
        """Enable one ISO weekday for automatic dailies."""

        self._validate_weekday(weekday)
        async with self._sessions() as session, session.begin():
            guild, settings, days = await self._authorized_schedule(session, actor)
            if weekday in days:
                raise ConflictError("Este dia da semana já está configurado na agenda.")
            session.add(GuildExecutionDay(guild_id=guild.id, weekday=weekday))
            updated_days = tuple(sorted((*days, weekday)))
            result = self._summary(settings, updated_days)
            discord_guild_id = guild.discord_guild_id
        await self._reload(discord_guild_id)
        return result

    async def remove_execution_day(self, *, actor: ActorContext, weekday: int) -> ScheduleSummary:
        """Disable one weekday while preserving at least one execution day."""

        self._validate_weekday(weekday)
        async with self._sessions() as session, session.begin():
            guild, settings, days = await self._authorized_schedule(session, actor)
            if weekday not in days:
                raise ConflictError("Este dia da semana não está configurado na agenda.")
            if len(days) == 1:
                raise ConflictError("Não é possível remover o último dia de execução.")
            execution_day = await session.get(GuildExecutionDay, (guild.id, weekday))
            if execution_day is None:
                raise ConflictError("Este dia da semana não está configurado na agenda.")
            await session.delete(execution_day)
            updated_days = tuple(day for day in days if day != weekday)
            result = self._summary(settings, updated_days)
            discord_guild_id = guild.discord_guild_id
        await self._reload(discord_guild_id)
        return result

    async def _authorized_schedule(
        self, session: AsyncSession, actor: ActorContext
    ) -> tuple[Guild, GuildSettings, tuple[int, ...]]:
        guild = await ensure_guild_record(
            session,
            discord_guild_id=actor.guild_id,
            guild_name=actor.guild_name,
            timezone=self._default_timezone,
        )
        await authorize_admin(session, guild=guild, actor=actor)
        settings = await session.get(GuildSettings, guild.id)
        if settings is None:  # pragma: no cover - protected by the guild invariant
            raise RuntimeError("Guild settings are missing")
        days = tuple(
            (
                await session.scalars(
                    select(GuildExecutionDay.weekday)
                    .where(GuildExecutionDay.guild_id == guild.id)
                    .order_by(GuildExecutionDay.weekday)
                )
            ).all()
        )
        return guild, settings, days

    async def _reload(self, discord_guild_id: int) -> None:
        if self._reloader is not None:
            await self._reloader.reconcile_guild(discord_guild_id)

    @staticmethod
    def _parse_time(value: str) -> time:
        if not _TIME_PATTERN.fullmatch(value):
            raise ValidationError("Informe todos os horários no formato HH:MM.")
        try:
            return time.fromisoformat(value)
        except ValueError as error:
            raise ValidationError("Informe todos os horários no formato HH:MM.") from error

    @staticmethod
    def _validate_weekday(weekday: int) -> None:
        if weekday < 0 or weekday > 6:
            raise ValidationError("Informe um dia da semana entre segunda e domingo.")

    @staticmethod
    def _summary(settings: GuildSettings, days: tuple[int, ...]) -> ScheduleSummary:
        return ScheduleSummary(
            timezone=settings.timezone,
            daily_enabled=settings.daily_enabled,
            execution_days=days,
            opening=settings.daily_open_time,
            first_reminder=settings.first_reminder_time,
            last_reminder=settings.last_reminder_time,
            closing=settings.daily_close_time,
            reporting=settings.daily_report_time,
        )
