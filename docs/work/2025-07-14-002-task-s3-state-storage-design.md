# S3 State Storage Design Pattern

## Overview
Design a pluggable state storage system for S3 multipart upload tracking that starts with in-memory storage and can be easily upgraded to PostgreSQL persistence later.

## Requirements
- **Initial**: In-memory storage for simplicity
- **Future**: PostgreSQL backend for persistence across restarts
- **Good Practices**: Interface-based design, dependency injection, easy swapping

## State Storage Interface Design

### 1. Core Interface
```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class MultipartUploadState:
    upload_id: str
    parts: List[Dict[str, str]]  # [{'ETag': 'etag', 'PartNumber': 1}]
    created_at: datetime
    last_updated: datetime

class StateStorageInterface(ABC):
    @abstractmethod
    async def get_upload_state(self, job_id: str) -> Optional[MultipartUploadState]:
        """Get multipart upload state for a job"""
        pass
    
    @abstractmethod
    async def save_upload_state(self, job_id: str, state: MultipartUploadState) -> None:
        """Save/update multipart upload state"""
        pass
    
    @abstractmethod
    async def delete_upload_state(self, job_id: str) -> None:
        """Delete multipart upload state (job completed)"""
        pass
    
    @abstractmethod
    async def list_active_uploads(self) -> List[str]:
        """List all job IDs with active uploads"""
        pass
    
    @abstractmethod
    async def cleanup_stale_uploads(self, max_age_hours: int = 24) -> int:
        """Clean up stale uploads, return count deleted"""
        pass
```

### 2. In-Memory Implementation
```python
class InMemoryStateStorage(StateStorageInterface):
    def __init__(self):
        self._uploads: Dict[str, MultipartUploadState] = {}
        self._lock = asyncio.Lock()
    
    async def get_upload_state(self, job_id: str) -> Optional[MultipartUploadState]:
        async with self._lock:
            return self._uploads.get(job_id)
    
    async def save_upload_state(self, job_id: str, state: MultipartUploadState) -> None:
        async with self._lock:
            state.last_updated = datetime.utcnow()
            self._uploads[job_id] = state
    
    async def delete_upload_state(self, job_id: str) -> None:
        async with self._lock:
            self._uploads.pop(job_id, None)
    
    async def list_active_uploads(self) -> List[str]:
        async with self._lock:
            return list(self._uploads.keys())
    
    async def cleanup_stale_uploads(self, max_age_hours: int = 24) -> int:
        async with self._lock:
            cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
            stale_jobs = [
                job_id for job_id, state in self._uploads.items()
                if state.last_updated < cutoff
            ]
            for job_id in stale_jobs:
                del self._uploads[job_id]
            return len(stale_jobs)
```

### 3. PostgreSQL Implementation (Future)
```python
class PostgreSQLStateStorage(StateStorageInterface):
    def __init__(self, db_session):
        self.db = db_session
    
    async def get_upload_state(self, job_id: str) -> Optional[MultipartUploadState]:
        # Query s3_upload_states table
        query = select(S3UploadState).where(S3UploadState.job_id == job_id)
        result = await self.db.execute(query)
        row = result.scalar_one_or_none()
        
        if row:
            return MultipartUploadState(
                upload_id=row.upload_id,
                parts=row.parts,
                created_at=row.created_at,
                last_updated=row.last_updated
            )
        return None
    
    async def save_upload_state(self, job_id: str, state: MultipartUploadState) -> None:
        # Upsert into s3_upload_states table
        stmt = insert(S3UploadState).values(
            job_id=job_id,
            upload_id=state.upload_id,
            parts=state.parts,
            created_at=state.created_at,
            last_updated=datetime.utcnow()
        ).on_conflict_do_update(
            index_elements=['job_id'],
            set_={
                'upload_id': stmt.excluded.upload_id,
                'parts': stmt.excluded.parts,
                'last_updated': stmt.excluded.last_updated
            }
        )
        await self.db.execute(stmt)
        await self.db.commit()
    
    # ... other methods
```

