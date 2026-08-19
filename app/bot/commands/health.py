"""Diagnostic Discord command."""

import discord
from discord.ext import commands


def register_health_command(bot: commands.Bot, *, app_name: str) -> None:
    """Register the health Slash Command on the bot command tree."""

    @bot.tree.command(name="health", description="Show the bot connection status")
    async def health(interaction: discord.Interaction) -> None:
        guild_name = interaction.guild.name if interaction.guild is not None else "Direct Message"
        latency_ms = round(bot.latency * 1_000)
        content = f"{app_name} | Latency: {latency_ms} ms | Guild: {guild_name}"
        await interaction.response.send_message(content, ephemeral=True)
