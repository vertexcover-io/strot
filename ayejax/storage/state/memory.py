import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .interface import StateStorageInterface, MultipartUploadState


class InMemoryStateStorage(StateStorageInterface):
    """In-memory storage for S3 multipart upload state."""
    
    def __init__(self):
        self._uploads: Dict[str, MultipartUploadState] = {}
        self._lock = asyncio.Lock()
    
    async def get_upload_state(self, job_id: str) -> Optional[MultipartUploadState]:
        """Get multipart upload state for a job."""
        async with self._lock:
            return self._uploads.get(job_id)
    
    async def save_upload_state(self, job_id: str, state: MultipartUploadState) -> None:
        """Save/update multipart upload state."""
        async with self._lock:
            state.last_updated = datetime.utcnow()
            self._uploads[job_id] = state
    
    async def delete_upload_state(self, job_id: str) -> None:
        """Delete multipart upload state (job completed)."""
        async with self._lock:
            self._uploads.pop(job_id, None)
    
    async def list_active_uploads(self) -> List[str]:
        """List all job IDs with active uploads."""
        async with self._lock:
            return list(self._uploads.keys())
    
    async def cleanup_stale_uploads(self, max_age_hours: int = 24) -> int:
        """Clean up stale uploads, return count deleted."""
        async with self._lock:
            cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
            stale_jobs = [
                job_id for job_id, state in self._uploads.items()
                if state.last_updated < cutoff
            ]
            for job_id in stale_jobs:
                del self._uploads[job_id]
            return len(stale_jobs)