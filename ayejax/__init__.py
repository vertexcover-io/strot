import asyncio
import contextlib
import io
import os
import re
from contextlib import asynccontextmanager, suppress
from json import dumps as json_dumps
from pathlib import Path
from typing import Any, Callable, Literal, cast, overload
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
    PAGINATION_KEYS_IDENTIFICATION_PROMPT_TEMPLATE,
)
from ayejax.helpers import draw_point_on_image, encode_image, keyword_match_ratio
from ayejax.logging import LoggerType
from ayejax.tag import Tag, TagLiteral
from ayejax.types import (
    AnalysisResult,
    Output,
    PaginationKeys,
    Point,
    Request,
    Response,
)

__all__ = (
    "analyze",
    "create_browser",
)


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
    max_steps: int = 30,
    browser: Browser | Literal["headless", "headed"] = "headed",
    logger: LoggerType,
    page_load_timeout: float | None = None,
) -> Output | None:
    """
    Run analysis on the given URL using the given tag.

    Args:
        url: The target web page URL to analyze.
        tag: The kind of information to look for (e.g. reviews).
        max_steps: The maximum number of steps to perform before exiting.
        browser: The browser to use.
        logger: The logger to use.
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
    max_steps: int = 30,
    browser: Browser | Literal["headless", "headed"] = "headed",
    logger: LoggerType,
    page_load_timeout: float | None = None,
) -> Output | None:
    """
    Run analysis on the given URL using the given tag.

    Args:
        url: The target web page URL to analyze.
        tag: The kind of information to look for (e.g. reviews).
        max_steps: The maximum number of steps to perform before exiting.
        browser: The browser to use.
        logger: The logger to use.
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
    max_steps: int = 30,
    browser: Browser | Literal["headless", "headed"] = "headed",
    logger: LoggerType,
    page_load_timeout: float | None = None,
) -> Output | None:
    """
    Run analysis on the given URL using the given query.

    Args:
        url: The target web page URL to analyze.
        query: The query to use for analysis.
        output_schema: The output schema to extract data from the response.
        max_steps: The maximum number of steps to perform before exiting.
        browser: The browser to use.
        logger: The logger to use.
        page_load_timeout: The timeout for waiting for the page to load.

    Returns:
        Tuple of output and metadata.
    """


