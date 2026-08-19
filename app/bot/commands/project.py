"""Project and membership Slash Commands."""

import discord
from discord import app_commands

from app.bot.commands.common import actor_from_interaction
from app.bot.contracts import ApplicationError, ProjectPresentationService


def build_project_group(service: ProjectPresentationService) -> app_commands.Group:
    """Build `/projeto` commands using an injected application service."""

    project = app_commands.Group(name="projeto", description="Projetos e participantes")

    @project.command(name="criar", description="Cria um projeto")
    @app_commands.describe(nome="Nome do projeto", canal="Canal público da daily")
    async def create(
        interaction: discord.Interaction,
        nome: str,
        canal: discord.TextChannel,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            created = await service.create_project(
                actor=actor_from_interaction(interaction),
                name=nome,
                channel_id=canal.id,
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return
        await interaction.edit_original_response(
            content=f"Projeto `{created.slug}` criado em {canal.mention}."
        )

    @project.command(name="listar", description="Lista os projetos")
    async def list_projects(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            projects = await service.list_projects(actor=actor_from_interaction(interaction))
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return

        lines = [
            (
                f"• **{item.name}** (`{item.slug}`) — {item.status} — "
                f"daily {'habilitada' if item.daily_enabled else 'desabilitada'} — "
                f"{item.participant_count} participante(s) — <#{item.channel_id}>"
            )
            for item in projects
        ]
        await interaction.edit_original_response(
            content="\n".join(lines) or "Nenhum projeto cadastrado."
        )

    @project.command(name="membro-adicionar", description="Adiciona um membro ao projeto")
    @app_commands.describe(projeto="Slug do projeto", usuario="Membro participante")
    async def add_member(
        interaction: discord.Interaction,
        projeto: str,
        usuario: discord.Member,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await service.add_member(
                actor=actor_from_interaction(interaction),
                project_slug=projeto,
                user_id=usuario.id,
                display_name=usuario.display_name,
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return
        await interaction.edit_original_response(
            content=f"{usuario.mention} foi adicionado ao projeto `{projeto}`."
        )

    @project.command(name="membro-remover", description="Remove um membro do projeto")
    @app_commands.describe(projeto="Slug do projeto", usuario="Membro participante")
    async def remove_member(
        interaction: discord.Interaction,
        projeto: str,
        usuario: discord.Member,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await service.remove_member(
                actor=actor_from_interaction(interaction),
                project_slug=projeto,
                user_id=usuario.id,
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return
        await interaction.edit_original_response(
            content=f"{usuario.mention} foi removido do projeto `{projeto}`."
        )

    @project.command(name="membros", description="Lista os membros ativos do projeto")
    @app_commands.describe(projeto="Slug do projeto")
    async def list_members(interaction: discord.Interaction, projeto: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            members = await service.list_members(
                actor=actor_from_interaction(interaction),
                project_slug=projeto,
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return

        lines = [f"• {member.display_name} (<@{member.user_id}>)" for member in members]
        await interaction.edit_original_response(
            content="\n".join(lines) or f"O projeto `{projeto}` não possui membros ativos."
        )

    return project


def register_project_commands(
    tree: app_commands.CommandTree[discord.Client],
    service: ProjectPresentationService,
) -> None:
    """Register the project group on a command tree."""

    tree.add_command(build_project_group(service))
