"""Discord adapter for paginated automatic and manual report publication."""

from collections.abc import Callable
from typing import Protocol, cast

import discord

from app.application.report_dto import (
    DailyReport,
    HistoricalReport,
    PreparedDailyReport,
    PreparedReport,
)
from app.bot.embeds.report import render_daily_report, render_report


class ReportDeliveryService(Protocol):
    async def attach_delivery(self, delivery_id: int, *, page_count: int) -> None: ...


class DiscordReportGatewayError(RuntimeError):
    """Safe report publication error containing only operational IDs."""


class DiscordReportGateway:
    """Publish complete paginated reports with deterministic nonces."""

    def __init__(self, bot: discord.Client, service: ReportDeliveryService) -> None:
        self._bot = bot
        self._service = service
        self._renderer: Callable[[DailyReport], tuple[discord.Embed, ...]] = render_daily_report
        self._historical_renderer: Callable[[HistoricalReport], tuple[discord.Embed, ...]] = (
            render_report
        )

    async def publish(self, prepared: PreparedDailyReport) -> int:
        """Preserve automatic publication for the legacy daily contract."""

        messageable = self._messageable(
            prepared.channel_id,
            unavailable=(
                f"Canal Discord {prepared.channel_id} indisponível para "
                f"a entrega {prepared.delivery_id}."
            ),
        )
        pages = self._renderer(prepared.report)
        try:
            await self._send_pages(
                messageable,
                pages,
                nonce=lambda page: _report_nonce(prepared.delivery_id, page),
            )
            await self._service.attach_delivery(prepared.delivery_id, page_count=len(pages))
        except Exception:
            raise DiscordReportGatewayError(
                f"Falha na entrega {prepared.delivery_id} ao canal {prepared.channel_id}."
            ) from None
        return len(pages)

    async def publish_report(self, prepared: PreparedReport) -> int:
        """Publish and confirm one typed automatic historical delivery."""

        kind = prepared.report.kind.value
        messageable = self._messageable(
            prepared.channel_id,
            unavailable=(
                f"Canal Discord {prepared.channel_id} indisponível para a entrega "
                f"{prepared.delivery_id} do relatório {kind}."
            ),
        )
        pages = self._historical_renderer(prepared.report)
        try:
            await self._send_pages(
                messageable,
                pages,
                nonce=lambda page: _report_nonce(prepared.delivery_id, page),
            )
            await self._service.attach_delivery(prepared.delivery_id, page_count=len(pages))
        except Exception:
            raise DiscordReportGatewayError(
                f"Falha no relatório {kind}, entrega {prepared.delivery_id}, "
                f"canal {prepared.channel_id}."
            ) from None
        return len(pages)

    async def publish_manual(
        self,
        *,
        channel_id: int,
        request_id: int,
        report: HistoricalReport,
    ) -> int:
        """Publish a repeatable manual request without creating delivery state."""

        kind = report.kind.value
        messageable = self._messageable(
            channel_id,
            unavailable=(
                f"Canal Discord {channel_id} indisponível para a solicitação "
                f"{request_id} do relatório {kind}."
            ),
        )
        pages = self._historical_renderer(report)
        try:
            await self._send_pages(
                messageable,
                pages,
                nonce=lambda page: _manual_nonce(request_id, page),
            )
        except Exception:
            raise DiscordReportGatewayError(
                f"Falha no relatório {kind}, solicitação {request_id}, canal {channel_id}."
            ) from None
        return len(pages)

    async def publish_all(
        self, prepared_reports: tuple[PreparedDailyReport, ...]
    ) -> tuple[DiscordReportGatewayError, ...]:
        """Publish legacy daily destinations while isolating failures."""

        errors: list[DiscordReportGatewayError] = []
        for prepared in prepared_reports:
            try:
                await self.publish(prepared)
            except DiscordReportGatewayError as error:
                errors.append(error)
        return tuple(errors)

    async def publish_all_reports(
        self, prepared_reports: tuple[PreparedReport, ...]
    ) -> tuple[DiscordReportGatewayError, ...]:
        """Publish historical destinations while isolating failures."""

        errors: list[DiscordReportGatewayError] = []
        for prepared in prepared_reports:
            try:
                await self.publish_report(prepared)
            except DiscordReportGatewayError as error:
                errors.append(error)
        return tuple(errors)

    def _messageable(self, channel_id: int, *, unavailable: str) -> discord.abc.Messageable:
        channel = self._bot.get_channel(channel_id)
        if channel is None or not hasattr(channel, "send"):
            raise DiscordReportGatewayError(unavailable)
        return cast(discord.abc.Messageable, channel)

    @staticmethod
    async def _send_pages(
        messageable: discord.abc.Messageable,
        pages: tuple[discord.Embed, ...],
        *,
        nonce: Callable[[int], int | str],
    ) -> None:
        for page_number, page in enumerate(pages, start=1):
            await messageable.send(
                embed=page,
                allowed_mentions=discord.AllowedMentions.none(),
                nonce=nonce(page_number),
            )


def _report_nonce(delivery_id: int, page_number: int) -> int:
    return (delivery_id << 16) + page_number


def _manual_nonce(request_id: int, page_number: int) -> str:
    return f"m{request_id:x}-{page_number:x}"
