from __future__ import annotations

import re
from typing import Literal
from webbrowser import open as open_url_in_browser

import desktop_notifier
from pyperclip import copy as copy_to_clipboard

from strot.streaming.notifiers.base import Notifier, UrgencyLevel

URGENCY_MAP = {
    "critical": desktop_notifier.Urgency.Critical,
    "normal": desktop_notifier.Urgency.Normal,
    "low": desktop_notifier.Urgency.Low,
}


class DesktopNotifier(Notifier):
    """Send desktop notifications using the desktop-notifier library."""

    def __init__(self, app_name: str = "Strot", click_action: Literal["open", "copy", "both"] = "both"):
        self._instance = desktop_notifier.DesktopNotifier(app_name)
        self._click_action = click_action

    async def send(
        self,
        title: str,
        message: str,
        urgency: UrgencyLevel = "normal",
    ) -> None:
        """Send desktop notification.

        Args:
            title: Notification title
            message: Notification message in markdown format
            urgency: Urgency level (critical, normal, low)
        """
        # Extract URL from message for on_clicked callback
        url_match = re.search(r"https?://[^\s]+", message)
        stream_url = url_match.group(0) if url_match else None

        def on_clicked():
            """Open stream URL in browser when notification is clicked."""
            if not stream_url:
                return

            if self._click_action in ("copy", "both"):
                copy_to_clipboard(stream_url)
            if self._click_action in ("open", "both"):
                open_url_in_browser(stream_url)

        await self._instance.send(
            title=title,
            message=message,
            urgency=URGENCY_MAP.get(urgency, desktop_notifier.Urgency.Normal),
            on_clicked=on_clicked,
        )
