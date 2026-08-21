"""Transactional audit writer and guild-scoped keyset query service."""

from copy import deepcopy
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto import (
    ActorContext,
    AuditCursor,
    AuditEventSummary,
    AuditFilters,
    AuditPage,
)
from app.application.errors import ValidationError
from app.application.guild_admin import authorize_admin, ensure_guild_record
from app.domain.enums import AuditAction
from app.infrastructure.database.models import AuditEvent, Guild

_PRIVATE_KEYS = (
    "token",
    "password",
    "secret",
    "credential",
    "answer",
    "response",
    "reason",
    "content",
)
_INVALID_AUDIT = "Os dados de auditoria informados são inválidos."


def append_audit_event(
    session: AsyncSession,
    *,
    guild: Guild,
    actor: ActorContext | None,
    action: AuditAction,
    target_type: str,
    target_id: int,
    details: dict[str, object],
    occurred_at: datetime | None = None,
) -> AuditEvent:
    """Validate and append an event to the caller-owned transaction."""

    if guild.id is None or not target_type or len(target_type) > 32 or target_id <= 0:
        raise ValidationError(_INVALID_AUDIT)
    _validate_json(details)
    values: dict[str, object] = {
        "guild_id": guild.id,
        "actor_user_id": actor.user_id if actor is not None else None,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "details": deepcopy(details),
    }
    if occurred_at is not None:
        values["occurred_at"] = occurred_at
    event = AuditEvent(**values)
    session.add(event)
    return event


def _validate_json(value: object, *, key: str | None = None) -> None:
    if key is not None and any(private in key.casefold() for private in _PRIVATE_KEYS):
        raise ValidationError(_INVALID_AUDIT)
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for item in value:
            _validate_json(item)
        return
    if isinstance(value, dict):
        for nested_key, nested_value in value.items():
            if not isinstance(nested_key, str):
                raise ValidationError(_INVALID_AUDIT)
            _validate_json(nested_value, key=nested_key)
        return
    raise ValidationError(_INVALID_AUDIT)


class AuditService:
    """Authorize and query one guild's immutable audit history."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        timezone: str = "America/Belem",
    ) -> None:
        self._sessions = sessions
        self._timezone = timezone

    async def list_events(
        self,
        *,
        actor: ActorContext,
        filters: AuditFilters | None = None,
        cursor: AuditCursor | None = None,
        limit: int = 25,
    ) -> AuditPage:
        """Return one authorized keyset page in reverse chronological order."""

        if not 1 <= limit <= 100:
            raise ValidationError("Informe um limite de auditoria entre 1 e 100.")
        selected = filters or AuditFilters()
        if selected.target_type is not None and (
            not selected.target_type or len(selected.target_type) > 32
        ):
            raise ValidationError(_INVALID_AUDIT)
        async with self._sessions() as session, session.begin():
            guild = await ensure_guild_record(
                session,
                discord_guild_id=actor.guild_id,
                guild_name=actor.guild_name,
                timezone=self._timezone,
            )
            await authorize_admin(session, guild=guild, actor=actor)
            query = select(AuditEvent).where(AuditEvent.guild_id == guild.id)
            if selected.action is not None:
                query = query.where(AuditEvent.action == selected.action)
            if selected.actor_user_id is not None:
                query = query.where(AuditEvent.actor_user_id == selected.actor_user_id)
            if selected.target_type is not None:
                query = query.where(AuditEvent.target_type == selected.target_type)
            if selected.target_id is not None:
                query = query.where(AuditEvent.target_id == selected.target_id)
            if selected.started_at is not None:
                query = query.where(AuditEvent.occurred_at >= selected.started_at)
            if selected.ended_at is not None:
                query = query.where(AuditEvent.occurred_at <= selected.ended_at)
            if cursor is not None:
                query = query.where(
                    or_(
                        AuditEvent.occurred_at < cursor.occurred_at,
                        and_(
                            AuditEvent.occurred_at == cursor.occurred_at,
                            AuditEvent.id < cursor.event_id,
                        ),
                    )
                )
            rows = (
                await session.scalars(
                    query.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(
                        limit + 1
                    )
                )
            ).all()
            visible = rows[:limit]
            next_cursor = (
                AuditCursor(visible[-1].occurred_at, visible[-1].id) if len(rows) > limit else None
            )
            return AuditPage(
                events=tuple(self._summary(event, actor.guild_id) for event in visible),
                next_cursor=next_cursor,
            )

    @staticmethod
    def _summary(event: AuditEvent, discord_guild_id: int) -> AuditEventSummary:
        return AuditEventSummary(
            id=event.id,
            guild_id=discord_guild_id,
            actor_user_id=event.actor_user_id,
            action=AuditAction(event.action),
            target_type=event.target_type,
            target_id=event.target_id,
            details=deepcopy(event.details),
            occurred_at=event.occurred_at,
        )
