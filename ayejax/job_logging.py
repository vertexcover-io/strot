"""
Job lifecycle integration for logging export.
"""
__all__ = [
    "JobLogContext",
    "JobAwareLogger", 
    "JobLoggerContext",
    "get_job_aware_logger",
    "with_job_logger",
    "start_job_logging",
    "finish_job_logging", 
    "log_job_event",
    "with_job_logging"
]
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from .logging import get_job_log_manager, get_logger


class JobLogContext:
    """Context manager for job logging lifecycle."""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.log_manager: Optional[Any] = None
        self.logger = get_logger(__name__)
    
    async def __aenter__(self):
        """Start job logging context."""
        self.log_manager = await get_job_log_manager()
        await self.log_manager.start_job_logging(self.job_id)
        
        # Log job start
        await self.log_job_event("job_started", {
            "job_id": self.job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event": "job_started"
        })
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Finish job logging context."""
        if self.log_manager:
            # Log job completion or error
            if exc_type:
                await self.log_job_event("job_failed", {
                    "job_id": self.job_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "event": "job_failed",
                    "error": str(exc_val),
                    "error_type": exc_type.__name__
                })
            else:
                await self.log_job_event("job_completed", {
                    "job_id": self.job_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "event": "job_completed"
                })
            
            await self.log_manager.finish_job_logging(self.job_id)
    
    async def log_job_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log a job event."""
        if self.log_manager:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "job_id": self.job_id,
                "event": event_type,
                "level": "INFO",
                **data
            }
            await self.log_manager.add_job_log(self.job_id, log_entry)
    
    async def log_job_info(self, message: str, **kwargs) -> None:
        """Log job info message."""
        await self.log_job_event("info", {
            "message": message,
            "level": "INFO",
            **kwargs
        })
    
    async def log_job_error(self, message: str, error: Optional[Exception] = None, **kwargs) -> None:
        """Log job error message."""
        log_data = {
            "message": message,
            "level": "ERROR",
            **kwargs
        }
        if error:
            log_data["error"] = str(error)
            log_data["error_type"] = error.__class__.__name__
        
        await self.log_job_event("error", log_data)
    
    async def log_job_debug(self, message: str, **kwargs) -> None:
        """Log job debug message."""
        await self.log_job_event("debug", {
            "message": message,
            "level": "DEBUG",
            **kwargs
        })
    
    # Logger-like interface for drop-in replacement
    async def info(self, event: str, **kwargs) -> None:
        """Logger-like info method."""
        await self.log_job_info(event, **kwargs)
    
    async def error(self, event: str, exception: Exception = None, **kwargs) -> None:
        """Logger-like error method."""
        await self.log_job_error(event, error=exception, **kwargs)
    
    async def debug(self, event: str, **kwargs) -> None:
        """Logger-like debug method."""
        await self.log_job_debug(event, **kwargs)
    
    async def warning(self, event: str, **kwargs) -> None:
        """Logger-like warning method."""
        await self.log_job_event("warning", {
            "message": event,
            "level": "WARNING",
            **kwargs
        })
    
    async def warn(self, event: str, **kwargs) -> None:
        """Logger-like warn method (alias for warning)."""
        await self.warning(event, **kwargs)


# Convenience functions for job logging
async def start_job_logging(job_id: str) -> None:
    """Start logging for a job."""
    log_manager = await get_job_log_manager()
    await log_manager.start_job_logging(job_id)


async def finish_job_logging(job_id: str) -> None:
    """Finish logging for a job."""
    log_manager = await get_job_log_manager()
    await log_manager.finish_job_logging(job_id)


async def log_job_event(job_id: str, event_type: str, data: Dict[str, Any]) -> None:
    """Log a job event."""
    log_manager = await get_job_log_manager()
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "job_id": job_id,
        "event": event_type,
        "level": "INFO",
        **data
    }
    await log_manager.add_job_log(job_id, log_entry)


