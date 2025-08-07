from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress
from typing import Literal, overload

from patchright.async_api import Browser, async_playwright

__all__ = ("launch_browser",)


@overload
def launch_browser(mode: Literal["headed", "headless"], /) -> AbstractAsyncContextManager[Browser]:
    """
    Launch a browser instance.

    Args:
        mode: browser mode to use. Can be "headed" or "headless".

    Yields:
        A browser instance.
    """


@overload
def launch_browser(ws_url: str, /) -> AbstractAsyncContextManager[Browser]:
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
    async with async_playwright() as p:
        if mode_or_ws_url == "headed":
            browser = await p.chromium.launch(headless=False)
        elif mode_or_ws_url == "headless":
            browser = await p.chromium.launch(headless=True)
        else:
            try:
                browser = await p.chromium.connect_over_cdp(mode_or_ws_url)
            except Exception:
                browser = await p.chromium.connect(mode_or_ws_url)
        try:
            yield browser
        finally:
            with suppress(Exception):
                await browser.close()
