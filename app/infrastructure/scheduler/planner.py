"""Pure planning of guild cron triggers and startup recovery actions."""

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]

from app.application.dto import ScheduleSummary

_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class ScheduleStage(StrEnum):
    """One recurring stage in the automatic daily cycle."""

    OPEN = "open"
    FIRST_REMINDER = "reminder1"
    LAST_REMINDER = "reminder2"
    CLOSE = "close"


class RecoveryAction(StrEnum):
    """Immediate work required when reconstructing an in-memory schedule."""

    ENSURE_OPEN = "ensure_open"
    CLOSE_OVERDUE = "close_overdue"


@dataclass(frozen=True, slots=True)
class PlannedJob:
    """A recurring stage and its configured APScheduler trigger."""

    stage: ScheduleStage
    trigger: CronTrigger


@dataclass(frozen=True, slots=True)
class SchedulePlan:
    """Deterministic scheduler input for one guild at one instant."""

    local_date: date
    jobs: tuple[PlannedJob, ...]
    recovery_actions: tuple[RecoveryAction, ...]


def plan_schedule(schedule: ScheduleSummary, now: datetime) -> SchedulePlan:
    """Build recurring triggers and immediate recovery work for a guild."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    timezone = ZoneInfo(schedule.timezone)
    local_now = now.astimezone(timezone)
    weekday_expression = ",".join(_WEEKDAYS[day] for day in schedule.execution_days)
    stages = (
        (ScheduleStage.OPEN, schedule.opening),
        (ScheduleStage.FIRST_REMINDER, schedule.first_reminder),
        (ScheduleStage.LAST_REMINDER, schedule.last_reminder),
        (ScheduleStage.CLOSE, schedule.closing),
    )
    jobs = (
        tuple(
            PlannedJob(
                stage=stage,
                trigger=_cron_trigger(
                    scheduled_time,
                    weekdays=weekday_expression,
                    timezone=timezone,
                ),
            )
            for stage, scheduled_time in stages
        )
        if schedule.daily_enabled
        else ()
    )

    recovery_actions: tuple[RecoveryAction, ...] = ()
    if local_now.time() >= schedule.closing:
        recovery_actions = (RecoveryAction.CLOSE_OVERDUE,)
    elif (
        schedule.daily_enabled
        and local_now.weekday() in schedule.execution_days
        and local_now.time() >= schedule.opening
    ):
        recovery_actions = (RecoveryAction.ENSURE_OPEN,)

    return SchedulePlan(
        local_date=local_now.date(),
        jobs=jobs,
        recovery_actions=recovery_actions,
    )


def _cron_trigger(
    scheduled_time: time,
    *,
    weekdays: str,
    timezone: ZoneInfo,
) -> CronTrigger:
    return CronTrigger(
        day_of_week=weekdays,
        hour=scheduled_time.hour,
        minute=scheduled_time.minute,
        second=scheduled_time.second,
        timezone=timezone,
    )
