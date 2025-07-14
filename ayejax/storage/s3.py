import asyncio
import json
from datetime import datetime
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from ayejax.logging import get_logger
from .interface import LogStorageInterface
from .state import StateStorageInterface, MultipartUploadState


class S3LogStorage(LogStorageInterface):
    """S3-compatible log storage implementation using multipart uploads."""
    
    def __init__(self, s3_client, state_storage: StateStorageInterface, logger=None):
        self.s3_client = s3_client
        self.state_storage = state_storage
        self.logger = logger or get_logger(__name__)
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def ensure_bucket_exists(self, bucket_name: str) -> bool:
        """Ensure the log bucket exists, create if necessary."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.s3_client.head_bucket(Bucket=bucket_name)
            )
            self.logger.info(f"Bucket {bucket_name} exists")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket doesn't exist, create it
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: self.s3_client.create_bucket(Bucket=bucket_name)
                    )
                    self.logger.info(f"Created bucket {bucket_name}")
                    return True
                except ClientError as create_error:
                    self.logger.error(f"Failed to create bucket {bucket_name}: {create_error}")
                    return False
            else:
                self.logger.error(f"Error checking bucket {bucket_name}: {e}")
                return False
    
    async def append_to_job_log(self, bucket: str, job_id: str, log_data: str) -> bool:
        """Append log data to job's log file using multipart upload."""
        try:
            # Get existing state
            state = await self.state_storage.get_upload_state(job_id)
            
            if state is None:
                # Start new multipart upload
                response = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: self.s3_client.create_multipart_upload(
                        Bucket=bucket,
                        Key=f"job-{job_id}.log",
                        ContentType="text/plain"
                    )
                )
                state = MultipartUploadState(
                    upload_id=response['UploadId'],
                    parts=[],
                    created_at=datetime.utcnow(),
                    last_updated=datetime.utcnow()
                )
                self.logger.debug(f"Started multipart upload for job {job_id}")
            
            # Upload new part
            part_number = len(state.parts) + 1
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.upload_part(
                    Bucket=bucket,
                    Key=f"job-{job_id}.log",
                    PartNumber=part_number,
                    UploadId=state.upload_id,
                    Body=log_data.encode('utf-8')
                )
            )
            
            # Update state
            state.parts.append({
                'ETag': response['ETag'],
                'PartNumber': part_number
            })
            
            await self.state_storage.save_upload_state(job_id, state)
            self.logger.debug(f"Uploaded part {part_number} for job {job_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to append log for job {job_id}: {e}")
            return False
    
    async def complete_multipart_upload(self, bucket: str, job_id: str) -> bool:
        """Complete multipart upload for a job."""
        try:
            state = await self.state_storage.get_upload_state(job_id)
            if state is None:
                self.logger.warning(f"No upload state found for job {job_id}")
                return False
            
            # Complete multipart upload
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.complete_multipart_upload(
                    Bucket=bucket,
                    Key=f"job-{job_id}.log",
                    UploadId=state.upload_id,
                    MultipartUpload={
                        "Parts": state.parts
                    }
                )
            )
            
            # Clean up state
            await self.state_storage.delete_upload_state(job_id)
            self.logger.info(f"Completed multipart upload for job {job_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to complete upload for job {job_id}: {e}")
            return False
    
    async def get_job_log(self, bucket: str, job_id: str) -> str:
        """Get complete log content for a job."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.get_object(
                    Bucket=bucket,
                    Key=f"job-{job_id}.log"
                )
            )
            return response['Body'].read().decode('utf-8')
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                self.logger.warning(f"Log file not found for job {job_id}")
                return ""
            else:
                self.logger.error(f"Failed to get log for job {job_id}: {e}")
                return ""
    
    async def setup_retention_policy(self, bucket: str, days: int) -> bool:
        """Setup retention policy for the bucket."""
        try:
            lifecycle_config = {
                'Rules': [
                    {
                        'ID': 'LogRetentionRule',
                        'Status': 'Enabled',
                        'Expiration': {
                            'Days': days
                        }
                    }
                ]
            }
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.put_bucket_lifecycle_configuration(
                    Bucket=bucket,
                    LifecycleConfiguration=lifecycle_config
                )
            )
            
            self.logger.info(f"Set retention policy for bucket {bucket}: {days} days")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set retention policy for bucket {bucket}: {e}")
            return False
    
    async def start_cleanup_task(self):
        """Start background task for cleaning up stale uploads."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Background loop for cleaning up stale uploads."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                cleaned = await self.state_storage.cleanup_stale_uploads(24)
                if cleaned > 0:
                    self.logger.info(f"Cleaned up {cleaned} stale uploads")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup resources (called on shutdown)."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass