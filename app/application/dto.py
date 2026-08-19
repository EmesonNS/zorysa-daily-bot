"""Stable data contracts shared by application and presentation layers."""

from dataclasses import dataclass
from datetime import datetime


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
