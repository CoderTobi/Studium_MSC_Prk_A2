"""Logging configuration.

Log records carry the request ID so that a client-side error (which shows the
``requestId``) can be matched to backend logs. Prompts, model responses and request
bodies are never logged.
"""

import logging
import sys

from shopping_list.request_context import current_request_id

LOGGER_NAME = "shopping_list"


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id()
        return True


def configure_logging(level: str) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    if not any(getattr(h, "_shopping_list", False) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
        )
        handler.addFilter(_RequestIdFilter())
        handler._shopping_list = True  # type: ignore[attr-defined]
        logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
