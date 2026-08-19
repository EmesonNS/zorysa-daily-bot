"""Presentation contracts shared by Discord commands, views, and modals.

Application-level actor and administration DTOs are re-exported here so the
Discord layer depends on the application layer, never the reverse.
"""

from collections.abc import Mapping
from typing import Protocol

from app.application.daily_dto import (
    DailyPanel,
    DailyParticipant,
    DailyResponseForm,
    OpenedDaily,
    QuestionPrompt,
)
from app.application.dto import (
    ActorContext,
    AdminRoleSummary,
    MemberSummary,
    ProjectSummary,
    ScheduleSummary,
)
from app.application.errors import ApplicationError

PresentationError = ApplicationError


class GuildAdminPresentationService(Protocol):
    """Application operations consumed by the `/config` group."""

    async def add_admin_role(self, *, actor: ActorContext, role_id: int) -> AdminRoleSummary: ...

    async def remove_admin_role(self, *, actor: ActorContext, role_id: int) -> None: ...

    async def list_admin_roles(self, *, actor: ActorContext) -> tuple[AdminRoleSummary, ...]: ...


class SchedulePresentationService(Protocol):
    """Application operations consumed by `/config agenda`."""

    async def get_schedule(self, *, actor: ActorContext) -> ScheduleSummary: ...

    async def update_times(
        self,
        *,
        actor: ActorContext,
        opening: str,
        first_reminder: str,
        last_reminder: str,
        closing: str,
    ) -> ScheduleSummary: ...

    async def update_timezone(self, *, actor: ActorContext, timezone: str) -> ScheduleSummary: ...

    async def add_execution_day(self, *, actor: ActorContext, weekday: int) -> ScheduleSummary: ...

    async def remove_execution_day(
        self, *, actor: ActorContext, weekday: int
    ) -> ScheduleSummary: ...


class ProjectPresentationService(Protocol):
    """Application operations consumed by the `/projeto` group."""

    async def create_project(
        self, *, actor: ActorContext, name: str, channel_id: int
    ) -> ProjectSummary: ...

    async def list_projects(self, *, actor: ActorContext) -> tuple[ProjectSummary, ...]: ...

    async def add_member(
        self,
        *,
        actor: ActorContext,
        project_slug: str,
        user_id: int,
        display_name: str,
    ) -> MemberSummary: ...

    async def remove_member(
        self, *, actor: ActorContext, project_slug: str, user_id: int
    ) -> None: ...

    async def list_members(
        self, *, actor: ActorContext, project_slug: str
    ) -> tuple[MemberSummary, ...]: ...


class DailyPresentationService(Protocol):
    """Application operations required by daily Discord interactions."""

    async def open_daily(self, *, actor: ActorContext, project_slug: str) -> OpenedDaily: ...

    async def attach_message(self, *, session_id: int, message_id: int) -> None: ...

    async def prepare_response(self, *, message_id: int, user_id: int) -> DailyResponseForm: ...

    async def submit_response(
        self, *, message_id: int, user_id: int, answers: Mapping[int, str]
    ) -> DailyPanel: ...


__all__ = [
    "ActorContext",
    "AdminRoleSummary",
    "ApplicationError",
    "DailyPanel",
    "DailyParticipant",
    "DailyPresentationService",
    "DailyResponseForm",
    "GuildAdminPresentationService",
    "MemberSummary",
    "OpenedDaily",
    "PresentationError",
    "ProjectPresentationService",
    "ProjectSummary",
    "QuestionPrompt",
    "SchedulePresentationService",
    "ScheduleSummary",
]
