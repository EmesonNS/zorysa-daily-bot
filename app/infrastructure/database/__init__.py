"""Asynchronous database infrastructure."""

from app.infrastructure.database.core import Database, DatabaseUnavailableError

__all__ = ["Database", "DatabaseUnavailableError"]
