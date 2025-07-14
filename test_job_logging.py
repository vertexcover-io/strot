#!/usr/bin/env python3
"""
Test script for job logging with MinIO.

Setup MinIO with Docker:
docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  quay.io/minio/minio server /data --console-address ":9001"

Environment variables:
export AYEJAX_AWS_ACCESS_KEY_ID=minioadmin
export AYEJAX_AWS_SECRET_ACCESS_KEY=minioadmin
export AYEJAX_AWS_ENDPOINT_URL=http://localhost:9000
export AYEJAX_AWS_REGION=us-east-1
export AYEJAX_LOG_BUCKET=ayejax-logs
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime

# Add the project to path
sys.path.insert(0, '/home/abhishek/Downloads/experiments/vertexcover/ayejax')

from ayejax.job_logging import JobLogContext, with_job_logging
from ayejax.logging import shutdown_job_log_manager


async def test_basic_logging():
    """Test basic job logging functionality."""
    job_id = str(uuid.uuid4())
    print(f"Testing basic logging for job: {job_id}")
    
    async with JobLogContext(job_id) as log_ctx:
        await log_ctx.log_job_info("Job started processing")
        await asyncio.sleep(2)  # Simulate work
        
        await log_ctx.log_job_info("Processing data", step="data_processing", progress=0.5)
        await asyncio.sleep(1)
        
        await log_ctx.log_job_debug("Debug information", debug_data={"key": "value"})
        await asyncio.sleep(1)
        
        await log_ctx.log_job_info("Processing complete", step="completion", progress=1.0)
    
    print(f"Job {job_id} logging completed")


async def test_error_logging():
    """Test error logging functionality."""
    job_id = str(uuid.uuid4())
    print(f"Testing error logging for job: {job_id}")
    
    try:
        async with JobLogContext(job_id) as log_ctx:
            await log_ctx.log_job_info("Job started with error scenario")
            await asyncio.sleep(1)
            
            await log_ctx.log_job_error("Something went wrong", error=ValueError("Test error"))
            await asyncio.sleep(1)
            
            # This will cause the context to log job_failed
            raise RuntimeError("Simulated job failure")
    except RuntimeError:
        print(f"Job {job_id} failed as expected")


@with_job_logging("job_id")
async def test_decorator_logging(job_id: str):
    """Test decorator-based logging."""
    print(f"Testing decorator logging for job: {job_id}")
    
    await asyncio.sleep(1)
    print("Doing some work...")
    await asyncio.sleep(1)
    
    return {"result": "success"}


async def test_concurrent_jobs():
    """Test concurrent job logging."""
    print("Testing concurrent job logging...")
    
    async def simulate_job(job_num: int):
        job_id = str(uuid.uuid4())
        async with JobLogContext(job_id) as log_ctx:
            await log_ctx.log_job_info(f"Job {job_num} started")
            await asyncio.sleep(job_num * 0.5)  # Different durations
            await log_ctx.log_job_info(f"Job {job_num} processing", step=f"step_{job_num}")
            await asyncio.sleep(1)
            await log_ctx.log_job_info(f"Job {job_num} completed")
    
    # Run 5 concurrent jobs
    tasks = [simulate_job(i) for i in range(1, 6)]
    await asyncio.gather(*tasks)
    
    print("All concurrent jobs completed")


async def test_long_running_job():
    """Test long-running job that will trigger multiple flushes."""
    job_id = str(uuid.uuid4())
    print(f"Testing long-running job: {job_id}")
    
    async with JobLogContext(job_id) as log_ctx:
        await log_ctx.log_job_info("Starting long-running job")
        
        # Generate logs for 45 seconds (should trigger 2+ flushes with 20s interval)
        for i in range(45):
            await log_ctx.log_job_info(f"Processing step {i}", step=i, timestamp=datetime.utcnow().isoformat())
            await asyncio.sleep(1)
        
        await log_ctx.log_job_info("Long-running job completed")
    
    print(f"Long-running job {job_id} completed")


async def main():
    """Run all tests."""
    # Check environment variables
    required_env = [
        "AYEJAX_AWS_ACCESS_KEY_ID",
        "AYEJAX_AWS_SECRET_ACCESS_KEY", 
        "AYEJAX_AWS_ENDPOINT_URL"
    ]
    
    missing_env = [var for var in required_env if not os.getenv(var)]
    if missing_env:
        print(f"Missing required environment variables: {missing_env}")
        print("Please set up MinIO and export the required variables.")
        return
    
    print("Starting job logging tests...")
    print(f"Using endpoint: {os.getenv('AYEJAX_AWS_ENDPOINT_URL')}")
    print(f"Using bucket: {os.getenv('AYEJAX_LOG_BUCKET', 'ayejax-logs')}")
    
    try:
        # Test basic logging
        await test_basic_logging()
        await asyncio.sleep(2)
        
        # Test error logging
        await test_error_logging()
        await asyncio.sleep(2)
        
        # Test decorator logging
        job_id = str(uuid.uuid4())
        result = await test_decorator_logging(job_id)
        print(f"Decorator test result: {result}")
        await asyncio.sleep(2)
        
        # Test concurrent jobs
        await test_concurrent_jobs()
        await asyncio.sleep(2)
        
        # Test long-running job (uncomment to test flush behavior)
        # await test_long_running_job()
        
        print("\nAll tests completed!")
        print("Check your MinIO console at http://localhost:9001 to see the log files.")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Shutdown the log manager
        await shutdown_job_log_manager()
        print("Log manager shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())