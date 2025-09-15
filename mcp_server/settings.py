import os
from typing import Literal

from pydantic import ValidationError, WebsocketUrl, field_validator
from pydantic_settings import BaseSettings

from mcp_server.exceptions import MissingEnvironmentVariablesError


class Settings(BaseSettings):
    model_config = {"env_prefix": "STROT_"}

    BROWSER_MODE_OR_WS_URL: Literal["headed", "headless"] | WebsocketUrl = "headed"
    """Either 'headed' | 'headless' or a ws://|wss:// WebSocket URL"""

    ANTHROPIC_API_KEY: str

    @field_validator("ANTHROPIC_API_KEY", mode="after")
    @classmethod
    def set_anthropic_api_key(cls, value: str):
        os.environ["STROT_ANTHROPIC_API_KEY"] = value
        return value

    def __init__(self, **kwargs):
        try:
            super().__init__(**kwargs)
        except ValidationError as e:
            missing_keys = []
            prefix = self.model_config["env_prefix"]
            for error in e.errors():
                if error["type"] == "missing":
                    field_name = error["loc"][0]
                    missing_keys.append(f"{prefix}{field_name}")

            if missing_keys:
                raise MissingEnvironmentVariablesError(missing_keys) from e
            else:
                raise


settings = Settings()
