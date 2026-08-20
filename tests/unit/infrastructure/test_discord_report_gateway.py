from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.report_dto import DailyReport, DailyReportMetrics, PreparedDailyReport
from app.infrastructure.discord.report_gateway import (
    DiscordReportGateway,
    DiscordReportGatewayError,
)


def _prepared(*, delivery_id: int = 7, channel_id: int = 500) -> PreparedDailyReport:
    report = DailyReport(
        report_date=date(2026, 8, 20),
        metrics=DailyReportMetrics(0, 0, 0, 0, 0, 0, 0.0),
        projects=(),
    )
    return PreparedDailyReport(delivery_id, channel_id, report)


def _gateway(channel: object) -> tuple[DiscordReportGateway, MagicMock]:
    bot = MagicMock()
    bot.get_channel.return_value = channel
    service = MagicMock()
    service.attach_delivery = AsyncMock()
    return DiscordReportGateway(bot, service), service


async def test_publishes_each_page_with_deterministic_nonce_and_no_mentions() -> None:
    channel = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=1)))
    gateway, service = _gateway(channel)
    gateway._renderer = MagicMock(return_value=(MagicMock(), MagicMock(), MagicMock()))

    count = await gateway.publish(_prepared())

    assert count == 3
    assert [call.kwargs["nonce"] for call in channel.send.await_args_list] == [
        458753,
        458754,
        458755,
    ]
    for call in channel.send.await_args_list:
        allowed = call.kwargs["allowed_mentions"]
        assert allowed.everyone is False and allowed.users is False and allowed.roles is False
    service.attach_delivery.assert_awaited_once_with(7, page_count=3)


async def test_confirms_delivery_only_after_all_pages() -> None:
    channel = SimpleNamespace(
        send=AsyncMock(side_effect=[SimpleNamespace(id=1), RuntimeError("token secreto")])
    )
    gateway, service = _gateway(channel)
    gateway._renderer = MagicMock(return_value=(MagicMock(), MagicMock()))

    with pytest.raises(DiscordReportGatewayError) as raised:
        await gateway.publish(_prepared())

    service.attach_delivery.assert_not_awaited()
    assert "7" in str(raised.value) and "500" in str(raised.value)
    assert "token" not in str(raised.value)


async def test_unavailable_channel_raises_safe_operational_error() -> None:
    gateway, _ = _gateway(None)
    with pytest.raises(DiscordReportGatewayError) as raised:
        await gateway.publish(_prepared())
    assert "500" in str(raised.value)


async def test_publish_all_isolates_one_channel_failure() -> None:
    failed = SimpleNamespace(send=AsyncMock(side_effect=RuntimeError("payload privado")))
    healthy = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=2)))
    bot = MagicMock()
    bot.get_channel.side_effect = lambda channel_id: failed if channel_id == 500 else healthy
    service = MagicMock()
    service.attach_delivery = AsyncMock()
    gateway = DiscordReportGateway(bot, service)

    errors = await gateway.publish_all((_prepared(), _prepared(delivery_id=8, channel_id=600)))

    assert len(errors) == 1
    healthy.send.assert_awaited_once()
    service.attach_delivery.assert_awaited_once_with(8, page_count=1)


async def test_empty_batch_finishes_without_discord_lookup() -> None:
    bot = MagicMock()
    gateway = DiscordReportGateway(bot, MagicMock())
    assert await gateway.publish_all(()) == ()
    bot.get_channel.assert_not_called()
