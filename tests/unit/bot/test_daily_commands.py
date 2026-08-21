from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from discord import app_commands

from app.bot.commands.daily import build_daily_group
from app.bot.contracts import ClosedDaily, JustifiedDaily, OpenedDaily
from tests.unit.bot.test_daily_presentation import _panel


def _interaction() -> MagicMock:
    interaction = MagicMock()
    interaction.guild_id = 123
    interaction.guild = SimpleNamespace(id=123, name="LACIS", owner_id=10)
    interaction.user = SimpleNamespace(id=10, roles=[])
    interaction.permissions.manage_guild = True
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


def _open_command(group: app_commands.Group) -> app_commands.Command:
    command = group.get_command("abrir")
    assert isinstance(command, app_commands.Command)
    return command


def _justify_command(group: app_commands.Group) -> app_commands.Command:
    command = group.get_command("justificar")
    assert isinstance(command, app_commands.Command)
    return command


def _command(group: app_commands.Group, name: str) -> app_commands.Command:
    command = group.get_command(name)
    assert isinstance(command, app_commands.Command)
    return command


def _project_service() -> MagicMock:
    project_service = MagicMock()
    project_service.list_projects = AsyncMock(
        return_value=(
            SimpleNamespace(
                name="AmazHealth",
                slug="amazhealth",
                channel_id=55,
                status="ACTIVE",
                daily_enabled=True,
                participant_count=2,
            ),
        )
    )
    return project_service


async def test_open_daily_publishes_panel_and_attaches_message_id() -> None:
    service = MagicMock()
    service.open_daily = AsyncMock(
        return_value=OpenedDaily(panel=_panel(), channel_id=55, message_id=None)
    )
    service.attach_message = AsyncMock()
    public_message = SimpleNamespace(id=999)
    channel = SimpleNamespace(send=AsyncMock(return_value=public_message))
    bot = MagicMock()
    bot.get_channel.return_value = channel
    interaction = _interaction()

    await _open_command(build_daily_group(bot, service, _project_service())).callback(
        interaction, "amazhealth"
    )

    channel.send.assert_awaited_once()
    kwargs = channel.send.await_args.kwargs
    assert kwargs["embed"].title == "Daily • AmazHealth"
    assert kwargs["view"].timeout is None
    assert kwargs["content"] == "<@10> <@20>"
    assert kwargs["allowed_mentions"].users is True
    assert kwargs["allowed_mentions"].roles is False
    assert kwargs["allowed_mentions"].everyone is False
    service.attach_message.assert_awaited_once_with(session_id=7, message_id=999)
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)


async def test_open_daily_does_not_duplicate_existing_message() -> None:
    service = MagicMock()
    service.open_daily = AsyncMock(
        return_value=OpenedDaily(panel=_panel(), channel_id=55, message_id=999)
    )
    service.attach_message = AsyncMock()
    bot = MagicMock()
    interaction = _interaction()

    await _open_command(build_daily_group(bot, service, _project_service())).callback(
        interaction, "amazhealth"
    )

    bot.get_channel.assert_not_called()
    service.attach_message.assert_not_awaited()
    content = interaction.edit_original_response.await_args.kwargs["content"]
    assert "já está aberta" in content


async def test_open_daily_project_parameter_has_autocomplete() -> None:
    service = MagicMock()
    project_service = _project_service()
    bot = MagicMock()
    interaction = _interaction()
    autocomplete = (
        _open_command(build_daily_group(bot, service, project_service))
        ._params["projeto"]
        .autocomplete
    )
    assert autocomplete is not None

    choices = await autocomplete(interaction, "health")

    assert [(choice.name, choice.value) for choice in choices] == [
        ("AmazHealth (amazhealth)", "amazhealth")
    ]


async def test_justify_daily_updates_existing_message() -> None:
    absence = MagicMock()
    absence.justify = AsyncMock(
        return_value=JustifiedDaily(panel=_panel(), channel_id=55, message_id=999)
    )
    message = SimpleNamespace(edit=AsyncMock())
    channel = SimpleNamespace(fetch_message=AsyncMock(return_value=message))
    bot = MagicMock()
    bot.get_channel.return_value = channel
    interaction = _interaction()
    member = SimpleNamespace(id=20)
    group = build_daily_group(bot, MagicMock(), _project_service(), absence)

    await _justify_command(group).callback(
        interaction, "amazhealth", member, "Consulta médica", "2026-08-19"
    )

    assert absence.justify.await_args.kwargs["project_slug"] == "amazhealth"
    assert absence.justify.await_args.kwargs["user_id"] == 20
    assert str(absence.justify.await_args.kwargs["local_date"]) == "2026-08-19"
    message.edit.assert_awaited_once()
    assert "Consulta médica" not in str(message.edit.await_args.kwargs)


