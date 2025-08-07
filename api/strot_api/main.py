from contextlib import asynccontextmanager, suppress

import boto3
from botocore.errorfactory import ClientError
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from strot import launch_browser
from strot_api.database import sessionmanager
from strot_api.routes import jobs, labels
from strot_api.settings import settings

boto3_session = boto3.Session(
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)

s3_client = boto3_session.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL)

try:
    s3_client.head_bucket(Bucket=settings.AWS_S3_LOG_BUCKET)
except ClientError as e:
    if e.response["Error"]["Code"] == "404":
        with suppress(ClientError):
            s3_client.create_bucket(Bucket=settings.AWS_S3_LOG_BUCKET)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""

    async with (
        sessionmanager,
        launch_browser(settings.BROWSER_WS_URL) as browser,
    ):
        app.state.browser = browser
        yield


app = FastAPI(title="Strot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(labels.router)


@app.get("/")
async def root():
    return {"message": "Strot API is running"}
