import os

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.dto import ActorContext
from app.application.errors import AuthorizationError, ConflictError
from app.application.guild_admin import GuildAdminService
from app.application.schedule import ScheduleService


def _actor(*, roles: tuple[int, ...] = (), owner: bool = False) -> ActorContext:
    return ActorContext(
        guild_id=9_003_000_001,
        guild_name="Guild Agenda",
        user_id=42,
        role_ids=roles,
        is_guild_owner=owner,
        can_manage_guild=owner,
    )


class RecordingReloader:
    def __init__(self) -> None:
        self.guild_ids: list[int] = []

    async def reconcile_guild(self, discord_guild_id: int) -> None:
        self.guild_ids.append(discord_guild_id)


@pytest.fixture
async def schedule_context():  # type: ignore[no-untyped-def]
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


async def test_schedule_defaults_updates_and_reloads_after_success(schedule_context) -> None:  # type: ignore[no-untyped-def]
    admin = GuildAdminService(schedule_context)
    await admin.add_admin_role(actor=_actor(owner=True), role_id=10)
    actor = _actor(roles=(10,))
    reloader = RecordingReloader()
    service = ScheduleService(schedule_context, reloader=reloader)

    initial = await service.get_schedule(actor=actor)
    assert initial.timezone == "America/Belem"
    assert initial.execution_days == (0, 1, 2, 3, 4)
    assert initial.formatted_times == ("09:00", "10:30", "11:30", "12:00")

    changed = await service.update_times(
        actor=actor,
        opening="08:15",
        first_reminder="09:45",
        last_reminder="10:30",
        closing="11:00",
    )
    assert changed.formatted_times == ("08:15", "09:45", "10:30", "11:00")
    assert reloader.guild_ids == [actor.guild_id]

    changed = await service.update_timezone(actor=actor, timezone="America/Sao_Paulo")
    assert changed.timezone == "America/Sao_Paulo"
    assert reloader.guild_ids == [actor.guild_id, actor.guild_id]


async def test_schedule_days_are_unique_and_never_empty(schedule_context) -> None:  # type: ignore[no-untyped-def]
    admin = GuildAdminService(schedule_context)
    await admin.add_admin_role(actor=_actor(owner=True), role_id=10)
    actor = _actor(roles=(10,))
    reloader = RecordingReloader()
    service = ScheduleService(schedule_context, reloader=reloader)

    await service.add_execution_day(actor=actor, weekday=6)
    with pytest.raises(ConflictError, match="já está configurado"):
        await service.add_execution_day(actor=actor, weekday=6)

    for weekday in (6, 4, 3, 2, 1):
        await service.remove_execution_day(actor=actor, weekday=weekday)
    with pytest.raises(ConflictError, match="último dia"):
        await service.remove_execution_day(actor=actor, weekday=0)

    assert (await service.get_schedule(actor=actor)).execution_days == (0,)
    assert len(reloader.guild_ids) == 6


async def test_schedule_requires_configured_admin_role(schedule_context) -> None:  # type: ignore[no-untyped-def]
    admin = GuildAdminService(schedule_context)
    await admin.add_admin_role(actor=_actor(owner=True), role_id=10)
    service = ScheduleService(schedule_context)

    with pytest.raises(AuthorizationError):
        await service.get_schedule(actor=_actor(owner=True))
