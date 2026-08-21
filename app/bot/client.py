"""Discord client configuration."""

import logging
from typing import Protocol

import discord
from discord.ext import commands

from app.bot.commands.config import register_config_commands
from app.bot.commands.daily import register_daily_commands
from app.bot.commands.health import register_health_command
from app.bot.commands.project import register_project_commands
from app.bot.commands.report import register_report_commands
from app.bot.contracts import (
    AbsencePresentationService,
    AuditPresentationService,
    DailyClosureGateway,
    DailyManagementPresentationService,
    DailyPresentationService,
    GuildAdminPresentationService,
    ManualReportGateway,
    ManualReportPresentationService,
    MemberLifecyclePresentationService,
    ProjectPresentationService,
    QuestionPresentationService,
    ReportChannelPresentationService,
    SchedulePresentationService,
)
from app.bot.views.daily import DailyResponseView

logger = logging.getLogger(__name__)


class AutomationLifecycle(Protocol):
    async def setup(self) -> None: ...

    async def ready(self) -> None: ...

    async def disconnect(self) -> None: ...

    async def shutdown(self) -> None: ...


class ZorysaBot(commands.Bot):
    """Discord bot with the minimum intents required for Slash Commands."""

    def __init__(
        self,
        *,
        app_name: str,
        guild_id: int | None = None,
        member_lifecycle_service: MemberLifecyclePresentationService | None = None,
        automation_lifecycle: AutomationLifecycle | None = None,
    ) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = True
        super().__init__(command_prefix=commands.when_mentioned, help_command=None, intents=intents)

        self._sync_guild = discord.Object(id=guild_id) if guild_id is not None else None
        self._daily_service: DailyPresentationService | None = None
        self._member_lifecycle_service = member_lifecycle_service
        self._automation_lifecycle = automation_lifecycle
        self._application_services_bound = False
        register_health_command(self, app_name=app_name)

    def bind_application_services(
        self,
        *,
        guild_admin_service: GuildAdminPresentationService,
        schedule_service: SchedulePresentationService,
        question_service: QuestionPresentationService,
        report_channel_service: ReportChannelPresentationService,
        audit_service: AuditPresentationService,
        project_service: ProjectPresentationService,
        daily_service: DailyPresentationService,
        absence_service: AbsencePresentationService,
        daily_management_service: DailyManagementPresentationService,
        daily_gateway: DailyClosureGateway,
        report_service: ManualReportPresentationService,
        report_gateway: ManualReportGateway,
    ) -> None:
        """Register the complete V1 command surface after gateways know this client."""

        if self._application_services_bound:
            raise ValueError("Application services are already configured")
        register_config_commands(
            self.tree,
            guild_admin_service,
            schedule_service,
            question_service,
            report_channel_service,
            audit_service,
        )
        register_project_commands(self.tree, project_service)
        register_daily_commands(
            self,
            daily_service,
            project_service,
            absence_service,
            management_service=daily_management_service,
            closure_gateway=daily_gateway,
        )
        register_report_commands(
            self.tree,
            report_service,
            report_gateway,
            project_service,
        )
        self._daily_service = daily_service
        self._application_services_bound = True

    async def setup_hook(self) -> None:
        """Synchronize commands globally or to the configured development guild."""

        if self._automation_lifecycle is not None:
            await self._automation_lifecycle.setup()

        if self._daily_service is not None:
            self.add_view(DailyResponseView(self._daily_service))

        if self._sync_guild is None:
            await self.tree.sync()
            return

        self.tree.copy_global_to(guild=self._sync_guild)
        await self.tree.sync(guild=self._sync_guild)

    def bind_automation_lifecycle(self, lifecycle: AutomationLifecycle) -> None:
        """Bind the fully composed scheduler before Discord starts."""

        if self._automation_lifecycle is not None:
            raise ValueError("Automation lifecycle is already configured")
        self._automation_lifecycle = lifecycle

    async def on_ready(self) -> None:
        if self._automation_lifecycle is not None:
            await self._automation_lifecycle.ready()

    async def on_disconnect(self) -> None:
        if self._automation_lifecycle is not None:
            await self._automation_lifecycle.disconnect()

    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent) -> None:
        """Close future memberships while isolating unavailable persistence."""

        if self._member_lifecycle_service is None:
            return
        try:
            await self._member_lifecycle_service.leave_guild(payload.guild_id, payload.user.id)
        except Exception:
            logger.error(
                "Failed to process member removal for guild %s user %s",
                payload.guild_id,
                payload.user.id,
            )

    async def close(self) -> None:
        if self._automation_lifecycle is not None:
            await self._automation_lifecycle.shutdown()
        await super().close()