# Decorator for automatic job logging
def with_job_logging(job_id_param: str = "job_id"):
    """Decorator to automatically add job logging to async functions."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract job_id from parameters
            job_id = None
            
            # First check kwargs
            if job_id_param in kwargs:
                job_id = kwargs[job_id_param]
            else:
                # Check positional arguments using function signature
                import inspect
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                
                if job_id_param in param_names:
                    param_index = param_names.index(job_id_param)
                    if param_index < len(args):
                        job_id = args[param_index]
                
                # If still not found, check if first arg has the attribute
                if job_id is None and args and hasattr(args[0], job_id_param):
                    job_id = getattr(args[0], job_id_param)
            
            if job_id is None:
                raise ValueError(f"Could not find {job_id_param} parameter for job logging")
            
            # Convert UUID to string if needed
            if isinstance(job_id, UUID):
                job_id = str(job_id)
            
            async with JobLogContext(job_id) as log_ctx:
                # Log function start
                await log_ctx.log_job_info(f"Starting {func.__name__}", function=func.__name__)
                
                try:
                    result = await func(*args, **kwargs)
                    await log_ctx.log_job_info(f"Completed {func.__name__}", function=func.__name__)
                    return result
                except Exception as e:
                    await log_ctx.log_job_error(f"Error in {func.__name__}: {e}", error=e, function=func.__name__)
                    raise
        
        return wrapper
    return decorator


class JobAwareLogger:
    """A logger that combines standard logging with job logging."""
    
    def __init__(self, job_id: str, standard_logger):
        self.job_id = job_id
        self.standard_logger = standard_logger
        self.job_context: Optional[JobLogContext] = None
        self._loop = None
        self._context_initialized = False
    
    def _get_or_create_loop(self):
        """Get current event loop or create a new one."""
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    def _schedule_job_log(self, coro):
        """Schedule async job logging in background without blocking."""
        try:
            if self._loop is None:
                self._loop = self._get_or_create_loop()
            
            # Try to schedule in current event loop
            self._loop.create_task(coro)
        except RuntimeError:
            # If no event loop, run in thread pool
            import threading
            def run_async():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(coro)
                    loop.close()
                except Exception:
                    pass  # Fail silently for background logging
            
            thread = threading.Thread(target=run_async)
            thread.daemon = True
            thread.start()
    
    async def _ensure_job_context(self):
        """Ensure job context is available."""
        if self.job_context is None:
            self.job_context = JobLogContext(self.job_id)
            await self.job_context.__aenter__()
    
    def _ensure_job_context_sync(self):
        """Ensure job context is available (synchronous version)."""
        if not self._context_initialized:
            self._schedule_job_log(self._ensure_job_context())
            self._context_initialized = True
    
    def info(self, event: str, **kwargs) -> None:
        """Log info to both standard logger and job logger."""
        self.standard_logger.info(event, **kwargs)
        self._ensure_job_context_sync()
        if self.job_context:
            self._schedule_job_log(self.job_context.info(event, **kwargs))
    
    def error(self, event: str, exception: Exception = None, **kwargs) -> None:
        """Log error to both standard logger and job logger."""
        self.standard_logger.error(event, exception=exception, **kwargs)
        self._ensure_job_context_sync()
        if self.job_context:
            self._schedule_job_log(self.job_context.error(event, exception=exception, **kwargs))
    
    def debug(self, event: str, **kwargs) -> None:
        """Log debug to both standard logger and job logger."""
        self.standard_logger.debug(event, **kwargs)
        self._ensure_job_context_sync()
        if self.job_context:
            self._schedule_job_log(self.job_context.debug(event, **kwargs))
    
    def warning(self, event: str, **kwargs) -> None:
        """Log warning to both standard logger and job logger."""
        self.standard_logger.warning(event, **kwargs)
        self._ensure_job_context_sync()
        if self.job_context:
            self._schedule_job_log(self.job_context.warning(event, **kwargs))
    
    def warn(self, event: str, **kwargs) -> None:
        """Log warning to both standard logger and job logger."""
        self.warning(event, **kwargs)
    
    async def cleanup(self):
        """Cleanup job context."""
        if self.job_context:
            await self.job_context.__aexit__(None, None, None)


def get_job_aware_logger(job_id: str, standard_logger) -> JobAwareLogger:
    """Get a job-aware logger that logs to both standard and job loggers."""
    return JobAwareLogger(str(job_id), standard_logger)


class JobLoggerContext:
    """Async context manager that provides a job-aware logger."""
    
    def __init__(self, job_id: str, standard_logger):
        self.job_id = str(job_id)
        self.standard_logger = standard_logger
        self.job_context = None
        self.logger = None
    
    async def __aenter__(self):
        """Enter context and return job-aware logger."""
        self.job_context = JobLogContext(self.job_id)
        await self.job_context.__aenter__()
        
        # Create a logger that writes to both standard and job logging
        class CombinedLogger:
            def __init__(self, standard_logger, job_context):
                self.standard_logger = standard_logger
                self.job_context = job_context
                self._loop = asyncio.get_event_loop()
            
            def _schedule_job_log(self, coro):
                """Schedule async job logging in background without blocking."""
                try:
                    # Try to schedule in current event loop
                    self._loop.create_task(coro)
                except RuntimeError:
                    # If no event loop, run in thread pool
                    import threading
                    def run_async():
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(coro)
                            loop.close()
                        except Exception:
                            pass  # Fail silently for background logging
                    
                    thread = threading.Thread(target=run_async)
                    thread.daemon = True
                    thread.start()
            
            def info(self, event: str, **kwargs):
                self.standard_logger.info(event, **kwargs)
                self._schedule_job_log(self.job_context.info(event, **kwargs))
            
            def error(self, event: str, exception: Exception = None, **kwargs):
                self.standard_logger.error(event, exception=exception, **kwargs)
                self._schedule_job_log(self.job_context.error(event, exception=exception, **kwargs))
            
            def debug(self, event: str, **kwargs):
                self.standard_logger.debug(event, **kwargs)
                self._schedule_job_log(self.job_context.debug(event, **kwargs))
            
            def warning(self, event: str, **kwargs):
                self.standard_logger.warning(event, **kwargs)
                self._schedule_job_log(self.job_context.warning(event, **kwargs))
            
            def warn(self, event: str, **kwargs):
                self.warning(event, **kwargs)
        
        self.logger = CombinedLogger(self.standard_logger, self.job_context)
        return self.logger
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context and cleanup job logging."""
        if self.job_context:
            await self.job_context.__aexit__(exc_type, exc_val, exc_tb)


def with_job_logger(job_id_param: str = "job_id"):
    """Decorator that injects a job-aware logger into the function."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract job_id from parameters
            job_id = None
            
            # First check kwargs
            if job_id_param in kwargs:
                job_id = kwargs[job_id_param]
            else:
                # Check positional arguments using function signature
                import inspect
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                
                if job_id_param in param_names:
                    param_index = param_names.index(job_id_param)
                    if param_index < len(args):
                        job_id = args[param_index]
            
            if job_id is None:
                raise ValueError(f"Could not find {job_id_param} parameter for job logging")
            
            # Convert UUID to string if needed
            if isinstance(job_id, UUID):
                job_id = str(job_id)
            
            # Get standard logger
            from .logging import get_logger, FileHandlerConfig
            from pathlib import Path
            
            LOG_DIR = Path.home() / ".ayejax" / "logs" / "api"
            standard_logger = get_logger(f"job-{job_id}", file_handler_config=FileHandlerConfig(directory=LOG_DIR / "jobs"))
            
            # Use JobLoggerContext
            async with JobLoggerContext(job_id, standard_logger) as logger:
                # Inject logger into function - replace existing logger param
                kwargs['logger'] = logger
                
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator