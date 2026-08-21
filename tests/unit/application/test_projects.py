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


@pytest.mark.parametrize(
    ("name", "channel_id"),
    [("", 3), ("x" * 101, 3), ("Projeto", 0)],
)
async def test_project_edit_validates_input_before_database_access(
    name: str, channel_id: int
) -> None:
    service = ProjectService(None)  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        await service.edit_project(
            actor=ActorContext(1, "Guild", 2, (), True, True),
            project_slug="projeto",
            name=name,
            channel_id=channel_id,
            daily_enabled=True,
        )
