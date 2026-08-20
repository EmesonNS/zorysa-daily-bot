from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from app.bot.contracts import (
    DailyPanel,
    DailyParticipant,
    DailyResponseForm,
    PresentationError,
    QuestionPrompt,
)
from app.bot.embeds.daily import render_daily_panel
from app.bot.modals.daily import DailyResponseModal
from app.bot.views.daily import DAILY_RESPONSE_CUSTOM_ID, DailyResponseView
from app.domain.enums import AssignmentStatus, SessionStatus


def _panel(*, answered: bool = False, closed: bool = False) -> DailyPanel:
    return DailyPanel(
        session_id=7,
        project_name="AmazHealth",
        local_date=date(2026, 8, 19),
        status=SessionStatus.CLOSED if closed else SessionStatus.OPEN,
        participants=(
            DailyParticipant(
                user_id=10,
                display_name="Ada",
                status=AssignmentStatus.ANSWERED if answered else AssignmentStatus.PENDING,
            ),
            DailyParticipant(
                user_id=20,
                display_name="Linus",
                status=(AssignmentStatus.NOT_ANSWERED if closed else AssignmentStatus.PENDING),
            ),
        ),
    )


def _form() -> DailyResponseForm:
    return DailyResponseForm(
        message_id=99,
        project_name="AmazHealth",
        local_date=date(2026, 8, 19),
        questions=(
            QuestionPrompt(id=1, text="O que você fez?", position=1, required=True),
            QuestionPrompt(id=2, text="Algum impedimento?", position=2, required=False),
        ),
    )


def _interaction(*, message: object | None = None) -> MagicMock:
    interaction = MagicMock()
    interaction.user.id = 10
    interaction.message = message
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    return interaction


def test_renderer_shows_progress_and_participant_states() -> None:
    embed = render_daily_panel(_panel(answered=True))

    assert embed.title == "Daily • AmazHealth"
    assert "19/08/2026" in (embed.description or "")
    assert embed.fields[0].value == "1/2 responderam"
    assert "✅ Ada" in embed.fields[1].value
    assert "⏳ Linus" in embed.fields[1].value


def test_renderer_shows_closed_result_without_private_answers() -> None:
    embed = render_daily_panel(_panel(answered=True, closed=True))

    assert "✅ Ada" in embed.fields[1].value
    assert "❌ Linus" in embed.fields[1].value
    assert "daily encerrada" in (embed.footer.text or "").lower()
    assert "Implementei a API secreta" not in str(embed.to_dict())


def test_persistent_view_has_stable_custom_id() -> None:
    view = DailyResponseView(MagicMock())

    assert view.timeout is None
    assert view.children[0].custom_id == DAILY_RESPONSE_CUSTOM_ID


async def test_button_rejects_user_without_assignment_ephemerally() -> None:
    service = MagicMock()
    service.prepare_response = AsyncMock(side_effect=PresentationError("Você não participa."))
    interaction = _interaction(message=SimpleNamespace(id=99))
    button = DailyResponseView(service).children[0]

    await button.callback(interaction)

    interaction.response.send_message.assert_awaited_once_with(
        "Você não participa.", ephemeral=True
    )
    interaction.response.send_modal.assert_not_awaited()


async def test_button_opens_dynamic_modal_for_assigned_user() -> None:
    service = MagicMock()
    service.prepare_response = AsyncMock(return_value=_form())
    original_message = SimpleNamespace(id=99, edit=AsyncMock())
    interaction = _interaction(message=original_message)
    button = DailyResponseView(service).children[0]

    await button.callback(interaction)

    modal = interaction.response.send_modal.await_args.args[0]
    assert isinstance(modal, DailyResponseModal)
    assert modal.title == "AmazHealth • 19/08/2026"
    assert [item.label for item in modal.children] == [
        "O que você fez?",
        "Algum impedimento?",
    ]
    assert [item.required for item in modal.children] == [True, False]


async def test_modal_submits_private_answers_and_updates_public_status() -> None:
    service = MagicMock()
    service.submit_response = AsyncMock(return_value=_panel(answered=True))
    original_message = SimpleNamespace(id=99, edit=AsyncMock())
    modal = DailyResponseModal(service, _form(), original_message=original_message)
    modal.children[0]._value = "Implementei a API secreta"
    modal.children[1]._value = "Nenhum"
    interaction = _interaction()

    await modal.on_submit(interaction)

    service.submit_response.assert_awaited_once_with(
        message_id=99,
        user_id=10,
        answers={1: "Implementei a API secreta", 2: "Nenhum"},
    )
    edit_kwargs = original_message.edit.await_args.kwargs
    assert isinstance(edit_kwargs["embed"], discord.Embed)
    assert "Implementei a API secreta" not in str(edit_kwargs)
    assert isinstance(edit_kwargs["view"], DailyResponseView)
    interaction.response.send_message.assert_awaited_once_with(
        "Daily respondida com sucesso.", ephemeral=True
    )


async def test_modal_reports_domain_error_without_editing_message() -> None:
    service = MagicMock()
    service.submit_response = AsyncMock(side_effect=PresentationError("Resposta obrigatória."))
    original_message = SimpleNamespace(id=99, edit=AsyncMock())
    modal = DailyResponseModal(service, _form(), original_message=original_message)
    interaction = _interaction()

    await modal.on_submit(interaction)

    original_message.edit.assert_not_awaited()
    interaction.response.send_message.assert_awaited_once_with(
        "Resposta obrigatória.", ephemeral=True
    )


def test_modal_refuses_more_than_discords_five_fields() -> None:
    form = DailyResponseForm(
        message_id=99,
        project_name="AmazHealth",
        local_date=date(2026, 8, 19),
        questions=tuple(
            QuestionPrompt(id=index, text=f"Pergunta {index}", position=index, required=True)
            for index in range(1, 7)
        ),
    )

    with pytest.raises(ValueError, match="cinco perguntas"):
        DailyResponseModal(MagicMock(), form, original_message=MagicMock())
