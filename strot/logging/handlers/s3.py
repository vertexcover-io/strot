import contextlib
import json
import logging
import threading
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel


class S3HandlerConfig(BaseModel):
    """Configuration for S3-compatible object storage logging."""

    boto3_session: boto3.Session
    """Configured boto3 session for S3 access."""
    bucket_name: str
    """S3 bucket name for storing logs."""
    endpoint_url: str | None = None
    """Custom S3 endpoint URL (for S3-compatible services)."""
    buffer_size: int = 100
    """Number of log records to buffer before flushing."""
    flush_interval: float = 20.0
    """Time in seconds to wait before flushing buffer."""

    class Config:
        arbitrary_types_allowed = True

    def get_handler(self, logger_name: str) -> logging.Handler:
        """Create and configure an S3LogHandler."""
        return S3LogHandler(
            session=self.boto3_session,
            bucket_name=self.bucket_name,
            key=f"{logger_name}.log",
            endpoint_url=self.endpoint_url,
            buffer_size=self.buffer_size,
            flush_interval=self.flush_interval,
        )


class S3LogHandler(logging.Handler):
    """
    Custom logging handler that writes logs to S3-compatible object storage.

    Features:
    - Buffering with configurable flush intervals
    - Automatic buffer management and cleanup
    - Thread-safe operations
    """

    def __init__(
        self,
        session: boto3.Session,
        bucket_name: str,
        key: str,
        endpoint_url: str | None = None,
        buffer_size: int = 100,
        flush_interval: float = 20.0,
        level=logging.NOTSET,
    ):
        """
        Initialize S3 log handler.

        Args:
            session: Configured boto3 session
            bucket_name: S3 bucket name
            key: S3 key for the log file
            endpoint_url: Custom S3 endpoint URL
            buffer_size: Number of log records to buffer before flushing
            flush_interval: Time in seconds to wait before flushing buffer
            level: Logging level
        """
        super().__init__(level)

        self.bucket_name = bucket_name
        self.key = key
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval

        # Create S3 client from session
        self.s3_client = session.client("s3", endpoint_url=endpoint_url)

        # Single buffer for this handler
        self._buffer: list[str] = []
        self._last_flush: float = time.time()
        self._lock = threading.RLock()

        # Background flush thread
        self._flush_thread = None
        self._stop_event = threading.Event()
        self._start_flush_thread()

        # Ensure bucket exists
        self._ensure_bucket_exists()

        # Create empty log file if it doesn't exist
        self._ensure_log_file_exists()

    def _ensure_bucket_exists(self):
        """Ensure the S3 bucket exists."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                with contextlib.suppress(ClientError):
                    self.s3_client.create_bucket(Bucket=self.bucket_name)

    def _ensure_log_file_exists(self):
        """Create an empty log file if it doesn't exist."""
        try:
            # Check if the log file already exists
            self.s3_client.head_object(Bucket=self.bucket_name, Key=self.key)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                # File doesn't exist, create an empty one
                try:
                    self.s3_client.put_object(Bucket=self.bucket_name, Key=self.key, Body=b"", ContentType="text/plain")
                except ClientError as create_error:
                    # Log error but don't fail initialization
                    print(f"Failed to create initial log file {self.key}: {create_error}")
            # If it's any other error, we can ignore it as the file might exist

    def _start_flush_thread(self):
        """Start background thread for periodic flushing."""
        if self._flush_thread is None:
            self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
            self._flush_thread.start()

    def _flush_loop(self):
        """Background loop for periodic flushing."""
        while not self._stop_event.wait(5.0):  # Check every 5 seconds
            self._flush_expired_buffers()

    def _flush_expired_buffers(self):
        """Flush buffer if it has exceeded flush interval."""
        current_time = time.time()

        with self._lock:
            if (current_time - self._last_flush) >= self.flush_interval and self._buffer:
                self._flush_buffer()

    def emit(self, record):
        """
        Emit a log record to the buffer.
        """
        try:
            # Format the record
            formatted_record = self.format(record)

            # Add timestamp and convert to JSON
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "message": formatted_record,
                "logger": record.name,
            }

            # Add any extra fields from record
            for key, value in record.__dict__.items():
                if key not in (
                    "name",
                    "msg",
                    "args",
                    "levelname",
                    "levelno",
                    "pathname",
                    "filename",
                    "module",
                    "lineno",
                    "funcName",
                    "created",
                    "msecs",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "processName",
                    "process",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                ):
                    log_entry[key] = value

            log_line = json.dumps(log_entry) + "\n"

            with self._lock:
                # Add to buffer
                self._buffer.append(log_line)

                # Check if buffer should be flushed
                if len(self._buffer) >= self.buffer_size:
                    self._flush_buffer()

        except Exception:
            self.handleError(record)

    def _flush_buffer(self):
        """Flush buffer to S3."""
        if not self._buffer:
            return

        try:
            # Get buffered logs
            logs = self._buffer.copy()
            self._buffer.clear()
            self._last_flush = time.time()

            # Get existing content from S3 first
            existing_content = ""

            try:
                response = self.s3_client.get_object(Bucket=self.bucket_name, Key=self.key)
                existing_content = response["Body"].read().decode("utf-8")
            except ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchKey":
                    # Re-raise if it's not a "file doesn't exist" error
                    raise

            # Append new logs to existing content
            new_content = "".join(logs)
            full_content = existing_content + new_content

            # Upload the combined content
            self.s3_client.put_object(
                Bucket=self.bucket_name, Key=self.key, Body=full_content.encode("utf-8"), ContentType="text/plain"
            )

        except Exception as e:
            # Log error but don't fail
            print(f"Failed to flush logs to {self.key}: {e}")

    def flush(self):
        """Flush buffer."""
        with self._lock:
            self._flush_buffer()

    def close(self):
        """Close handler and flush remaining logs."""
        # Stop flush thread
        if self._flush_thread:
            self._stop_event.set()
            self._flush_thread.join(timeout=5.0)

        # Flush remaining logs
        self.flush()

        # Clean up buffer
        with self._lock:
            self._buffer.clear()

        super().close()
