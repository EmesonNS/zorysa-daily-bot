import pytest

from app.application.errors import ValidationError
from app.application.member_lifecycle import MemberLifecycleService


@pytest.mark.parametrize(
    ("guild_id", "user_id"),
    [(0, 1), (1, 0), (-1, -1)],
)
async def test_leave_guild_validates_discord_ids_before_database_access(
    guild_id: int, user_id: int
) -> None:
    service = MemberLifecycleService(None)  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        await service.leave_guild(guild_id, user_id)
