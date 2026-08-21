"""Project and membership Slash Commands."""

import discord
from discord import app_commands

from app.bot.commands.common import actor_from_interaction, autocomplete_projects
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

    @project.command(name="editar", description="Edita nome, canal e estado da daily")
    @app_commands.describe(
        projeto="Slug estável do projeto",
        nome="Novo nome exibido",
        canal="Novo canal público da daily",
        daily_habilitada="Permite abertura de novas dailies",
    )
    async def edit(
        interaction: discord.Interaction,
        projeto: str,
        nome: str,
        canal: discord.TextChannel,
        daily_habilitada: bool,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            edited = await service.edit_project(
                actor=actor_from_interaction(interaction),
                project_slug=projeto,
                name=nome,
                channel_id=canal.id,
                daily_enabled=daily_habilitada,
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return
        state = "habilitada" if edited.daily_enabled else "desabilitada"
        await interaction.edit_original_response(
            content=f"Projeto `{edited.slug}` atualizado em {canal.mention}; daily {state}."
        )

    @project.command(name="detalhes", description="Mostra estado e histórico básico do projeto")
    @app_commands.describe(projeto="Slug do projeto")
    async def details(interaction: discord.Interaction, projeto: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            result = await service.project_details(
                actor=actor_from_interaction(interaction), project_slug=projeto
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return
        summary = result.summary
        members = [
            f"• {member.display_name} (<@{member.user_id}>)"
            for member in result.active_members[:15]
        ]
        if len(result.active_members) > 15:
            members.append(f"• … e mais {len(result.active_members) - 15} membro(s)")
        daily_state = "habilitada" if summary.daily_enabled else "desabilitada"
        content = (
            f"**{summary.name}** (`{summary.slug}`)\n"
            f"Estado: **{summary.status}** — daily {daily_state}\n"
            f"Canal: <#{summary.channel_id}>\n"
            f"{summary.participant_count} membro(s) ativo(s) — "
            f"{result.membership_count} associação(ões) históricas — "
            f"{result.session_count} daily(s)\n\n"
            f"**Membros ativos**\n{chr(10).join(members) or 'Nenhum membro ativo.'}"
        )
        await interaction.edit_original_response(content=content)

    @project.command(name="arquivar", description="Arquiva o projeto e encerra memberships")
    @app_commands.describe(projeto="Slug do projeto ativo")
    async def archive(interaction: discord.Interaction, projeto: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            archived = await service.archive_project(
                actor=actor_from_interaction(interaction), project_slug=projeto
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return
        await interaction.edit_original_response(
            content=(
                f"Projeto `{archived.slug}` arquivado; daily desabilitada e "
                "memberships ativas encerradas."
            )
        )

    @project.command(name="listar", description="Lista projetos e canais associados")
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
                f"{item.participant_count} participante(s) — Canal: <#{item.channel_id}>"
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

    async def active_project_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await autocomplete_projects(
            interaction, current, service, statuses=frozenset({"ACTIVE"})
        )

    async def all_project_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await autocomplete_projects(interaction, current, service)

    edit.autocomplete("projeto")(active_project_autocomplete)
    archive.autocomplete("projeto")(active_project_autocomplete)
    add_member.autocomplete("projeto")(active_project_autocomplete)
    remove_member.autocomplete("projeto")(active_project_autocomplete)
    list_members.autocomplete("projeto")(active_project_autocomplete)
    details.autocomplete("projeto")(all_project_autocomplete)

    return project


def build_member_group(service: ProjectPresentationService) -> app_commands.Group:
    """Build guild member queries backed by current project memberships."""

    member = app_commands.Group(name="membro", description="Consultas por membro do servidor")

    @member.command(name="projetos", description="Lista os projetos ativos de um membro")
    @app_commands.describe(usuario="Membro do servidor")
    async def projects(interaction: discord.Interaction, usuario: discord.Member) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            items = await service.list_member_projects(
                actor=actor_from_interaction(interaction), user_id=usuario.id
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return
        lines = [
            f"• **{item.name}** (`{item.slug}`) — Canal: <#{item.channel_id}>" for item in items
        ]
        await interaction.edit_original_response(
            content=(
                f"**{usuario.display_name}**\n\n"
                + ("Projetos ativos:\n" + "\n".join(lines) if lines else "Nenhum projeto ativo.")
            )
        )

    return member


def register_project_commands(
    tree: app_commands.CommandTree[discord.Client],
    service: ProjectPresentationService,
) -> None:
    """Register the project group on a command tree."""

    tree.add_command(build_project_group(service))
    tree.add_command(build_member_group(service))
