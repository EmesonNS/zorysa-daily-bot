import os
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.dto import ActorContext
from app.application.errors import AuthorizationError, NotFoundError, ValidationError
from app.application.guild_admin import GuildAdminService
from app.application.report_channels import ReportChannelService
from app.domain.enums import AuditAction
from app.infrastructure.database.models import AuditEvent, DailyReportDelivery, Guild, ReportChannel


def _actor(
    *, guild_id: int = 9_005_000_001, roles: tuple[int, ...] = (), owner: bool = False
) -> ActorContext:
    return ActorContext(
        guild_id=guild_id,
        guild_name=f"Guild {guild_id}",
        user_id=42,
        role_ids=roles,
        is_guild_owner=owner,
        can_manage_guild=owner,
    )


@pytest.fixture
async def report_channel_context():  # type: ignore[no-untyped-def]
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as connection:
        transaction = await connection.begin()
        sessions = async_sessionmaker(
            connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield sessions
        finally:
            await transaction.rollback()
    await engine.dispose()


async def _configured_actor(context, *, guild_id: int = 9_005_000_001) -> ActorContext:  # type: ignore[no-untyped-def]
    await GuildAdminService(context).add_admin_role(
        actor=_actor(guild_id=guild_id, owner=True), role_id=10
    )
    return _actor(guild_id=guild_id, roles=(10,))


async def test_supports_zero_and_multiple_channels_in_stable_order(report_channel_context) -> None:  # type: ignore[no-untyped-def]
    actor = await _configured_actor(report_channel_context)
    service = ReportChannelService(report_channel_context)
    assert await service.list_channels(actor=actor) == ()

    await service.save_channel(actor=actor, channel_id=300, daily=True, weekly=False, monthly=False)
    await service.save_channel(actor=actor, channel_id=100, daily=False, weekly=True, monthly=True)

    channels = await service.list_channels(actor=actor)
    assert [channel.channel_id for channel in channels] == [100, 300]
    assert channels[0].weekly is True and channels[0].monthly is True


async def test_save_upserts_flags_without_duplicate(report_channel_context) -> None:  # type: ignore[no-untyped-def]
    actor = await _configured_actor(report_channel_context)
    service = ReportChannelService(report_channel_context)

    await service.save_channel(actor=actor, channel_id=100, daily=True, weekly=False, monthly=False)
    updated = await service.save_channel(
        actor=actor, channel_id=100, daily=False, weekly=True, monthly=True
    )

    assert (updated.daily, updated.weekly, updated.monthly) == (False, True, True)
    async with report_channel_context() as session:
        assert await session.scalar(select(func.count(ReportChannel.id))) == 1


async def test_remove_preserves_historical_delivery(report_channel_context) -> None:  # type: ignore[no-untyped-def]
    actor = await _configured_actor(report_channel_context)
    service = ReportChannelService(report_channel_context)
    await service.save_channel(actor=actor, channel_id=100, daily=True, weekly=False, monthly=False)
    async with report_channel_context() as session, session.begin():
        guild_id = await session.scalar(
            select(Guild.id).where(Guild.discord_guild_id == actor.guild_id)
        )
        session.add(
            DailyReportDelivery(
                guild_id=guild_id,
                report_date=date(2026, 8, 20),
                discord_channel_id=100,
            )
        )

    await service.remove_channel(actor=actor, channel_id=100)

    assert await service.list_channels(actor=actor) == ()
    async with report_channel_context() as session:
        assert await session.scalar(select(func.count(DailyReportDelivery.id))) == 1
    with pytest.raises(NotFoundError):
        await service.remove_channel(actor=actor, channel_id=100)


async def test_channel_mutations_are_audited_and_failed_attempts_are_not(
    report_channel_context,
) -> None:  # type: ignore[no-untyped-def]
    actor = await _configured_actor(report_channel_context)
    service = ReportChannelService(report_channel_context)

    await service.save_channel(actor=actor, channel_id=100, daily=True, weekly=False, monthly=False)
    await service.save_channel(actor=actor, channel_id=100, daily=False, weekly=True, monthly=True)
    with pytest.raises(ValidationError, match="ao menos um"):
        await service.save_channel(
            actor=actor, channel_id=200, daily=False, weekly=False, monthly=False
        )
    with pytest.raises(AuthorizationError):
        await service.save_channel(
            actor=_actor(owner=True),
            channel_id=200,
            daily=True,
            weekly=False,
            monthly=False,
        )
    await service.remove_channel(actor=actor, channel_id=100)
    with pytest.raises(NotFoundError):
        await service.remove_channel(actor=actor, channel_id=100)

    async with report_channel_context() as session:
        events = (
            await session.scalars(
                select(AuditEvent)
                .where(AuditEvent.target_type == "report_channel")
                .order_by(AuditEvent.id)
            )
        ).all()

    assert [AuditAction(event.action) for event in events] == [
        AuditAction.REPORT_CHANNEL_SAVED,
        AuditAction.REPORT_CHANNEL_SAVED,
        AuditAction.REPORT_CHANNEL_REMOVED,
    ]
    assert [event.target_id for event in events] == [100, 100, 100]
    assert events[0].details == {
        "channel_id": 100,
        "daily": True,
        "weekly": False,
        "monthly": False,
    }
    assert events[1].details == {
        "channel_id": 100,
        "daily": False,
        "weekly": True,
        "monthly": True,
    }
    assert events[2].details == events[1].details


async def test_channels_are_isolated_by_guild(report_channel_context) -> None:  # type: ignore[no-untyped-def]
    first = await _configured_actor(report_channel_context)
    second = await _configured_actor(report_channel_context, guild_id=9_005_000_002)
    service = ReportChannelService(report_channel_context)
    await service.save_channel(actor=first, channel_id=100, daily=True, weekly=False, monthly=False)
    await service.save_channel(
        actor=second, channel_id=200, daily=True, weekly=False, monthly=False
    )

    assert [item.channel_id for item in await service.list_channels(actor=first)] == [100]
    assert [item.channel_id for item in await service.list_channels(actor=second)] == [200]


async def test_requires_configured_admin_role(report_channel_context) -> None:  # type: ignore[no-untyped-def]
    await _configured_actor(report_channel_context)

    with pytest.raises(AuthorizationError):
        await ReportChannelService(report_channel_context).list_channels(actor=_actor(owner=True))
