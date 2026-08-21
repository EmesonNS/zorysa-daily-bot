"""Guild-scoped report destination administration."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.audit import append_audit_event
from app.application.dto import ActorContext, ReportChannelSummary
from app.application.errors import ConflictError, NotFoundError, ValidationError
from app.application.guild_admin import authorize_admin, ensure_guild_record
from app.domain.enums import AuditAction
from app.infrastructure.database.models import Guild, ReportChannel


class ReportChannelService:
    """List, upsert, and remove typed report destinations."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        timezone: str = "America/Belem",
    ) -> None:
        self._sessions = sessions
        self._timezone = timezone

    async def list_channels(self, *, actor: ActorContext) -> tuple[ReportChannelSummary, ...]:
        """List this guild's report destinations in channel ID order."""

        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            channels = (
                await session.scalars(
                    select(ReportChannel)
                    .where(ReportChannel.guild_id == guild.id)
                    .order_by(ReportChannel.discord_channel_id, ReportChannel.id)
                )
            ).all()
            return tuple(self._summary(channel) for channel in channels)

    async def save_channel(
        self,
        *,
        actor: ActorContext,
        channel_id: int,
        daily: bool,
        weekly: bool,
        monthly: bool,
    ) -> ReportChannelSummary:
        """Create or update one channel's enabled report types."""

        self._validate(channel_id, daily=daily, weekly=weekly, monthly=monthly)
        try:
            async with self._sessions() as session, session.begin():
                guild = await self._authorized_guild(session, actor)
                channel = await session.scalar(
                    select(ReportChannel)
                    .where(
                        ReportChannel.guild_id == guild.id,
                        ReportChannel.discord_channel_id == channel_id,
                    )
                    .with_for_update()
                )
                if channel is None:
                    channel = ReportChannel(
                        guild_id=guild.id,
                        discord_channel_id=channel_id,
                        daily_enabled=daily,
                        weekly_enabled=weekly,
                        monthly_enabled=monthly,
                    )
                    session.add(channel)
                else:
                    channel.daily_enabled = daily
                    channel.weekly_enabled = weekly
                    channel.monthly_enabled = monthly
                await session.flush()
                append_audit_event(
                    session,
                    guild=guild,
                    actor=actor,
                    action=AuditAction.REPORT_CHANNEL_SAVED,
                    target_type="report_channel",
                    target_id=channel_id,
                    details=self._audit_details(channel),
                )
                return self._summary(channel)
        except IntegrityError as error:
            raise ConflictError(
                "Este canal foi configurado em outra interação; tente novamente."
            ) from error

    async def remove_channel(self, *, actor: ActorContext, channel_id: int) -> None:
        """Remove only current configuration, preserving historical deliveries."""

        if channel_id <= 0:
            raise ValidationError("O canal de relatório informado é inválido.")
        async with self._sessions() as session, session.begin():
            guild = await self._authorized_guild(session, actor)
            channel = await session.scalar(
                select(ReportChannel).where(
                    ReportChannel.guild_id == guild.id,
                    ReportChannel.discord_channel_id == channel_id,
                )
            )
            if channel is None:
                raise NotFoundError("Este canal não está configurado para relatórios.")
            append_audit_event(
                session,
                guild=guild,
                actor=actor,
                action=AuditAction.REPORT_CHANNEL_REMOVED,
                target_type="report_channel",
                target_id=channel_id,
                details=self._audit_details(channel),
            )
            await session.delete(channel)

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
    def _validate(channel_id: int, *, daily: bool, weekly: bool, monthly: bool) -> None:
        if channel_id <= 0:
            raise ValidationError("O canal de relatório informado é inválido.")
        if not any((daily, weekly, monthly)):
            raise ValidationError("Habilite ao menos um tipo de relatório para este canal.")

    @staticmethod
    def _summary(channel: ReportChannel) -> ReportChannelSummary:
        return ReportChannelSummary(
            channel_id=channel.discord_channel_id,
            daily=channel.daily_enabled,
            weekly=channel.weekly_enabled,
            monthly=channel.monthly_enabled,
        )

    @staticmethod
    def _audit_details(channel: ReportChannel) -> dict[str, object]:
        return {
            "channel_id": channel.discord_channel_id,
            "daily": channel.daily_enabled,
            "weekly": channel.weekly_enabled,
            "monthly": channel.monthly_enabled,
        }