async def test_justify_daily_reports_missing_message_safely() -> None:
    absence = MagicMock()
    absence.justify = AsyncMock(
        return_value=JustifiedDaily(panel=_panel(), channel_id=55, message_id=None)
    )
    bot = MagicMock()
    interaction = _interaction()

    await _justify_command(
        build_daily_group(bot, MagicMock(), _project_service(), absence)
    ).callback(interaction, "amazhealth", SimpleNamespace(id=20), "Férias", None)

    bot.get_channel.assert_not_called()
    assert "mensagem" in interaction.edit_original_response.await_args.kwargs["content"]


async def test_status_is_public_and_renders_only_the_answer_free_panel() -> None:
    management = MagicMock(status=AsyncMock(return_value=_panel()))
    interaction = _interaction()
    interaction.user = SimpleNamespace(id=99, roles=[])
    interaction.permissions.manage_guild = False
    group = build_daily_group(
        MagicMock(),
        MagicMock(),
        _project_service(),
        management_service=management,
        closure_gateway=MagicMock(),
    )

    await _command(group, "status").callback(interaction, "amazhealth", "2026-08-19")

    assert management.status.await_args.kwargs == {
        "discord_guild_id": 123,
        "project_slug": "amazhealth",
        "local_date": date(2026, 8, 19),
    }
    embed = interaction.edit_original_response.await_args.kwargs["embed"]
    assert embed.title == "Daily • AmazHealth"
    assert "resposta privada" not in str(embed.to_dict())


async def test_close_updates_main_message_and_confirms_ephemerally() -> None:
    closed = ClosedDaily(
        panel=_panel(closed=True),
        channel_id=55,
        message_id=999,
        closed_at=SimpleNamespace(),
    )
    management = MagicMock(close=AsyncMock(return_value=closed))
    gateway = MagicMock(publish_closed=AsyncMock())
    interaction = _interaction()
    group = build_daily_group(
        MagicMock(),
        MagicMock(),
        _project_service(),
        management_service=management,
        closure_gateway=gateway,
    )

    await _command(group, "fechar").callback(interaction, "amazhealth", None)

    assert management.close.await_args.kwargs["project_slug"] == "amazhealth"
    assert management.close.await_args.kwargs["local_date"] is None
    gateway.publish_closed.assert_awaited_once_with(closed)
    assert "encerrada" in interaction.edit_original_response.await_args.kwargs["content"]


async def test_status_and_close_autocomplete_include_archived_projects() -> None:
    projects = _project_service()
    projects.list_projects.return_value += (
        SimpleNamespace(
            name="Arquivado",
            slug="arquivado",
            channel_id=66,
            status="ARCHIVED",
            daily_enabled=False,
            participant_count=0,
        ),
    )
    group = build_daily_group(
        MagicMock(),
        MagicMock(),
        projects,
        management_service=MagicMock(),
        closure_gateway=MagicMock(),
    )
    interaction = _interaction()

    for name in ("status", "fechar"):
        autocomplete = _command(group, name)._params["projeto"].autocomplete
        assert autocomplete is not None
        assert [choice.value for choice in await autocomplete(interaction, "arquiv")] == [
            "arquivado"
        ]


async def test_status_rejects_invalid_date_without_calling_service() -> None:
    management = MagicMock(status=AsyncMock())
    interaction = _interaction()
    group = build_daily_group(
        MagicMock(),
        MagicMock(),
        _project_service(),
        management_service=management,
        closure_gateway=MagicMock(),
    )

    await _command(group, "status").callback(interaction, "amazhealth", "19/08/2026")

    management.status.assert_not_awaited()
    assert "AAAA-MM-DD" in interaction.edit_original_response.await_args.kwargs["content"]


async def test_close_hides_gateway_failure_and_keeps_service_result() -> None:
    management = MagicMock(
        close=AsyncMock(return_value=ClosedDaily(_panel(closed=True), 55, None, SimpleNamespace()))
    )
    gateway = MagicMock(
        publish_closed=AsyncMock(side_effect=RuntimeError("token resposta privada"))
    )
    interaction = _interaction()
    group = build_daily_group(
        MagicMock(),
        MagicMock(),
        _project_service(),
        management_service=management,
        closure_gateway=gateway,
    )

    await _command(group, "fechar").callback(interaction, "amazhealth", None)

    content = interaction.edit_original_response.await_args.kwargs["content"]
    assert "encerrada" in content and "mensagem" in content
    assert "token" not in content and "resposta privada" not in content
