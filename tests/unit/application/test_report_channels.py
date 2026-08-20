import pytest

from app.application.dto import ActorContext
from app.application.errors import ValidationError
from app.application.report_channels import ReportChannelService


def _actor() -> ActorContext:
    return ActorContext(1, "Guild", 2, (), True, True)


@pytest.mark.parametrize("channel_id", [0, -1])
async def test_report_channel_id_is_validated_before_database_access(channel_id: int) -> None:
    service = ReportChannelService(None)  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="canal"):
        await service.save_channel(
            actor=_actor(),
            channel_id=channel_id,
            daily=True,
            weekly=False,
            monthly=False,
        )


async def test_report_channel_requires_at_least_one_enabled_type() -> None:
    service = ReportChannelService(None)  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="tipo"):
        await service.save_channel(
            actor=_actor(),
            channel_id=10,
            daily=False,
            weekly=False,
            monthly=False,
        )
