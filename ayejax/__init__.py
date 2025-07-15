import os
import re
import time
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
from playwright.async_api import (
    Response as PageResponse,
)
from pydantic import BaseModel

from ayejax import llm, pagination
from ayejax.adapter import SchemaAdapter, drop_titles
from ayejax.debug_session import DebugSession
from ayejax.popup import PopupDismisser
from ayejax.constants import (
    ANALYSIS_PROMPT_TEMPLATE_WITH_SECTION_NAVIGATION,
    ANALYSIS_PROMPT_TEMPLATE_WITHOUT_SECTION_NAVIGATION,
    EXCLUDE_KEYWORDS,
    EXTRACTION_CODE_GENERATION_PROMPT_TEMPLATE,
    HEADERS_TO_IGNORE,
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
    output_schema: type[BaseModel],
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
        output_schema: The output schema to extract data from the response.
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
    **kwargs: Any,
) -> tuple[Output | None, Metadata]:
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
            run_ctx = _RunContext(page=page, logger=logger, url=url, tag=tag)
            await run_ctx.load_url(url, page_load_timeout)
            result = await run_ctx(query, output_schema, max_view_scrolls)
            
            # Finalize debug session with successful result
            if run_ctx._debug_session:
                run_ctx._debug_session.finalize(result=result)
                
            return result
        except Exception as exc:
            # Finalize debug session with error
            if hasattr(run_ctx, '_debug_session') and run_ctx._debug_session:
                run_ctx._debug_session.finalize(error=str(exc))
            raise
        finally:
            await browser_ctx.close()

    if isinstance(browser, str):
        async with create_browser(browser) as browser:
            return await run(browser)

    return await run(browser)


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
            await self._page.wait_for_load_state("domcontentloaded")
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

    async def scroll_last_similar_element_into_view(self, keywords: list[str]) -> bool:
        texts_in_view_to_last_sibling_selectors: dict[str, str] = await self._eval(
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
        for text, selector in sorted(
            texts_in_view_to_last_sibling_selectors.items(),
            key=lambda x: len(x[0]),
            reverse=True,
        ):
            self._logger.info("scroll-to-last-visible-sibling", action="matching", text=text)

            best_match_ratio = 0.0
            for keyword in sorted(keywords, key=len, reverse=True):
                match_ratio = keyword_match_ratio([keyword], text)
                self._logger.info(
                    "scroll-to-last-visible-sibling", action="matching", match_ratio=match_ratio, keyword=keyword
                )

                if match_ratio > best_match_ratio:
                    best_match_ratio = match_ratio

            if best_match_ratio:
                self._logger.info("scroll-to-last-visible-sibling", text=text, selector=selector)
                await self._page.locator(selector).scroll_into_view_if_needed()
                return True

        return False


class _continue: ...


class _RunContext:
    def __init__(
        self,
        page: Page,
        logger: LoggerType,
        url: str = None,
        tag: str = None,
    ) -> None:
        self._page = page
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

        # Initialize debug session if enabled
        debug_enabled = os.getenv('AYEJAX_DEBUG_LOCAL', 'true').lower() == 'true'
        self._debug_session = DebugSession(url, tag) if debug_enabled and url and tag else None
        if self._debug_session:
            self._debug_session.setup_directories()
            self._logger.info("debug-session", session_id=self._debug_session.session_id, 
                            session_dir=str(self._debug_session.session_dir))

        # Initialize popup dismisser
        self._popup_dismisser = PopupDismisser(logger)

        self._page.on("response", self.response_handler)

    async def load_url(self, url: str, load_timeout: float | None) -> None:
        # Compile a regex to match asset file extensions
        asset_regex = re.compile(r"\.(css|woff|woff2|ttf|eot|svg|png|jpg|jpeg|gif)$", re.IGNORECASE)

        # Set up routing to abort requests for non-essential assets
        await self._page.route(asset_regex, lambda route: route.abort())

        # Navigate to the page. This will now be much faster.
        await self._page.goto(url, timeout=load_timeout, wait_until="domcontentloaded")
        
        # It's good practice to unroute after the page has loaded, so that any
        # subsequent, necessary asset requests (e.g., from user interaction) are not blocked.
        await self._page.unroute(asset_regex)

        await self._page.wait_for_timeout(5000)
        self._ignore_js_files = False
        
        # Debug logging: capture initial page load
        if self._debug_session:
            screenshot = await self._page.screenshot(type="png", animations="disabled")
            viewport = await self._page.evaluate("({width: window.innerWidth, height: window.innerHeight})")
            self._debug_session.log_event("page_load", {
                "url": url,
                "viewport": viewport,
                "timeout": load_timeout
            }, screenshot)

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

    async def perform_analysis(self, query: str) -> AnalysisResult | None:
        try:
            # With asset requests being aborted, the screenshot should no longer time out
            # waiting for fonts. The invalid 'wait_for_fonts' argument is removed.
            screenshot = await self._page.screenshot(
                type="png",
                timeout=60000,  # A generous timeout is still fine
                animations="disabled"  # Disables CSS animations for a stable capture
            )
            
            # Log screenshot metadata
            screenshot_size = len(screenshot)
            self._logger.info("analysis", action="screenshot-captured", 
                            size_bytes=screenshot_size, 
                            current_url=self._page.url,
                            section_navigated=self._section_navigated)
            if not self._section_navigated:
                prompt = ANALYSIS_PROMPT_TEMPLATE_WITH_SECTION_NAVIGATION % query
                template_type = "WITH_SECTION_NAVIGATION"
            else:
                prompt = ANALYSIS_PROMPT_TEMPLATE_WITHOUT_SECTION_NAVIGATION % query
                template_type = "WITHOUT_SECTION_NAVIGATION"

            # Log detailed prompt information
            self._logger.info("analysis", action="llm-request", 
                            template_type=template_type,
                            query=query,
                            prompt_length=len(prompt),
                            prompt_preview=prompt[:200] + "..." if len(prompt) > 200 else prompt)

            llm_input = llm.LLMInput(prompt=prompt, image=screenshot)
            completion = await self._llm_client.get_completion(llm_input, json=True)
            
            # Log detailed completion information
            self._logger.info("analysis", action="llm-completion", 
                            completion=completion.value,
                            completion_length=len(completion.value),
                            input_tokens=getattr(completion, 'input_tokens', 'unknown'),
                            output_tokens=getattr(completion, 'output_tokens', 'unknown'))
            self._completions.append(completion)
            
            # Debug logging: save LLM call details
            if self._debug_session:
                step = self._debug_session.log_event("llm_analysis", {
                    "template_type": template_type,
                    "query": query,
                    "prompt_length": len(prompt),
                    "screenshot_size": screenshot_size,
                    "current_url": self._page.url
                }, screenshot)
                
                # Save LLM request/response files
                request_data = {
                    "template": template_type,
                    "query": query,
                    "prompt": prompt,
                    "prompt_length": len(prompt),
                    "screenshot_size": screenshot_size
                }
                
                response_data = {
                    "completion": completion.value,
                    "input_tokens": getattr(completion, 'input_tokens', 'unknown'),
                    "output_tokens": getattr(completion, 'output_tokens', 'unknown')
                }
                
                self._debug_session.save_llm_call(step, request_data, response_data)
                
        except Exception as exc:
            self._logger.error("analysis", action="llm-completion", exception=exc, query=query)
            raise

        try:
            # Log validation attempt
            self._logger.info("analysis", action="validation-attempt", json_input=completion.value)
            result = AnalysisResult.model_validate_json(completion.value)
            self._logger.info("analysis", action="validation-success", 
                            keywords_count=len(result.keywords) if result.keywords else 0,
                            has_popup_point=result.popup_element_point is not None,
                            has_popup_area=result.popup_area is not None,
                            has_background_point=result.background_overlay_point is not None,
                            popup_type=result.popup_type,
                            has_nav_point=result.navigation_element_point is not None)
            
            # Debug logging: update LLM response with validation result
            if self._debug_session:
                # Update the most recent LLM call response with validation success
                response_data["validation_result"] = {
                    "success": True,
                    "keywords_count": len(result.keywords) if result.keywords else 0,
                    "has_popup_point": result.popup_element_point is not None,
                    "has_nav_point": result.navigation_element_point is not None
                }
                self._debug_session.save_llm_call(step, request_data, response_data)
                
            return result
        except Exception as exc:
            self._logger.error("analysis", action="result-validation", 
                            exception=exc, 
                            json_input=completion.value,
                            validation_error_detail=str(exc))
            
            # Debug logging: update LLM response with validation failure
            if self._debug_session:
                response_data["validation_result"] = {
                    "success": False,
                    "error": str(exc),
                    "json_input": completion.value
                }
                self._debug_session.save_llm_call(step, request_data, response_data)
                self._debug_session.update_timeline_event(step, {"status": "validation_failed", "error": str(exc)})
                
            raise

    def perform_matching(self, keywords: list[str]) -> Response | None:
        self._logger.info("matching", keywords=keywords)
        for response in self._captured_responses:
            score = keyword_match_ratio(keywords, response.value)
            self._logger.info("matching", url=response.request.url, score=score)
            if score < 0.4:
                continue

            return response

    async def determine_strategy(self, response: Response, query: str) -> pagination.StrategyInfo | None:  # noqa: C901
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

                analysis_result = await self.perform_analysis(query)
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

            if await self._js_ctx.scroll_last_similar_element_into_view(keywords):
                return _continue

        should_continue = False
        
        # Enhanced popup handling with multiple strategies
        popup_dismissal_result = await self._popup_dismisser.dismiss_popup(self._page, result)
        
        # Debug logging for popup dismissal
        if self._debug_session:
            step = self._debug_session.log_event("popup_dismissal", {
                "popup_detected": popup_dismissal_result["popup_detected"],
                "popup_type": popup_dismissal_result["popup_type"],
                "success": popup_dismissal_result["popup_dismissed"],
                "strategy": popup_dismissal_result["successful_strategy"]
            })
            self._debug_session.log_popup_dismissal(step, popup_dismissal_result)
            
        if popup_dismissal_result["popup_dismissed"]:
            should_continue = True
            self._logger.info("popup-handling", 
                            result="dismissed", 
                            strategy=popup_dismissal_result["successful_strategy"],
                            attempts=len(popup_dismissal_result["attempts"]))

        if navigation_element_point := result.navigation_element_point:
            position_before = await self._page.evaluate("() => ({ scrollX: window.scrollX, scrollY: window.scrollY })")
            await self._js_ctx.click_element_at_point(navigation_element_point.x, navigation_element_point.y)
            position_after = await self._page.evaluate("() => ({ scrollX: window.scrollX, scrollY: window.scrollY })")

            if self._section_navigated:
                should_continue = True
            elif (
                position_before["scrollX"] != position_after["scrollX"]
                or position_before["scrollY"] != position_after["scrollY"]
            ):
                self._section_navigated = True
                should_continue = True
            else:
                should_continue = False

        return _continue if should_continue else None

    async def get_extraction_code_and_items_count(
        self, output_schema: type[BaseModel], response_text: str
    ) -> tuple[str | None, int | None]:
        adapter = SchemaAdapter(list[output_schema])  # Every schema will treated as If we're extracting a list of items
        schema_dict = drop_titles(adapter.schema.copy())
        formatted_output_schema = json_dumps(schema_dict, indent=2, default=str)
        retries = 3
        while retries:
            try:
                completion = await self._llm_client.get_completion(
                    llm.LLMInput(
                        prompt=EXTRACTION_CODE_GENERATION_PROMPT_TEMPLATE % (formatted_output_schema, response_text)
                    )
                )
                self._completions.append(completion)
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
                self._logger.info("generate-extraction-code", action="success", extracted_items_count=len(items))
            except Exception:
                retries -= 1
                if retries <= 0:
                    raise
            else:
                return code, len(items)

    async def __call__(
        self,
        query: str,
        output_schema: type[BaseModel],
        max_view_scrolls: int = 30,
    ) -> tuple[Output | None, Metadata]:
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

            analysis_result = await self.perform_analysis(query)
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
                self._logger.error("main-loop", action="process-analysis-error", exception=e)
                continue

            if isinstance(response, Response):
                self._logger.info("main-loop", action="found-matching-response", url=response.request.url)

                # Filter out headers to ignore
                for key in list(response.request.headers):
                    if key.lstrip(":").lower() in HEADERS_TO_IGNORE:
                        response.request.headers.pop(key)

                code, items_count = await self.get_extraction_code_and_items_count(output_schema, response.value)
                output = Output(
                    request=response.request,
                    pagination_strategy=await self.determine_strategy(response, query),
                    schema_extractor_code=code,
                    items_count_on_first_extraction=items_count or 1,
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