## Database Schema (Future)
```sql
CREATE TABLE s3_upload_states (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL UNIQUE,
    upload_id VARCHAR(255) NOT NULL,
    parts JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_job_id FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX idx_s3_upload_states_job_id ON s3_upload_states(job_id);
CREATE INDEX idx_s3_upload_states_last_updated ON s3_upload_states(last_updated);
```

## Factory Pattern for Configuration
```python
class StateStorageFactory:
    @staticmethod
    def create_storage(backend_type: str, **kwargs) -> StateStorageInterface:
        if backend_type == "memory":
            return InMemoryStateStorage()
        elif backend_type == "postgresql":
            db_session = kwargs.get('db_session')
            if not db_session:
                raise ValueError("db_session required for PostgreSQL backend")
            return PostgreSQLStateStorage(db_session)
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")

# Usage in S3LogStorage
class S3LogStorage(LogStorageInterface):
    def __init__(self, s3_client, state_storage: StateStorageInterface):
        self.s3_client = s3_client
        self.state_storage = state_storage
```

## Configuration
```python
# Environment variables
S3_STATE_STORAGE_BACKEND=memory  # or postgresql
S3_STATE_CLEANUP_INTERVAL_HOURS=24

# In settings.py
class S3LogSettings(BaseSettings):
    state_storage_backend: str = "memory"
    state_cleanup_interval_hours: int = 24
```

## Integration with S3LogStorage
```python
class S3LogStorage(LogStorageInterface):
    def __init__(self, s3_client, state_storage: StateStorageInterface):
        self.s3_client = s3_client
        self.state_storage = state_storage
        self._cleanup_task = None
    
    async def start_cleanup_task(self):
        """Start background task for cleaning up stale uploads"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                cleaned = await self.state_storage.cleanup_stale_uploads(24)
                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} stale uploads")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
    
    async def append_to_job_log(self, bucket: str, job_id: str, log_data: str) -> bool:
        # Get existing state
        state = await self.state_storage.get_upload_state(job_id)
        
        if state is None:
            # Start new multipart upload
            response = await self.s3_client.create_multipart_upload(
                Bucket=bucket,
                Key=f"job-{job_id}.log"
            )
            state = MultipartUploadState(
                upload_id=response['UploadId'],
                parts=[],
                created_at=datetime.utcnow(),
                last_updated=datetime.utcnow()
            )
        
        # Upload new part
        part_number = len(state.parts) + 1
        response = await self.s3_client.upload_part(
            Bucket=bucket,
            Key=f"job-{job_id}.log",
            PartNumber=part_number,
            UploadId=state.upload_id,
            Body=log_data
        )
        
        # Update state
        state.parts.append({
            'ETag': response['ETag'],
            'PartNumber': part_number
        })
        
        await self.state_storage.save_upload_state(job_id, state)
        return True
```

## Migration Strategy
1. **Phase 1**: Implement in-memory storage with full interface
2. **Phase 2**: Add PostgreSQL implementation when needed
3. **Phase 3**: Update factory to choose backend via config
4. **Phase 4**: Add database migration for s3_upload_states table

## Benefits of This Design
- **Separation of Concerns**: State storage is independent of S3 operations
- **Testability**: Easy to mock StateStorageInterface
- **Flexibility**: Can add Redis, file-based, or other backends later
- **Performance**: In-memory is fast, PostgreSQL adds persistence
- **Cleanup**: Built-in stale upload cleanup mechanism
- **Type Safety**: Full typing support with dataclasses

## Testing Strategy
```python
# Test with mock storage
class MockStateStorage(StateStorageInterface):
    def __init__(self):
        self.states = {}
    
    async def get_upload_state(self, job_id: str):
        return self.states.get(job_id)
    
    # ... implement other methods

# In tests
async def test_s3_log_storage():
    mock_storage = MockStateStorage()
    s3_storage = S3LogStorage(mock_s3_client, mock_storage)
    
    await s3_storage.append_to_job_log("bucket", "job-123", "log data")
    
    state = await mock_storage.get_upload_state("job-123")
    assert state is not None
    assert len(state.parts) == 1
```

---

**Status**: Design Complete - Ready for Implementation  
**Created**: 2025-07-14  
**Pattern**: Interface-based state storage with in-memory start and PostgreSQL migration path