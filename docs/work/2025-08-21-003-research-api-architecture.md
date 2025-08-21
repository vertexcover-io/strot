# Strot API Architecture

## Overview

The Strot API (`api/strot_api/`) is a FastAPI-based REST server that provides HTTP endpoints for managing analysis jobs and labels. It serves as the orchestration layer between web clients and the strot analysis engine, handling job queuing, execution tracking, and result storage.

## Core Architecture

### FastAPI Application (`main.py`)

- **Framework**: FastAPI with async/await support
- **CORS**: Configured for localhost:3000 frontend access
- **Lifespan Management**: Context manager handles browser and database connection lifecycle
- **Browser Integration**: Shared browser instance managed at application level
- **AWS S3 Integration**: Log bucket creation and management for job logging

### Configuration Management (`settings.py`)

**Environment Variables** (prefixed with `STROT_`):

- **Browser**: WebSocket URL for browser connection (`ws://localhost:5678/patchright`)
- **Database**: PostgreSQL connection parameters with auto-generated URI
- **AWS**: S3 credentials and bucket configuration for job logging
- **Validation**: Automatic PostgreSQL URI construction from components

### Database Layer (`database/`)

#### Session Management (`__init__.py`)

- **SessionManager**: Async context manager for database lifecycle
- **Connection Handling**: Automatic rollback on exceptions
- **Dependency Injection**: FastAPI dependency for database sessions
- **Engine Management**: SQLAlchemy async engine with connection pooling

#### Schema Design

**Labels Table** (`schema/label.py`):

```sql
- id: UUID (primary key)
- name: String(50) (unique) - Label identifier
- requirement: Text - Natural language query description
- output_schema: JSONB - Pydantic schema for data extraction
- created_at/updated_at: Timestamps with auto-update
```

**Jobs Table** (`schema/job.py`):

```sql
- id: UUID (primary key)
- url: Text - Target URL for analysis
- label_id: UUID (foreign key to labels, cascade delete)
- status: String(20) - "pending" | "ready" | "failed"
- source: JSONB - Strot Source object (analysis metadata)
- usage_count: Integer - Number of times source has been used
- last_used_at: Timestamp - Last source usage
- error: Text - Error message for failed jobs
- initiated_at/completed_at: Timestamps for job lifecycle
```

**Relationships**:

- One-to-many: Label → Jobs with cascade deletion
- Foreign key constraints ensure referential integrity

## API Endpoints

### Labels Management (`routes/labels.py`)

**POST /labels** - Create Label:

- Input: `name`, `requirement`, `output_schema`
- Validation: Unique name constraint
- Response: Full label object with metadata

**GET /labels** - List Labels:

- Pagination: `limit` (1-100), `offset`
- Search: By name or requirement text (case-insensitive)
- Response: Paginated list with `has_next` indicator

**GET /labels/{label_id}** - Get Label:

- Path parameter: UUID label identifier
- Response: Complete label details

**PUT /labels/{label_id}** - Update Label:

- Partial updates: `requirement` and/or `output_schema`
- Validation: Only provided fields updated
- Response: Updated label object

**DELETE /labels/{label_id}** - Delete Label:

- Protection: Fails if jobs exist unless `force=true`
- Cascade: Force deletion removes associated jobs
- Response: 204 No Content

### Jobs Management (`routes/jobs.py`)

**POST /v1/jobs** - Create Job:

- Input: `url` (HttpUrl), `label` (string name)
- Validation: Label must exist
- Background Processing: Async job execution via BackgroundTasks
- Response: `job_id` with 202 Accepted status

**GET /v1/jobs** - List Jobs:

- Pagination: `limit` (1-100), `offset`
- Filters: `status`, `label` name, URL `search`
- Ordering: Most recent first
- Eager Loading: Includes label relationship
- Response: Paginated job list with usage statistics

**GET /v1/jobs/{job_id}** - Get Job:

- Path parameter: UUID job identifier
- Optional Data Extraction: `limit`, `offset` query parameters
- Timeout Detection: Auto-fails stale pending jobs (60s inactivity)
- Source Execution: On-demand data extraction using stored source
- Usage Tracking: Increments count and updates timestamp
- Response: Job details with optional extracted data

**DELETE /v1/jobs/{job_id}** - Delete Job:

- Protection: Cannot delete pending jobs
- Cleanup: Removes job record
- Response: 204 No Content

## Background Job Processing

### Job Execution Flow (`process_job_request`)

1. **Analysis Invocation**: Calls `strot.analyze()` with job parameters
2. **Browser Sharing**: Uses application-level shared browser instance
3. **Logging Integration**: S3-backed structured logging with job ID
4. **Result Storage**: Serializes Source object to JSONB column
5. **Status Updates**: Atomically updates job status and metadata
6. **Error Handling**: Captures exceptions and stores error messages

### Source Data Extraction

- **On-Demand**: Data extraction happens when `limit` parameter provided
- **Source Object**: Uses stored analysis metadata for actual scraping
- **Pagination Support**: Respects limit/offset parameters
- **Usage Analytics**: Tracks extraction frequency and timing
- **Error Isolation**: Source execution errors don't fail job retrieval

## Infrastructure Integration

### AWS S3 Logging

- **Structured Logging**: JSON-formatted logs per job
- **S3 Handler**: Automatic log upload with 15-second flush interval
- **Job Isolation**: Each job gets dedicated log file (`job-{uuid}.log`)
- **Timeout Detection**: Log activity monitoring for stale job detection

### Browser Management

- **Shared Instance**: Single browser shared across all jobs
- **WebSocket Connection**: Persistent connection to browser service
- **Resilient Connection**: Auto-reconnection via ResilientBrowser
- **Resource Efficiency**: Connection pooling reduces overhead

### Database Features

- **Async Operations**: Full async/await support with asyncpg
- **Transaction Management**: Automatic rollback on exceptions
- **Eager Loading**: Optimized queries with relationship loading
- **Migration Support**: Alembic integration for schema versioning

## API Design Patterns

### Error Handling

- **HTTP Status Codes**: Semantic status codes (404, 400, 422, etc.)
- **Detailed Messages**: Descriptive error messages with context
- **Validation**: Pydantic model validation with field-level errors
- **Exception Isolation**: Background task failures don't crash API

### Response Models

- **Type Safety**: Pydantic models for all request/response data
- **Pagination**: Consistent pagination pattern with metadata
- **Relationship Loading**: Efficient database queries with joins
- **Null Safety**: Optional fields properly handled

### Security Considerations

- **Input Validation**: URL validation and parameter sanitization
- **Resource Limits**: Pagination limits and timeout protections
- **Error Disclosure**: Safe error messages without sensitive data
- **Background Safety**: Isolated job execution with error containment

This architecture provides a robust, scalable API layer for managing web analysis jobs with comprehensive error handling, efficient resource usage, and clear separation of concerns between job orchestration and analysis execution.
