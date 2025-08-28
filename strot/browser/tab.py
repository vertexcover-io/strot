import contextlib
from urllib.parse import parse_qsl, urlparse

from patchright.async_api import BrowserContext, Page
from patchright.async_api import Response as InterceptedResponse

from strot.analyzer.schema import Response
from strot.analyzer.schema.request import Request
from strot.browser.plugin import Plugin

EXCLUDE_KEYWORDS = {"analytics", "telemetry", "events", "collector", "track", "collect"}


class Tab:
    def __init__(
        self,
        browser_context: BrowserContext,
        viewport_size: dict[str, int] | None = None,
        load_timeout: float | None = None,
    ) -> None:
        self._browser_context = browser_context
        self._viewport_size = viewport_size or {"width": 1280, "height": 800}
        self._load_timeout = load_timeout

        self._page: Page | None = None
        self._page_headers: dict[str, str] | None = None
        self._responses: list[Response] = []
        self._plugin: Plugin | None = None

    def is_empty(self) -> bool:
        return self._page is None

    async def goto(self, url: str) -> None:
        await self.reset()

        self._page = await self._browser_context.new_page()
        self._page.on("response", self._handle_ajax_response)

        await self._page.set_viewport_size(self._viewport_size)

        with contextlib.suppress(Exception):
            response = await self._page.goto(url, timeout=self._load_timeout, wait_until="domcontentloaded")
            if response:
                self._page_headers = await response.request.all_headers()

        await self._page.wait_for_timeout(5000)
        self._page.on("load", self._handle_server_side_rendering)

        self._plugin = Plugin(self._page)

    @property
    def responses(self) -> list[Response]:
        return self._responses

    @property
    def plugin(self) -> Plugin | None:
        return self._plugin

    async def reset(self) -> None:
        if self._page:
            with contextlib.suppress(Exception):
                await self._page.close()
            self._page = None
            self._page_headers = None
            self._plugin = None
            self._responses.clear()

    async def _handle_ajax_response(self, response: InterceptedResponse) -> None:
        rsc_type = response.request.resource_type
        if rsc_type not in ("xhr", "fetch"):
            return

        url = urlparse(response.request.url)
        if url.scheme.lower() not in ("http", "https"):
            return

        clean_url = (url.netloc + url.path).lower()
        if any(w in clean_url for w in EXCLUDE_KEYWORDS):
            return

        with contextlib.suppress(Exception):
            self._responses.append(
                Response(
                    value=await response.text(),
                    request=Request(
                        method=response.request.method,
                        url=f"{url.scheme}://{url.netloc}{url.path}",
                        queries=dict(parse_qsl(url.query)),
                        type="ajax",
                        headers=await response.request.all_headers(),
                        post_data=response.request.post_data_json,
                    ),
                )
            )

    async def _handle_server_side_rendering(self, page: Page) -> None:
        parsed_url = urlparse(page.url)
        if parsed_url.scheme.lower() not in ("http", "https"):
            return

        self._responses.append(
            Response(
                value=await page.content(),
                request=Request(
                    method="GET",
                    url=f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}",
                    type="ssr",
                    queries=dict(parse_qsl(parsed_url.query)),
                    headers=self._page_headers or {},
                    post_data=None,
                ),
            )
        )
