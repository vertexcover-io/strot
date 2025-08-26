import asyncio
import inspect
from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress
from typing import Any, Literal, overload

from patchright.async_api import Browser, async_playwright

__all__ = ("launch_browser",)


@overload
def launch_browser(mode: Literal["headed", "headless"], /) -> "AbstractAsyncContextManager[ResilientBrowser]":
    """
    Launch a browser instance.

    Args:
        mode: browser mode to use. Can be "headed" or "headless".

    Yields:
        A browser instance.
    """


@overload
def launch_browser(ws_url: str, /) -> "AbstractAsyncContextManager[ResilientBrowser]":
    """
    Launch a browser instance.

    Args:
        ws_url: The WebSocket URL to the browser instance.

    Yields:
        A browser instance.
    """


@asynccontextmanager
async def launch_browser(mode_or_ws_url: str, /):
    """
    Launch a browser instance.

    Args:
        mode_or_ws_url: The browser mode or WebSocket URL.

    Yields:
        A browser instance.
    """
    browser = ResilientBrowser(mode_or_ws_url)
    try:
        await browser.connect()
        yield browser
    finally:
        with suppress(Exception):
            await browser.close()


class ResilientBrowser:
    """Browser wrapper that automatically reinitializes the browser instance."""

    def __init__(self, mode_or_ws_url: str, max_retries: int = 3):
        self.mode_or_ws_url = mode_or_ws_url
        self.max_retries = max_retries
        self._browser: Browser | None = None
        self._playwright = None
        self._lock = asyncio.Lock()
        self._initializing = False

    async def _get_instance(self) -> Browser:
        """Get browser instance with connection check."""
        async with self._lock:
            # Check if current browser is still connected
            if await self.is_connected():
                return self._browser

            # Prevent multiple initialization attempts
            if self._initializing:
                # Wait for ongoing initialization
                while self._initializing:
                    await asyncio.sleep(0.1)
                if await self.is_connected():
                    return self._browser

            self._initializing = True
            try:
                # Cleanup old instances
                await self._close_browser()

                # Create new playwright instance if needed
                if not self._playwright:
                    self._playwright = await async_playwright().__aenter__()

                # Launch browser based on mode
                if self.mode_or_ws_url == "headed":
                    browser = await self._playwright.chromium.launch(headless=False)
                elif self.mode_or_ws_url == "headless":
                    browser = await self._playwright.chromium.launch(headless=True)
                else:
                    # Try CDP connection first, fallback to WebSocket
                    try:
                        browser = await self._playwright.chromium.connect_over_cdp(self.mode_or_ws_url)
                    except Exception:
                        browser = await self._playwright.chromium.connect(self.mode_or_ws_url)

                self._browser = browser

                return browser
            finally:
                self._initializing = False

    async def is_connected(self) -> bool:
        """Check if browser is connected."""
        try:
            if not self._browser:
                return False
            return await self._browser.is_connected()
        except Exception:
            return False

    async def connect(self) -> None:
        """Connect to the browser."""
        await self._get_instance()

    def _is_method(self, name: str) -> bool:
        """Check if an attribute is a method using inspect."""
        try:
            # Get the attribute from the class
            attr = getattr(Browser, name, None)
            if attr is None:
                return True  # Assume method if not found

            # Check if it's a method or function
            return (
                inspect.ismethod(attr)
                or inspect.isfunction(attr)
                or inspect.iscoroutinefunction(attr)
                or callable(attr)
            )
        except Exception:
            return True  # Assume method on error

    def __getattr__(self, name: str) -> Any:
        """Proxy attribute access with resilient logic."""

        # Check if it's a method or property
        if self._is_method(name):
            # Return async wrapper for methods
            async def method_wrapper(*args, **kwargs):
                for attempt in range(self.max_retries + 1):
                    try:
                        browser = await self._get_instance()
                        attr = getattr(browser, name)

                        if inspect.iscoroutinefunction(attr):
                            return await attr(*args, **kwargs)
                        else:
                            return attr(*args, **kwargs)

                    except Exception:
                        if attempt < self.max_retries:
                            # Force reconnection
                            async with self._lock:
                                await self._close_browser()
                            await asyncio.sleep(0.5 * (attempt + 1))
                        else:
                            raise

            return method_wrapper

        # For properties, try to return directly if connected
        if self._browser is None:
            raise AttributeError("Browser not connected. Call '.connect()' first.")

        return getattr(self._browser, name)

    async def new_page(self, **kwargs):
        """Create a new page with retry logic."""
        browser = await self._get_instance()
        return await browser.new_page(**kwargs)

    async def new_context(self, **kwargs):
        """Create a new context with retry logic."""
        browser = await self._get_instance()
        return await browser.new_context(**kwargs)

    async def _close_browser(self):
        """Close the browser."""
        if self._browser:
            with suppress(Exception):
                await self._browser.close()
            self._browser = None

    async def close(self):
        """Close the browser and cleanup."""
        async with self._lock:
            await self._close_browser()

            if self._playwright:
                with suppress(Exception):
                    await self._playwright.__aexit__(None, None, None)
                self._playwright = None
