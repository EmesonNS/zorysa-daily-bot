from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from discord import app_commands

from app.application.errors import ValidationError
from app.application.report_dto import DailyReportMetrics, HistoricalReport, ReportPeriod
from app.bot.commands.report import build_report_group
from app.bot.contracts import ProjectSummary
from app.domain.enums import ReportKind


def _interaction(*, channel_id: int | None = 700) -> MagicMock:
    interaction = MagicMock()
    interaction.id = 123456
    interaction.guild_id = 321
    interaction.guild = SimpleNamespace(id=321, name="LACIS", owner_id=10)
    interaction.user = SimpleNamespace(id=10, roles=[])
    interaction.permissions.manage_guild = True
    interaction.channel_id = channel_id
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


def _report(kind: ReportKind) -> HistoricalReport:
    return HistoricalReport(
        kind,
        ReportPeriod(kind, date(2026, 8, 1), date(2026, 8, 21), "período"),
        DailyReportMetrics(0, 0, 0, 0, 0, 0, 0.0),
        (),
    )


def _command(group: app_commands.Group) -> app_commands.Command:
    command = group.get_command("gerar")
    assert isinstance(command, app_commands.Command)
    return command


@pytest.mark.parametrize(
    ("kind", "period"),
    [
        (ReportKind.DAILY, "2026-08-21"),
        (ReportKind.WEEKLY, "2026-08-17"),
        (ReportKind.MONTHLY, "2026-08"),
    ],
)
async def test_generate_passes_type_period_project_and_channel_to_services(
    kind: ReportKind, period: str
) -> None:
    service = MagicMock()
    service.build_manual = AsyncMock(
        return_value=SimpleNamespace(channel_id=700, report=_report(kind))
    )
    gateway = MagicMock(publish_manual=AsyncMock(return_value=2))
    projects = MagicMock()
    interaction = _interaction()
    command = _command(build_report_group(service, gateway, projects))

    await command.callback(interaction, kind.value, period, "zorysa")

    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    call = service.build_manual.await_args.kwargs
    assert call["kind"] == kind
    assert call["period_text"] == period
    assert call["project_slug"] == "zorysa"
    assert call["channel_id"] == 700
    gateway.publish_manual.assert_awaited_once_with(
        channel_id=700,
        request_id=123456,
        report=service.build_manual.return_value.report,
    )
    assert "2 página(s)" in interaction.edit_original_response.await_args.kwargs["content"]


async def test_generate_registers_choices_and_project_autocomplete() -> None:
    service = MagicMock()
    gateway = MagicMock()
    projects = MagicMock()
    projects.list_projects = AsyncMock(
        return_value=(ProjectSummary("Zorysa", "zorysa", 7, "ACTIVE", True, 1),)
    )
    interaction = _interaction()
    command = _command(build_report_group(service, gateway, projects))

    assert [(choice.name, choice.value) for choice in command._params["tipo"].choices] == [
        ("Diário", "DAILY"),
        ("Semanal", "WEEKLY"),
        ("Mensal", "MONTHLY"),
    ]
    autocomplete = command._params["projeto"].autocomplete
    assert autocomplete is not None
    choices = await autocomplete(interaction, "zor")
    assert [(choice.name, choice.value) for choice in choices] == [("Zorysa (zorysa)", "zorysa")]


async def test_generate_surfaces_safe_application_error_ephemerally() -> None:
    service = MagicMock(build_manual=AsyncMock(side_effect=ValidationError("Período inválido.")))
    interaction = _interaction()

    await _command(build_report_group(service, MagicMock(), MagicMock())).callback(
        interaction, "DAILY", "inválido", None
    )

    assert interaction.edit_original_response.await_args.kwargs["content"] == "Período inválido."


async def test_generate_rejects_interaction_without_channel() -> None:
    service = MagicMock(build_manual=AsyncMock())
    interaction = _interaction(channel_id=None)

    await _command(build_report_group(service, MagicMock(), MagicMock())).callback(
        interaction, "DAILY", None, None
    )

    service.build_manual.assert_not_awaited()
    assert "canal" in interaction.edit_original_response.await_args.kwargs["content"].casefold()


async def test_generate_hides_unexpected_gateway_failure() -> None:
    report = _report(ReportKind.DAILY)
    service = MagicMock(
        build_manual=AsyncMock(return_value=SimpleNamespace(channel_id=700, report=report))
    )
    gateway = MagicMock(
        publish_manual=AsyncMock(side_effect=RuntimeError("token e resposta privada"))
    )
    interaction = _interaction()

    await _command(build_report_group(service, gateway, MagicMock())).callback(
        interaction, "DAILY", None, None
    )

    content = interaction.edit_original_response.await_args.kwargs["content"]
    assert "Não foi possível publicar" in content
    assert "token" not in content and "resposta" not in content
