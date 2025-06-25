import re
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from tempfile import gettempdir
from typing import Callable, Literal
from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, Page, Response, sync_playwright

from ayejax.har import Data
from ayejax.logging import LoggerType


class HarBuilder:
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

        pattern = rf"https?:\/\/[^?]*\b(?:{'|'.join(map(re.escape, filter_keywords))})\b"
        if filter_mode == "exclude":
            pattern = f"^(?!{pattern}).+"
        self.filter_pattern = re.compile(pattern, re.IGNORECASE)

    @contextmanager
    def _new_context(self, har_file: Path) -> Generator[BrowserContext, None, None]:
        is_browser_provided = isinstance(self.browser, Browser)
        if not is_browser_provided:
            p = sync_playwright().start()
            b = p.chromium.launch(headless=self.browser == "headless")
        else:
            p, b = None, self.browser

        ctx = b.new_context(
            bypass_csp=True,
            record_har_path=har_file,
            record_har_mode="full",
            record_har_url_filter=self.filter_pattern,
        )

        yield ctx
        ctx.close(reason="done")
        if not is_browser_provided:
            b.close(reason="done")
            p.stop()

    def _response_handler(self, response: Response, callback: Callable[[Response], None]):
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

        callback(response)

    def run(
        self,
        *,
        url: str,
        wait_timeout: float | None = None,
        on_response: Callable[[Response], None],
        page_callback: Callable[[Page], None],
        logger: LoggerType,
    ) -> Data:
        datetime_fmt = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        har_file = Path(gettempdir()) / f"{datetime_fmt}--ayejax.har"

        with self._new_context(har_file=har_file) as browser_ctx:
            logger.info("page", action="create", url=url)
            page = browser_ctx.new_page()

            try:
                logger.info("page", action="wait", url=url)
                page.goto(url, timeout=wait_timeout, wait_until="commit")
            except Exception as e:
                if f"Timeout {wait_timeout}ms exceeded" not in str(e):
                    logger.error("page", action="wait", url=url, error=str(e))
                raise

            page.on("response", lambda r: self._response_handler(r, on_response))

            page_callback(page)

        har_data = Data.model_validate_json(har_file.read_bytes())
        har_file.unlink()

        return har_data
