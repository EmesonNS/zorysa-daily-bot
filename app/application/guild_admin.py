"""Guild initialization and administrator-role application service."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto import ActorContext, AdminRoleSummary
from app.application.errors import AuthorizationError, ConflictError
from app.infrastructure.database.models import (
    AdminRole,
    DailyQuestion,
    Guild,
    GuildExecutionDay,
    GuildSettings,
)

DEFAULT_DAILY_QUESTIONS: tuple[str, ...] = (
    "O que você fez desde a última daily?",
    "O que pretende fazer hoje?",
    "Possui algum impedimento?",
    "Alguma observação importante?",
)


async def ensure_guild_record(
    session: AsyncSession,
    *,
    discord_guild_id: int,
    guild_name: str,
    timezone: str,
) -> Guild:
    """Return the guild, creating its settings and default questions once."""

    guild = await session.scalar(select(Guild).where(Guild.discord_guild_id == discord_guild_id))
    if guild is not None:
        if guild.name != guild_name:
            guild.name = guild_name
        return guild

    guild = Guild(discord_guild_id=discord_guild_id, name=guild_name)
    guild.settings = GuildSettings(timezone=timezone)
    guild.questions = [
        DailyQuestion(text=text, position=position, required=True, active=True)
        for position, text in enumerate(DEFAULT_DAILY_QUESTIONS, start=1)
    ]
    guild.execution_days = [GuildExecutionDay(weekday=weekday) for weekday in range(5)]
    session.add(guild)
    await session.flush()
    return guild


async def authorize_admin(
    session: AsyncSession, *, guild: Guild, actor: ActorContext
) -> tuple[int, ...]:
    """Enforce bootstrap permissions, then configured-role-only permissions."""

    configured = tuple(
        (
            await session.scalars(
                select(AdminRole.discord_role_id).where(AdminRole.guild_id == guild.id)
            )
        ).all()
    )
    if configured:
        if set(configured).isdisjoint(actor.role_ids):
            raise AuthorizationError(
                "Você não possui um cargo administrativo configurado neste servidor."
            )
    elif not (actor.is_guild_owner or actor.can_manage_guild):
        raise AuthorizationError(
            "Somente o dono do servidor ou alguém com Gerenciar Servidor pode "
            "configurar o primeiro cargo administrativo."
        )
    return configured


class GuildAdminService:
    """Initialize guild configuration and maintain administrator roles."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        timezone: str = "America/Belem",
    ) -> None:
        self._sessions = sessions
        self._timezone = timezone

    async def ensure_guild(self, *, discord_guild_id: int, guild_name: str) -> None:
        """Initialize a guild with settings and the four default questions."""

        try:
            async with self._sessions() as session, session.begin():
                await ensure_guild_record(
                    session,
                    discord_guild_id=discord_guild_id,
                    guild_name=guild_name,
                    timezone=self._timezone,
                )
        except IntegrityError as error:
            raise ConflictError(
                "O servidor já está sendo inicializado; tente novamente."
            ) from error

    async def add_admin_role(self, *, actor: ActorContext, role_id: int) -> AdminRoleSummary:
        """Add an administrator role after applying the bootstrap rule."""

        if role_id <= 0:
            raise ConflictError("O cargo informado é inválido.")
        try:
            async with self._sessions() as session, session.begin():
                guild = await self._guild_for_actor(session, actor)
                await authorize_admin(session, guild=guild, actor=actor)
                existing = await session.scalar(
                    select(AdminRole.id).where(
                        AdminRole.guild_id == guild.id,
                        AdminRole.discord_role_id == role_id,
                    )
                )
                if existing is not None:
                    raise ConflictError("Este cargo já é administrador do bot.")
                session.add(AdminRole(guild_id=guild.id, discord_role_id=role_id))
        except IntegrityError as error:
            raise ConflictError("Este cargo já é administrador do bot.") from error
        return AdminRoleSummary(role_id=role_id)

    async def remove_admin_role(self, *, actor: ActorContext, role_id: int) -> None:
        """Remove a role while keeping at least one configured administrator role."""

        async with self._sessions() as session, session.begin():
            guild = await self._guild_for_actor(session, actor)
            configured = await authorize_admin(session, guild=guild, actor=actor)
            role = await session.scalar(
                select(AdminRole).where(
                    AdminRole.guild_id == guild.id,
                    AdminRole.discord_role_id == role_id,
                )
            )
            if role is None:
                raise ConflictError("Este cargo não está configurado como administrador.")
            if len(configured) == 1:
                raise ConflictError("Não é possível remover o último cargo administrativo.")
            await session.delete(role)

    async def list_admin_roles(self, *, actor: ActorContext) -> tuple[AdminRoleSummary, ...]:
        """List configured administrator roles in stable order."""

        async with self._sessions() as session, session.begin():
            guild = await self._guild_for_actor(session, actor)
            await authorize_admin(session, guild=guild, actor=actor)
            role_ids: Sequence[int] = (
                await session.scalars(
                    select(AdminRole.discord_role_id)
                    .where(AdminRole.guild_id == guild.id)
                    .order_by(AdminRole.discord_role_id)
                )
            ).all()
            return tuple(AdminRoleSummary(role_id=value) for value in role_ids)

    async def _guild_for_actor(self, session: AsyncSession, actor: ActorContext) -> Guild:
        return await ensure_guild_record(
            session,
            discord_guild_id=actor.guild_id,
            guild_name=actor.guild_name,
            timezone=self._timezone,
        )


async def count_admin_roles(session: AsyncSession, *, guild_id: int) -> int:
    """Return the role count for diagnostics and service-level tests."""

    return int(
        await session.scalar(select(func.count(AdminRole.id)).where(AdminRole.guild_id == guild_id))
        or 0
    )
