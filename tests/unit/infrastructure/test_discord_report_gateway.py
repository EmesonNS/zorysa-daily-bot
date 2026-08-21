from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.report_dto import (
    DailyReport,
    DailyReportMetrics,
    HistoricalReport,
    PreparedDailyReport,
    PreparedReport,
    ReportPeriod,
)
from app.domain.enums import ReportKind
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


def _historical(*, kind: ReportKind = ReportKind.WEEKLY) -> HistoricalReport:
    return HistoricalReport(
        kind,
        ReportPeriod(kind, date(2026, 8, 17), date(2026, 8, 23), "semana"),
        DailyReportMetrics(0, 0, 0, 0, 0, 0, 0.0),
        (),
    )


async def test_publishes_historical_delivery_and_confirms_after_every_page() -> None:
    channel = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=1)))
    gateway, service = _gateway(channel)
    gateway._historical_renderer = MagicMock(return_value=(MagicMock(), MagicMock()))
    prepared = PreparedReport(9, 700, _historical())

    count = await gateway.publish_report(prepared)

    assert count == 2
    service.attach_delivery.assert_awaited_once_with(9, page_count=2)
    assert [call.kwargs["nonce"] for call in channel.send.await_args_list] == [589825, 589826]


async def test_historical_failure_exposes_only_kind_and_operational_ids() -> None:
    channel = SimpleNamespace(send=AsyncMock(side_effect=RuntimeError("token secreto")))
    gateway, service = _gateway(channel)
    prepared = PreparedReport(9, 700, _historical(kind=ReportKind.MONTHLY))

    with pytest.raises(DiscordReportGatewayError) as captured:
        await gateway.publish_report(prepared)

    message = str(captured.value)
    assert "MONTHLY" in message and "9" in message and "700" in message
    assert "token" not in message
    assert captured.value.__cause__ is None
    service.attach_delivery.assert_not_awaited()


async def test_publish_all_reports_isolates_destinations() -> None:
    failed = SimpleNamespace(send=AsyncMock(side_effect=RuntimeError("privado")))
    healthy = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=2)))
    bot = MagicMock()
    bot.get_channel.side_effect = lambda channel_id: failed if channel_id == 700 else healthy
    service = MagicMock(attach_delivery=AsyncMock())
    gateway = DiscordReportGateway(bot, service)

    errors = await gateway.publish_all_reports(
        (
            PreparedReport(9, 700, _historical()),
            PreparedReport(10, 701, _historical()),
        )
    )

    assert len(errors) == 1
    healthy.send.assert_awaited_once()
    service.attach_delivery.assert_awaited_once_with(10, page_count=1)


async def test_manual_publication_uses_request_nonce_without_confirming_delivery() -> None:
    channel = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=2)))
    gateway, service = _gateway(channel)
    gateway._historical_renderer = MagicMock(return_value=(MagicMock(), MagicMock()))

    count = await gateway.publish_manual(
        channel_id=700,
        request_id=123456789,
        report=_historical(),
    )

    assert count == 2
    assert [call.kwargs["nonce"] for call in channel.send.await_args_list] == [
        "m75bcd15-1",
        "m75bcd15-2",
    ]
    service.attach_delivery.assert_not_awaited()


async def test_manual_publication_allows_repeating_same_report() -> None:
    channel = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=2)))
    gateway, _ = _gateway(channel)

    await gateway.publish_manual(channel_id=700, request_id=10, report=_historical())
    await gateway.publish_manual(channel_id=700, request_id=11, report=_historical())

    assert channel.send.await_count == 2
    first_nonce = channel.send.await_args_list[0].kwargs["nonce"]
    second_nonce = channel.send.await_args_list[1].kwargs["nonce"]
    assert first_nonce != second_nonce


async def test_manual_failure_is_safe_and_contains_request_context() -> None:
    channel = SimpleNamespace(send=AsyncMock(side_effect=RuntimeError("credencial privada")))
    gateway, _ = _gateway(channel)

    with pytest.raises(DiscordReportGatewayError) as captured:
        await gateway.publish_manual(channel_id=700, request_id=55, report=_historical())

    message = str(captured.value)
    assert "WEEKLY" in message and "55" in message and "700" in message
    assert "credencial" not in message
