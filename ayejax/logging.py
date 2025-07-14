import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from inspect import currentframe
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from structlog.processors import CallsiteParameter

__all__ = (
    "setup_logging",
    "get_logger",
    "FileHandlerConfig",
    "LogLevel",
    "LoggerType",
    "JobLogManager",
    "JobLogSettings",
)

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
    console_handler.setFormatter(UnstructuredLoggingFormatter())

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


def get_logger(
    name: str | None = None, *, file_handler_config: FileHandlerConfig | None = None, **initial_values: Any
) -> LoggerType:
    """
    Get a logger instance.

    Args:
        name: Logger name. Defaults to the name of the file where it is called.
        file_handler_config: Configuration for the file handler. Defaults to None (no file logging).
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
        logger.addHandler(file_handler)

    return logger


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


class JobLogSettings(BaseSettings):
    """Settings for job log export."""
    log_backend: str = "s3"
    log_bucket: str = "ayejax-logs"
    log_flush_interval: int = 20  # seconds
    log_retention_days: int = 7
    
    # S3 settings
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_endpoint_url: str = ""
    aws_region: str = "us-east-1"
    
    # State storage settings
    s3_state_storage_backend: str = "memory"
    s3_state_cleanup_interval_hours: int = 24
    
    class Config:
        env_prefix = "AYEJAX_"


class JobLogBuffer:
    """Buffer for job logs before flushing to storage."""
    
    def __init__(self, job_id: str, flush_interval: int = 20):
        self.job_id = job_id
        self.flush_interval = flush_interval
        self.buffer: List[str] = []
        self.last_flush = datetime.utcnow()
        self._lock = asyncio.Lock()
    
    async def add_log(self, log_line: str) -> None:
        """Add log line to buffer."""
        async with self._lock:
            self.buffer.append(log_line)
    
    async def get_and_clear_buffer(self) -> List[str]:
        """Get buffered logs and clear buffer."""
        async with self._lock:
            logs = self.buffer.copy()
            self.buffer.clear()
            self.last_flush = datetime.utcnow()
            return logs
    
    def should_flush(self) -> bool:
        """Check if buffer should be flushed."""
        return (datetime.utcnow() - self.last_flush).total_seconds() >= self.flush_interval
    
    def has_logs(self) -> bool:
        """Check if buffer has logs."""
        return len(self.buffer) > 0


class JobLogManager:
    """Manager for job log collection and export."""
    
    def __init__(self, settings: JobLogSettings):
        self.settings = settings
        self.storage: Optional[Any] = None  # LogStorageInterface
        self.buffers: Dict[str, JobLogBuffer] = {}
        self.flush_task: Optional[asyncio.Task] = None
        self.logger = get_logger(__name__)
        self._shutdown = False
    
    async def initialize(self) -> None:
        """Initialize log storage and start background tasks."""
        if self.settings.log_backend == "s3":
            from .storage import LogStorageFactory
            
            self.storage = LogStorageFactory.create_s3_storage(
                endpoint_url=self.settings.aws_endpoint_url,
                access_key_id=self.settings.aws_access_key_id,
                secret_access_key=self.settings.aws_secret_access_key,
                region_name=self.settings.aws_region,
                state_backend=self.settings.s3_state_storage_backend,
            )
            
            # Ensure bucket exists
            await self.storage.ensure_bucket_exists(self.settings.log_bucket)
            
            # Setup retention policy
            await self.storage.setup_retention_policy(
                self.settings.log_bucket, 
                self.settings.log_retention_days
            )
            
            # Start cleanup task for S3 storage
            if hasattr(self.storage, 'start_cleanup_task'):
                await self.storage.start_cleanup_task()
            
            self.logger.info("Job log manager initialized with S3 backend")
        else:
            raise ValueError(f"Unknown log backend: {self.settings.log_backend}")
        
        # Start flush task
        self.flush_task = asyncio.create_task(self._flush_loop())
    
    async def start_job_logging(self, job_id: str) -> None:
        """Start logging for a job."""
        if job_id not in self.buffers:
            self.buffers[job_id] = JobLogBuffer(job_id, self.settings.log_flush_interval)
            self.logger.debug(f"Started logging for job {job_id}")
    
    async def add_job_log(self, job_id: str, log_data: dict) -> None:
        """Add log entry for a job."""
        if job_id not in self.buffers:
            await self.start_job_logging(job_id)
        
        # Convert log data to JSON string
        log_line = json.dumps(log_data) + "\n"
        await self.buffers[job_id].add_log(log_line)
    
    async def finish_job_logging(self, job_id: str) -> None:
        """Finish logging for a job and flush remaining logs."""
        if job_id in self.buffers:
            # Flush remaining logs
            await self._flush_job_logs(job_id)
            
            # Complete multipart upload if using S3
            if hasattr(self.storage, 'complete_multipart_upload'):
                await self.storage.complete_multipart_upload(
                    self.settings.log_bucket, job_id
                )
            
            # Remove buffer
            del self.buffers[job_id]
            self.logger.debug(f"Finished logging for job {job_id}")
    
    async def _flush_job_logs(self, job_id: str) -> None:
        """Flush logs for a specific job."""
        if job_id not in self.buffers:
            return
        
        buffer = self.buffers[job_id]
        if not buffer.has_logs():
            return
        
        logs = await buffer.get_and_clear_buffer()
        if logs and self.storage:
            log_data = "".join(logs)
            success = await self.storage.append_to_job_log(
                self.settings.log_bucket, job_id, log_data
            )
            if success:
                self.logger.debug(f"Flushed {len(logs)} log lines for job {job_id}")
            else:
                self.logger.error(f"Failed to flush logs for job {job_id}")
    
    async def _flush_loop(self) -> None:
        """Background loop for flushing logs."""
        while not self._shutdown:
            try:
                # Check each buffer for flush conditions
                for job_id, buffer in list(self.buffers.items()):
                    if buffer.should_flush() and buffer.has_logs():
                        await self._flush_job_logs(job_id)
                
                # Sleep for a short interval
                await asyncio.sleep(5)  # Check every 5 seconds
            except Exception as e:
                self.logger.error(f"Error in flush loop: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown log manager and flush all remaining logs."""
        self._shutdown = True
        
        # Cancel flush task
        if self.flush_task:
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush all remaining logs
        for job_id in list(self.buffers.keys()):
            await self.finish_job_logging(job_id)
        
        # Cleanup storage
        if self.storage:
            await self.storage.cleanup()
        
        self.logger.info("Job log manager shutdown complete")


# Global job log manager instance
_job_log_manager: Optional[JobLogManager] = None


async def get_job_log_manager() -> JobLogManager:
    """Get global job log manager instance."""
    global _job_log_manager
    if _job_log_manager is None:
        settings = JobLogSettings()
        _job_log_manager = JobLogManager(settings)
        await _job_log_manager.initialize()
    return _job_log_manager


async def shutdown_job_log_manager() -> None:
    """Shutdown global job log manager."""
    global _job_log_manager
    if _job_log_manager:
        await _job_log_manager.shutdown()
        _job_log_manager = None
