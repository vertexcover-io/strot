# Ayejax Dashboard

A modern web application for analyzing Ayejax web scraping jobs and their execution reports.

## Features

- **Job Management**: View all jobs with latest-only filtering for unique URL+tag combinations
- **Real-time Status**: See job status (pending, ready, failed) with live updates
- **Output Visualization**: View structured output data from successful jobs
- **Analysis Reports**: Comprehensive reports showing:
  - Analysis steps and LLM interactions
  - Pagination detection attempts
  - Code generation processes
  - Cost and token usage metrics
- **Log Viewing**: Raw log file viewing with terminal-style display
- **S3 Integration**: Automatic fetching of log files from S3-compatible storage

## Tech Stack

- **Frontend**: Next.js 15 + React + TypeScript + Tailwind CSS
- **Database**: PostgreSQL with Prisma ORM
- **Storage**: AWS S3-compatible (MinIO)
- **UI Components**: Lucide React icons + custom components

## Prerequisites

- Node.js 18+ and npm
- PostgreSQL database running with Ayejax schema
- S3-compatible storage (MinIO) with job log files

## Setup

1. **Install dependencies**:

   ```bash
   npm install
   ```

2. **Configure environment variables**:
   Set the following AYEJAX\_ prefixed environment variables in your system (same as the Python API):

   ```bash
   # PostgreSQL Configuration
   export AYEJAX_POSTGRES_USER="your_postgres_user"
   export AYEJAX_POSTGRES_PASSWORD="your_postgres_password"
   export AYEJAX_POSTGRES_DB="your_database_name"
   export AYEJAX_POSTGRES_HOST="localhost"
   export AYEJAX_POSTGRES_PORT="5432"

   # AWS S3 Configuration
   export AYEJAX_AWS_ACCESS_KEY_ID="your_access_key"
   export AYEJAX_AWS_SECRET_ACCESS_KEY="your_secret_key"
   export AYEJAX_AWS_REGION="us-east-1"
   export AYEJAX_AWS_S3_ENDPOINT_URL="http://localhost:9000"
   export AYEJAX_AWS_S3_LOG_BUCKET="job-logs"

   # Optional: Environment mode (default: local)
   export AYEJAX_ENV="local"
   ```

   **Note**: The dashboard reads directly from system environment variables, just like the Python API does. It does not use `.env` files.

3. **Generate Prisma client**:

   ```bash
   npx prisma generate
   ```

4. **Start development server**:

   ```bash
   npm run dev
   ```

5. **Open the dashboard**:
   Navigate to `http://localhost:3000`

## Usage

### Job List View

- Browse all jobs with status filtering
- Jobs are automatically filtered to show latest for each URL+tag combination
- Click on any job card to view details

### Job Detail View

- **Details Tab**: Basic job information and metadata
- **Output Tab**: Structured output data (if available)
- **Report Tab**: Comprehensive analysis report with:
  - Cost and token usage summary
  - Step-by-step analysis breakdown
  - LLM interaction details
  - Pagination detection results
  - Code generation attempts
- **Logs Tab**: Raw JSONL log files in terminal format

### Report Features

- **Collapsible Sections**: Expand/collapse different parts of the report
- **LLM Metadata**: Provider, model, token usage, and costs
- **Status Indicators**: Visual status for each step and process
- **Code Viewing**: Syntax-highlighted generated code
- **Performance Metrics**: Total costs, tokens, and execution time

## Architecture

- **API Routes**: `/api/jobs` for job listing, `/api/jobs/[id]` for details, `/api/jobs/[id]/report` for reports
- **Database**: Prisma ORM connecting to existing Ayejax PostgreSQL schema
- **Storage**: S3 client for fetching log files from MinIO/S3
- **Report Generation**: TypeScript implementation parsing JSONL logs into structured reports

## Development

This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

- Uses Next.js App Router for file-based routing
- TypeScript for type safety
- Tailwind CSS for styling
- Prisma for database ORM
- AWS SDK for S3 operations

## Deployment

The application can be deployed to any platform supporting Next.js:

1. **Vercel**: `npx vercel`
2. **Docker**: Build and run with Docker
3. **Traditional hosting**: Build with `npm run build` and serve

Make sure to set the environment variables in your deployment environment.

## Future Enhancements

- Real-time job status updates via WebSockets
- Export reports to PDF/HTML
- Job filtering and search capabilities
- Bulk job operations
- Performance analytics and trends
- User authentication and authorization
