"""Pure planning of guild cron triggers and startup recovery actions."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
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
    DAILY_REPORT = "daily-report"
    WEEKLY_REPORT = "weekly-report"
    MONTHLY_REPORT = "monthly-report"


class RecoveryAction(StrEnum):
    """Immediate work required when reconstructing an in-memory schedule."""

    ENSURE_OPEN = "ensure_open"
    CLOSE_OVERDUE = "close_overdue"
    PUBLISH_DAILY_REPORT = "publish_daily_report"
    PUBLISH_WEEKLY_REPORT = "publish_weekly_report"
    PUBLISH_MONTHLY_REPORT = "publish_monthly_report"


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
    daily_stages = (
        (ScheduleStage.OPEN, schedule.opening),
        (ScheduleStage.FIRST_REMINDER, schedule.first_reminder),
        (ScheduleStage.LAST_REMINDER, schedule.last_reminder),
        (ScheduleStage.CLOSE, schedule.closing),
        (ScheduleStage.DAILY_REPORT, schedule.reporting),
    )
    jobs: tuple[PlannedJob, ...] = ()
    if schedule.daily_enabled and schedule.execution_days:
        daily_jobs = tuple(
            PlannedJob(
                stage=stage,
                trigger=_cron_trigger(
                    scheduled_time,
                    weekdays=weekday_expression,
                    timezone=timezone,
                ),
            )
            for stage, scheduled_time in daily_stages
        )
        weekly_job = PlannedJob(
            stage=ScheduleStage.WEEKLY_REPORT,
            trigger=_cron_trigger(
                schedule.weekly_reporting,
                weekdays=_WEEKDAYS[schedule.weekly_report_weekday],
                timezone=timezone,
            ),
        )
        monthly_days = ",".join(f"last {_WEEKDAYS[weekday]}" for weekday in schedule.execution_days)
        monthly_job = PlannedJob(
            stage=ScheduleStage.MONTHLY_REPORT,
            trigger=CronTrigger(
                day=monthly_days,
                hour=schedule.monthly_reporting.hour,
                minute=schedule.monthly_reporting.minute,
                second=schedule.monthly_reporting.second,
                timezone=timezone,
            ),
        )
        jobs = (*daily_jobs, weekly_job, monthly_job)

    recovery_actions: list[RecoveryAction] = []
    if local_now.time() >= schedule.closing:
        recovery_actions.append(RecoveryAction.CLOSE_OVERDUE)
    elif (
        schedule.daily_enabled
        and local_now.weekday() in schedule.execution_days
        and local_now.time() >= schedule.opening
    ):
        recovery_actions.append(RecoveryAction.ENSURE_OPEN)

    if schedule.daily_enabled:
        if (
            local_now.weekday() in schedule.execution_days
            and local_now.time() >= schedule.reporting
        ):
            recovery_actions.append(RecoveryAction.PUBLISH_DAILY_REPORT)
        if (
            local_now.weekday() == schedule.weekly_report_weekday
            and local_now.time() >= schedule.weekly_reporting
        ):
            recovery_actions.append(RecoveryAction.PUBLISH_WEEKLY_REPORT)
        if local_now.time() >= schedule.monthly_reporting and is_last_execution_day(
            local_now.date(), schedule.execution_days
        ):
            recovery_actions.append(RecoveryAction.PUBLISH_MONTHLY_REPORT)

    return SchedulePlan(
        local_date=local_now.date(),
        jobs=jobs,
        recovery_actions=tuple(recovery_actions),
    )


def is_last_execution_day(candidate: date, execution_days: tuple[int, ...]) -> bool:
    """Return whether candidate is the final configured weekday in its month."""

    if candidate.weekday() not in execution_days:
        return False
    following = candidate + timedelta(days=1)
    while following.month == candidate.month:
        if following.weekday() in execution_days:
            return False
        following += timedelta(days=1)
    return True


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
