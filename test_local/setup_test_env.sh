#!/bin/bash

echo "Setting up MinIO test environment..."

# Start MinIO with docker-compose
echo "Starting MinIO container..."
docker-compose -f docker-compose.test.yml up -d

# Wait for MinIO to be ready
echo "Waiting for MinIO to be ready..."
sleep 5

# Check if MinIO is running
if ! curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; then
    echo "MinIO is not ready yet, waiting..."
    sleep 10
fi

# Export environment variables
echo "Exporting environment variables..."
export AYEJAX_AWS_ACCESS_KEY_ID=minioadmin
export AYEJAX_AWS_SECRET_ACCESS_KEY=minioadmin
export AYEJAX_AWS_ENDPOINT_URL=http://localhost:9000
export AYEJAX_AWS_REGION=us-east-1
export AYEJAX_LOG_BUCKET=ayejax-logs

echo "Environment variables set:"
echo "  AYEJAX_AWS_ACCESS_KEY_ID=$AYEJAX_AWS_ACCESS_KEY_ID"
echo "  AYEJAX_AWS_SECRET_ACCESS_KEY=$AYEJAX_AWS_SECRET_ACCESS_KEY"
echo "  AYEJAX_AWS_ENDPOINT_URL=$AYEJAX_AWS_ENDPOINT_URL"
echo "  AYEJAX_AWS_REGION=$AYEJAX_AWS_REGION"
echo "  AYEJAX_LOG_BUCKET=$AYEJAX_LOG_BUCKET"

echo ""
echo "MinIO setup complete!"
echo "- MinIO API: http://localhost:9000"
echo "- MinIO Console: http://localhost:9001"
echo "- Username: minioadmin"
echo "- Password: minioadmin"
echo ""
echo "To run the test:"
echo "  python test_job_logging.py"
echo ""
echo "To stop MinIO:"
echo "  docker-compose -f docker-compose.test.yml down"