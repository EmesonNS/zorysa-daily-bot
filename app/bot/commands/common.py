"""Shared Discord command helpers."""

import discord

from app.bot.contracts import ActorContext


def actor_from_interaction(interaction: discord.Interaction) -> ActorContext:
    """Build a tenancy and authorization context from a guild interaction."""

    if interaction.guild_id is None or interaction.guild is None:
        raise ValueError("Este comando só pode ser usado em um servidor.")

    roles = getattr(interaction.user, "roles", ())
    return ActorContext(
        guild_id=interaction.guild_id,
        guild_name=interaction.guild.name,
        user_id=interaction.user.id,
        role_ids=tuple(role.id for role in roles),
        is_guild_owner=interaction.guild.owner_id == interaction.user.id,
        can_manage_guild=interaction.permissions.manage_guild,
    )
