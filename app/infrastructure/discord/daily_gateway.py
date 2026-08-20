"""Discord adapter for automatic daily publications."""

from typing import Protocol, cast

import discord

from app.application.daily_dto import ClosedDaily, OpenedDaily, PreparedReminder
from app.bot.contracts import DailyPresentationService
from app.bot.embeds.daily import render_daily_panel
from app.bot.views.daily import DailyResponseView
from app.domain.enums import NotificationKind


class AutomaticNotificationService(Protocol):
    """Persistence operation required after publishing a reminder."""

    async def attach_notification(self, notification_id: int, message_id: int) -> None: ...


class DiscordDailyGatewayError(RuntimeError):
    """Safe operational error containing no Discord response or private content."""


class DiscordDailyGateway:
    """Publish automatic daily stages through the configured Discord client."""

    def __init__(
        self,
        bot: discord.Client,
        daily_service: DailyPresentationService,
        automatic_service: AutomaticNotificationService,
    ) -> None:
        self._bot = bot
        self._daily_service = daily_service
        self._automatic_service = automatic_service

    async def publish_opened(self, opened: OpenedDaily) -> int:
        """Publish one main panel and persist its Discord message identifier."""

        if opened.message_id is not None:
            return opened.message_id
        channel = self._messageable(opened.channel_id, opened.panel.session_id, "send")
        mentions = " ".join(
            f"<@{participant.user_id}>" for participant in opened.panel.participants
        )
        try:
            message = await channel.send(
                content=mentions,
                embed=render_daily_panel(opened.panel),
                view=DailyResponseView(self._daily_service),
                allowed_mentions=_user_mentions_only(),
                nonce=_daily_nonce(opened.panel.session_id, "open"),
            )
            await self._daily_service.attach_message(
                session_id=opened.panel.session_id,
                message_id=message.id,
            )
        except Exception:
            raise DiscordDailyGatewayError(
                f"Falha ao publicar a sessão {opened.panel.session_id} no Discord."
            ) from None
        return message.id

    async def publish_reminder(self, reminder: PreparedReminder) -> int:
        """Publish a reminder to its pending snapshot and confirm the reservation."""

        channel = self._messageable(reminder.channel_id, reminder.session_id, "send")
        content = " ".join(f"<@{recipient.user_id}>" for recipient in reminder.recipients)
        if reminder.kind == NotificationKind.LAST_REMINDER:
            content = f"{content}\nÚltimo lembrete: esta daily será encerrada em breve."
        try:
            message = await channel.send(
                content=content,
                allowed_mentions=_user_mentions_only(),
                nonce=_daily_nonce(reminder.session_id, reminder.kind),
            )
            await self._automatic_service.attach_notification(
                notification_id=reminder.notification_id,
                message_id=message.id,
            )
        except Exception:
            raise DiscordDailyGatewayError(
                f"Falha ao publicar lembrete da sessão {reminder.session_id} no Discord."
            ) from None
        return message.id

    async def publish_closed(self, closed: ClosedDaily) -> None:
        """Replace the main panel with its final state and remove the response view."""

        if closed.message_id is None:
            raise DiscordDailyGatewayError(
                f"Mensagem principal ausente para a sessão {closed.panel.session_id}."
            )
        channel = self._messageable(closed.channel_id, closed.panel.session_id, "fetch_message")
        try:
            message = await channel.fetch_message(closed.message_id)
            await message.edit(
                embed=render_daily_panel(closed.panel),
                view=None,
            )
        except Exception:
            raise DiscordDailyGatewayError(
                f"Falha ao atualizar a sessão {closed.panel.session_id} no Discord."
            ) from None

    def _messageable(
        self,
        channel_id: int,
        session_id: int,
        operation: str,
    ) -> discord.abc.Messageable:
        channel = self._bot.get_channel(channel_id)
        if channel is None or not hasattr(channel, operation):
            raise DiscordDailyGatewayError(
                f"Canal Discord {channel_id} indisponível para a sessão {session_id}."
            )
        return cast(discord.abc.Messageable, channel)


def _user_mentions_only() -> discord.AllowedMentions:
    return discord.AllowedMentions(
        users=True,
        roles=False,
        everyone=False,
        replied_user=False,
    )


def _daily_nonce(session_id: int, stage: str | NotificationKind) -> int:
    stage_code = {
        "open": 1,
        NotificationKind.FIRST_REMINDER: 2,
        NotificationKind.LAST_REMINDER: 3,
    }[stage]
    return session_id * 10 + stage_code
