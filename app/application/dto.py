"""Stable data contracts shared by application and presentation layers."""

from dataclasses import dataclass
from datetime import datetime, time


@dataclass(frozen=True, slots=True)
class ActorContext:
    guild_id: int
    guild_name: str
    user_id: int
    role_ids: tuple[int, ...]
    is_guild_owner: bool
    can_manage_guild: bool


@dataclass(frozen=True, slots=True)
class AdminRoleSummary:
    role_id: int


@dataclass(frozen=True, slots=True)
class ProjectSummary:
    name: str
    slug: str
    channel_id: int
    status: str
    daily_enabled: bool
    participant_count: int


@dataclass(frozen=True, slots=True)
class MemberSummary:
    user_id: int
    display_name: str
    joined_at: datetime


@dataclass(frozen=True, slots=True)
class ScheduleSummary:
    timezone: str
    daily_enabled: bool
    execution_days: tuple[int, ...]
    opening: time
    first_reminder: time
    last_reminder: time
    closing: time
    reporting: time

    @property
    def formatted_times(self) -> tuple[str, str, str, str, str]:
        return (
            self.opening.strftime("%H:%M"),
            self.first_reminder.strftime("%H:%M"),
            self.last_reminder.strftime("%H:%M"),
            self.closing.strftime("%H:%M"),
            self.reporting.strftime("%H:%M"),
        )
