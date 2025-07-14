# Supabase Logging Export System

## Overview
Design and implement a job-based logging system that stores logs in Supabase storage buckets with regular flushing to prevent data loss during application crashes.

## Requirements Analysis

### Core Requirements  
1. **Single file per job**: One log file per job ID for easy analysis
2. **Appendable storage**: Support appending to existing files in Supabase
3. **Time-based flushing**: 20-second intervals to minimize crash data loss
4. **Full job lifecycle**: Log from creation through completion
5. **Bucket management**: Auto-create logs bucket, 7-day retention
6. **Backend agnostic**: Interface for swapping storage backends
7. **Integration**: Extend existing `ayejax/logging.py` system
8. **Performance**: Handle 5 jobs/second creation rate

### Current State Analysis
- Project uses structlog with JSON formatting
- Job model has UUID primary key suitable for log organization  
- TimedRotatingFileHandler available but needs cloud integration
- No Supabase credentials yet (need setup)
- No API endpoints needed initially

## Architecture Design

### 1. Core Components

#### A. Log Storage Interface (Backend Agnostic)
```python
# Abstract interface for swappable backends  
class LogStorageInterface:
    async def ensure_bucket_exists(self, bucket_name: str) -> bool
    async def append_to_job_log(self, bucket: str, job_id: str, log_data: str) -> bool
    async def get_job_log(self, bucket: str, job_id: str) -> str
    async def setup_retention_policy(self, bucket: str, days: int) -> bool
```

#### B. Backend Implementations

**Supabase Implementation:**
```python
class SupabaseLogStorage(LogStorageInterface):
    # Note: No true append - requires download→modify→upload
    # Cache file content locally, batch uploads every 20s
```

**S3-Compatible Implementation:**
```python
class S3LogStorage(LogStorageInterface):
    # True append support using S3 multipart uploads
    # Each log chunk becomes a new part, assembled on read
    # Much more efficient for frequent appends
```

#### C. Job Log Buffer Manager
```python
# Manages per-job log buffering and timed flushing
class JobLogBuffer:
    job_id: str
    buffer: List[str]  # Log lines waiting to flush
    last_flush: datetime
    flush_interval: int = 20  # seconds
```

### 2. Simplified Flushing Strategy

#### Time-based Flushing (Selected)
- **Mechanism**: Fixed 20-second interval flush per job
- **Pros**: Simple, predictable, max 20s data loss on crash
- **Implementation**: asyncio background task per active job
- **Triggers**: 
  - Timer: Every 20 seconds
  - Job completion: Immediate flush
  - Job error: Immediate flush
  - Application shutdown: Flush all buffers

#### Backend-Specific Append Strategies

**Supabase Challenge & Solution:**
- **Problem**: No direct append support
- **Solution**: Download→modify→upload pattern
- **Optimization**: Local caching, batch multiple appends

**S3-Compatible Advantage:**
- **Native Support**: S3 multipart uploads for true append
- **Efficiency**: Each flush creates new part, no download needed
- **Performance**: Much faster for frequent appends

### 3. Simplified System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Extended        │───▶│  JobLogBuffer    │───▶│ LogStorageInterface │
│ StructLog       │    │                  │    │                 │
│                 │    │ - Per-job buffer │    │ - ensure_bucket │
│ - Job context   │    │ - 20s timer      │    │ - append_to_log │
│ - JSON format   │    │ - Event triggers │    │ - get_job_log   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                  │                        │
                                  │                        ▼
                       ┌──────────▼──────────┐   ┌─────────────────┐
                       │ Background Flusher  │   │ SupabaseStorage │
                       │                     │   │                 │
                       │ - asyncio timer     │   │ - Download file │
                       │ - Batch operations  │   │ - Append data   │
                       │ - Error handling    │   │ - Re-upload     │
                       └─────────────────────┘   └─────────────────┘
