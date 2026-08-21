from datetime import date
from types import SimpleNamespace

import pytest

from app.application.historical_reports import as_daily_report, report_kind_enabled
from app.application.report_dto import (
    DailyReportMetrics,
    HistoricalReport,
    HistoricalReportEntry,
    HistoricalReportProject,
    ReportPeriod,
)
from app.domain.enums import AssignmentStatus, ReportKind


def _report(kind: ReportKind = ReportKind.DAILY) -> HistoricalReport:
    period = ReportPeriod(kind, date(2026, 8, 21), date(2026, 8, 21), "21/08/2026")
    metrics = DailyReportMetrics(1, 1, 1, 1, 0, 0, 100.0)
    entry = HistoricalReportEntry(
        local_date=date(2026, 8, 21),
        user_id=10,
        display_name="Ada",
        status=AssignmentStatus.ANSWERED,
        answers=(),
    )
    return HistoricalReport(
        kind=kind,
        period=period,
        metrics=metrics,
        projects=(HistoricalReportProject("Alpha", "alpha", (entry,)),),
    )


def test_daily_historical_report_converts_to_legacy_contract() -> None:
    report = as_daily_report(_report())

    assert report.report_date == date(2026, 8, 21)
    assert report.projects[0].name == "Alpha"
    assert report.projects[0].participants[0].display_name == "Ada"


@pytest.mark.parametrize("kind", [ReportKind.WEEKLY, ReportKind.MONTHLY])
def test_non_daily_report_cannot_convert_to_legacy_contract(kind: ReportKind) -> None:
    with pytest.raises(ValueError, match="daily"):
        as_daily_report(_report(kind))


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (ReportKind.DAILY, True),
        (ReportKind.WEEKLY, False),
        (ReportKind.MONTHLY, True),
    ],
)
def test_report_kind_selects_only_its_channel_flag(kind: ReportKind, expected: bool) -> None:
    channel = SimpleNamespace(
        daily_enabled=True,
        weekly_enabled=False,
        monthly_enabled=True,
    )

    assert report_kind_enabled(kind, channel) is expected
