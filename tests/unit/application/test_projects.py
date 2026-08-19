import pytest

from app.application.dto import ActorContext
from app.application.errors import ValidationError
from app.application.projects import ProjectService, project_slug


def test_project_slug_normalizes_accents_and_separators() -> None:
    assert project_slug("  Saúde & Inovação  ") == "saude-inovacao"


async def test_project_slug_rejects_name_without_ascii_identifier() -> None:
    actor = ActorContext(
        guild_id=1,
        guild_name="Guild",
        user_id=2,
        role_ids=(),
        is_guild_owner=True,
        can_manage_guild=True,
    )
    service = ProjectService(None)  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="nome de projeto válido"):
        # Validation happens before a database session is opened.
        await service.create_project(actor=actor, name="---", channel_id=3)
