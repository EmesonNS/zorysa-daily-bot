"""Manual daily Slash Commands."""

from datetime import date
from typing import cast

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.commands.common import actor_from_interaction, autocomplete_projects
from app.bot.contracts import (
    AbsencePresentationService,
    ApplicationError,
    DailyClosureGateway,
    DailyManagementPresentationService,
    DailyPresentationService,
    ProjectPresentationService,
)
from app.bot.embeds.daily import render_daily_panel
from app.bot.views.daily import DailyResponseView


def build_daily_group(
    bot: commands.Bot,
    service: DailyPresentationService,
    project_service: ProjectPresentationService,
    absence_service: AbsencePresentationService | None = None,
    *,
    management_service: DailyManagementPresentationService | None = None,
    closure_gateway: DailyClosureGateway | None = None,
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

    async def active_project_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await autocomplete_projects(
            interaction, current, project_service, statuses=frozenset({"ACTIVE"})
        )

    async def all_project_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await autocomplete_projects(interaction, current, project_service)

    open_daily.autocomplete("projeto")(active_project_autocomplete)

    if absence_service is not None:

        @daily.command(name="justificar", description="Registra uma ausência justificada")
        @app_commands.describe(
            projeto="Projeto da daily",
            membro="Participante ausente",
            motivo="Motivo administrativo da ausência",
            data="Data opcional no formato AAAA-MM-DD",
        )
        async def justify_absence(
            interaction: discord.Interaction,
            projeto: str,
            membro: discord.Member,
            motivo: str,
            data: str | None = None,
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                local_date = date.fromisoformat(data) if data else None
                justified = await absence_service.justify(
                    actor=actor_from_interaction(interaction),
                    project_slug=projeto,
                    user_id=membro.id,
                    local_date=local_date,
                    reason=motivo,
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            if justified.message_id is None:
                await interaction.edit_original_response(
                    content="A daily foi atualizada, mas ainda não possui mensagem publicada."
                )
                return
            channel = bot.get_channel(justified.channel_id)
            if channel is None or not hasattr(channel, "fetch_message"):
                await interaction.edit_original_response(
                    content="A ausência foi salva, mas o canal da daily não está acessível."
                )
                return
            try:
                message = await channel.fetch_message(justified.message_id)
                await message.edit(embed=render_daily_panel(justified.panel))
            except discord.HTTPException:
                await interaction.edit_original_response(
                    content="A ausência foi salva, mas a mensagem da daily não pôde ser atualizada."
                )
                return
            await interaction.edit_original_response(content="Ausência justificada com sucesso.")

        justify_absence.autocomplete("projeto")(all_project_autocomplete)

    if (management_service is None) != (closure_gateway is None):
        raise ValueError("Daily management service and closure gateway must be provided together")
    if management_service is not None and closure_gateway is not None:

        @daily.command(name="status", description="Mostra o estado público de uma daily")
        @app_commands.describe(
            projeto="Projeto da daily",
            data="Data opcional no formato AAAA-MM-DD",
        )
        async def status(
            interaction: discord.Interaction,
            projeto: str,
            data: str | None = None,
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                local_date = date.fromisoformat(data) if data else None
            except ValueError:
                await interaction.edit_original_response(
                    content="Informe a data no formato AAAA-MM-DD."
                )
                return
            if interaction.guild_id is None:
                await interaction.edit_original_response(
                    content="Este comando só pode ser usado em um servidor."
                )
                return
            try:
                panel = await management_service.status(
                    discord_guild_id=interaction.guild_id,
                    project_slug=projeto,
                    local_date=local_date,
                )
            except ApplicationError as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(embed=render_daily_panel(panel))

        @daily.command(name="fechar", description="Encerra manualmente uma daily")
        @app_commands.describe(
            projeto="Projeto da daily",
            data="Data opcional no formato AAAA-MM-DD",
        )
        async def close(
            interaction: discord.Interaction,
            projeto: str,
            data: str | None = None,
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                local_date = date.fromisoformat(data) if data else None
            except ValueError:
                await interaction.edit_original_response(
                    content="Informe a data no formato AAAA-MM-DD."
                )
                return
            try:
                closed = await management_service.close(
                    actor=actor_from_interaction(interaction),
                    project_slug=projeto,
                    local_date=local_date,
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            try:
                await closure_gateway.publish_closed(closed)
            except Exception:
                await interaction.edit_original_response(
                    content=(
                        "A daily foi encerrada, mas a mensagem principal não pôde ser atualizada."
                    )
                )
                return
            await interaction.edit_original_response(content="Daily encerrada com sucesso.")

        status.autocomplete("projeto")(all_project_autocomplete)
        close.autocomplete("projeto")(all_project_autocomplete)

    return daily


def register_daily_commands(
    bot: commands.Bot,
    service: DailyPresentationService,
    project_service: ProjectPresentationService,
    absence_service: AbsencePresentationService,
) -> None:
    """Register the daily group on a bot command tree."""

    bot.tree.add_command(build_daily_group(bot, service, project_service, absence_service))
