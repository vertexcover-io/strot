import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from pydantic import BaseModel


class FileHandlerConfig(BaseModel):
    """Configuration for file-based logging handler."""

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

    def get_handler(self, logger_name: str) -> logging.Handler:
        """Create and configure a TimedRotatingFileHandler."""
        target_dir = Path(self.directory)
        target_dir.mkdir(parents=True, exist_ok=True)

        file_handler = TimedRotatingFileHandler(
            filename=target_dir / f"{logger_name}.log",
            when=self.when,
            interval=self.interval,
            backupCount=self.backupCount,
            encoding=self.encoding,
            delay=self.delay,
            utc=self.utc,
        )
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        return file_handler
