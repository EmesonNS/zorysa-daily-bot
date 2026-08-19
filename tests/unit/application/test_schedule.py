from datetime import time

import pytest

from app.application.dto import ActorContext
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
    ("opening", "first", "last", "closing"),
    [
        ("9:00", "10:30", "11:30", "12:00"),
        ("09:00", "08:30", "11:30", "12:00"),
        ("09:00", "10:30", "10:30", "12:00"),
        ("09:00", "10:30", "13:00", "12:00"),
    ],
)
async def test_schedule_rejects_invalid_format_or_order_before_database_access(
    opening: str, first: str, last: str, closing: str
) -> None:
    service = ScheduleService(None)  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        await service.update_times(
            actor=_actor(),
            opening=opening,
            first_reminder=first,
            last_reminder=last,
            closing=closing,
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
