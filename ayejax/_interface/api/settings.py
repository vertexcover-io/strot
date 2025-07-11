from typing import Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: Literal["local", "prod"] = "local"

    POSTGRES_USER: str = "synacktra"
    POSTGRES_PASSWORD: str = "secretpassword"
    POSTGRES_DB: str = "default"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_URI: str = Field(default="")

    @field_validator("POSTGRES_URI", mode="after")
    @classmethod
    def validate_db_uri(cls, _, info: ValidationInfo):
        password = info.data["POSTGRES_PASSWORD"]
        user = info.data["POSTGRES_USER"]
        host = info.data["POSTGRES_HOST"]
        port = info.data["POSTGRES_PORT"]
        name = info.data["POSTGRES_DB"]
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"

    EXTERNAL_API_REQUEST_TIMEOUT: int = 30


settings = Settings()
