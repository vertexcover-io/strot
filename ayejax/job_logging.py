"""
Job lifecycle integration for logging export.
"""
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