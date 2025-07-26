# Strot UI

A modern web application for managing Strot web scraping jobs through a clean interface. This UI connects to the Strot API to provide job management, log viewing, and data analysis capabilities.

## Features

- **Job Management**: Create, view, and manage web scraping jobs
- **Label Management**: Create and edit labels (schemas) for data extraction
- **Real-time Status**: Live job status updates with auto-refresh for pending jobs
- **Log Viewing**: Raw and rendered log viewing with terminal-style display
- **Data Preview**: View extracted data with copy-to-clipboard functionality
- **API Integration**: Full integration with Strot API endpoints
- **Source Tab**: Generate curl commands for programmatic access

## Tech Stack

- **Frontend**: Next.js 15 + React + TypeScript + Tailwind CSS
- **API Integration**: Custom API client for Strot endpoints
- **Storage**: S3-compatible storage for log files
- **UI Components**: Heroicons + Lucide React + custom components

## Prerequisites

- Node.js 18+ and npm
- Running Strot API server
- S3-compatible storage (MinIO) with job log files

## Setup

1. **Install dependencies**:

   ```bash
   npm install
   ```

2. **Configure environment variables**:

   The UI requires S3 credentials for log viewing and API configuration. Set these STROT\_ prefixed environment variables:

   ```bash
   # API Configuration
   export STROT_API_BASE_URL="http://localhost:1337"

   # S3 Configuration for log viewing
   export STROT_AWS_ACCESS_KEY_ID="your_access_key"
   export STROT_AWS_SECRET_ACCESS_KEY="your_secret_key"
   export STROT_AWS_REGION="us-east-1"
   export STROT_AWS_S3_ENDPOINT_URL="http://localhost:9000"
   export STROT_AWS_S3_LOG_BUCKET="job-logs"
   ```

3. **Start development server**:

   ```bash
   npm run dev
   ```

4. **Open the UI**:
   Navigate to `http://localhost:3000`

## Usage

### Jobs Management

- **View Jobs**: Browse all jobs with status, search, and pagination
- **Create Jobs**: Submit new scraping jobs with URL and label selection
- **Job Details**: View comprehensive job information in 3 tabs:
  - **Job Details**: Basic information, status, and metadata
  - **Source**: API endpoint with curl command and extracted data preview
  - **Log Viewer**: Raw and rendered log viewing with auto-refresh

### Labels Management

- **View Labels**: Browse all available labels (extraction schemas)
- **Create Labels**: Define new labels with requirements and output schemas
- **Edit Labels**: Modify existing label configurations

### Features

- **Auto-refresh**: Pending jobs automatically refresh every 15 seconds
- **Search & Filter**: Find jobs by URL, status, or label
- **Copy Functionality**: Copy curl commands and JSON data to clipboard
- **Responsive Design**: Works on desktop and mobile devices

## Architecture

- **API Client**: TypeScript client for all Strot API interactions
- **Component Based**: Modular React components with TypeScript
- **S3 Integration**: Direct S3 access for log file retrieval
- **No Database**: UI communicates only with API, no direct database access

## Development

This is a [Next.js](https://nextjs.org) project using:

- Next.js App Router for file-based routing
- TypeScript for type safety
- Tailwind CSS for styling
- Custom API client for Strot integration
- AWS SDK for S3 log file access

## API Endpoints

The UI expects the following API endpoints:

- `GET /v1/jobs` - List jobs with filtering and pagination
- `POST /v1/jobs` - Create new jobs
- `GET /v1/jobs/{id}` - Get job details with optional data sampling
- `DELETE /v1/jobs/{id}` - Delete jobs
- `GET /labels` - List labels
- `POST /labels` - Create labels
- `PUT /labels/{id}` - Update labels
- `DELETE /labels/{id}` - Delete labels

## Deployment

The application can be deployed to any platform supporting Next.js:

1. **Vercel**: `npx vercel`
2. **Docker**: Build and run with Docker
3. **Traditional hosting**: Build with `npm run build` and serve

Make sure to set the environment variables in your deployment environment.

## Configuration

- **API URL**: Set `STROT_API_BASE_URL` to your Strot API server (default: http://localhost:1337)
- **S3 Access**: Configure STROT*AWS*\* credentials for log file access

## Future Enhancements

- Real-time WebSocket updates for job status
- Export functionality for reports and data
- Advanced search and filtering options
- Bulk job operations
- Performance analytics dashboard
- User management and permissions