async def analyze(
    url: str,
    query_or_tag: str | Tag | TagLiteral,
    /,
    *,
    max_steps: int = 30,
    browser: Browser | Literal["headless", "headed"] = "headed",
    logger: LoggerType,
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
            logger.info("analysis", action="begin", status="pending", url=url, query=query)
            run_ctx = _AnalyzerContext(page=page, logger=logger)
            await run_ctx.load_url(url, page_load_timeout)
            output = await run_ctx(query, output_schema, max_steps)
            if not output:
                logger.info(
                    "analysis", action="end", status="failed", url=url, query=query, reason="No relevant request found"
                )
            else:
                logger.info(
                    "analysis",
                    action="end",
                    status="success",
                    url=url,
                    query=query,
                    relevant_api_call=output.request.url,
                )
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
        self._anthropic_client = llm.LLMClient(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key=os.getenv("AYEJAX_ANTHROPIC_API_KEY"),
            cost_per_1m_input=3.0,
            cost_per_1m_output=15.0,
        )
        self._groq_client = llm.LLMClient(
            provider="groq",
            model="moonshotai/kimi-k2-instruct",
            api_key=os.getenv("AYEJAX_GROQ_API_KEY"),
            cost_per_1m_input=1.0,
            cost_per_1m_output=3.0,
        )

        self._js_ctx = _JSContext(page)

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

    async def request_llm_completion(
        self,
        client: llm.LLMClient,
        event: str,
        input: llm.LLMInput,
        json: bool,
        validator: Callable[[str], Any],
    ) -> Any:
        try:
            self._logger.info(
                event, action="llm-completion", provider=client.provider, model=client.model, status="pending"
            )
            completion = await client.get_completion(input, json=json)
            self._logger.info(
                event,
                action="llm-completion",
                provider=client.provider,
                model=client.model,
                status="success",
                result=completion.value,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
                cost=client.calculate_cost(completion.input_tokens, completion.output_tokens),
            )
        except Exception as e:
            self._logger.info(
                event, action="llm-completion", provider=client.provider, model=client.model, status="failed", reason=e
            )
            raise

        try:
            return validator(completion.value)
        except Exception as e:
            self._logger.info(event, action="llm-completion:validation", status="failed", reason=e)
            raise

    async def get_extraction_code_and_items_count(
        self, output_schema: type[BaseModel], response_text: str
    ) -> tuple[str | None, int | None]:
        # Every schema will be treated as If we're extracting a list of items
        adapter = SchemaAdapter(list[output_schema])
        llm_input = llm.LLMInput(
            prompt=EXTRACTION_CODE_GENERATION_PROMPT_TEMPLATE
            % (
                json_dumps(drop_titles(adapter.schema), indent=2),
                response_text,
            )
        )

        def validate(value: str) -> tuple[str, int]:
            # Pattern to match code fences with optional language specification
            # Matches ```python, ```py, or just ``` followed by code and ending ```
            pattern = r"```(?:python|py)?\s*\n(.*?)\n```"

            matches = re.findall(pattern, value, re.DOTALL)
            if not matches:
                return None

            code = matches[0].strip()
            namespace = {}
            exec(code, namespace)  # noqa: S102
            items = adapter.validate_python(namespace["extract_data"](response_text))
            return code, len(items)

        for _ in range(3):
            try:
                return cast(
                    tuple[str, int],
                    await self.request_llm_completion(
                        client=self._groq_client,
                        event="code-generation",
                        input=llm_input,
                        json=False,
                        validator=validate,
                    ),
                )
            except Exception:  # noqa: S112
                continue
        return None, None

    async def detect_pagination_keys(self, parameters: dict[str, Any]) -> PaginationKeys:
        llm_input = llm.LLMInput(
            prompt=PAGINATION_KEYS_IDENTIFICATION_PROMPT_TEMPLATE.format(
                parameters=json_dumps(parameters, indent=2),
                output_schema=json_dumps(drop_titles(PaginationKeys.model_json_schema()), indent=2),
            )
        )

        for _ in range(3):
            try:
                return cast(
                    PaginationKeys,
                    await self.request_llm_completion(
                        client=self._anthropic_client,
                        event="detect-pagination",
                        input=llm_input,
                        json=True,
                        validator=lambda x: PaginationKeys.model_validate_json(x),
                    ),
                )
            except Exception:  # noqa: S112
                continue
        return PaginationKeys()

    async def detect_pagination_strategy(  # noqa: C901
        self, keys: PaginationKeys, parameters: dict[str, Any]
    ) -> pagination.StrategyInfo | None:
        if keys.page_number_key and keys.offset_key:
            return pagination.strategy.PageOffsetInfo(
                page_key=keys.page_number_key,
                offset_key=keys.offset_key,
                base_offset=int(parameters[keys.offset_key]) // int(parameters[keys.page_number_key]),
            )
        elif keys.limit_key and keys.offset_key:
            return pagination.strategy.LimitOffsetInfo(
                limit_key=keys.limit_key,
                offset_key=keys.offset_key,
            )
        elif keys.page_number_key:
            return pagination.strategy.PageInfo(page_key=keys.page_number_key, limit_key=keys.limit_key)
        elif cursor_key := keys.cursor_key:
            cursor = parameters.get(cursor_key)
            if isinstance(cursor, str):
                for c_response in self._captured_responses:
                    patterns = pagination.strategy.StringCursorInfo.generate_patterns(c_response.value, cursor)
                    if patterns:
                        return pagination.strategy.StringCursorInfo(
                            cursor_key=cursor_key,
                            limit_key=keys.limit_key,
                            default_cursor=cursor,
                            patterns=patterns,
                        )
            elif isinstance(cursor, dict):
                for c_response in self._captured_responses:
                    patterns_map = pagination.strategy.MapCursorInfo.generate_patterns_map(c_response.value, cursor)
                    if any(patterns_map.values()):
                        return pagination.strategy.MapCursorInfo(
                            cursor_key=cursor_key,
                            limit_key=keys.limit_key,
                            default_cursor=cursor,
                            patterns_map=patterns_map,
                        )

    async def run_step(self, query: str) -> Response | None:  # noqa: C901
        screenshot = await self._page.screenshot(type="png")
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            output_schema=json_dumps(drop_titles(AnalysisResult.model_json_schema()), indent=2), query=query
        )

        try:
            result = cast(
                AnalysisResult,
                await self.request_llm_completion(
                    client=self._anthropic_client,
                    event="run-step",
                    input=llm.LLMInput(prompt=prompt, image=screenshot),
                    json=True,
                    validator=lambda x: AnalysisResult.model_validate_json(x),
                ),
            )
        except Exception:
            return None

        if sections := result.text_sections:
            response_to_return = None
            for response in self._captured_responses:
                score = keyword_match_ratio(sections, response.value)
                if score < 0.5:
                    continue

                response_to_return = response
                break

            if element := await self._js_ctx.get_last_similar_element(sections):
                self._logger.info(
                    "run-step", context=encode_image(screenshot), step="advance", action="scroll", target=element
                )
                await self._js_ctx.scroll_to_element(element)

            return response_to_return

        def get_context(point: Point) -> bytes:
            image = draw_point_on_image(screenshot, point)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return encode_image(buffer.getvalue())

        if point := result.close_overlay_popup_coords:
            self._logger.info(
                "run-step",
                context=get_context(point),
                step="close-overlay-popup",
                action="click",
                point=point.model_dump(),
            )
            if await self._js_ctx.click_at_point(point):
                return

        if point := result.load_more_content_coords:
            self._logger.info(
                "run-step",
                context=get_context(point),
                step="load-more-content",
                action="click",
                point=point.model_dump(),
            )
            if await self._js_ctx.click_at_point(point):
                return

        if point := result.skip_to_content_coords:
            self._logger.info(
                "run-step", context=get_context(point), step="skip-to-content", action="click", point=point.model_dump()
            )
            if await self._js_ctx.click_at_point(point):
                return

        self._logger.info(
            "run-step", context=encode_image(screenshot), step="fallback", action="scroll", target="next-view"
        )
        await self._js_ctx.scroll_to_next_view()

    async def __call__(  # noqa: C901
        self,
        query: str,
        output_schema: type[BaseModel],
        max_steps: int = 30,
    ) -> Output | None:
        first_response = None
        pagination_keys = PaginationKeys()
        for step in range(1, max_steps + 1):
            try:
                self._logger.info("analysis", action="run-step", step_count=step, status="pending")
                response = await self.run_step(query)
            except Exception as e:
                self._logger.info("analysis", action="run-step", step_count=step, status="failed", reason=e)
                response = None

            if not response:
                self._logger.info(
                    "analysis", action="run-step", step_count=step, status="failed", reason="No response on this step."
                )
                await asyncio.sleep(2.5)  # Wait before retrying for click/scroll event to take effect.
                continue

            if first_response is None:
                first_response = response

            self._logger.info(
                "analysis",
                action="run-step",
                step_count=step,
                status="success",
                method=response.request.method,
                url=response.request.url,
                queries=response.request.queries,
                data=response.request.post_data,
            )

            request_parameters = response.request.parameters
            self._logger.info(
                "analysis",
                action="detect-pagination",
                request_parameters=request_parameters,
                status="pending",
            )
            if request_parameters and not pagination_keys.strategy_available():
                pagination_keys = await self.detect_pagination_keys(request_parameters)

            pagination_strategy = await self.detect_pagination_strategy(pagination_keys, request_parameters)
            if pagination_strategy is None:
                self._logger.info(
                    "analysis",
                    action="detect-pagination",
                    request_parameters=request_parameters,
                    status="failed",
                    reason="No pagination keys detected. Trying again after collecting new responses.",
                )
                continue

            if isinstance(
                pagination_strategy, (pagination.strategy.StringCursorInfo, pagination.strategy.MapCursorInfo)
            ):
                log_kwargs = {
                    "cursor_key": pagination_strategy.cursor_key,
                    "default_cursor": pagination_strategy.default_cursor,
                }
            else:
                log_kwargs = pagination_strategy.model_dump()

            self._logger.info(
                "analysis",
                action="detect-pagination",
                request_parameters=request_parameters,
                status="success",
                strategy=pagination_strategy.name,
                **log_kwargs,
            )

            self._logger.info("analysis", action="code-generation", status="pending")
            code, items_count = await self.get_extraction_code_and_items_count(output_schema, response.value)
            if not code:
                self._logger.info(
                    "analysis", action="code-generation", status="failed", reason="LLM failed to generate code."
                )
            else:
                self._logger.info("analysis", action="code-generation", status="success", code=code)

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

    def __init__(self, page: Page) -> None:
        self._page = page

    async def evaluate(self, expr: str, args=None) -> bool:
        if not await self._page.evaluate("() => window.scriptInjected === true"):
            _ = await self._page.add_script_tag(path=Path(__file__).parent / "inject.js")

        await self._page.wait_for_load_state("domcontentloaded")
        result = await self._page.evaluate(expr, args)
        await self._page.wait_for_load_state("domcontentloaded")
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

    async def get_last_similar_element(self, text_sections: list[str]) -> str | None:
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
            for section in sorted(text_sections, key=len, reverse=True):
                match_ratio = keyword_match_ratio([section], text_in_view)

                if match_ratio > best_match_ratio:
                    best_match_ratio = match_ratio

            if best_match_ratio:
                return selector

    async def scroll_to_element(self, selector: str) -> None:
        await self._page.locator(selector).scroll_into_view_if_needed()
