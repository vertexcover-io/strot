import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Literal, overload
from urllib.parse import parse_qsl, urlparse

from playwright.async_api import (
    Browser,
    Page,
    async_playwright,
)
from playwright.async_api import (
    Response as PageResponse,
)

from ayejax import llm, pagination
from ayejax.constants import (
    EXCLUDE_KEYWORDS,
    HEADERS_TO_IGNORE,
    PROMPT_TEMPLATE_WITH_SECTION_NAVIGATION,
    PROMPT_TEMPLATE_WITHOUT_SECTION_NAVIGATION,
)
from ayejax.helpers import keyword_match_ratio
from ayejax.logging import LoggerType
from ayejax.tag import Tag, TagLiteral
from ayejax.types import (
    AnalysisResult,
    Metadata,
    Output,
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
    max_view_scrolls: int = 30,
    page_load_timeout: float | None = None,
) -> tuple[Output | None, Metadata]:
    """
    Run analysis on the given URL using the given tag.

    Args:
        url: The target web page URL to analyze.
        tag: The kind of information to look for (e.g. reviews).
        browser: The browser to use.
        logger: The logger to use.
        max_view_scrolls: The maximum number of view scrolls to perform before exiting.
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
    max_view_scrolls: int = 30,
    page_load_timeout: float | None = None,
) -> tuple[Output | None, Metadata]:
    """
    Run analysis on the given URL using the given tag.

    Args:
        url: The target web page URL to analyze.
        tag: The kind of information to look for (e.g. reviews).
        browser: The browser to use.
        logger: The logger to use.
        max_view_scrolls: The maximum number of view scrolls to perform before exiting.
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
    browser: Browser | Literal["headless", "headed"] = "headed",
    logger: LoggerType,
    max_view_scrolls: int = 30,
    page_load_timeout: float | None = None,
) -> tuple[Output | None, Metadata]:
    """
    Run analysis on the given URL using the given query.

    Args:
        url: The target web page URL to analyze.
        query: The query to use for analysis.
        browser: The browser to use.
        logger: The logger to use.
        max_view_scrolls: The maximum number of view scrolls to perform before exiting.
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
    max_view_scrolls: int = 30,
    page_load_timeout: float | None = None,
) -> tuple[Output | None, Metadata]:
    if isinstance(query_or_tag, Tag):
        query = query_or_tag.value
    else:
        query = Tag[query_or_tag].value if query_or_tag in Tag.__members__ else query_or_tag

    async def run(browser: Browser):
        browser_ctx = await browser.new_context(bypass_csp=True)
        page = await browser_ctx.new_page()
        try:
            run_ctx = _RunContext(query=query, page=page, logger=logger)
            await run_ctx.load_url(url, page_load_timeout)
            return await run_ctx(max_view_scrolls)
        finally:
            await browser_ctx.close()

    if isinstance(browser, str):
        async with create_browser(browser) as browser:
            return await run(browser)

    return await run(browser)


analyse = analyze  # Alias for :func:`analyze`
find = analyze  # Alias for :func:`analyze` (backward compatible)


class _JSContext:
    """
    Context manager for JavaScript evaluation.
    """

    def __init__(self, page: Page, logger: LoggerType) -> None:
        self._page = page
        self._logger = logger

    async def _eval(self, expr: str, args=None) -> bool:
        if not await self._page.evaluate("() => window.scriptInjected === true"):
            _ = await self._page.add_script_tag(path=Path(__file__).parent / "inject.js")

        try:
            self._logger.info("page", action="eval", expr=expr, args=args)
            result = await self._page.evaluate(expr, args)
            await self._page.wait_for_load_state("domcontentloaded")
        except Exception as e:
            self._logger.error("page", action="eval", expr=expr, args=args, exception=e)
            raise
        else:
            return result

    async def click_element_at_point(self, x: float, y: float) -> None:
        await self._page.mouse.move(x, y)
        await self._page.mouse.click(x, y)
        await self._page.wait_for_timeout(2000)

    async def scroll_to_next_view(self, direction: Literal["up", "down"] = "down") -> bool:
        return await self._eval("([direction]) => scrollToNextView({ direction })", [direction])


class _continue: ...


class _RunContext:
    def __init__(
        self,
        page: Page,
        query: str,
        logger: LoggerType,
    ) -> None:
        self._page = page
        self._query = query
        self._logger = logger
        self._llm_client = llm.LLMClient(
            provider="anthropic",
            model="claude-3-7-sonnet-latest",
            logger=logger,
        )

        self._js_ctx = _JSContext(page, logger)

        self._ignore_js_files = True
        self._captured_responses: list[Response] = []
        self._completions: list[llm.LLMCompletion] = []
        self._section_navigated = False

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

        try:
            self._logger.info("on-response", action="capture", url=response.request.url)
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
        except Exception as exc:
            self._logger.error("on-response", action="capture", url=response.request.url, exception=exc)

    async def perform_analysis(self) -> AnalysisResult | None:
        try:
            screenshot = await self._page.screenshot(type="png")
            if not self._section_navigated:
                prompt = PROMPT_TEMPLATE_WITH_SECTION_NAVIGATION % self._query
            else:
                prompt = PROMPT_TEMPLATE_WITHOUT_SECTION_NAVIGATION % self._query

            llm_input = llm.LLMInput(prompt=prompt, image=screenshot)
            completion = self._llm_client.get_completion(llm_input, json=True)
            self._logger.info("analysis", action="llm-completion", completion=completion.value)
            self._completions.append(completion)
        except Exception as exc:
            self._logger.error("analysis", action="llm-completion", exception=exc)
            raise

        try:
            return AnalysisResult.model_validate_json(completion.value)
        except Exception as exc:
            self._logger.error("analysis", action="result-validation", exception=exc)

    def perform_matching(self, keywords: list[str]) -> Response | None:
        self._logger.info("matching", keywords=keywords)
        for response in self._captured_responses:
            score = keyword_match_ratio(keywords, response.value)
            self._logger.info("matching", url=response.request.url, score=score)
            if score < 0.4:
                continue

            return response

    async def determine_strategy(self, response: Response) -> pagination.StrategyInfo | None:  # noqa: C901
        request = response.request

        def get_key(candidates: set[str], entries: dict[str, Any]) -> str | None:
            return next((k for k in candidates if k in entries), None)

        def get_entries(request: Request) -> dict[str, Any]:
            if request.method.lower() == "post" and isinstance(request.post_data, dict):
                return request.post_data
            return request.queries

        async def build_next_cursor_info(entries: dict[str, Any]):
            cursor_key = get_key(pagination.NEXT_CURSOR_KEY_CANDIDATES, entries)

            examples = []
            max_collection_attempts = 5  # Limit attempts to collect example data
            previous_response_text = response.value
            cursor_loop_iteration = 0

            self._logger.info(
                "cursor-pattern-builder",
                action="start",
                initial_cursor_key=cursor_key,
                target_mappings=3,
                max_attempts=max_collection_attempts,
            )

            self._captured_responses.clear()
            while len(examples) < 3 and max_collection_attempts > 0:
                cursor_loop_iteration += 1
                self._logger.info(
                    "cursor-pattern-builder",
                    iteration=cursor_loop_iteration,
                    collected_mappings=len(examples),
                    remaining_attempts=max_collection_attempts,
                    current_cursor_key=cursor_key,
                )

                analysis_result = await self.perform_analysis()
                if not analysis_result:
                    max_collection_attempts -= 1
                    self._logger.warning(
                        "cursor-pattern-builder", action="analysis-failed", remaining_attempts=max_collection_attempts
                    )
                    continue

                self._logger.info(
                    "cursor-pattern-builder",
                    action="analysis-success",
                    keywords=analysis_result.keywords,
                    has_popup=analysis_result.popup_element_point is not None,
                    has_navigation=analysis_result.navigation_element_point is not None,
                )

                new_response = await self.process_analysis_result(analysis_result)
                if new_response is _continue:
                    self._logger.info("cursor-pattern-builder", action="continue-processing")
                    continue

                # Clear captured responses for next iteration
                self._captured_responses.clear()

                if not new_response:
                    max_collection_attempts -= 1
                    self._logger.warning(
                        "cursor-pattern-builder", action="no-response", remaining_attempts=max_collection_attempts
                    )
                    continue

                self._logger.info("cursor-pattern-builder", action="got-response", url=new_response.request.url)

                new_entries = get_entries(new_response.request)
                if cursor_key is None:
                    cursor_key = get_key(pagination.NEXT_CURSOR_KEY_CANDIDATES, new_entries)
                    self._logger.info("cursor-pattern-builder", action="found-cursor-key", cursor_key=cursor_key)

                if cursor_key is None:
                    self._logger.error(
                        "cursor-pattern-builder", action="no-cursor-key-found", available_keys=list(new_entries.keys())
                    )
                    return None

                # Extract cursor value from the new response's request
                cursor_value = new_entries.get(cursor_key)

                self._logger.info(
                    "cursor-pattern-builder",
                    action="cursor-extraction",
                    cursor_key=cursor_key,
                    cursor_value=cursor_value,
                )

                if cursor_value:
                    examples.append(
                        pagination.pattern_builder.Example(
                            input=previous_response_text,
                            output=str(cursor_value),
                        )
                    )
                    previous_response_text = new_response.value
                    self._logger.info(
                        "cursor-pattern-builder",
                        action="mapping-added",
                        total_mappings=len(examples),
                        cursor_value=cursor_value,
                    )

                max_collection_attempts -= 1

            if len(examples) >= 2:
                pattern_builder = pagination.pattern_builder.PatternBuilder(examples)
                pattern_builder.run()

                if patterns := pattern_builder.patterns:
                    return pagination.strategy.NextCursorInfo(
                        cursor_key=cursor_key, first_cursor=entries.get(cursor_key), patterns=patterns
                    )

            return None

        async def build_strategy_info(entries: dict[str, Any]) -> pagination.StrategyInfo | None:
            page_key = get_key(pagination.PAGE_KEY_CANDIDATES, entries)
            offset_key = get_key(pagination.OFFSET_KEY_CANDIDATES, entries)
            limit_key = get_key(pagination.LIMIT_KEY_CANDIDATES, entries)

            self._logger.info("build-strategy-info", page_key=page_key, offset_key=offset_key, limit_key=limit_key)

            if page_key and offset_key:
                return pagination.strategy.PageOffsetInfo(
                    page_key=page_key,
                    offset_key=offset_key,
                    base_offset=int(entries[offset_key]) // int(entries[page_key]),
                )
            elif limit_key and offset_key:
                return pagination.strategy.LimitOffsetInfo(
                    limit_key=limit_key,
                    offset_key=offset_key,
                )
            elif page_key:
                return pagination.strategy.PageOnlyInfo(page_key=page_key)

            return await build_next_cursor_info(entries)

        strategy_info = await build_strategy_info(get_entries(request))

        return strategy_info

    async def process_analysis_result(self, result: AnalysisResult) -> Response | _continue | None:
        if keywords := result.keywords:
            matching_response = self.perform_matching(keywords)
            if matching_response:
                return matching_response

        should_continue = False
        if popup_element_point := result.popup_element_point:
            await self._js_ctx.click_element_at_point(popup_element_point.x, popup_element_point.y)
            should_continue = True

        if navigation_element_point := result.navigation_element_point:
            await self._js_ctx.click_element_at_point(navigation_element_point.x, navigation_element_point.y)
            self._section_navigated = True
            should_continue = True

        return _continue if should_continue else None

    async def __call__(self, max_view_scrolls: int) -> tuple[Output | None, Metadata]:
        analysis_retry_count = 5
        main_loop_iteration = 0

        self._logger.info("main-loop", action="start", max_view_scrolls=max_view_scrolls)

        while max_view_scrolls:
            main_loop_iteration += 1
            self._logger.info(
                "main-loop",
                iteration=main_loop_iteration,
                remaining_scrolls=max_view_scrolls,
                retry_count=analysis_retry_count,
                captured_responses=len(self._captured_responses),
            )

            analysis_result = await self.perform_analysis()
            if not analysis_result:
                analysis_retry_count -= 1
                self._logger.warning("main-loop", action="analysis-failed", retry_count=analysis_retry_count)
                if analysis_retry_count <= 0:
                    self._logger.error("main-loop", action="max-retries-exceeded")
                    break

                continue

            analysis_retry_count = 5
            self._logger.info(
                "main-loop",
                action="analysis-success",
                keywords=analysis_result.keywords,
                has_popup=analysis_result.popup_element_point is not None,
                has_navigation=analysis_result.navigation_element_point is not None,
            )

            try:
                response = await self.process_analysis_result(analysis_result)
            except Exception as e:
                self._logger.error("main-loop", action="process-analysis-error", error=str(e))
                continue

            if isinstance(response, Response):
                self._logger.info("main-loop", action="found-matching-response", url=response.request.url)

                # Filter out headers to ignore
                for key in list(response.request.headers):
                    if key.lstrip(":").lower() in HEADERS_TO_IGNORE:
                        response.request.headers.pop(key)

                output = Output(
                    request=response.request,
                    pagination_strategy=await self.determine_strategy(response),
                )
                metadata = Metadata(
                    extracted_keywords=analysis_result.keywords,
                    completions=self._completions,
                )
                return output, metadata
            elif response is _continue:
                self._logger.info("main-loop", action="continue-processing")
                continue

            self._logger.info("main-loop", action="scrolling-to-next-view")
            if not (await self._js_ctx.scroll_to_next_view()):
                self._logger.info("main-loop", action="scroll-failed-or-end")
                break

            max_view_scrolls -= 1
            time.sleep(2.5)

        self._logger.info(
            "main-loop",
            action="completed-without-match",
            total_iterations=main_loop_iteration,
            total_completions=len(self._completions),
        )

        return None, Metadata(
            extracted_keywords=[],
            completions=self._completions,
        )
