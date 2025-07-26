from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from strot.analyzer import create_browser
from strot_api.database import sessionmanager
from strot_api.routes import jobs, labels
from strot_api.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""

    async with (
        sessionmanager,
        create_browser(settings.BROWSER_TYPE) as browser,
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
