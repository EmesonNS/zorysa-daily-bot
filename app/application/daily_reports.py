"""Backward-compatible daily report façade over historical aggregation."""

from collections.abc import Callable
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.historical_reports import (
    HistoricalReportService,
    as_daily_report,
    calculate_metrics,
)
from app.application.report_dto import DailyReport, PreparedDailyReport, ReportPeriod
from app.domain.enums import ReportKind

__all__ = ["DailyReportService", "calculate_metrics"]


class DailyReportService:
    """Preserve the M3 daily API while delegating to the M4 aggregator."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._historical = HistoricalReportService(sessions, clock=clock)

    async def build_report(self, discord_guild_id: int, report_date: date) -> DailyReport:
        period = ReportPeriod(
            ReportKind.DAILY,
            report_date,
            report_date,
            report_date.strftime("%d/%m/%Y"),
        )
        report = await self._historical.build_report(discord_guild_id, ReportKind.DAILY, period)
        return as_daily_report(report)

    async def prepare_deliveries(
        self, discord_guild_id: int, report_date: date
    ) -> tuple[PreparedDailyReport, ...]:
        prepared = await self._historical.prepare_deliveries(
            discord_guild_id, ReportKind.DAILY, report_date
        )
        return tuple(
            PreparedDailyReport(item.delivery_id, item.channel_id, as_daily_report(item.report))
            for item in prepared
        )

    async def attach_delivery(self, delivery_id: int, *, page_count: int) -> None:
        await self._historical.attach_delivery(delivery_id, page_count=page_count)
