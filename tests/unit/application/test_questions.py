import pytest

from app.application.dto import ActorContext
from app.application.errors import ValidationError
from app.application.questions import QuestionService


def _actor() -> ActorContext:
    return ActorContext(
        guild_id=1,
        guild_name="Guild",
        user_id=2,
        role_ids=(),
        is_guild_owner=True,
        can_manage_guild=True,
    )


@pytest.mark.parametrize("text", ["", "   ", "x" * 1001])
async def test_question_text_is_validated_before_database_access(text: str) -> None:
    service = QuestionService(None)  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="texto"):
        await service.add_question(actor=_actor(), text=text, required=True)


async def test_question_position_is_validated_before_database_access() -> None:
    service = QuestionService(None)  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="posição"):
        await service.move_question(actor=_actor(), question_id=1, position=0)
