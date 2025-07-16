import contextlib
import io
import re
from contextlib import asynccontextmanager, suppress
from json import dumps as json_dumps
from pathlib import Path
from typing import Any, Literal, overload
from urllib.parse import parse_qsl, urlparse

from playwright.async_api import (
    Browser,
    Page,
    async_playwright,
)
from playwright.async_api import Response as PageResponse
from pydantic import BaseModel

from ayejax import llm, pagination
from ayejax.adapter import SchemaAdapter, drop_titles
from ayejax.constants import (
    ANALYSIS_PROMPT_TEMPLATE,
    EXCLUDE_KEYWORDS,
    EXTRACTION_CODE_GENERATION_PROMPT_TEMPLATE,
    HEADERS_TO_IGNORE,
)
from ayejax.helpers import draw_point_on_image, encode_image, keyword_match_ratio
from ayejax.logging import LoggerType
from ayejax.tag import Tag, TagLiteral
from ayejax.types import (
    AnalysisResult,
    Output,
    Point,
    Request,
    Response,
)

__all__ = ("analyse", "analyze", "create_browser", "find")


@asynccontextmanager
async def create_browser(mode: Literal["headed", "headless"]):
    """
    Create a browser instance that will be automatically closed.

    Args:
        mode: browser mode to use. Can be "headed" or "headless".

    Yields:
        A browser instance.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=mode == "headless")
        try:
            yield browser
        finally:
            with suppress(Exception):
                await browser.close()


@overload
async def analyze(
    url: str,
    tag: Tag,
    /,
    *,
    browser: Browser | Literal["headless", "headed"] = "headed",
    logger: LoggerType,
    max_attempts: int = 30,
    page_load_timeout: float | None = None,
) -> Output | None:
    """
    Run analysis on the given URL using the given tag.

    Args:
        url: The target web page URL to analyze.
        tag: The kind of information to look for (e.g. reviews).
        browser: The browser to use.
        logger: The logger to use.
        max_attempts: The maximum number of attempts to perform before exiting.
        page_load_timeout: The timeout for waiting for the page to load.

    Returns:
        Tuple of output and metadata.
    """


@overload
async def analyze(
    url: str,
    tag: TagLiteral,
    /,
    *,
    browser: Browser | Literal["headless", "headed"] = "headed",
    logger: LoggerType,
    max_attempts: int = 30,
    page_load_timeout: float | None = None,
) -> Output | None:
    """
    Run analysis on the given URL using the given tag.

    Args:
        url: The target web page URL to analyze.
        tag: The kind of information to look for (e.g. reviews).
        browser: The browser to use.
        logger: The logger to use.
        max_attempts: The maximum number of attempts to perform before exiting.
        page_load_timeout: The timeout for waiting for the page to load.

    Returns:
        Tuple of output and metadata.
    """


@overload
async def analyze(
    url: str,
    query: str,
    /,
    *,
    output_schema: type[BaseModel],
    browser: Browser | Literal["headless", "headed"] = "headed",
    logger: LoggerType,
    max_attempts: int = 30,
    page_load_timeout: float | None = None,
) -> Output | None:
    """
    Run analysis on the given URL using the given query.

    Args:
        url: The target web page URL to analyze.
        query: The query to use for analysis.
        output_schema: The output schema to extract data from the response.
        browser: The browser to use.
        logger: The logger to use.
        max_attempts: The maximum number of attempts to perform before exiting.
        page_load_timeout: The timeout for waiting for the page to load.

    Returns:
        Tuple of output and metadata.
    """


async def analyze(
    url: str,
    query_or_tag: str | Tag | TagLiteral,
    /,
    *,
    browser: Browser | Literal["headless", "headed"] = "headed",
    logger: LoggerType,
    max_attempts: int = 30,
    page_load_timeout: float | None = None,
    **kwargs: Any,
) -> Output | None:
    output_schema = None
    if isinstance(query_or_tag, Tag):
        query = query_or_tag.value.query
        output_schema = query_or_tag.value.output_schema
    elif query_or_tag in Tag.__members__:
        query = Tag[query_or_tag].value.query
        output_schema = Tag[query_or_tag].value.output_schema
    else:
        query = query_or_tag
        output_schema = kwargs.get("output_schema")
        if not output_schema:
            raise ValueError("output_schema is required when using a query")

    async def run(browser: Browser):
        browser_ctx = await browser.new_context(bypass_csp=True)
        page = await browser_ctx.new_page()
        try:
            logger.info("analyzer", action="init", url=url, query=query)
            run_ctx = _AnalyzerContext(page=page, logger=logger)
            await run_ctx.load_url(url, page_load_timeout)
            output = await run_ctx(query, output_schema, max_attempts)
            if not output:
                logger.info("analyzer", action="end", status="failed", message="No relevant request found")
            else:
                logger.info("analyzer", action="end", status="success", relevant_api_call=output.request.url)
            return output
        finally:
            await browser_ctx.close()

    if isinstance(browser, str):
        async with create_browser(browser) as browser:
            return await run(browser)

    return await run(browser)


class _AnalyzerContext:
    def __init__(
        self,
        page: Page,
        logger: LoggerType,
    ) -> None:
        self._page = page
        self._logger = logger
        self._llm_client = llm.LLMClient(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
        )

        self._js_ctx = _JSContext(page, logger)

        self._ignore_js_files = True
        self._captured_responses: list[Response] = []

        self._page.on("response", self.response_handler)

    async def load_url(self, url: str, load_timeout: float | None) -> None:
        await self._page.goto(url, timeout=load_timeout, wait_until="commit")
        await self._page.wait_for_timeout(5000)
        self._ignore_js_files = False

    async def response_handler(self, response: PageResponse) -> None:
        rsc_type = response.request.resource_type
        if rsc_type not in ("xhr", "fetch"):
            return

        url = urlparse(response.request.url)
        if self._ignore_js_files and url.path.endswith(".js"):
            return

        if url.scheme.lower() not in ("http", "https"):
            return

        clean_url = (url.netloc + url.path).lower()
        if any(w in clean_url for w in EXCLUDE_KEYWORDS):
            return

        with contextlib.suppress(Exception):
            self._captured_responses.append(
                Response(
                    value=await response.text(),
                    request=Request(
                        method=response.request.method,
                        url=f"{url.scheme}://{url.netloc}{url.path}",
                        queries=dict(parse_qsl(url.query)),
                        headers=await response.request.all_headers(),
                        post_data=response.request.post_data_json,
                    ),
                )
            )

    async def get_extraction_code_and_items_count(
        self, output_schema: type[BaseModel], response_text: str
    ) -> tuple[str | None, int | None]:
        adapter = SchemaAdapter(
            list[output_schema]
        )  # Every schema will be treated as If we're extracting a list of items
        formatted_output_schema = json_dumps(drop_titles(adapter.schema), indent=2)

        for _ in range(3):
            try:
                self._logger.info(
                    "code-generation",
                    action="llm-completion",
                    status="pending",
                )
                completion = await self._llm_client.get_completion(
                    llm.LLMInput(
                        prompt=EXTRACTION_CODE_GENERATION_PROMPT_TEMPLATE % (formatted_output_schema, response_text)
                    )
                )
                self._logger.info(
                    "code-generation",
                    action="llm-completion",
                    status="success",
                    input_tokens=completion.input_tokens,
                    output_tokens=completion.output_tokens,
                )
            except Exception as e:
                self._logger.info(
                    "code-generation",
                    action="llm-completion",
                    status="failed",
                    exception=e,
                )
                continue

            try:
                # Pattern to match code fences with optional language specification
                # Matches ```python, ```py, or just ``` followed by code and ending ```
                pattern = r"```(?:python|py)?\s*\n(.*?)\n```"

                matches = re.findall(pattern, completion.value, re.DOTALL)
                if not matches:
                    return None

                code = matches[0].strip()
                namespace = {}
                exec(code, namespace)  # noqa: S102
                items = adapter.validate_python(namespace["extract_data"](response_text))
                self._logger.info("code-generation", action="validation", status="success")
            except Exception as e:
                self._logger.info("code-generation", action="validation", status="failed", exception=e)
                continue
            else:
                return code, len(items)

    async def determine_pagination_strategy(self, response: Response, query: str):  # noqa: C901
        def get_key(candidates: set[str], entries: dict[str, Any]) -> str | None:
            return next((k for k in candidates if k in entries), None)

        def get_entries(request: Request) -> dict[str, Any]:
            if request.method.lower() == "post" and isinstance(request.post_data, dict):
                return request.post_data
            return request.queries

        async def build_strategy_info(entries: dict[str, Any]) -> pagination.StrategyInfo | None:
            page_key = get_key(pagination.PAGE_KEY_CANDIDATES, entries)
            offset_key = get_key(pagination.OFFSET_KEY_CANDIDATES, entries)
            limit_key = get_key(pagination.LIMIT_KEY_CANDIDATES, entries)

            if page_key and offset_key:
                base_offset = int(entries[offset_key]) // int(entries[page_key])
                self._logger.info(
                    "determine-strategy",
                    action="build-strategy-info",
                    strategy="page-offset",
                    page_key=page_key,
                    offset_key=offset_key,
                    base_offset=base_offset,
                )
                return pagination.strategy.PageOffsetInfo(
                    page_key=page_key,
                    offset_key=offset_key,
                    base_offset=base_offset,
                )
            elif limit_key and offset_key:
                self._logger.info(
                    "determine-strategy",
                    action="build-strategy-info",
                    strategy="limit-offset",
                    limit_key=limit_key,
                    offset_key=offset_key,
                )
                return pagination.strategy.LimitOffsetInfo(
                    limit_key=limit_key,
                    offset_key=offset_key,
                )
            elif page_key:
                self._logger.info(
                    "determine-strategy",
                    action="build-strategy-info",
                    strategy="page-only",
                    page_key=page_key,
                )
                return pagination.strategy.PageOnlyInfo(page_key=page_key)

            self._captured_responses.clear()  # clear so it does not match previous responses
            for attempt in range(getattr(self, "attempts_left", 20)):
                try:
                    self._logger.info("determine-strategy", action="run-step", step_count=attempt, status="pending")
                    new_response = await self.run_step(query)
                except Exception as e:
                    self._logger.info(
                        "determine-strategy", action="run-step", step_count=attempt, status="failed", exception=e
                    )
                    continue

                if not new_response:
                    continue

                self._logger.info(
                    "determine-strategy",
                    action="run-step",
                    step_count=attempt,
                    status="success",
                    method=new_response.request.method,
                    url=new_response.request.url,
                    queries=new_response.request.queries,
                    data=new_response.request.post_data,
                )
                new_entries = get_entries(new_response.request)
                cursor_key = get_key(pagination.NEXT_CURSOR_KEY_CANDIDATES, new_entries)
                if cursor_key is None:  # The request doesn't have any pagination available
                    return None

                first_cursor = entries.get(cursor_key)
                pagination_patterns = pagination.get_patterns(response.value, new_entries[cursor_key])
                self._logger.info(
                    "determine-strategy",
                    action="build-strategy-info",
                    strategy="next-cursor",
                    cursor_key=cursor_key,
                    first_cursor=first_cursor,
                    pagination_patterns=len(pagination_patterns),
                )
                return pagination.strategy.NextCursorInfo(
                    cursor_key=cursor_key,
                    first_cursor=entries.get(cursor_key),
                    patterns=pagination_patterns,
                )

            return None

        return await build_strategy_info(get_entries(response.request))

    async def run_step(self, query: str) -> Response | None:  # noqa: C901
        screenshot = await self._page.screenshot(type="png")
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            output_schema=drop_titles(AnalysisResult.model_json_schema()), query=query
        )

        try:
            self._logger.info("run-step", action="llm-completion", status="pending", query=query)
            completion = await self._llm_client.get_completion(llm.LLMInput(prompt=prompt, image=screenshot), json=True)
            self._logger.info(
                "run-step",
                action="llm-completion",
                status="success",
                result=completion.value,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
                cost=completion.calculate_cost(3.0, 15.0),
            )
        except Exception as e:
            self._logger.info("run-step", action="llm-completion", status="failed", exception=e)
            return None

        result = AnalysisResult.model_validate_json(completion.value)
        if sections := result.text_sections:
            self._logger.info("run-step", step="text-processing", context=encode_image(screenshot))
            for response in self._captured_responses:
                self._logger.info("run-step", action="matching", against=response.value[:100])
                score = keyword_match_ratio(sections, response.value)
                self._logger.info("run-step", action="matching", url=response.request.url, score=score)
                if score < 0.4:
                    continue

                return response

            if await self._js_ctx.skip_similar_content(sections):
                return

        def get_context(point: Point) -> bytes:
            image = draw_point_on_image(screenshot, point)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return encode_image(buffer.getvalue())

        if result.close_overlay_popup_coords:
            self._logger.info(
                "run-step", step="close-overlay-popup", context=get_context(result.close_overlay_popup_coords)
            )
            if await self._js_ctx.click_at_point(result.close_overlay_popup_coords):
                return

        if result.load_more_content_coords:
            self._logger.info(
                "run-step", step="load-more-content", context=get_context(result.load_more_content_coords)
            )
            if await self._js_ctx.click_at_point(result.load_more_content_coords):
                return

        if result.skip_to_content_coords:
            self._logger.info("run-step", step="skip-to-content", context=get_context(result.skip_to_content_coords))
            if await self._js_ctx.click_at_point(result.skip_to_content_coords):
                return

        self._logger.info(
            "run-step",
            step="scroll-to-next-view",
            context=None,  # If we're here, then context has already been logged
        )
        await self._js_ctx.scroll_to_next_view()

    async def __call__(
        self,
        query: str,
        output_schema: type[BaseModel],
        max_attempts: int = 30,
    ) -> Output | None:
        for attempt in range(1, max_attempts + 1):
            try:
                self._logger.info("analysis", action="run-step", step_count=attempt, status="pending")
                response = await self.run_step(query)
            except Exception as e:
                self._logger.info("analysis", action="run-step", step_count=attempt, status="failed", exception=e)
                response = None

            if not response:
                continue

            self._logger.info(
                "analysis",
                action="run-step",
                step_count=attempt,
                status="success",
                method=response.request.method,
                url=response.request.url,
                queries=response.request.queries,
                data=response.request.post_data,
            )

            self.attempts_left = max_attempts - attempt
            pagination_strategy = await self.determine_pagination_strategy(response, query)
            code, items_count = await self.get_extraction_code_and_items_count(output_schema, response.value)

            # Filter out headers to ignore
            for key in list(response.request.headers):
                if key.lstrip(":").lower() in HEADERS_TO_IGNORE:
                    response.request.headers.pop(key)

            output = Output(
                request=response.request,
                pagination_strategy=pagination_strategy,
                schema_extractor_code=code,
                items_count_on_first_extraction=items_count or 1,
            )

            return output


class _JSContext:
    """
    Context manager for JavaScript evaluation.
    """

    def __init__(self, page: Page, logger: LoggerType) -> None:
        self._page = page
        self._logger = logger

    async def evaluate(self, expr: str, args=None) -> bool:
        if not await self._page.evaluate("() => window.scriptInjected === true"):
            _ = await self._page.add_script_tag(path=Path(__file__).parent / "inject.js")

        try:
            self._logger.info("page", action="eval", expr=expr, args=args)
            await self._page.wait_for_load_state("domcontentloaded")
            result = await self._page.evaluate(expr, args)
            await self._page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            self._logger.error("page", action="eval", expr=expr, args=args, exception=e)
            raise
        else:
            return result

    async def get_selectors_in_view(self) -> set[str]:
        selectors = await self.evaluate(
            """
            () => {
                const elements = getElementsInView(getElementsInDOM());
                return elements.map(elem => generateCSSSelector(elem));
            }
            """
        )
        return set(selectors)

    async def click_at_point(self, point: Point) -> bool:
        before_selectors = await self.get_selectors_in_view()
        await self._page.mouse.move(point.x, point.y)
        await self._page.mouse.click(point.x, point.y)
        await self._page.wait_for_timeout(2000)
        after_selectors = await self.get_selectors_in_view()

        added = after_selectors - before_selectors
        removed = before_selectors - after_selectors
        return len(added) > 0 or len(removed) > 0

    async def scroll_to_next_view(self, direction: Literal["up", "down"] = "down") -> bool:
        return await self.evaluate("([direction]) => scrollToNextView({ direction })", [direction])

    async def skip_similar_content(self, text_sections: list[str]) -> bool:
        texts_in_view_to_last_sibling_selectors: dict[str, str] = await self.evaluate(
            """
            () => {
                const textsInViewToLastSiblingSelector = {};
                const mapping = mapLastVisibleSiblings(1.25);
                mapping.forEach((lastSiblingElement, elementInView) => {
                    textsInViewToLastSiblingSelector[elementInView.textContent.trim()] = generateCSSSelector(lastSiblingElement);
                });
                return textsInViewToLastSiblingSelector;
            }
            """
        )

        # Sort texts by length (longer first) to prioritize longer matching texts
        for text_in_view, selector in sorted(
            texts_in_view_to_last_sibling_selectors.items(),
            key=lambda x: len(x[0]),
            reverse=True,
        ):
            best_match_ratio = 0.0
            self._logger.info("skip-similar-content", action="matching", against=text_in_view[:100])
            for section in sorted(text_sections, key=len, reverse=True):
                match_ratio = keyword_match_ratio([section], text_in_view)
                self._logger.info("skip-similar-content", action="matching", sections=[section], score=match_ratio)

                if match_ratio > best_match_ratio:
                    best_match_ratio = match_ratio

            if best_match_ratio:
                self._logger.info("skip-similar-content", target_selector=selector, status="success")
                await self._page.locator(selector).scroll_into_view_if_needed()
                return True

        self._logger.info("skip-similar-content", target_selector=None, status="failed")
        return False
