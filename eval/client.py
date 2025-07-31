from typing import Any

import boto3
import httpx
from botocore.exceptions import ClientError

from strot.logging import LoggerType, get_logger

from .settings import settings


class StrotClient:
    """Client for interacting with the strot API and S3."""

    def __init__(self, logger: LoggerType | None = None):
        self._logger = logger or get_logger()
        self._api_client = httpx.AsyncClient(base_url=settings.API_BASE_URL)
        self._s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        )

    async def create_job(self, target_url: str, label: str) -> str:
        """Create a new job."""
        self._logger.info("create-job", url=target_url, label=label, status="pending")
        try:
            response = await self._api_client.post("/v1/jobs", json={"url": target_url, "label": label})
            response.raise_for_status()
            job_id = response.json()["job_id"]
            self._logger.info("create-job", url=target_url, label=label, status="completed", job_id=job_id)
        except Exception as e:
            self._logger.info("create-job", url=target_url, label=label, status="failed", reason=str(e))
            raise
        else:
            return job_id

    async def get_job(self, job_id: str) -> dict[str, Any]:
        """Fetch job details from API"""
        self._logger.info("get-job", job_id=job_id, status="pending")
        try:
            response = await self._api_client.get(f"/v1/jobs/{job_id}")
            response.raise_for_status()
            job_data = response.json()
            self._logger.info("get-job", job_id=job_id, status="completed", job_status=job_data.get("status"))
        except Exception as e:
            self._logger.info("get-job", job_id=job_id, status="failed", reason=str(e))
            raise
        else:
            return job_data

    async def fetch_data(self, job_id: str, *, limit: int, offset: int) -> list[dict[str, Any]]:
        """Fetch job data"""
        self._logger.info("fetch-data", job_id=job_id, limit=limit, offset=offset, status="pending")
        try:
            response = await self._api_client.get(
                f"/v1/jobs/{job_id}",
                params={"limit": limit, "offset": offset},
                timeout=None,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            json_resposnse = response.json()
            result = json_resposnse.get("result") or {}
            if "error" in result:
                self._logger.info(
                    "fetch-data", job_id=job_id, limit=limit, offset=offset, status="failed", reason=result["error"]
                )
                return []

            data = result.get(json_resposnse.get("label")) or []
            self._logger.info(
                "fetch-data", job_id=job_id, limit=limit, offset=offset, status="completed", entity_count=len(data)
            )
        except Exception as e:
            self._logger.info("fetch-data", job_id=job_id, limit=limit, offset=offset, status="failed", reason=str(e))
            raise
        else:
            return data

    def fetch_logs(self, job_id: str) -> str:
        """Fetch job logs."""
        bucket_name = settings.AWS_S3_LOG_BUCKET
        object_key = f"job-{job_id}.log"

        self._logger.info("fetch-logs", job_id=job_id, bucket=bucket_name, key=object_key, status="pending")
        try:
            response = self._s3_client.get_object(Bucket=bucket_name, Key=object_key)
            log_content = response["Body"].read().decode("utf-8")
            self._logger.info(
                "fetch-logs",
                job_id=job_id,
                bucket=bucket_name,
                key=object_key,
                status="completed",
                content_size=len(log_content),
            )
        except Exception as e:
            if isinstance(e, ClientError) and e.response["Error"]["Code"] == "NoSuchKey":
                self._logger.info(
                    "fetch-logs",
                    job_id=job_id,
                    bucket=bucket_name,
                    key=object_key,
                    status="failed",
                    reason="Logs not found",
                )
                raise FileNotFoundError(f"Logs for job {job_id} not found in S3") from e

            self._logger.info(
                "fetch-logs", job_id=job_id, bucket=bucket_name, key=object_key, status="failed", reason=str(e)
            )
            raise
        else:
            return log_content
