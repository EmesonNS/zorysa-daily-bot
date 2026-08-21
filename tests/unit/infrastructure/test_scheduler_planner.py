from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.application.dto import ScheduleSummary
from app.infrastructure.scheduler.planner import (
    RecoveryAction,
    ScheduleStage,
    is_last_execution_day,
    plan_schedule,
)


def _schedule(
    *,
    timezone: str = "America/Belem",
    execution_days: tuple[int, ...] = (0, 1, 2, 3, 4),
    daily_enabled: bool = True,
) -> ScheduleSummary:
    return ScheduleSummary(
        timezone=timezone,
        daily_enabled=daily_enabled,
        execution_days=execution_days,
        opening=time(9, 0),
        first_reminder=time(10, 30),
        last_reminder=time(11, 30),
        closing=time(12, 0),
        reporting=time(12, 10),
    )


def _local_datetime(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int = 0,
    *,
    timezone: str = "America/Belem",
) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(timezone))


def test_plan_builds_seven_cron_triggers_with_configured_timezone_and_times() -> None:
    schedule = _schedule(execution_days=(0, 2, 4))

    plan = plan_schedule(schedule, _local_datetime(2026, 8, 19, 8))

    assert tuple(job.stage for job in plan.jobs) == (
        ScheduleStage.OPEN,
        ScheduleStage.FIRST_REMINDER,
        ScheduleStage.LAST_REMINDER,
        ScheduleStage.CLOSE,
        ScheduleStage.DAILY_REPORT,
        ScheduleStage.WEEKLY_REPORT,
        ScheduleStage.MONTHLY_REPORT,
    )
    assert tuple(str(job.trigger.timezone) for job in plan.jobs) == (
        "America/Belem",
        "America/Belem",
        "America/Belem",
        "America/Belem",
        "America/Belem",
        "America/Belem",
        "America/Belem",
    )

    expected = (
        datetime(2026, 8, 19, 9, 0, tzinfo=ZoneInfo("America/Belem")),
        datetime(2026, 8, 19, 10, 30, tzinfo=ZoneInfo("America/Belem")),
        datetime(2026, 8, 19, 11, 30, tzinfo=ZoneInfo("America/Belem")),
        datetime(2026, 8, 19, 12, 0, tzinfo=ZoneInfo("America/Belem")),
        datetime(2026, 8, 19, 12, 10, tzinfo=ZoneInfo("America/Belem")),
        datetime(2026, 8, 21, 12, 20, tzinfo=ZoneInfo("America/Belem")),
        datetime(2026, 8, 26, 12, 20, tzinfo=ZoneInfo("America/Belem")),
    )
    now = _local_datetime(2026, 8, 19, 8)
    assert tuple(job.trigger.get_next_fire_time(None, now) for job in plan.jobs) == expected


def test_trigger_keeps_local_hour_across_daylight_saving_transition() -> None:
    schedule = _schedule(timezone="America/New_York")
    now = datetime(2026, 3, 6, 15, 0, tzinfo=UTC)

    plan = plan_schedule(schedule, now)
    opening = plan.jobs[0].trigger.get_next_fire_time(None, now)

    assert opening == datetime(2026, 3, 9, 9, 0, tzinfo=ZoneInfo("America/New_York"))
    assert opening is not None
    assert opening.astimezone(UTC) == datetime(2026, 3, 9, 13, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("now", "expected_actions"),
    [
        (_local_datetime(2026, 8, 19, 8, 59), ()),
        (_local_datetime(2026, 8, 19, 9, 0), (RecoveryAction.ENSURE_OPEN,)),
        (_local_datetime(2026, 8, 19, 10, 31), (RecoveryAction.ENSURE_OPEN,)),
        (_local_datetime(2026, 8, 19, 11, 31), (RecoveryAction.ENSURE_OPEN,)),
        (_local_datetime(2026, 8, 19, 11, 59), (RecoveryAction.ENSURE_OPEN,)),
        (_local_datetime(2026, 8, 19, 12, 0), (RecoveryAction.CLOSE_OVERDUE,)),
        (_local_datetime(2026, 8, 19, 12, 1), (RecoveryAction.CLOSE_OVERDUE,)),
    ],
)
def test_recovery_actions_follow_open_and_close_boundaries(
    now: datetime,
    expected_actions: tuple[RecoveryAction, ...],
) -> None:
    plan = plan_schedule(_schedule(), now)

    assert plan.local_date == now.date()
    assert plan.recovery_actions == expected_actions
    assert not {
        ScheduleStage.FIRST_REMINDER,
        ScheduleStage.LAST_REMINDER,
    }.intersection(action.value for action in plan.recovery_actions)


def test_recovery_does_not_open_on_disabled_weekday() -> None:
    saturday = _local_datetime(2026, 8, 22, 10, 0)

    plan = plan_schedule(_schedule(), saturday)

    assert saturday.weekday() == 5
    assert plan.recovery_actions == ()


