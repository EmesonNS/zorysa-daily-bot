"""Manual historical report Slash Commands."""

import discord
from discord import app_commands

from app.bot.commands.common import actor_from_interaction, autocomplete_projects
from app.bot.contracts import (
    ApplicationError,
    ManualReportGateway,
    ManualReportPresentationService,
    ProjectPresentationService,
)
from app.domain.enums import ReportKind


def build_report_group(
    service: ManualReportPresentationService,
    gateway: ManualReportGateway,
    project_service: ProjectPresentationService,
) -> app_commands.Group:
    """Build `/relatorio gerar` with injected application and Discord adapters."""

    report = app_commands.Group(name="relatorio", description="Relatórios históricos da daily")

    @report.command(name="gerar", description="Gera um relatório histórico no canal atual")
    @app_commands.describe(
        tipo="Tipo do período",
        periodo="Data YYYY-MM-DD ou mês YYYY-MM; vazio usa o período atual",
        projeto="Projeto opcional; vazio inclui todos",
    )
    @app_commands.choices(
        tipo=[
            app_commands.Choice(name="Diário", value=ReportKind.DAILY.value),
            app_commands.Choice(name="Semanal", value=ReportKind.WEEKLY.value),
            app_commands.Choice(name="Mensal", value=ReportKind.MONTHLY.value),
        ]
    )
    async def generate(
        interaction: discord.Interaction,
        tipo: str,
        periodo: str | None = None,
        projeto: str | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if interaction.channel_id is None:
            await interaction.edit_original_response(
                content="Este comando precisa ser usado em um canal do servidor."
            )
            return
        try:
            prepared = await service.build_manual(
                actor=actor_from_interaction(interaction),
                kind=ReportKind(tipo),
                period_text=periodo,
                project_slug=projeto,
                channel_id=interaction.channel_id,
            )
        except (ApplicationError, ValueError) as error:
            await interaction.edit_original_response(content=str(error))
            return
        try:
            page_count = await gateway.publish_manual(
                channel_id=prepared.channel_id,
                request_id=interaction.id,
                report=prepared.report,
            )
        except Exception:
            await interaction.edit_original_response(
                content="Não foi possível publicar o relatório no canal atual."
            )
            return
        await interaction.edit_original_response(
            content=f"Relatório publicado com {page_count} página(s) neste canal."
        )

    async def project_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await autocomplete_projects(interaction, current, project_service)

    generate.autocomplete("projeto")(project_autocomplete)
    return report


def register_report_commands(
    tree: app_commands.CommandTree[discord.Client],
    service: ManualReportPresentationService,
    gateway: ManualReportGateway,
    project_service: ProjectPresentationService,
) -> None:
    """Register the manual report group on a command tree."""

    tree.add_command(build_report_group(service, gateway, project_service))
