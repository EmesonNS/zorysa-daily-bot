from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.daily_dto import (
    ClosedDaily,
    DailyPanel,
    DailyParticipant,
    OpenedDaily,
    PreparedReminder,
    ReminderRecipient,
)
from app.bot.views.daily import DailyResponseView
from app.domain.enums import AssignmentStatus, NotificationKind, SessionStatus
from app.infrastructure.discord.daily_gateway import (
    DiscordDailyGateway,
    DiscordDailyGatewayError,
)


def _panel(*, closed: bool = False) -> DailyPanel:
    return DailyPanel(
        session_id=41,
        project_name="AmazHealth",
        local_date=date(2026, 8, 19),
        status=SessionStatus.CLOSED if closed else SessionStatus.OPEN,
        participants=(
            DailyParticipant(
                user_id=101,
                display_name="Ada",
                status=AssignmentStatus.ANSWERED if closed else AssignmentStatus.PENDING,
            ),
            DailyParticipant(
                user_id=202,
                display_name="Grace",
                status=(AssignmentStatus.NOT_ANSWERED if closed else AssignmentStatus.PENDING),
            ),
        ),
    )


def _gateway(channel: object) -> tuple[DiscordDailyGateway, MagicMock, MagicMock]:
    bot = MagicMock()
    bot.get_channel.return_value = channel
    daily_service = MagicMock()
    daily_service.attach_message = AsyncMock()
    automatic_service = MagicMock()
    automatic_service.attach_notification = AsyncMock()
    return (
        DiscordDailyGateway(bot, daily_service, automatic_service),
        daily_service,
        automatic_service,
    )


async def test_publish_opened_mentions_snapshot_and_attaches_persistent_message() -> None:
    message = SimpleNamespace(id=9001)
    channel = SimpleNamespace(send=AsyncMock(return_value=message))
    gateway, daily_service, _ = _gateway(channel)
    opened = OpenedDaily(panel=_panel(), channel_id=501, message_id=None)

    message_id = await gateway.publish_opened(opened)

    assert message_id == 9001
    kwargs = channel.send.await_args.kwargs
    assert kwargs["content"] == "<@101> <@202>"
    assert kwargs["embed"].title == "Daily • AmazHealth"
    assert isinstance(kwargs["view"], DailyResponseView)
    assert kwargs["nonce"] == 411
    assert kwargs["allowed_mentions"].users is True
    assert kwargs["allowed_mentions"].roles is False
    assert kwargs["allowed_mentions"].everyone is False
    daily_service.attach_message.assert_awaited_once_with(session_id=41, message_id=9001)


@pytest.mark.parametrize(
    ("kind", "expected_nonce", "expected_notice"),
    [
        (
            NotificationKind.FIRST_REMINDER,
            412,
            "Primeiro lembrete: não se esqueça de responder à daily.",
        ),
        (
            NotificationKind.LAST_REMINDER,
            413,
            "Último lembrete: esta daily será encerrada em breve.",
        ),
    ],
)
async def test_publish_reminder_mentions_only_pending_recipients(
    kind: NotificationKind,
    expected_nonce: int,
    expected_notice: str,
) -> None:
    message = SimpleNamespace(id=9002)
    channel = SimpleNamespace(send=AsyncMock(return_value=message))
    gateway, _, automatic_service = _gateway(channel)
    reminder = PreparedReminder(
        notification_id=71,
        session_id=41,
        project_name="AmazHealth",
        channel_id=501,
        kind=kind,
        recipients=(ReminderRecipient(user_id=202, display_name="Grace"),),
    )

    message_id = await gateway.publish_reminder(reminder)

    assert message_id == 9002
    kwargs = channel.send.await_args.kwargs
    assert "<@202>" in kwargs["content"]
    assert "<@101>" not in kwargs["content"]
    assert expected_notice in kwargs["content"]
    assert kwargs["nonce"] == expected_nonce
    assert kwargs["allowed_mentions"].users is True
    assert kwargs["allowed_mentions"].roles is False
    assert kwargs["allowed_mentions"].everyone is False
    automatic_service.attach_notification.assert_awaited_once_with(
        notification_id=71,
        message_id=9002,
    )


async def test_publish_closed_edits_main_message_without_view_or_private_content() -> None:
    message = SimpleNamespace(edit=AsyncMock())
    channel = SimpleNamespace(fetch_message=AsyncMock(return_value=message))
    gateway, _, _ = _gateway(channel)
    closed = ClosedDaily(
        panel=_panel(closed=True),
        channel_id=501,
        message_id=9001,
        closed_at=datetime(2026, 8, 19, 15, 0, tzinfo=UTC),
    )

    await gateway.publish_closed(closed)

    channel.fetch_message.assert_awaited_once_with(9001)
    kwargs = message.edit.await_args.kwargs
    assert kwargs["view"] is None
    assert "✅ Ada" in kwargs["embed"].fields[1].value
    assert "❌ Grace" in kwargs["embed"].fields[1].value
    assert "resposta privada" not in str(kwargs)


async def test_gateway_exposes_safe_error_when_channel_is_unavailable() -> None:
    gateway, daily_service, _ = _gateway(None)
    opened = OpenedDaily(panel=_panel(), channel_id=501, message_id=None)

    with pytest.raises(DiscordDailyGatewayError) as raised:
        await gateway.publish_opened(opened)

    assert "501" in str(raised.value)
    assert "AmazHealth" not in str(raised.value)
    daily_service.attach_message.assert_not_awaited()


async def test_gateway_does_not_leak_external_error_when_message_fetch_fails() -> None:
    channel = SimpleNamespace(
        fetch_message=AsyncMock(side_effect=RuntimeError("token resposta privada"))
    )
    gateway, _, _ = _gateway(channel)
    closed = ClosedDaily(
        panel=_panel(closed=True),
        channel_id=501,
        message_id=9001,
        closed_at=datetime(2026, 8, 19, 15, 0, tzinfo=UTC),
    )

    with pytest.raises(DiscordDailyGatewayError) as raised:
        await gateway.publish_closed(closed)

    assert "41" in str(raised.value)
    assert "token" not in str(raised.value)
    assert "resposta privada" not in str(raised.value)
