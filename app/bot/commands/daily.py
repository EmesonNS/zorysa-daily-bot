"""Manual daily Slash Commands."""

from typing import cast

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.commands.common import actor_from_interaction, autocomplete_projects
from app.bot.contracts import (
    ApplicationError,
    DailyPresentationService,
    ProjectPresentationService,
)
from app.bot.embeds.daily import render_daily_panel
from app.bot.views.daily import DailyResponseView


def build_daily_group(
    bot: commands.Bot,
    service: DailyPresentationService,
    project_service: ProjectPresentationService,
) -> app_commands.Group:
    """Build `/daily` commands using an injected application service."""

    daily = app_commands.Group(name="daily", description="Operações da daily")

    @daily.command(name="abrir", description="Abre a daily de um projeto")
    @app_commands.describe(projeto="Slug do projeto")
    async def open_daily(interaction: discord.Interaction, projeto: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            opened = await service.open_daily(
                actor=actor_from_interaction(interaction),
                project_slug=projeto,
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return

        if opened.message_id is not None:
            await interaction.edit_original_response(
                content=(
                    f"A daily de `{projeto}` já está aberta "
                    f"(<#{opened.channel_id}> / mensagem `{opened.message_id}`)."
                )
            )
            return

        channel = bot.get_channel(opened.channel_id)
        if channel is None or not hasattr(channel, "send"):
            await interaction.edit_original_response(
                content="Não foi possível acessar o canal configurado para o projeto."
            )
            return

        messageable = cast(discord.abc.Messageable, channel)
        participant_mentions = " ".join(
            f"<@{participant.user_id}>" for participant in opened.panel.participants
        )
        message = await messageable.send(
            content=participant_mentions,
            embed=render_daily_panel(opened.panel),
            view=DailyResponseView(service),
            allowed_mentions=discord.AllowedMentions(
                users=True,
                roles=False,
                everyone=False,
            ),
        )
        await service.attach_message(
            session_id=opened.panel.session_id,
            message_id=message.id,
        )
        await interaction.edit_original_response(
            content=f"Daily aberta com sucesso em <#{opened.channel_id}>."
        )

    async def project_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await autocomplete_projects(interaction, current, project_service)

    open_daily.autocomplete("projeto")(project_autocomplete)

    return daily


def register_daily_commands(
    bot: commands.Bot,
    service: DailyPresentationService,
    project_service: ProjectPresentationService,
) -> None:
    """Register the daily group on a bot command tree."""

    bot.tree.add_command(build_daily_group(bot, service, project_service))
