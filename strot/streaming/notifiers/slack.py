"""Slack notifier for human intervention requests."""

from __future__ import annotations

import httpx

from strot.streaming.notifiers.base import Notifier, UrgencyLevel

URGENCY_CONFIG = {
    "critical": {"color": "#ff0000", "emoji": "🚨"},
    "normal": {"color": "#ffa500", "emoji": "⚠️"},
    "low": {"color": "#808080", "emoji": "ℹ️"},  # noqa: RUF001
}


class SlackNotifier(Notifier):
    """Send intervention notifications to Slack using webhooks or Bot API.

    Supports two methods:
    1. Webhook URL (simpler, no token needed)
    2. Bot token + channel (more flexible, requires bot setup)
    """

    def __init__(
        self,
        webhook_url: str | None = None,
        bot_token: str | None = None,
        channel: str | None = None,
    ):
        """Initialize Slack notifier.

        Args:
            webhook_url: Slack incoming webhook URL (preferred method)
            bot_token: Slack bot token (alternative to webhook)
            channel: Slack channel ID or name (required if using bot_token)

        Raises:
            ValueError: If neither webhook_url nor (bot_token + channel) provided
        """
        if webhook_url:
            self.webhook_url = webhook_url
            self.bot_token = None
            self.channel = None
        elif bot_token and channel:
            self.webhook_url = None
            self.bot_token = bot_token
            self.channel = channel
        else:
            msg = "Must provide either webhook_url or (bot_token + channel)"
            raise ValueError(msg)

    async def send(
        self,
        title: str,
        message: str,
        urgency: UrgencyLevel = "normal",
    ) -> None:
        """Send notification to Slack.

        Args:
            title: Notification title
            message: Message in markdown format
            urgency: Urgency level (critical, normal, low)

        Raises:
            httpx.HTTPError: If Slack API request fails
        """
        config = URGENCY_CONFIG.get(urgency, URGENCY_CONFIG["normal"])

        # Format message with urgency indicator
        formatted_message = f"{config["emoji"]} {title}\n\n{message}"

        if self.webhook_url:
            await self._send_via_webhook(formatted_message, config["color"])
        else:
            await self._send_via_bot_api(formatted_message, config["color"])

    async def _send_via_webhook(self, formatted_message: str, color: str) -> None:
        """Send message using incoming webhook."""
        # Use attachments for colored sidebar
        payload = {
            "text": formatted_message,
            "attachments": [
                {
                    "color": color,
                    "text": "",  # Empty text, color is just for the sidebar
                }
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.webhook_url, json=payload, timeout=10.0)
            response.raise_for_status()

    async def _send_via_bot_api(self, formatted_message: str, color: str) -> None:
        """Send message using Bot API."""
        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "channel": self.channel,
            "text": formatted_message,
            "attachments": [
                {
                    "color": color,
                    "text": "",  # Empty text, color is just for the sidebar
                }
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=10.0)
            response.raise_for_status()

            # Check Slack API response
            data = response.json()
            if not data.get("ok"):
                error = data.get("error", "Unknown error")
                raise RuntimeError(f"Slack API error: {error}")
