"""
Main FastAPI application for the API marketplace
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ayejax import create_browser
from ayejax._interface.api.database import sessionmanager
from ayejax._interface.api.routes import apis, jobs
from ayejax._interface.api.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""

    async with (
        sessionmanager,
        create_browser("headless" if settings.ENV == "prod" else "headed") as browser,
    ):
        app.state.browser = browser
        yield


app = FastAPI(title="Ayejax API Marketplace", version="1.0.0", lifespan=lifespan)

app.include_router(apis.router)
app.include_router(jobs.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Ayejax API Marketplace"}
