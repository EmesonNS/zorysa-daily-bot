"""Presentation contracts shared by Discord commands, views, and modals.

Application-level actor and administration DTOs are re-exported here so the
Discord layer depends on the application layer, never the reverse.
"""

from collections.abc import Mapping
from datetime import date
from typing import Protocol

from app.application.daily_dto import (
    ClosedDaily,
    DailyPanel,
    DailyParticipant,
    DailyResponseForm,
    JustifiedDaily,
    OpenedDaily,
    QuestionPrompt,
)
from app.application.dto import (
    ActorContext,
    AdminRoleSummary,
    AuditCursor,
    AuditEventSummary,
    AuditFilters,
    AuditPage,
    MemberSummary,
    ProjectDetails,
    ProjectSummary,
    QuestionSummary,
    ReportChannelSummary,
    ScheduleSummary,
)
from app.application.errors import ApplicationError
from app.application.report_dto import HistoricalReport, ManualReport
from app.domain.enums import ReportKind

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
        reporting: str,
    ) -> ScheduleSummary: ...

    async def update_timezone(self, *, actor: ActorContext, timezone: str) -> ScheduleSummary: ...

    async def add_execution_day(self, *, actor: ActorContext, weekday: int) -> ScheduleSummary: ...

    async def remove_execution_day(
        self, *, actor: ActorContext, weekday: int
    ) -> ScheduleSummary: ...

    async def update_management_reports(
        self,
        *,
        actor: ActorContext,
        weekly_weekday: int,
        weekly_reporting: str,
        monthly_reporting: str,
    ) -> ScheduleSummary: ...


class AuditPresentationService(Protocol):
    """Read-only audit operations consumed by `/config auditoria`."""

    async def list_events(
        self,
        *,
        actor: ActorContext,
        filters: AuditFilters | None = None,
        cursor: AuditCursor | None = None,
        limit: int = 25,
    ) -> AuditPage: ...


class QuestionPresentationService(Protocol):
    """Application operations consumed by `/config perguntas`."""

    async def list_questions(self, *, actor: ActorContext) -> tuple[QuestionSummary, ...]: ...

    async def add_question(
        self, *, actor: ActorContext, text: str, required: bool
    ) -> QuestionSummary: ...

    async def edit_question(
        self,
        *,
        actor: ActorContext,
        question_id: int,
        text: str,
        required: bool,
    ) -> QuestionSummary: ...

    async def move_question(
        self, *, actor: ActorContext, question_id: int, position: int
    ) -> tuple[QuestionSummary, ...]: ...

    async def set_question_active(
        self, *, actor: ActorContext, question_id: int, active: bool
    ) -> QuestionSummary: ...


class ReportChannelPresentationService(Protocol):
    """Application operations consumed by `/config relatorios`."""

    async def list_channels(self, *, actor: ActorContext) -> tuple[ReportChannelSummary, ...]: ...

    async def save_channel(
        self,
        *,
        actor: ActorContext,
        channel_id: int,
        daily: bool,
        weekly: bool,
        monthly: bool,
    ) -> ReportChannelSummary: ...

    async def remove_channel(self, *, actor: ActorContext, channel_id: int) -> None: ...


class ProjectPresentationService(Protocol):
    """Application operations consumed by the `/projeto` group."""

    async def create_project(
        self, *, actor: ActorContext, name: str, channel_id: int
    ) -> ProjectSummary: ...

    async def list_projects(self, *, actor: ActorContext) -> tuple[ProjectSummary, ...]: ...

    async def edit_project(
        self,
        *,
        actor: ActorContext,
        project_slug: str,
        name: str,
        channel_id: int,
        daily_enabled: bool,
    ) -> ProjectSummary: ...

    async def archive_project(
        self, *, actor: ActorContext, project_slug: str
    ) -> ProjectSummary: ...

    async def project_details(
        self, *, actor: ActorContext, project_slug: str
    ) -> ProjectDetails: ...

    async def list_member_projects(
        self, *, actor: ActorContext, user_id: int
    ) -> tuple[ProjectSummary, ...]: ...

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


class ManualReportPresentationService(Protocol):
    """Authorized manual report workflow consumed by `/relatorio`."""

    async def build_manual(
        self,
        *,
        actor: ActorContext,
        kind: ReportKind,
        period_text: str | None,
        project_slug: str | None,
        channel_id: int,
    ) -> ManualReport: ...


class ManualReportGateway(Protocol):
    """Public Discord publication required by the manual report command."""

    async def publish_manual(
        self,
        *,
        channel_id: int,
        request_id: int,
        report: HistoricalReport,
    ) -> int: ...


class DailyPresentationService(Protocol):
    """Application operations required by daily Discord interactions."""

    async def open_daily(self, *, actor: ActorContext, project_slug: str) -> OpenedDaily: ...

    async def attach_message(self, *, session_id: int, message_id: int) -> None: ...

    async def prepare_response(self, *, message_id: int, user_id: int) -> DailyResponseForm: ...

    async def submit_response(
        self, *, message_id: int, user_id: int, answers: Mapping[int, str]
    ) -> DailyPanel: ...


class DailyManagementPresentationService(Protocol):
    """Public status and authorized closure consumed by `/daily`."""

    async def status(
        self,
        *,
        discord_guild_id: int,
        project_slug: str,
        local_date: date | None,
    ) -> DailyPanel: ...

    async def close(
        self,
        *,
        actor: ActorContext,
        project_slug: str,
        local_date: date | None,
    ) -> ClosedDaily: ...


class DailyClosureGateway(Protocol):
    """Discord panel update required after manual closure."""

    async def publish_closed(self, closed: ClosedDaily) -> None: ...


class AbsencePresentationService(Protocol):
    async def justify(
        self,
        *,
        actor: ActorContext,
        project_slug: str,
        user_id: int,
        local_date: date | None,
        reason: str,
    ) -> JustifiedDaily: ...


class MemberLifecyclePresentationService(Protocol):
    """System membership cleanup consumed by Discord member events."""

    async def leave_guild(self, discord_guild_id: int, discord_user_id: int) -> int: ...


__all__ = [
    "ActorContext",
    "AbsencePresentationService",
    "AdminRoleSummary",
    "ApplicationError",
    "AuditCursor",
    "AuditEventSummary",
    "AuditFilters",
    "AuditPage",
    "AuditPresentationService",
    "ClosedDaily",
    "DailyPanel",
    "DailyClosureGateway",
    "DailyManagementPresentationService",
    "DailyParticipant",
    "DailyPresentationService",
    "DailyResponseForm",
    "GuildAdminPresentationService",
    "MemberSummary",
    "ManualReportGateway",
    "ManualReportPresentationService",
    "MemberLifecyclePresentationService",
    "JustifiedDaily",
    "OpenedDaily",
    "PresentationError",
    "ProjectDetails",
    "ProjectPresentationService",
    "ProjectSummary",
    "QuestionPrompt",
    "QuestionPresentationService",
    "QuestionSummary",
    "ReportChannelPresentationService",
    "ReportChannelSummary",
    "SchedulePresentationService",
    "ScheduleSummary",
]
