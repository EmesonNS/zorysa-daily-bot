"""Discord adapter for paginated daily report publication."""

from collections.abc import Callable
from typing import Protocol, cast

import discord

from app.application.report_dto import DailyReport, PreparedDailyReport
from app.bot.embeds.report import render_daily_report


class ReportDeliveryService(Protocol):
    async def attach_delivery(self, delivery_id: int, *, page_count: int) -> None: ...


class DiscordReportGatewayError(RuntimeError):
    """Safe report publication error containing only operational IDs."""


class DiscordReportGateway:
    """Publish all report pages and confirm delivery only after completion."""

    def __init__(self, bot: discord.Client, service: ReportDeliveryService) -> None:
        self._bot = bot
        self._service = service
        self._renderer: Callable[[DailyReport], tuple[discord.Embed, ...]] = render_daily_report

    async def publish(self, prepared: PreparedDailyReport) -> int:
        channel = self._bot.get_channel(prepared.channel_id)
        if channel is None or not hasattr(channel, "send"):
            raise DiscordReportGatewayError(
                f"Canal Discord {prepared.channel_id} indisponível para "
                f"a entrega {prepared.delivery_id}."
            )
        messageable = cast(discord.abc.Messageable, channel)
        pages = self._renderer(prepared.report)
        try:
            for page_number, page in enumerate(pages, start=1):
                await messageable.send(
                    embed=page,
                    allowed_mentions=discord.AllowedMentions.none(),
                    nonce=_report_nonce(prepared.delivery_id, page_number),
                )
            await self._service.attach_delivery(
                prepared.delivery_id,
                page_count=len(pages),
            )
        except Exception:
            raise DiscordReportGatewayError(
                f"Falha na entrega {prepared.delivery_id} ao canal {prepared.channel_id}."
            ) from None
        return len(pages)

    async def publish_all(
        self, prepared_reports: tuple[PreparedDailyReport, ...]
    ) -> tuple[DiscordReportGatewayError, ...]:
        errors: list[DiscordReportGatewayError] = []
        for prepared in prepared_reports:
            try:
                await self.publish(prepared)
            except DiscordReportGatewayError as error:
                errors.append(error)
        return tuple(errors)


def _report_nonce(delivery_id: int, page_number: int) -> int:
    return (delivery_id << 16) + page_number
