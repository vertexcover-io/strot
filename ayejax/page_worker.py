from collections.abc import Awaitable, Generator
from contextlib import asynccontextmanager
from typing import Callable, Literal
from urllib.parse import urlparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Response,
    async_playwright,
)

from ayejax.logging import LoggerType


class PageWorker:
    def __init__(
        self,
        *,
        browser: Browser | Literal["headless", "headed"],
        filter_keywords: list[str],
        filter_mode: Literal["include", "exclude"],
    ) -> None:
        self.browser = browser
        self.filter_keywords = filter_keywords
        self.filter_mode = filter_mode

    @asynccontextmanager
    async def _new_context(self) -> Generator[BrowserContext, None, None]:
        is_browser_provided = isinstance(self.browser, Browser)
        if not is_browser_provided:
            p = await async_playwright().start()
            b = await p.chromium.launch(headless=self.browser == "headless")
        else:
            p, b = None, self.browser

        ctx = await b.new_context(bypass_csp=True)

        yield ctx
        await ctx.close(reason="done")
        if not is_browser_provided:
            await b.close(reason="done")
            await p.stop()

    async def _response_handler(self, response: Response, callback: Callable[[Response], Awaitable[None]]) -> None:
        resource_type = response.request.resource_type
        if resource_type not in ("xhr", "fetch"):
            return

        url = urlparse(response.request.url)
        if url.scheme.lower() not in ("http", "https"):
            return

        clean_url = url.netloc + url.path
        has_filter_keywords = any(w in clean_url.lower() for w in self.filter_keywords)
        if (
            self.filter_mode == "exclude"
            and has_filter_keywords
            or self.filter_mode == "include"
            and not has_filter_keywords
        ):
            return

        await callback(response)

    async def run(
        self,
        *,
        url: str,
        wait_timeout: float | None = None,
        on_response: Callable[[Response], Awaitable[None]],
        page_callback: Callable[[Page], Awaitable[None]],
        logger: LoggerType,
    ) -> None:
        async with self._new_context() as browser_ctx:
            logger.info("page", action="create", url=url)
            page = await browser_ctx.new_page()

            try:
                logger.info("page", action="wait", url=url)
                await page.goto(url, timeout=wait_timeout, wait_until="commit")
            except Exception as e:
                if f"Timeout {wait_timeout}ms exceeded" not in str(e):
                    logger.error("page", action="wait", url=url, error=str(e))
                raise

            async def handler(response: Response):
                await self._response_handler(response, on_response)

            page.on("response", handler)

            await page_callback(page)
