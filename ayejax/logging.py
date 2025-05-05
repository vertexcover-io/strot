from __future__ import annotations

import sys

from loguru import logger
from loguru._logger import Logger as LoguruLogger

__all__ = ("Logger",)


logger.remove(0)

DEFAULT_LOGGER_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> <bg #0f0707>[{extra[class_name]}]</bg #0f0707> <level>{message}</level>"
)


class Logger:
    """
    Logger class that can be inherited for class based logging.

    Examples:

        >>> class ClassName(Logger, format="<level>{message}</level>"):
        ...     def __init__(self):
        ...         self.logger.info("Class initialized")
        ...
        ...     @classmethod
        ...     def cls_method(cls):
        ...         cls.logger.info("Class method called")
        ...
        >>> ClassName()
        >>> ClassName.cls_method()
        >>> ClassName.logger.info("Hello Logger")
    """

    logger: LoguruLogger

    @classmethod
    def __init_subclass__(cls, *, format: str | None = None, cls_name: str | None = None):
        """
        Args:
            format: Logging format to use.
            cls_name: Custom name for the class.
        """
        cls_name = cls_name or cls.__name__
        logger.add(
            sys.stdout,
            format=format or DEFAULT_LOGGER_FORMAT,
            filter=lambda record: record["extra"].get("class_name") == cls_name,
        )
        cls.logger = logger.bind(class_name=cls_name).opt(colors=True)  # type: ignore[assignment]
