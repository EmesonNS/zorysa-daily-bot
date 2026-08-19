from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from discord import app_commands

from app.bot.commands.project import build_project_group
from app.bot.contracts import MemberSummary, ProjectSummary


def _interaction() -> MagicMock:
    interaction = MagicMock()
    interaction.guild_id = 123
    interaction.guild = SimpleNamespace(id=123, name="LACIS", owner_id=10)
    interaction.user = SimpleNamespace(id=10, roles=[])
    interaction.permissions.manage_guild = True
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


def _command(group: app_commands.Group, name: str) -> app_commands.Command:
    command = group.get_command(name)
    assert isinstance(command, app_commands.Command)
    return command


async def test_create_project_uses_selected_channel() -> None:
    service = MagicMock()
    service.create_project = AsyncMock(
        return_value=ProjectSummary(
            name="AmazHealth",
            slug="amazhealth",
            channel_id=55,
            status="ACTIVE",
            daily_enabled=True,
            participant_count=0,
        )
    )
    interaction = _interaction()
    channel = SimpleNamespace(id=55, mention="#daily")

    await _command(build_project_group(service), "criar").callback(
        interaction, "AmazHealth", channel
    )

    assert service.create_project.await_args.kwargs["channel_id"] == 55
    content = interaction.edit_original_response.await_args.kwargs["content"]
    assert "amazhealth" in content
    assert "#daily" in content


async def test_list_projects_shows_status_daily_and_member_count() -> None:
    service = MagicMock()
    service.list_projects = AsyncMock(
        return_value=(
            ProjectSummary(
                name="AmazHealth",
                slug="amazhealth",
                channel_id=55,
                status="ACTIVE",
                daily_enabled=True,
                participant_count=2,
            ),
        )
    )
    interaction = _interaction()

    command = _command(build_project_group(service), "listar")
    assert command.description == "Lista projetos e canais associados"
    await command.callback(interaction)

    content = interaction.edit_original_response.await_args.kwargs["content"]
    assert "AmazHealth" in content
    assert "ACTIVE" in content
    assert "habilitada" in content
    assert "2 participante(s)" in content
    assert "Canal: <#55>" in content


async def test_project_parameters_autocomplete_registered_projects() -> None:
    service = MagicMock()
    service.list_projects = AsyncMock(
        return_value=tuple(
            ProjectSummary(
                name=f"Projeto {index}",
                slug=f"projeto-{index}",
                channel_id=index,
                status="ACTIVE",
                daily_enabled=True,
                participant_count=0,
            )
            for index in range(30)
        )
        + (
            ProjectSummary(
                name="AmazHealth",
                slug="amazhealth",
                channel_id=55,
                status="ACTIVE",
                daily_enabled=True,
                participant_count=2,
            ),
        )
    )
    interaction = _interaction()
    group = build_project_group(service)

    for command_name in ("membro-adicionar", "membro-remover", "membros"):
        command = _command(group, command_name)
        autocomplete = command._params["projeto"].autocomplete
        assert autocomplete is not None

        choices = await autocomplete(interaction, "AMAZ")

        assert [(choice.name, choice.value) for choice in choices] == [
            ("AmazHealth (amazhealth)", "amazhealth")
        ]

    autocomplete = _command(group, "membros")._params["projeto"].autocomplete
    assert autocomplete is not None
    unfiltered = await autocomplete(interaction, "")
    assert len(unfiltered) == 25


async def test_project_autocomplete_returns_empty_list_on_service_error() -> None:
    service = MagicMock()
    service.list_projects = AsyncMock(side_effect=RuntimeError("consulta indisponível"))
    interaction = _interaction()
    autocomplete = _command(build_project_group(service), "membros")._params["projeto"].autocomplete
    assert autocomplete is not None

    assert await autocomplete(interaction, "ama") == []


async def test_member_commands_add_remove_and_list() -> None:
    service = MagicMock()
    service.add_member = AsyncMock()
    service.remove_member = AsyncMock()
    service.list_members = AsyncMock(
        return_value=(
            MemberSummary(
                user_id=20,
                display_name="Ada",
                joined_at=datetime(2026, 8, 19, tzinfo=UTC),
            ),
        )
    )
    group = build_project_group(service)
    interaction = _interaction()
    user = SimpleNamespace(id=20, display_name="Ada", mention="@Ada")

    await _command(group, "membro-adicionar").callback(interaction, "amazhealth", user)
    service.add_member.assert_awaited_once()
    assert service.add_member.await_args.kwargs["display_name"] == "Ada"

    await _command(group, "membro-remover").callback(interaction, "amazhealth", user)
    service.remove_member.assert_awaited_once()

    await _command(group, "membros").callback(interaction, "amazhealth")
    assert "Ada" in interaction.edit_original_response.await_args.kwargs["content"]
