import pytest

from app.application.absences import AbsenceService
from app.application.dto import ActorContext
from app.application.errors import ValidationError


def _actor() -> ActorContext:
    return ActorContext(1, "Guild", 2, (), True, True)


@pytest.mark.parametrize("reason", ["", "   ", "x" * 1001])
async def test_absence_reason_is_validated_before_database_access(reason: str) -> None:
    service = AbsenceService(None)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="motivo"):
        await service.justify(
            actor=_actor(), project_slug="projeto", user_id=3, local_date=None, reason=reason
        )
