import asyncio
import os

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def _read_applied_revisions(database_url: str) -> list[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT version_num FROM alembic_version"))
            return list(result.scalars())
    finally:
        await engine.dispose()


def test_upgrade_head_is_idempotent_and_records_revision() -> None:
    database_url = os.environ["DATABASE_URL"]
    config = Config("alembic.ini")

    command.upgrade(config, "head")
    command.upgrade(config, "head")

    head_revision = ScriptDirectory.from_config(config).get_current_head()
    assert head_revision is not None
    assert asyncio.run(_read_applied_revisions(database_url)) == [head_revision]