def test_recovery_after_close_can_close_overdue_sessions_on_disabled_weekday() -> None:
    saturday = _local_datetime(2026, 8, 22, 12, 1)

    plan = plan_schedule(_schedule(), saturday)

    assert plan.recovery_actions == (RecoveryAction.CLOSE_OVERDUE,)


def test_disabled_schedule_has_no_recurring_jobs_or_open_recovery() -> None:
    plan = plan_schedule(
        _schedule(daily_enabled=False),
        _local_datetime(2026, 8, 19, 10, 0),
    )

    assert plan.jobs == ()
    assert plan.recovery_actions == ()


def test_planner_converts_aware_now_to_guild_timezone() -> None:
    now_utc = datetime(2026, 8, 19, 12, 30, tzinfo=UTC)

    plan = plan_schedule(_schedule(), now_utc)

    assert plan.local_date.isoformat() == "2026-08-19"
    assert plan.recovery_actions == (RecoveryAction.ENSURE_OPEN,)


def test_planner_rejects_naive_now() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        plan_schedule(_schedule(), datetime(2026, 8, 19, 9, 0))


def test_report_trigger_is_strictly_after_close() -> None:
    plan = plan_schedule(_schedule(), _local_datetime(2026, 8, 19, 8))
    close = plan.jobs[-2].trigger.get_next_fire_time(None, _local_datetime(2026, 8, 19, 8))
    report = plan.jobs[-1].trigger.get_next_fire_time(None, _local_datetime(2026, 8, 19, 8))
    assert close is not None and report is not None and report > close


def test_report_stage_never_appears_as_recovery_action() -> None:
    plan = plan_schedule(_schedule(), _local_datetime(2026, 8, 19, 12, 5))
    assert plan.recovery_actions == (RecoveryAction.CLOSE_OVERDUE,)


def test_weekly_trigger_uses_configured_weekday_independent_of_execution_days() -> None:
    schedule = _schedule(execution_days=(0, 2))
    schedule = ScheduleSummary(
        **{
            field: getattr(schedule, field)
            for field in (
                "timezone",
                "daily_enabled",
                "execution_days",
                "opening",
                "first_reminder",
                "last_reminder",
                "closing",
                "reporting",
            )
        },
        weekly_report_weekday=4,
        weekly_reporting=time(13, 15),
    )

    plan = plan_schedule(schedule, _local_datetime(2026, 8, 19, 8))
    weekly = next(job for job in plan.jobs if job.stage == ScheduleStage.WEEKLY_REPORT)

    assert weekly.trigger.get_next_fire_time(None, _local_datetime(2026, 8, 19, 8)) == (
        _local_datetime(2026, 8, 21, 13, 15)
    )


def test_monthly_trigger_fires_on_last_candidates_for_configured_execution_days() -> None:
    plan = plan_schedule(
        _schedule(execution_days=(0, 2, 4)),
        _local_datetime(2026, 8, 1, 8),
    )
    monthly = next(job for job in plan.jobs if job.stage == ScheduleStage.MONTHLY_REPORT)

    assert "last mon,last wed,last fri" in str(monthly.trigger)
    assert monthly.trigger.get_next_fire_time(None, _local_datetime(2026, 8, 1, 8)) == (
        _local_datetime(2026, 8, 26, 12, 20)
    )


@pytest.mark.parametrize(
    ("candidate", "execution_days", "expected"),
    [
        (date(2026, 8, 28), (0, 1, 2, 3, 4), False),
        (date(2026, 8, 31), (0, 1, 2, 3, 4), True),
        (date(2026, 8, 28), (2, 4), True),
        (date(2026, 8, 29), (0, 1, 2, 3, 4), False),
        (date(2026, 12, 31), (3,), True),
        (date(2028, 2, 29), (1,), True),
        (date(2026, 12, 31), (), False),
    ],
)
def test_last_execution_day_predicate(
    candidate: date,
    execution_days: tuple[int, ...],
    expected: bool,
) -> None:
    assert is_last_execution_day(candidate, execution_days) is expected


def test_recovery_includes_only_reports_due_on_current_local_day() -> None:
    friday = plan_schedule(_schedule(), _local_datetime(2026, 8, 21, 12, 30))
    month_end = plan_schedule(_schedule(), _local_datetime(2026, 8, 31, 12, 30))

    assert friday.recovery_actions == (
        RecoveryAction.CLOSE_OVERDUE,
        RecoveryAction.PUBLISH_DAILY_REPORT,
        RecoveryAction.PUBLISH_WEEKLY_REPORT,
    )
    assert month_end.recovery_actions == (
        RecoveryAction.CLOSE_OVERDUE,
        RecoveryAction.PUBLISH_DAILY_REPORT,
        RecoveryAction.PUBLISH_MONTHLY_REPORT,
    )
