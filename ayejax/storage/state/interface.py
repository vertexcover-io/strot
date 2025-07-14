from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class MultipartUploadState:
    """State for S3 multipart upload."""
    upload_id: str
    parts: List[Dict[str, str]] = field(default_factory=list)  # [{'ETag': 'etag', 'PartNumber': 1}]
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)


class StateStorageInterface(ABC):
    """Abstract interface for storing S3 multipart upload state."""
    
    @abstractmethod
    async def get_upload_state(self, job_id: str) -> Optional[MultipartUploadState]:
        """Get multipart upload state for a job."""
        pass
    
    @abstractmethod
    async def save_upload_state(self, job_id: str, state: MultipartUploadState) -> None:
        """Save/update multipart upload state."""
        pass
    
    @abstractmethod
    async def delete_upload_state(self, job_id: str) -> None:
        """Delete multipart upload state (job completed)."""
        pass
    
    @abstractmethod
    async def list_active_uploads(self) -> List[str]:
        """List all job IDs with active uploads."""
        pass
    
    @abstractmethod
    async def cleanup_stale_uploads(self, max_age_hours: int = 24) -> int:
        """Clean up stale uploads, return count deleted."""
        pass