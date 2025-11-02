"""Base class for human intervention notifiers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

UrgencyLevel = Literal["critical", "normal", "low"]


class Notifier(ABC):
    """Abstract base class for sending human intervention notifications.

    Implementations should send notifications via their respective channels
    (Slack, email, SMS, etc.) when human intervention is required.
    """

    @abstractmethod
    async def send(
        self,
        title: str,
        message: str,
        urgency: UrgencyLevel = "normal",
    ) -> None:
        """Send a notification.

        Args:
            title: Notification title
            message: Notification message in markdown format,
                typically containing intervention reason and stream URL.
            urgency: Urgency level of the notification
        """
        ...
