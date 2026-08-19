"""Administrative role Slash Commands."""

import discord
from discord import app_commands

from app.bot.commands.common import actor_from_interaction
from app.bot.contracts import ApplicationError, GuildAdminPresentationService


def build_config_group(service: GuildAdminPresentationService) -> app_commands.Group:
    """Build `/config admin` commands using an injected application service."""

    config = app_commands.Group(name="config", description="Configurações do Zorysa Daily Bot")
    admin = app_commands.Group(name="admin", description="Cargos administrativos")

    @admin.command(name="role-adicionar", description="Adiciona um cargo administrativo")
    @app_commands.describe(cargo="Cargo que poderá administrar o bot")
    async def add_role(interaction: discord.Interaction, cargo: discord.Role) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await service.add_admin_role(
                actor=actor_from_interaction(interaction),
                role_id=cargo.id,
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return
        await interaction.edit_original_response(
            content=f"Cargo administrativo adicionado: {cargo.name}."
        )

    @admin.command(name="role-remover", description="Remove um cargo administrativo")
    @app_commands.describe(cargo="Cargo que deixará de administrar o bot")
    async def remove_role(interaction: discord.Interaction, cargo: discord.Role) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await service.remove_admin_role(
                actor=actor_from_interaction(interaction),
                role_id=cargo.id,
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return
        await interaction.edit_original_response(
            content=f"Cargo administrativo removido: {cargo.name}."
        )

    @admin.command(name="roles", description="Lista os cargos com acesso administrativo")
    async def list_roles(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            roles = await service.list_admin_roles(actor=actor_from_interaction(interaction))
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return

        content = "\n".join(f"• <@&{role.role_id}>" for role in roles)
        if content:
            content = f"Cargos com acesso administrativo ao bot:\n{content}"
        await interaction.edit_original_response(
            content=content or "Nenhum cargo administrativo configurado."
        )

    config.add_command(admin)
    return config


def register_config_commands(
    tree: app_commands.CommandTree[discord.Client],
    service: GuildAdminPresentationService,
) -> None:
    """Register the config group on a command tree."""

    tree.add_command(build_config_group(service))
