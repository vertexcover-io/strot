import json
import logging
from enum import Enum
from inspect import currentframe
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel
from structlog.processors import CallsiteParameter

LoggerType = structlog.stdlib.BoundLogger


class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class FileHandlerConfig(BaseModel):
    directory: str | Path
    """Directory to store the log file."""
    when: str = "midnight"
    """When to rotate the log file."""
    interval: int = 1
    """Interval between rotations."""
    backupCount: int = 0
    """Number of backup files to keep."""
    encoding: str | None = None
    """Encoding to use for the log file."""
    delay: bool = False
    """Delay the creation of the log file."""
    utc: bool = False
    """Whether to use UTC time for the log file."""


def create_logger(
    name: str | None = None,
    *,
    level: LogLevel | None = None,
    file_handler_config: FileHandlerConfig | None = None,
    overrides: dict[str, LogLevel | None] | None = None,
    **initial_values: Any,
) -> LoggerType:
    """
    Create a new logger instance.

    Args:
        name: Logger name. Defaults to the name of the file where it is called.
        level: Logging level. Defaults to INFO.
        file_handler_config: Configuration for the file handler. Defaults to None (no file logging).
        overrides: Logger names mapped to their logging levels. Defaults to {}. If a value is None, the logger will be disabled.
        initial_values: Initial values to add to the logger context.

    Returns:
        LoggerType: A new logger instance.
    """
    if name is None:
        try:
            frame = currentframe()
            source = frame.f_back.f_code.co_filename
            name = Path(source).stem
            if name == "__init__":
                name = Path(source).parent.stem
        except Exception:
            name = "unknown"

    logging.getLogger(name).handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(UnstructuredLoggingFormatter())

    handlers = [console_handler]

    if file_handler_config is not None:
        target_dir = Path(file_handler_config.directory)
        target_dir.mkdir(parents=True, exist_ok=True)

        file_handler = TimedRotatingFileHandler(
            filename=target_dir / f"{name}.log",
            when=file_handler_config.when,
            interval=file_handler_config.interval,
            backupCount=file_handler_config.backupCount,
            encoding=file_handler_config.encoding,
            delay=file_handler_config.delay,
            utc=file_handler_config.utc,
        )
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        handlers.append(file_handler)

    logging.basicConfig(
        level=(level or LogLevel.INFO).value,
        format="%(message)s",
        handlers=handlers,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.format_exc_info,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.CallsiteParameterAdder(parameters=[CallsiteParameter.FUNC_NAME]),
            structlog.stdlib.filter_by_level,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    for logger_name, log_level in (overrides or {}).items():
        lg = logging.getLogger(logger_name)
        if log_level is None:
            lg.disabled = True
        else:
            lg.setLevel(log_level.value)

    return structlog.get_logger(name, **initial_values)


class UnstructuredLoggingFormatter(logging.Formatter):
    def format(self, record):
        try:
            data = json.loads(record.getMessage())
        except json.JSONDecodeError:
            data = {"message": record.getMessage()}

        message_parts = [data.pop("level", record.levelname).upper(), f"event={data.pop('event', 'unknown')!r}"]
        for k, v in data.items():
            if v is None:
                continue
            if k in ("func_name", "msg", "message", "timestamp"):
                message_parts.append(v)
            elif k in ("exception", "error"):
                if isinstance(v, Exception):
                    message_parts.append(f"{v.__class__.__name__}: {v!s}")
                else:
                    message_parts.append(v)
            elif isinstance(v, float):
                message_parts.append(f"{k}={v:.2f}")
            else:
                message_parts.append(f"{k}={v!r}")

        if record.exc_info:
            message_parts.append(self.formatException(record.exc_info))

        return " | ".join(message_parts)
