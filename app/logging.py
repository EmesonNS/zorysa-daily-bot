"""Logging configuration with explicit secret redaction."""

import logging
from collections.abc import Iterable


class SecretRedactionFilter(logging.Filter):
    """Replace configured secret values in formatted log messages."""

    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self._secrets = tuple(secret for secret in secrets if secret)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in self._secrets:
            message = message.replace(secret, "[REDACTED]")
        record.msg = message
        record.args = ()
        return True


def configure_logging(*, level: str, secrets: Iterable[str] = ()) -> None:
    """Configure the root logger for application and dependency messages."""

    handler = logging.StreamHandler()
    handler.addFilter(SecretRedactionFilter(secrets))
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
