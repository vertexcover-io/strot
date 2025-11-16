from __future__ import annotations

import asyncio
import uuid
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader

from strot import llm
from strot.logging import LoggerType, get_logger
from strot.streaming.config import StreamingConfig
from strot.streaming.server import StreamingServer

if TYPE_CHECKING:
    from strot.browser.tab import Tab

# Setup Jinja2 templates
TEMPLATE_DIR = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)


class StreamingManager:
    """
    Singleton manager for browser streaming sessions.
    Handles human intervention requests and verification.
    """

    _instance: StreamingManager | None = None
    _lock = asyncio.Lock()

    def __new__(cls, config: StreamingConfig | None = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: StreamingConfig | None = None):
        if self._initialized:
            return

        self._config = config or StreamingConfig()
        self._server: StreamingServer | None = None
        self._server_task: asyncio.Task | None = None
        self._initialized = True

    async def request_intervention(
        self,
        tab: Tab,
        reason: str,
        logger: LoggerType | None = None,
    ) -> bool:
        """
        Request human intervention for a specific tab.

        Args:
            tab: The browser tab requiring intervention
            reason: Description of what needs to be done
            logger: Logger instance

        Returns:
            True if intervention was successful, False if timeout or failed
        """
        logger = logger or get_logger()
        session_id = str(uuid.uuid4())[:8]  # Shorter ID
        timeout = self._config.intervals.get("timeout", 600.0)
        check_interval = self._config.intervals.get("check_interval", 10.0)

        # Start server if not running
        await self._ensure_server_running(logger)

        # Register session with server
        await self._server.register_session(session_id, tab, reason)

        # Generate stream URL and notification
        stream_url = f"http://{self._config.server_host}:{self._config.server_port}/?session={session_id}"

        # Render notification from template
        notification_template = jinja_env.get_template("notification.jinja")
        notification_message = notification_template.render(reason=reason, stream_url=stream_url)
        notification_title = "🔔 Human Intervention Required"

        # Print to terminal
        print("\n" + "=" * 70)
        print("🔔 HUMAN INTERVENTION REQUIRED")
        print("=" * 70)
        print(f"Reason: {reason}")
        print(f"Stream URL: {stream_url}")
        print("=" * 70)
        print("\n")

        try:
            if callable(self._config.intervention_notifier):
                # For async callbacks
                await self._config.intervention_notifier(notification_message)
            else:
                # Use notifier instance
                await self._config.intervention_notifier.send(
                    title=notification_title,
                    message=notification_message,
                    urgency="critical",
                )
        except Exception as e:
            logger.error(
                "human-intervention",
                action="notify",
                session_id=session_id,
                status="error",
                error=str(e),
            )

        logger.info(
            "human-intervention",
            action="request",
            session_id=session_id,
            reason=reason,
            stream_url=stream_url,
        )

        # Wait for user to access the session before starting verification
        wait_elapsed = 0.0
        wait_check_interval = 2.0
        max_wait_time = timeout  # Use full timeout for access

        logger.info(
            "human-intervention",
            action="waiting-for-access",
            session_id=session_id,
            status="pending",
        )

        while wait_elapsed < max_wait_time:
            if self._server.is_session_accessed(session_id):
                logger.info(
                    "human-intervention",
                    action="waiting-for-access",
                    session_id=session_id,
                    elapsed=wait_elapsed,
                    status="accessed",
                )
                print(f"✓ User accessed session {session_id}, starting verification...\n")
                break

            await asyncio.sleep(wait_check_interval)
            wait_elapsed += wait_check_interval
        else:
            # User never accessed the URL
            logger.info(
                "human-intervention",
                action="waiting-for-access",
                session_id=session_id,
                elapsed=wait_elapsed,
                status="timeout",
            )
            print(f"\n⏱️ User did not access session {session_id} within {max_wait_time}s\n")
            await self._server.unregister_session(session_id)
            return False

        # Verification loop
        elapsed = 0.0
        remaining_timeout = timeout - wait_elapsed
        llm_client = llm.LLMClient(
            provider="anthropic",
            model=self._config.verification_model,
            api_key=None,  # Will use env var
            cost_per_1m_input=3.0,
            cost_per_1m_output=15.0,
        )

        # Load verification prompt template
        verification_template = jinja_env.get_template("verification_prompt.jinja")

        while elapsed < remaining_timeout:
            await asyncio.sleep(check_interval)
            elapsed += check_interval

            logger.info(
                "human-intervention",
                action="verify",
                session_id=session_id,
                elapsed=elapsed,
                status="checking",
            )

            # Get latest frame from stream (avoid taking new screenshot which causes blink)
            try:
                screenshot = self._server.get_latest_frame(session_id)
                if not screenshot:
                    # Fallback to taking screenshot if no frame available
                    screenshot = await tab.plugin.take_screenshot(type="png")

                # Render verification prompt from template
                prompt = verification_template.render(reason=reason)

                completion = await llm_client.get_completion(
                    llm.LLMInput(prompt=prompt, image=screenshot),
                    json=False,
                )

                response = completion.value

                if response.strip().upper().startswith("YES"):
                    logger.info(
                        "human-intervention",
                        action="verify",
                        session_id=session_id,
                        elapsed=elapsed,
                        status="completed",
                    )
                    print(f"\n✅ Human intervention completed for session {session_id}\n")

                    # Notify frontend before cleanup
                    await self._server.notify_task_completed(session_id)
                    await asyncio.sleep(0.5)  # Give time for message to be sent

                    await self._server.unregister_session(session_id)
                    return True

                logger.info(
                    "human-intervention",
                    action="verify",
                    session_id=session_id,
                    elapsed=elapsed,
                    status="pending",
                    llm_response=response,
                )

            except Exception as e:
                logger.error(
                    "human-intervention",
                    action="verify",
                    session_id=session_id,
                    elapsed=elapsed,
                    status="error",
                    error=str(e),
                )

        # Timeout
        logger.info(
            "human-intervention",
            action="timeout",
            session_id=session_id,
            elapsed=elapsed,
        )
        print(f"\n⏱️ Human intervention timed out for session {session_id}\n")
        await self._server.unregister_session(session_id)
        return False

    async def _ensure_server_running(self, logger: LoggerType):
        """Start the streaming server if not already running"""
        if self._server is not None and self._server_task is not None and not self._server_task.done():
            return

        logger.info("streaming-server", action="start", status="pending")

        self._server = StreamingServer(port=self._config.server_port, host=self._config.server_host)
        self._server_task = asyncio.create_task(self._server.start())

        # Wait a bit for server to start
        await asyncio.sleep(2)

        logger.info("streaming-server", action="start", status="success", port=self._config.server_port)

    async def cleanup(self):
        """Cleanup streaming server"""
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._server_task

        self._server = None
        self._server_task = None
