"""Configuration models for streaming and human intervention."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field

from strot.streaming.notifiers.base import Notifier
from strot.streaming.notifiers.desktop import DesktopNotifier


class IntervalConfig(TypedDict, total=False):
    """Configuration for intervention timing intervals."""

    timeout: float  # Maximum time to wait for intervention (seconds)
    check_interval: float  # How often to check if task is complete (seconds)


class StreamingConfig(BaseModel):
    """Configuration for streaming server and human intervention."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    server_host: str = Field(default="localhost", description="Host for streaming server")
    server_port: int = Field(default=8004, description="Port for streaming server")

    intervention_notifier: Notifier | Callable[[str], Awaitable[None]] = Field(
        default_factory=lambda: DesktopNotifier(),
        description="Notifier instance or callback function for sending intervention notifications",
    )

    intervals: IntervalConfig = Field(
        default_factory=lambda: IntervalConfig(
            timeout=600.0,  # 10 minutes default
            check_interval=15.0,  # Check every 15 seconds
        ),
        description="Timing configuration for intervention verification",
    )

    verification_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="LLM model to use for task verification",
    )
