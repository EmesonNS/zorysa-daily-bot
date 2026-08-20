"""Administrative role Slash Commands."""

import discord
from discord import app_commands

from app.bot.commands.common import actor_from_interaction
from app.bot.contracts import (
    ApplicationError,
    GuildAdminPresentationService,
    SchedulePresentationService,
    ScheduleSummary,
)

_WEEKDAYS = (
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
)
_WEEKDAY_CHOICES = [
    app_commands.Choice(name=name, value=value) for value, name in enumerate(_WEEKDAYS)
]


def _format_schedule(schedule: ScheduleSummary) -> str:
    status = "Ativa" if schedule.daily_enabled else "Desativada"
    days = ", ".join(_WEEKDAYS[weekday] for weekday in schedule.execution_days)
    opening, first, last, closing, reporting = schedule.formatted_times
    return (
        f"**Agenda automática:** {status}\n"
        f"**Timezone:** `{schedule.timezone}`\n"
        f"**Dias:** {days}\n"
        f"**Abertura:** {opening}\n"
        f"**Primeiro lembrete:** {first}\n"
        f"**Último lembrete:** {last}\n"
        f"**Fechamento:** {closing}\n"
        f"**Relatório:** {reporting}"
    )


def build_config_group(
    service: GuildAdminPresentationService,
    schedule_service: SchedulePresentationService | None = None,
) -> app_commands.Group:
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
    if schedule_service is not None:
        agenda = app_commands.Group(name="agenda", description="Agenda automática da daily")

        @agenda.command(name="visualizar", description="Mostra a agenda automática atual")
        async def view_schedule(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                schedule = await schedule_service.get_schedule(
                    actor=actor_from_interaction(interaction)
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(content=_format_schedule(schedule))

        @agenda.command(name="horarios", description="Altera os cinco horários da agenda")
        @app_commands.rename(
            primeiro_lembrete="primeiro-lembrete",
            ultimo_lembrete="ultimo-lembrete",
        )
        @app_commands.describe(
            abertura="Horário de abertura em HH:MM",
            primeiro_lembrete="Primeiro lembrete em HH:MM",
            ultimo_lembrete="Último lembrete em HH:MM",
            fechamento="Horário de fechamento em HH:MM",
            relatorio="Horário do relatório diário em HH:MM",
        )
        async def update_times(
            interaction: discord.Interaction,
            abertura: str,
            primeiro_lembrete: str,
            ultimo_lembrete: str,
            fechamento: str,
            relatorio: str,
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                schedule = await schedule_service.update_times(
                    actor=actor_from_interaction(interaction),
                    opening=abertura,
                    first_reminder=primeiro_lembrete,
                    last_reminder=ultimo_lembrete,
                    closing=fechamento,
                    reporting=relatorio,
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(content=_format_schedule(schedule))

        @agenda.command(name="timezone", description="Altera o timezone IANA da agenda")
        @app_commands.describe(valor="Timezone IANA, por exemplo America/Belem")
        async def update_timezone(interaction: discord.Interaction, valor: str) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                schedule = await schedule_service.update_timezone(
                    actor=actor_from_interaction(interaction), timezone=valor
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(content=_format_schedule(schedule))

        @agenda.command(name="dia-adicionar", description="Adiciona um dia à agenda")
        @app_commands.choices(dia=_WEEKDAY_CHOICES)
        async def add_day(interaction: discord.Interaction, dia: app_commands.Choice[int]) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                schedule = await schedule_service.add_execution_day(
                    actor=actor_from_interaction(interaction), weekday=dia.value
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(content=_format_schedule(schedule))

        @agenda.command(name="dia-remover", description="Remove um dia da agenda")
        @app_commands.choices(dia=_WEEKDAY_CHOICES)
        async def remove_day(
            interaction: discord.Interaction, dia: app_commands.Choice[int]
        ) -> None:
            await interaction.response.defer(ephemeral=True)
            try:
                schedule = await schedule_service.remove_execution_day(
                    actor=actor_from_interaction(interaction), weekday=dia.value
                )
            except (ApplicationError, ValueError) as error:
                await interaction.edit_original_response(content=str(error))
                return
            await interaction.edit_original_response(content=_format_schedule(schedule))

        config.add_command(agenda)
    return config


def register_config_commands(
    tree: app_commands.CommandTree[discord.Client],
    service: GuildAdminPresentationService,
    schedule_service: SchedulePresentationService,
) -> None:
    """Register the config group on a command tree."""

    tree.add_command(build_config_group(service, schedule_service))