```

### 4. Simplified File Organization

```
ayejax-logs/                    # Single bucket
├── job-{uuid}.log              # One file per job (complete lifecycle)
├── job-{uuid}.log              # Easy to download and analyze
├── job-{uuid}.log              # Contains: creation → execution → completion
└── ...
```

**File Format**:
- **Filename**: `job-{uuid}.log` (e.g., `job-123e4567-e89b-12d3-a456-426614174000.log`)
- **Content**: JSON lines format (one JSON object per line)
- **Retention**: 7 days automatic deletion
- **Size**: Grows throughout job lifecycle, flushed every 20s

## Simplified Implementation Plan

### Phase 1: Foundation (Day 1)
1. **Dependencies**: Add `supabase` and `boto3` to pyproject.toml 
2. **LogStorageInterface**: Abstract interface with 4 methods
3. **Backend Implementations**: 
   - **SupabaseLogStorage**: Download→modify→upload pattern
   - **S3LogStorage**: Multipart upload for true append
4. **Configuration**: Environment variables for both backends

### Phase 2: Integration (Day 1-2)  
1. **Extend logging.py**: Add job context and buffering
2. **JobLogBuffer**: Per-job buffer with 20s timer
3. **Backend Factory**: Select backend based on config
4. **Job Lifecycle Hooks**: Start/stop logging on job events
5. **Bucket Setup**: Auto-create bucket on application startup

### Phase 3: Production Ready (Day 2-3)
1. **Error Handling**: Retry logic, fallback to local files
2. **Performance**: Connection pooling, batch operations  
3. **Retention**: 7-day bucket lifecycle policy
4. **Testing**: Unit tests for both backends

### Phase 4: Deployment (Day 3)
1. **Environment Setup**: Backend-specific credentials
2. **Configuration**: Production environment variables
3. **Monitoring**: Basic health checks and error logging
4. **Documentation**: Setup and usage instructions for both backends

## Technology Choices

### Dependencies
- `supabase`: Python client for Supabase integration  
- `boto3`: AWS SDK for S3-compatible storage (Amazon S3, Cloudflare R2, Storj)
- `asyncio`: For 20-second timer and non-blocking operations
- `structlog`: Extend existing logging (already in use)
- `pydantic`: Configuration management (already in use)

### Configuration Requirements

#### Option 1: Supabase Backend
```python
AYEJAX_LOG_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
AYEJAX_LOG_BUCKET=ayejax-logs
AYEJAX_LOG_FLUSH_INTERVAL=20
AYEJAX_LOG_RETENTION_DAYS=7
```

#### Option 2: S3-Compatible Backend
```python
AYEJAX_LOG_BACKEND=s3
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_ENDPOINT_URL=https://s3.amazonaws.com  # or R2/Storj endpoint
AWS_REGION=us-east-1
AYEJAX_LOG_BUCKET=ayejax-logs
AYEJAX_LOG_FLUSH_INTERVAL=20
AYEJAX_LOG_RETENTION_DAYS=7
```

## Risk Assessment & Solutions

### Key Challenges
1. **No True Append**: Supabase requires download→modify→upload for append
2. **Performance**: 5 jobs/second * 20s buffering = 100 concurrent buffers
3. **S3 State Management**: Track multipart upload state across app restarts
4. **File Conflicts**: Multiple processes trying to update same job log
5. **Network Failures**: Upload failures during 20s flush intervals

### Simple Solutions
1. **Append Strategy**: 
   - **Supabase**: Cache file content locally, batch multiple log lines
   - **S3**: Use multipart uploads for true append operations
2. **S3 State Management**: In-memory state with database persistence for recovery
3. **Memory Management**: Limit buffer size per job (e.g., 1000 lines max)
4. **Conflict Resolution**: Use job-specific file locking mechanism
5. **Failure Handling**: Fallback to local files, retry on next flush cycle

## S3-Compatible Implementation Details

### S3 Multipart Upload Strategy & State Storage

#### Option 1: In-Memory State (Recommended)
```python
class S3LogStorage(LogStorageInterface):
    def __init__(self):
        self.active_uploads: Dict[str, MultipartUploadState] = {}
        # job_id -> {upload_id, parts: []}
    
    async def append_to_job_log(self, bucket: str, job_id: str, log_data: str):
        # 1. Check if multipart upload exists in memory
        # 2. If not, initiate multipart upload & store state
        # 3. Upload log_data as new part
        # 4. Store part ETag in active_uploads[job_id].parts
```

#### Option 2: Database State (More Robust)
```python
# Add to existing job model
class Job(Base):
    # ... existing fields ...
    s3_upload_id: str | None = None
    s3_parts: JSON | None = None  # Store parts info as JSON
```

#### Option 3: Redis/Cache State (Distributed)
```python
# For multi-instance deployments
class S3LogStorage(LogStorageInterface):
    async def get_upload_state(self, job_id: str):
        return await redis.get(f"s3_upload:{job_id}")
    
    async def save_upload_state(self, job_id: str, state: dict):
        await redis.set(f"s3_upload:{job_id}", json.dumps(state))
```

#### Recommended Approach: In-Memory + Database Fallback
- **Primary**: In-memory for active jobs (fast access)
- **Persistence**: Save upload_id to database on job completion
- **Recovery**: Rebuild active_uploads from database on startup

### S3 Provider Endpoints
```python
# Amazon S3
AWS_ENDPOINT_URL=https://s3.amazonaws.com

# Cloudflare R2  
AWS_ENDPOINT_URL=https://your-account.r2.cloudflarestorage.com

# Storj
AWS_ENDPOINT_URL=https://gateway.storjshare.io
```

### S3 Advantages over Supabase
- **True Append**: No download→modify→upload cycle
- **Better Performance**: Direct append operations
- **Lower Bandwidth**: Only upload new data
- **Atomic Operations**: Each part upload is atomic
- **Cost Effective**: No data transfer for reads during append

## Success Criteria
- [ ] Single log file per job for easy analysis
- [ ] Max 20 seconds log loss during crashes
- [ ] Handle 5 jobs/second creation rate
- [ ] 7-day retention policy working
- [ ] Backend swapping capability maintained
- [ ] Integration with existing logging system

## Implementation Changes Required

### 1. Add Dependencies
```bash
uv add supabase boto3
```

### 2. Extend ayejax/logging.py
- Add job context support to structlog
- Implement JobLogBuffer class
- Add background flush timer
- Create LogStorageInterface

### 3. Create new files
- `ayejax/storage/` - Storage interface and implementations
- `ayejax/storage/supabase.py` - Supabase-specific implementation
- `ayejax/storage/s3.py` - S3-compatible implementation (AWS/R2/Storj)
- `ayejax/storage/factory.py` - Backend factory based on config
- Environment configuration for multiple backends

### 4. Integration points
- Job creation: Start logging context
- Job completion: Immediate flush
- Application startup: Initialize bucket
- Application shutdown: Flush all buffers

---

**Status**: Planning Complete - Ready for Implementation  
**Created**: 2025-07-14  
**Last Updated**: 2025-07-14  
**Simplified Requirements**: Single file per job, 20s flush, 7-day retention, 5 jobs/sec support