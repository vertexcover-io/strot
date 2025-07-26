# Strot API

FastAPI server for the Strot web scraping and API discovery service.

## Features

- Job management for web scraping tasks
- Label management for organizing jobs
- Browser automation with Playwright
- PostgreSQL database with SQLAlchemy
- S3-compatible object storage for logs
- Automatic database migrations with Alembic

## Environment Variables

Required:

- `STROT_ANTHROPIC_API_KEY` - Anthropic API key for LLM calls

Optional (with defaults):

- `STROT_POSTGRES_HOST` - Database host (default: localhost)
- `STROT_POSTGRES_USER` - Database user (default: strot-user)
- `STROT_POSTGRES_PASSWORD` - Database password (default: secretpassword)
- `STROT_POSTGRES_DB` - Database name (default: default)
- `STROT_POSTGRES_PORT` - Database port (default: 5432)
- `STROT_AWS_ACCESS_KEY_ID` - S3 access key (default: minioadmin)
- `STROT_AWS_SECRET_ACCESS_KEY` - S3 secret key (default: minioadmin)
- `STROT_AWS_S3_ENDPOINT_URL` - S3 endpoint (default: http://localhost:9000)
- `STROT_AWS_S3_LOG_BUCKET` - S3 bucket for logs (default: job-logs)
- `STROT_BROWSER_TYPE` - Browser type (default: headless)

## Development

### Local Development

1. Install dependencies:

```bash
uv sync
```

2. Start PostgreSQL and MinIO:

```bash
docker-compose up postgres minio -d
```

3. Run migrations:

```bash
alembic upgrade head
```

4. Start the API server:

```bash
STROT_ANTHROPIC_API_KEY=your_key uv run uvicorn strot_api.main:app --reload
```

### Docker

Build and run with Docker Compose:

```bash
export STROT_ANTHROPIC_API_KEY=your_key
docker-compose up api
```

## API Endpoints

- `GET /` - Health check
- `GET /jobs` - List all jobs
- `POST /jobs` - Create a new job
- `GET /jobs/{job_id}` - Get job details
- `DELETE /jobs/{job_id}` - Delete a job
- `GET /jobs/{job_id}/logs` - Get job logs
- `GET /labels` - List all labels
- `POST /labels` - Create a new label
- `PUT /labels/{label_id}` - Update a label
- `DELETE /labels/{label_id}` - Delete a label

## Database

The API uses PostgreSQL with SQLAlchemy ORM. Database migrations are managed with Alembic.

### Creating Migrations

```bash
alembic revision --autogenerate -m "Description of changes"
```

### Running Migrations

```bash
alembic upgrade head
```
