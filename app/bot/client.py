"""Discord client configuration."""

import discord
from discord.ext import commands

from app.bot.commands.health import register_health_command


class ZorysaBot(commands.Bot):
    """Discord bot with the minimum intents required for Slash Commands."""

    def __init__(self, *, app_name: str, guild_id: int | None = None) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(command_prefix=commands.when_mentioned, help_command=None, intents=intents)

        self._sync_guild = discord.Object(id=guild_id) if guild_id is not None else None
        register_health_command(self, app_name=app_name)

    async def setup_hook(self) -> None:
        """Synchronize commands globally or to the configured development guild."""

        if self._sync_guild is None:
            await self.tree.sync()
            return

        self.tree.copy_global_to(guild=self._sync_guild)
        await self.tree.sync(guild=self._sync_guild)
