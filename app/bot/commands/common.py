"""Shared Discord command helpers."""

import discord
from discord import app_commands

from app.bot.contracts import (
    ActorContext,
    ProjectPresentationService,
)


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


async def autocomplete_projects(
    interaction: discord.Interaction,
    current: str,
    service: ProjectPresentationService,
) -> list[app_commands.Choice[str]]:
    """Suggest registered projects by name or slug without surfacing lookup errors."""

    try:
        projects = await service.list_projects(actor=actor_from_interaction(interaction))
    except Exception:
        return []

    query = current.casefold().strip()
    matching = (
        project
        for project in projects
        if not query or query in project.name.casefold() or query in project.slug.casefold()
    )
    return [
        app_commands.Choice(
            name=f"{project.name} ({project.slug})"[:100],
            value=project.slug,
        )
        for project in list(matching)[:25]
    ]
