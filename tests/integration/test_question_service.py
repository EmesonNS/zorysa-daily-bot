import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.daily import DailyService
from app.application.dto import ActorContext
from app.application.errors import AuthorizationError, ConflictError
from app.application.guild_admin import DEFAULT_DAILY_QUESTIONS, GuildAdminService
from app.application.projects import ProjectService
from app.application.questions import QuestionService
from app.domain.enums import AuditAction
from app.infrastructure.database.models import AuditEvent, DailyQuestionSnapshot


def _actor(*, roles: tuple[int, ...] = (), owner: bool = False) -> ActorContext:
    return ActorContext(
        guild_id=9_004_000_001,
        guild_name="Guild Perguntas",
        user_id=42,
        role_ids=roles,
        is_guild_owner=owner,
        can_manage_guild=owner,
    )


@pytest.fixture
async def question_context():  # type: ignore[no-untyped-def]
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


async def _configured_actor(question_context) -> ActorContext:  # type: ignore[no-untyped-def]
    await GuildAdminService(question_context).add_admin_role(actor=_actor(owner=True), role_id=10)
    return _actor(roles=(10,))


async def test_lists_defaults_and_edits_question(question_context) -> None:  # type: ignore[no-untyped-def]
    actor = await _configured_actor(question_context)
    service = QuestionService(question_context)

    initial = await service.list_questions(actor=actor)
    assert [question.text for question in initial] == list(DEFAULT_DAILY_QUESTIONS)
    assert [question.position for question in initial] == [1, 2, 3, 4]

    edited = await service.edit_question(
        actor=actor,
        question_id=initial[0].id,
        text="Qual foi sua principal entrega?",
        required=False,
    )
    assert edited.text == "Qual foi sua principal entrega?"
    assert edited.required is False


async def test_adds_up_to_five_active_questions(question_context) -> None:  # type: ignore[no-untyped-def]
    actor = await _configured_actor(question_context)
    service = QuestionService(question_context)

    added = await service.add_question(actor=actor, text="Precisa de ajuda?", required=True)
    assert added.position == 5 and added.active is True

    with pytest.raises(ConflictError, match="cinco"):
        await service.add_question(actor=actor, text="Sexta pergunta", required=True)


async def test_moves_questions_and_keeps_contiguous_unique_positions(question_context) -> None:  # type: ignore[no-untyped-def]
    actor = await _configured_actor(question_context)
    service = QuestionService(question_context)
    questions = await service.list_questions(actor=actor)

    await service.move_question(actor=actor, question_id=questions[-1].id, position=1)

    reordered = await service.list_questions(actor=actor)
    assert [question.id for question in reordered] == [
        questions[-1].id,
        questions[0].id,
        questions[1].id,
        questions[2].id,
    ]
    assert [question.position for question in reordered] == [1, 2, 3, 4]


async def test_active_question_bounds_preserve_configuration(question_context) -> None:  # type: ignore[no-untyped-def]
    actor = await _configured_actor(question_context)
    service = QuestionService(question_context)
    defaults = await service.list_questions(actor=actor)

    for question in defaults[:-1]:
        await service.set_question_active(actor=actor, question_id=question.id, active=False)
    with pytest.raises(ConflictError, match="uma pergunta"):
        await service.set_question_active(actor=actor, question_id=defaults[-1].id, active=False)

    for question in defaults[:-1]:
        await service.set_question_active(actor=actor, question_id=question.id, active=True)
    fifth = await service.add_question(actor=actor, text="Quinta", required=False)
    await service.set_question_active(actor=actor, question_id=defaults[0].id, active=False)
    sixth = await service.add_question(actor=actor, text="Sexta inativa depois", required=False)
    await service.set_question_active(actor=actor, question_id=sixth.id, active=False)
    await service.set_question_active(actor=actor, question_id=defaults[0].id, active=True)
    with pytest.raises(ConflictError, match="cinco"):
        await service.set_question_active(actor=actor, question_id=sixth.id, active=True)
    assert fifth.active is True


async def test_question_mutations_are_audited_without_text_or_failed_attempts(
    question_context,
) -> None:  # type: ignore[no-untyped-def]
    actor = await _configured_actor(question_context)
    service = QuestionService(question_context)
    defaults = await service.list_questions(actor=actor)

    added = await service.add_question(actor=actor, text="Texto privado", required=False)
    with pytest.raises(ConflictError, match="cinco"):
        await service.add_question(actor=actor, text="Tentativa rejeitada", required=True)
    await service.edit_question(
        actor=actor,
        question_id=defaults[0].id,
        text="Texto alterado",
        required=False,
    )
    await service.move_question(actor=actor, question_id=defaults[-1].id, position=1)
    await service.set_question_active(actor=actor, question_id=added.id, active=False)
    await service.set_question_active(actor=actor, question_id=added.id, active=False)
    await service.set_question_active(actor=actor, question_id=added.id, active=True)

    async with question_context() as session:
        events = (
            await session.scalars(
                select(AuditEvent)
                .where(AuditEvent.target_type == "daily_question")
                .order_by(AuditEvent.id)
            )
        ).all()

    assert [AuditAction(event.action) for event in events] == [
        AuditAction.QUESTION_ADDED,
        AuditAction.QUESTION_EDITED,
        AuditAction.QUESTION_MOVED,
        AuditAction.QUESTION_DEACTIVATED,
        AuditAction.QUESTION_ACTIVATED,
    ]
    assert [event.target_id for event in events] == [
        added.id,
        defaults[0].id,
        defaults[-1].id,
        added.id,
        added.id,
    ]
    assert events[0].details == {"position": 5, "required": False, "active": True}
    assert events[1].details == {"required": False, "active": True}
    assert events[2].details == {"previous_position": 4, "position": 1}
    assert events[3].details == {"active": False}
    assert events[4].details == {"active": True}
    assert all("text" not in event.details for event in events)


async def test_requires_configured_admin_role(question_context) -> None:  # type: ignore[no-untyped-def]
    await _configured_actor(question_context)

    with pytest.raises(AuthorizationError):
        await QuestionService(question_context).list_questions(actor=_actor(owner=True))


async def test_open_session_keeps_snapshot_and_next_session_uses_edit(question_context) -> None:  # type: ignore[no-untyped-def]
    actor = await _configured_actor(question_context)
    project_service = ProjectService(question_context)
    await project_service.create_project(actor=actor, name="Zorysa", channel_id=100)
    await project_service.add_member(
        actor=actor, project_slug="zorysa", user_id=200, display_name="Emeson"
    )
    questions = QuestionService(question_context)
    original = (await questions.list_questions(actor=actor))[0]

    first = await DailyService(
        question_context, clock=lambda: datetime(2026, 8, 20, 12, tzinfo=UTC)
    ).open_daily(actor=actor, project_slug="zorysa")
    await questions.edit_question(
        actor=actor,
        question_id=original.id,
        text="Texto atualizado",
        required=original.required,
    )

    second = await DailyService(
        question_context, clock=lambda: datetime(2026, 8, 21, 12, tzinfo=UTC)
    ).open_daily(actor=actor, project_slug="zorysa")
    async with question_context() as session:
        first_text = await session.scalar(
            select(DailyQuestionSnapshot.text).where(
                DailyQuestionSnapshot.session_id == first.panel.session_id,
                DailyQuestionSnapshot.position == 1,
            )
        )
        second_text = await session.scalar(
            select(DailyQuestionSnapshot.text).where(
                DailyQuestionSnapshot.session_id == second.panel.session_id,
                DailyQuestionSnapshot.position == 1,
            )
        )
    assert first_text == original.text
    assert second_text == "Texto atualizado"
