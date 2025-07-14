from abc import ABC, abstractmethod


class LogStorageInterface(ABC):
    """Abstract interface for log storage backends."""
    
    @abstractmethod
    async def ensure_bucket_exists(self, bucket_name: str) -> bool:
        """Ensure the log bucket exists, create if necessary."""
        pass
    
    @abstractmethod
    async def append_to_job_log(self, bucket: str, job_id: str, log_data: str) -> bool:
        """Append log data to job's log file."""
        pass
    
    @abstractmethod
    async def get_job_log(self, bucket: str, job_id: str) -> str:
        """Get complete log content for a job."""
        pass
    
    @abstractmethod
    async def setup_retention_policy(self, bucket: str, days: int) -> bool:
        """Setup retention policy for the bucket."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources (called on shutdown)."""
        pass