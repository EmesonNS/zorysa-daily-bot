"""Pure resolution of daily, weekly, and monthly report periods."""

import re
from calendar import monthrange
from datetime import date, timedelta

from app.application.errors import ValidationError
from app.application.report_dto import ReportPeriod
from app.domain.enums import ReportKind

_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
_MONTH_PATTERN = re.compile(r"\d{4}-\d{2}")
_INVALID_PERIOD = "Informe um período válido para o relatório selecionado."


def resolve_period(kind: ReportKind, value: str | None, local_today: date) -> ReportPeriod:
    """Resolve an optional user value into one inclusive local-date interval."""

    normalized = value.strip() if value is not None else ""
    try:
        if kind == ReportKind.MONTHLY:
            reference = local_today if not normalized else _parse_month(normalized)
            start = reference.replace(day=1)
            end = reference.replace(day=monthrange(reference.year, reference.month)[1])
            label = start.strftime("%m/%Y")
        elif kind in (ReportKind.DAILY, ReportKind.WEEKLY):
            reference = local_today if not normalized else _parse_date(normalized)
            if kind == ReportKind.DAILY:
                start = end = reference
                label = start.strftime("%d/%m/%Y")
            else:
                start = reference - timedelta(days=reference.weekday())
                end = start + timedelta(days=6)
                label = f"{start:%d/%m/%Y} a {end:%d/%m/%Y}"
        else:
            raise ValueError
    except (TypeError, ValueError) as error:
        raise ValidationError(_INVALID_PERIOD) from error
    return ReportPeriod(kind=kind, start=start, end=end, label=label)


def _parse_date(value: str) -> date:
    if _DATE_PATTERN.fullmatch(value) is None:
        raise ValueError
    return date.fromisoformat(value)


def _parse_month(value: str) -> date:
    if _MONTH_PATTERN.fullmatch(value) is None:
        raise ValueError
    year, month = (int(part) for part in value.split("-"))
    return date(year, month, 1)
