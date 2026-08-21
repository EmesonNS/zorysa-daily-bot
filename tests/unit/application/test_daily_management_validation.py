from datetime import date

import pytest

from app.application.daily_management import DailyManagementService
from app.application.errors import ValidationError


@pytest.mark.parametrize(
    ("guild_id", "project_slug"),
    [(0, "projeto"), (1, ""), (1, "   ")],
)
async def test_status_validates_scope_before_database_access(
    guild_id: int, project_slug: str
) -> None:
    service = DailyManagementService(None)  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        await service.status(
            discord_guild_id=guild_id,
            project_slug=project_slug,
            local_date=date(2026, 8, 21),
        )
