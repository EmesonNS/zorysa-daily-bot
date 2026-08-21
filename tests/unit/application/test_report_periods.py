from datetime import date

import pytest

from app.application.errors import ValidationError
from app.application.report_periods import resolve_period
from app.domain.enums import ReportKind


def test_resolve_explicit_daily_period() -> None:
    period = resolve_period(ReportKind.DAILY, "2026-08-21", date(2030, 1, 1))

    assert period.kind == ReportKind.DAILY
    assert period.start == date(2026, 8, 21)
    assert period.end == date(2026, 8, 21)
    assert period.label == "21/08/2026"


def test_resolve_week_from_any_date_as_monday_through_sunday() -> None:
    period = resolve_period(ReportKind.WEEKLY, "2026-08-21", date(2030, 1, 1))

    assert period.start == date(2026, 8, 17)
    assert period.end == date(2026, 8, 23)
    assert period.label == "17/08/2026 a 23/08/2026"


def test_resolve_week_crossing_calendar_year() -> None:
    period = resolve_period(ReportKind.WEEKLY, "2026-01-01", date(2030, 1, 1))

    assert period.start == date(2025, 12, 29)
    assert period.end == date(2026, 1, 4)


def test_resolve_month_in_leap_year() -> None:
    period = resolve_period(ReportKind.MONTHLY, "2024-02", date(2030, 1, 1))

    assert period.start == date(2024, 2, 1)
    assert period.end == date(2024, 2, 29)
    assert period.label == "02/2024"


@pytest.mark.parametrize(
    ("kind", "expected_start", "expected_end"),
    [
        (ReportKind.DAILY, date(2026, 8, 21), date(2026, 8, 21)),
        (ReportKind.WEEKLY, date(2026, 8, 17), date(2026, 8, 23)),
        (ReportKind.MONTHLY, date(2026, 8, 1), date(2026, 8, 31)),
    ],
)
def test_omitted_period_uses_local_today(
    kind: ReportKind, expected_start: date, expected_end: date
) -> None:
    period = resolve_period(kind, None, date(2026, 8, 21))

    assert (period.start, period.end) == (expected_start, expected_end)


def test_blank_period_uses_local_today() -> None:
    period = resolve_period(ReportKind.MONTHLY, "  ", date(2026, 8, 21))

    assert (period.start, period.end) == (date(2026, 8, 1), date(2026, 8, 31))


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        (ReportKind.DAILY, "21/08/2026"),
        (ReportKind.DAILY, "2026-02-30"),
        (ReportKind.WEEKLY, "2026-W34"),
        (ReportKind.MONTHLY, "2026-13"),
    ],
)
def test_invalid_period_is_rejected_without_echoing_input(kind: ReportKind, value: str) -> None:
    with pytest.raises(ValidationError) as captured:
        resolve_period(kind, value, date(2026, 8, 21))

    assert value not in str(captured.value)
    assert str(captured.value) == "Informe um período válido para o relatório selecionado."
