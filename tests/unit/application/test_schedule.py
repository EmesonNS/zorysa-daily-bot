from datetime import time

import pytest

from app.application.dto import ActorContext, ScheduleSummary
from app.application.errors import ValidationError
from app.application.schedule import ScheduleService


def _actor() -> ActorContext:
    return ActorContext(
        guild_id=1,
        guild_name="Guild",
        user_id=2,
        role_ids=(),
        is_guild_owner=True,
        can_manage_guild=True,
    )


@pytest.mark.parametrize(
    ("opening", "first", "last", "closing", "reporting"),
    [
        ("9:00", "10:30", "11:30", "12:00", "12:10"),
        ("09:00", "08:30", "11:30", "12:00", "12:10"),
        ("09:00", "10:30", "10:30", "12:00", "12:10"),
        ("09:00", "10:30", "13:00", "12:00", "12:10"),
        ("09:00", "10:30", "11:30", "12:00", "12:00"),
        ("09:00", "10:30", "11:30", "12:00", "12:0"),
    ],
)
async def test_schedule_rejects_invalid_format_or_order_before_database_access(
    opening: str, first: str, last: str, closing: str, reporting: str
) -> None:
    service = ScheduleService(None)  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        await service.update_times(
            actor=_actor(),
            opening=opening,
            first_reminder=first,
            last_reminder=last,
            closing=closing,
            reporting=reporting,
        )


async def test_schedule_rejects_unknown_timezone_before_database_access() -> None:
    service = ScheduleService(None)  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="timezone IANA"):
        await service.update_timezone(actor=_actor(), timezone="Mars/Olympus")


async def test_schedule_rejects_weekday_outside_iso_range() -> None:
    service = ScheduleService(None)  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="dia da semana"):
        await service.add_execution_day(actor=_actor(), weekday=7)


def test_schedule_dto_keeps_time_values_without_seconds_or_timezone() -> None:
    assert time.fromisoformat("09:00").strftime("%H:%M") == "09:00"


def test_schedule_summary_formats_all_five_stages() -> None:
    schedule = ScheduleSummary(
        timezone="America/Belem",
        daily_enabled=True,
        execution_days=(0,),
        opening=time(9),
        first_reminder=time(10, 30),
        last_reminder=time(11, 30),
        closing=time(12),
        reporting=time(12, 10),
        weekly_report_weekday=4,
        weekly_reporting=time(12, 20),
        monthly_reporting=time(12, 20),
    )

    assert schedule.formatted_times == ("09:00", "10:30", "11:30", "12:00", "12:10")
    assert schedule.formatted_management_reports == (4, "12:20", "12:20")


@pytest.mark.parametrize(
    ("weekday", "weekly", "monthly"),
    [(7, "12:20", "12:20"), (4, "12:2", "12:20"), (4, "12:20", "25:00")],
)
async def test_management_schedule_rejects_invalid_values_before_database_access(
    weekday: int, weekly: str, monthly: str
) -> None:
    with pytest.raises(ValidationError):
        await ScheduleService(None).update_management_reports(  # type: ignore[arg-type]
            actor=_actor(),
            weekly_weekday=weekday,
            weekly_reporting=weekly,
            monthly_reporting=monthly,
        )
