import os
from typing import Literal

from pydantic import WebsocketUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STROT_",
        # This allows reading from both prefixed and non-prefixed env vars
        case_sensitive=False,
        extra="ignore",
    )

    BROWSER_MODE_OR_WS_URL: Literal["headed", "headless"] | WebsocketUrl = "headed"
    """Either 'headed' | 'headless' or a ws://|wss:// WebSocket URL"""

    ANTHROPIC_API_KEY: str

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Create two env settings sources: one with prefix, one without
        from pydantic_settings import EnvSettingsSource

        # First try with prefix, then without
        env_with_prefix = EnvSettingsSource(settings_cls, env_prefix="STROT_", case_sensitive=False)
        env_without_prefix = EnvSettingsSource(settings_cls, env_prefix="", case_sensitive=False)

        return (
            init_settings,
            env_with_prefix,
            env_without_prefix,  # Fallback to non-prefixed
            dotenv_settings,
            file_secret_settings,
        )

    @field_validator("ANTHROPIC_API_KEY", mode="after")
    @classmethod
    def set_anthropic_api_key(cls, value: str):
        os.environ["STROT_ANTHROPIC_API_KEY"] = value
        return value


settings = Settings()
