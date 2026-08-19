"""Discord client configuration."""

import discord
from discord.ext import commands

from app.bot.commands.config import register_config_commands
from app.bot.commands.daily import register_daily_commands
from app.bot.commands.health import register_health_command
from app.bot.commands.project import register_project_commands
from app.bot.contracts import (
    DailyPresentationService,
    GuildAdminPresentationService,
    ProjectPresentationService,
    SchedulePresentationService,
)
from app.bot.views.daily import DailyResponseView


class ZorysaBot(commands.Bot):
    """Discord bot with the minimum intents required for Slash Commands."""

    def __init__(
        self,
        *,
        app_name: str,
        guild_id: int | None = None,
        guild_admin_service: GuildAdminPresentationService | None = None,
        schedule_service: SchedulePresentationService | None = None,
        project_service: ProjectPresentationService | None = None,
        daily_service: DailyPresentationService | None = None,
    ) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(command_prefix=commands.when_mentioned, help_command=None, intents=intents)

        self._sync_guild = discord.Object(id=guild_id) if guild_id is not None else None
        self._daily_service = daily_service
        register_health_command(self, app_name=app_name)
        services = (guild_admin_service, schedule_service, project_service, daily_service)
        if any(service is not None for service in services):
            if any(service is None for service in services):
                raise ValueError("All manual daily services must be provided together")
            assert guild_admin_service is not None
            assert schedule_service is not None
            assert project_service is not None
            assert daily_service is not None
            register_config_commands(self.tree, guild_admin_service, schedule_service)
            register_project_commands(self.tree, project_service)
            register_daily_commands(self, daily_service, project_service)

    async def setup_hook(self) -> None:
        """Synchronize commands globally or to the configured development guild."""

        if self._daily_service is not None:
            self.add_view(DailyResponseView(self._daily_service))

        if self._sync_guild is None:
            await self.tree.sync()
            return

        self.tree.copy_global_to(guild=self._sync_guild)
        await self.tree.sync(guild=self._sync_guild)
