import base64
import io
import json
import logging
from enum import Enum
from inspect import currentframe
from pathlib import Path
from typing import Any, Protocol

import structlog
from PIL import Image
from structlog.processors import CallsiteParameter

__all__ = (
    "setup_logging",
    "get_logger",
    "LogLevel",
    "LoggerType",
    "BaseHandlerConfig",
)

LoggerType = structlog.stdlib.BoundLogger


class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class BaseHandlerConfig(Protocol):
    """Protocol for handler configurations."""

    def get_handler(self, logger_name: str) -> logging.Handler:
        """Get a configured logging handler."""
        ...


_level = LogLevel.INFO


def setup_logging(
    level: LogLevel | None = None,
    overrides: dict[str, LogLevel | None] | None = None,
) -> None:
    """
    Initialize the logger.

    Args:
        level: Logging level. Defaults to INFO.
        overrides: Logger names mapped to their logging levels. If level value is None, the logger will be disabled.
    """
    if level is not None:
        global _level
        _level = level

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ConsoleFormatter())

    logging.basicConfig(
        level=_level.value,
        format="%(message)s",
        handlers=[console_handler],
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


def get_logger(name: str | None = None, /, *handler_config: BaseHandlerConfig, **initial_values: Any) -> LoggerType:
    """
    Get a logger instance.

    Args:
        name: Logger name. Defaults to the name of the file where it is called.
        handler_config: Logging handler configurations.
        initial_values: Initial values to add to the logger context.

    Returns:
        LoggerType: A logger instance.
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

    logger: LoggerType = structlog.get_logger(name, **initial_values)

    for config in handler_config:
        logger.addHandler(config.get_handler(name))

    return logger


class ConsoleFormatter(logging.Formatter):
    def format(self, record):  # noqa: C901
        try:
            data = json.loads(record.getMessage())
        except json.JSONDecodeError:
            data = {"message": record.getMessage()}

        message_parts = [data.pop("level", record.levelname).upper(), f"event={data.pop("event", "unknown")!r}"]
        for k, v in data.items():
            if v is None:
                continue
            if k in ("func_name", "msg", "message", "timestamp"):
                message_parts.append(v)
            elif isinstance(v, Exception):
                message_parts.append(f"{v.__class__.__name__}: {v!s}")
            elif isinstance(v, float):
                message_parts.append(f"{k}={v:.2f}")
            elif isinstance(v, str):
                if "\n" in v:
                    message_parts.append(f"{k}='''\n{v.strip("\n")}\n'''")
                    continue
                try:
                    if Image.open(io.BytesIO(base64.b64decode(v))).format:
                        message_parts.append(f"{k}={v[:100]}...")
                        continue
                except Exception:  # noqa: S110
                    pass
                message_parts.append(f"{k}={v!r}")
            else:
                message_parts.append(f"{k}={v!r}")

        if record.exc_info:
            message_parts.append(self.formatException(record.exc_info))

        return " | ".join(message_parts)
