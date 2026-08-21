from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.application.audit import append_audit_event
from app.application.dto import ActorContext
from app.application.errors import ValidationError
from app.domain.enums import AuditAction
from app.infrastructure.database.models import AuditEvent, Guild


def _actor() -> ActorContext:
    return ActorContext(100, "Guild", 42, (10,), False, False)


def test_append_audit_event_adds_safe_event_to_callers_session() -> None:
    session = MagicMock()
    guild = Guild(id=7, discord_guild_id=100, name="Guild")
    occurred_at = datetime(2026, 8, 21, 12, tzinfo=UTC)

    event = append_audit_event(
        session,
        guild=guild,
        actor=_actor(),
        action=AuditAction.PROJECT_CREATED,
        target_type="project",
        target_id=9,
        details={"slug": "alpha", "channel_id": 500},
        occurred_at=occurred_at,
    )

    session.add.assert_called_once_with(event)
    assert isinstance(event, AuditEvent)
    assert event.guild_id == 7 and event.actor_user_id == 42
    assert event.occurred_at == occurred_at


@pytest.mark.parametrize(
    "private_key",
    ["token", "password", "secret", "credential", "answer", "response", "reason", "content"],
)
def test_append_rejects_private_detail_keys(private_key: str) -> None:
    with pytest.raises(ValidationError, match="auditoria"):
        append_audit_event(
            MagicMock(),
            guild=Guild(id=7, discord_guild_id=100, name="Guild"),
            actor=_actor(),
            action=AuditAction.PROJECT_EDITED,
            target_type="project",
            target_id=9,
            details={private_key: "privado"},
        )


def test_append_rejects_nested_private_detail_keys() -> None:
    with pytest.raises(ValidationError, match="auditoria"):
        append_audit_event(
            MagicMock(),
            guild=Guild(id=7, discord_guild_id=100, name="Guild"),
            actor=None,
            action=AuditAction.MEMBER_LEFT_GUILD,
            target_type="member",
            target_id=42,
            details={"change": {"answer": "privado"}},
        )


@pytest.mark.parametrize(("target_type", "target_id"), [("", 1), ("x" * 33, 1), ("project", 0)])
def test_append_rejects_invalid_target(target_type: str, target_id: int) -> None:
    with pytest.raises(ValidationError, match="auditoria"):
        append_audit_event(
            MagicMock(),
            guild=Guild(id=7, discord_guild_id=100, name="Guild"),
            actor=_actor(),
            action=AuditAction.PROJECT_EDITED,
            target_type=target_type,
            target_id=target_id,
            details={},
        )


def test_append_rejects_non_json_details() -> None:
    with pytest.raises(ValidationError, match="auditoria"):
        append_audit_event(
            MagicMock(),
            guild=Guild(id=7, discord_guild_id=100, name="Guild"),
            actor=_actor(),
            action=AuditAction.PROJECT_EDITED,
            target_type="project",
            target_id=9,
            details={"created_at": datetime.now(UTC)},
        )
