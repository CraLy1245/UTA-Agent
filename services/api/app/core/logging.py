from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from services.api.app.core.security import redact_text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))

    def formatException(self, exc_info: object) -> str:
        return redact_text(super().formatException(exc_info))  # type: ignore[arg-type]


def _handler(path: Path, *, level: int) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path, maxBytes=2_000_000, backupCount=3, encoding="utf-8", delay=True
    )
    handler.setLevel(level)
    handler.setFormatter(
        RedactingFormatter(
            "%(asctime)s %(levelname)s conversation_id=%(conversation_id)s "
            "turn_id=%(turn_id)s job_id=%(job_id)s module=%(name)s %(message)s"
        )
    )
    return handler


class ContextDefaults(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for name in ("conversation_id", "turn_id", "job_id"):
            if not hasattr(record, name):
                setattr(record, name, "-")
        return True


def configure_logging(log_directory: str) -> None:
    directory = Path(log_directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    formatter_filter = ContextDefaults()
    targets = {
        "survival.app": ("app.log", logging.INFO),
        "survival.agent": ("agent.log", logging.INFO),
        "survival.worker": ("worker.log", logging.INFO),
    }
    for logger_name, (filename, level) in targets.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.propagate = False
        if not logger.handlers:
            handler = _handler(directory / filename, level=level)
            handler.addFilter(formatter_filter)
            logger.addHandler(handler)

    error_logger = logging.getLogger("survival.error")
    error_logger.setLevel(logging.ERROR)
    error_logger.propagate = False
    if not error_logger.handlers:
        handler = _handler(directory / "error.log", level=logging.ERROR)
        handler.addFilter(formatter_filter)
        error_logger.addHandler(handler)
