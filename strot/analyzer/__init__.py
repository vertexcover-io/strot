import asyncio
import contextlib
import io
import os
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from json import dumps as json_dumps
from typing import Any, Literal, cast
from urllib.parse import parse_qsl, urlparse

from playwright.async_api import Browser, Page, async_playwright
from playwright.async_api import Response as PageResponse
from pydantic import BaseModel

from strot import llm
from strot.analyzer._meta import prompts
from strot.analyzer._meta.plugin import Plugin
from strot.analyzer.schema import Point, Response, pagination_strategy
from strot.analyzer.schema.request import Request
from strot.analyzer.schema.source import Source
from strot.analyzer.utils import draw_point_on_image, encode_image, parse_python_code, text_match_ratio
from strot.logging import LoggerType, get_logger, setup_logging
from strot.type_adapter import TypeAdapter

__all__ = ("analyze", "create_browser")

setup_logging()

EXCLUDE_KEYWORDS = {"analytics", "telemetry", "events", "collector", "track", "collect"}
"""URL filtering keywords"""


HEADERS_TO_IGNORE = {
    "accept-encoding",
    "host",
    "method",
    "path",
    "scheme",
    "version",
    "authority",
    "protocol",
    "content-length",
}


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


async def analyze(
    *,
    url: str,
    query: str,
    output_schema: type[BaseModel],
    max_steps: int = 30,
    browser: Browser | Literal["headless", "headed"] = "headed",
    logger: LoggerType | None = None,
    page_load_timeout: float | None = None,
) -> Source | None:
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
    """
    if logger is None:
        logger = get_logger()

    async def run(browser: Browser):
        browser_ctx = await browser.new_context(bypass_csp=True)
        page = await browser_ctx.new_page()
        try:
            logger.info("analysis", action="begin", status="pending", url=url, query=query)
            run_ctx = _AnalyzerContext(page=page, logger=logger)
            await run_ctx.load_url(url, page_load_timeout)
            source = await run_ctx(query, output_schema, max_steps)
            if not source:
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
                    source_url=source.request.url,
                )
        except Exception as e:
            logger.info("analysis", action="end", status="failed", url=url, query=query, reason=e)
            return None
        else:
            return source
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
            api_key=os.getenv("STROT_ANTHROPIC_API_KEY"),
            cost_per_1m_input=3.0,
            cost_per_1m_output=15.0,
        )

        self._plugin = Plugin(page)

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
        event: str,
        input: llm.LLMInput,
        json: bool,
        validator: Callable[[str], Any],
    ) -> Any:
        try:
            self._logger.info(
                event,
                action="llm-completion",
                provider=self._llm_client.provider,
                model=self._llm_client.model,
                status="pending",
            )
            completion = await self._llm_client.get_completion(input, json=json)
            self._logger.info(
                event,
                action="llm-completion",
                provider=self._llm_client.provider,
                model=self._llm_client.model,
                status="success",
                result=completion.value,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
                cost=self._llm_client.calculate_cost(completion.input_tokens, completion.output_tokens),
            )
        except Exception as e:
            self._logger.info(
                event,
                action="llm-completion",
                provider=self._llm_client.provider,
                model=self._llm_client.model,
                status="failed",
                reason=e,
            )
            raise

        try:
            return validator(completion.value)
        except Exception as e:
            self._logger.info(event, action="llm-completion:validation", status="failed", reason=e)
            raise

    async def get_extraction_code_and_default_limit(
        self, output_schema: type[BaseModel], response_text: str
    ) -> tuple[str | None, int | None]:
        # Every schema will be treated as If we're extracting a list of items
        type_adapter = TypeAdapter(list[output_schema])
        schema = type_adapter.generate_schema(drop_titles=True)
        schema.pop("description", None)
        llm_input = llm.LLMInput(
            prompt=prompts.GENERATE_EXTRACTION_CODE_PROMPT_TEMPLATE.render(
                output_schema=json_dumps(schema, indent=2),
                api_response=response_text,
            )
        )

        def validate(value: str) -> tuple[str, int]:
            if code := parse_python_code(value):
                namespace = {}
                exec(code, namespace)  # noqa: S102
                data = type_adapter.validate_python(namespace["extract_data"](response_text))
                return code, len(data)

            raise ValueError("Code extraction failed")

        for _ in range(3):
            try:
                return cast(
                    tuple[str, int],
                    await self.request_llm_completion(
                        event="code-generation",
                        input=llm_input,
                        json=False,
                        validator=validate,
                    ),
                )
            except Exception:  # noqa: S112
                continue
        return None, None

    async def detect_pagination_keys(self, parameters: dict[str, Any]) -> prompts.schema.PaginationKeys:
        type_adapter = TypeAdapter(prompts.schema.PaginationKeys)
        schema = type_adapter.generate_schema(drop_titles=True)
        schema.pop("description", None)
        llm_input = llm.LLMInput(
            prompt=prompts.IDENTIFY_PAGINATION_KEYS_PROMPT_TEMPLATE.render(
                parameters=json_dumps(parameters, indent=2),
                output_schema=json_dumps(schema, indent=2),
            )
        )

        for _ in range(3):
            try:
                return cast(
                    prompts.schema.PaginationKeys,
                    await self.request_llm_completion(
                        event="detect-pagination",
                        input=llm_input,
                        json=True,
                        validator=lambda x: type_adapter.validate_json(x),
                    ),
                )
            except Exception:  # noqa: S112
                continue
        return prompts.schema.PaginationKeys()

    async def detect_pagination_strategy(  # noqa: C901
        self, keys: prompts.schema.PaginationKeys, parameters: dict[str, Any]
    ) -> pagination_strategy.PaginationStrategy | None:
        if keys.page_number_key and keys.offset_key:
            return pagination_strategy.PageOffsetInfo(
                page_key=keys.page_number_key,
                offset_key=keys.offset_key,
                base_offset=int(parameters[keys.offset_key]) // int(parameters[keys.page_number_key]),
            )
        elif keys.limit_key and keys.offset_key:
            return pagination_strategy.LimitOffsetInfo(
                limit_key=keys.limit_key,
                offset_key=keys.offset_key,
            )
        elif keys.page_number_key:
            return pagination_strategy.PageInfo(page_key=keys.page_number_key, limit_key=keys.limit_key)
        elif cursor_key := keys.cursor_key:
            cursor = parameters.get(cursor_key)
            if isinstance(cursor, str):
                for c_response in self._captured_responses:
                    patterns = pagination_strategy.StringCursorInfo.generate_patterns(c_response.value, cursor)
                    if patterns:
                        return pagination_strategy.StringCursorInfo(
                            cursor_key=cursor_key,
                            limit_key=keys.limit_key,
                            default_cursor=cursor,
                            patterns=patterns,
                        )
            elif isinstance(cursor, dict):
                for c_response in self._captured_responses:
                    patterns_map = pagination_strategy.MapCursorInfo.generate_patterns_map(c_response.value, cursor)
                    if any(patterns_map.values()):
                        return pagination_strategy.MapCursorInfo(
                            cursor_key=cursor_key,
                            limit_key=keys.limit_key,
                            default_cursor=cursor,
                            patterns_map=patterns_map,
                        )

    async def run_step(self, query: str) -> Response | None:  # noqa: C901
        screenshot = await self._page.screenshot(type="png")
        type_adapter = TypeAdapter(prompts.schema.StepResult)
        schema = type_adapter.generate_schema(drop_titles=True)
        schema.pop("description", None)
        prompt = prompts.ANALYZE_CURRENT_VIEW_PROMPT_TEMPLATE.render(
            output_schema=json_dumps(schema, indent=2), requirement=query
        )

        try:
            result = cast(
                prompts.schema.StepResult,
                await self.request_llm_completion(
                    event="run-step",
                    input=llm.LLMInput(prompt=prompt, image=screenshot),
                    json=True,
                    validator=lambda x: type_adapter.validate_json(x),
                ),
            )
        except Exception:
            return None

        if sections := result.text_sections:
            response_to_return = None
            for response in self._captured_responses:
                score = text_match_ratio(sections, response.value)
                if score < 0.5:
                    continue

                response_to_return = response
                break

            if element := await self._plugin.get_last_similar_element(sections):
                self._logger.info(
                    "run-step", context=encode_image(screenshot), step="advance", action="scroll", target=element
                )
                await self._plugin.scroll_to_element(element)

            if element or response_to_return:
                # If either similar element skip was performed or response was found, end the step
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
            if await self._plugin.click_at_point(point):
                return

        if point := result.load_more_content_coords:
            self._logger.info(
                "run-step",
                context=get_context(point),
                step="load-more-content",
                action="click",
                point=point.model_dump(),
            )
            if await self._plugin.click_at_point(point):
                return

        if point := result.skip_to_content_coords:
            self._logger.info(
                "run-step", context=get_context(point), step="skip-to-content", action="click", point=point.model_dump()
            )
            if await self._plugin.click_at_point(point):
                return

        self._logger.info(
            "run-step", context=encode_image(screenshot), step="fallback", action="scroll", target="next-view"
        )
        await self._plugin.scroll_to_next_view()

    async def __call__(  # noqa: C901
        self,
        query: str,
        output_schema: type[BaseModel],
        max_steps: int = 30,
    ) -> Source | None:
        last_response = None
        pagination_keys = prompts.schema.PaginationKeys()
        strategy = None
        for step in range(1, max_steps + 1):
            try:
                self._logger.info("analysis", action="run-step", step_count=step, status="pending")
                response = await self.run_step(query)
                last_response = response
            except Exception as e:
                self._logger.info("analysis", action="run-step", step_count=step, status="failed", reason=e)
                response = None

            if not response:
                self._logger.info(
                    "analysis", action="run-step", step_count=step, status="failed", reason="No response on this step."
                )
                await asyncio.sleep(2.5)
                continue

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

            request_parameters = response.request.simple_parameters
            self._logger.info(
                "analysis",
                action="detect-pagination",
                request_parameters=request_parameters,
                status="pending",
            )
            if not request_parameters:
                self._logger.info(
                    "analysis",
                    action="detect-pagination",
                    request_parameters=request_parameters,
                    status="failed",
                    reason="No pagination compatible parameters detected.",
                )
                continue

            if not pagination_keys.strategy_available():
                pagination_keys = await self.detect_pagination_keys(request_parameters)

            strategy = await self.detect_pagination_strategy(pagination_keys, request_parameters)
            if strategy is None:
                self._logger.info(
                    "analysis",
                    action="detect-pagination",
                    request_parameters=request_parameters,
                    status="failed",
                    reason="No pagination strategy detected. Trying again after collecting new responses.",
                )
                continue

            if isinstance(strategy, pagination_strategy.StringCursorInfo | pagination_strategy.MapCursorInfo):
                log_kwargs = {
                    "cursor_key": strategy.cursor_key,
                    "limit_key": strategy.limit_key,
                    "default_cursor": strategy.default_cursor,
                }
            else:
                log_kwargs = strategy.model_dump()

            self._logger.info(
                "analysis",
                action="detect-pagination",
                request_parameters=request_parameters,
                status="success",
                strategy=strategy.name,
                **log_kwargs,
            )
            break

        if not last_response:
            return None

        self._logger.info("analysis", action="code-generation", status="pending")
        code, default_limit = await self.get_extraction_code_and_default_limit(output_schema, last_response.value)
        if not code:
            self._logger.info(
                "analysis", action="code-generation", status="failed", reason="LLM failed to generate code."
            )
        else:
            self._logger.info("analysis", action="code-generation", status="success", code=code)

        # Filter out headers to ignore
        for key in list(last_response.request.headers):
            if key.lstrip(":").lower() in HEADERS_TO_IGNORE:
                last_response.request.headers.pop(key)

        return Source(
            request=last_response.request,
            pagination_strategy=strategy,
            extraction_code=code,
            default_limit=default_limit or 1,
        )
