import asyncio
import contextlib
import io
import os
from collections.abc import Callable
from json import dumps as json_dumps
from typing import Any, cast
from urllib.parse import parse_qsl, urlparse

from patchright.async_api import Browser, Page
from patchright.async_api import Response as InterceptedResponse
from pydantic import BaseModel

from strot import llm
from strot.analyzer._meta import prompts
from strot.analyzer._meta.plugin import Plugin
from strot.analyzer.schema import HTMLResponsePreprocessor, Point, Response, pagination_strategy
from strot.analyzer.schema.request import Request
from strot.analyzer.schema.source import Source
from strot.analyzer.utils import (
    draw_point_on_image,
    encode_image,
    extract_potential_cursors,
    generate_patterns,
    get_potential_pagination_parameters,
    parse_python_code,
    text_match_ratio,
)
from strot.browser import launch_browser
from strot.logging import LoggerType, get_logger, setup_logging
from strot.type_adapter import TypeAdapter

__all__ = ("analyze",)

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


async def analyze(
    *,
    url: str,
    query: str,
    output_schema: type[BaseModel],
    max_steps: int = 30,
    browser: Browser | None = None,
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
    logger = logger or get_logger()

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
            with contextlib.suppress(Exception):
                await browser_ctx.close()

    if browser is None:
        async with launch_browser("headed") as browser_instance:
            return await run(browser_instance)

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
        self._page_headers = None
        self._captured_responses: list[Response] = []

        self._page.on("response", self.handle_ajax_response)

    async def load_url(self, url: str, load_timeout: float | None) -> None:
        await self._page.set_viewport_size({"width": 1280, "height": 800})
        with contextlib.suppress(Exception):
            response = await self._page.goto(url, timeout=load_timeout, wait_until="domcontentloaded")
            if response:
                self._page_headers = await response.request.all_headers()

        await self._page.wait_for_timeout(5000)
        self._page.on("load", self.handle_server_side_rendering)
        self._ignore_js_files = False

    async def handle_ajax_response(self, response: InterceptedResponse) -> None:
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
                        type="ajax",
                        headers=await response.request.all_headers(),
                        post_data=response.request.post_data_json,
                    ),
                )
            )

    async def handle_server_side_rendering(self, page: Page) -> None:
        parsed_url = urlparse(page.url)
        if parsed_url.scheme.lower() not in ("http", "https"):
            return

        self._captured_responses.append(
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
        page_param = None
        if keys.page_number_key:
            page_param = pagination_strategy.NumberParameter(
                key=keys.page_number_key,
                default_value=int(parameters.get(keys.page_number_key, 0)),
            )

        cursor_param = None
        if (
            (cursor_key := keys.cursor_key)
            and (cursor := parameters.get(cursor_key))
            and (potential_sub_cursors := extract_potential_cursors(cursor))
        ):
            best_match_count, best_response_text = 0, None

            for response in self._captured_responses:
                response_parameters = get_potential_pagination_parameters(response.request)
                if response_parameters and set(response_parameters).issubset(parameters):
                    match_count = sum(1 for v in potential_sub_cursors if v in response.value)
                    if match_count >= best_match_count:
                        best_match_count = match_count
                        best_response_text = response.value

            if best_response_text and best_match_count > 0:
                pattern_map = {}
                for value in potential_sub_cursors:
                    if patterns := generate_patterns(best_response_text, value):
                        pattern_map[value] = patterns

                if pattern_map:
                    cursor_param = pagination_strategy.CursorParameter(
                        key=cursor_key, default_value=str(cursor), pattern_map=pattern_map
                    )

        offset_param = None
        if keys.offset_key:
            offset_param = pagination_strategy.NumberParameter(
                key=keys.offset_key,
                default_value=int(parameters.get(keys.offset_key, 0)),
            )

        limit_param = None
        if keys.limit_key:
            limit_param = pagination_strategy.NumberParameter(
                key=keys.limit_key,
                default_value=int(parameters.get(keys.limit_key, 1)),
            )

        if page_param or offset_param or cursor_param:
            return pagination_strategy.PaginationStrategy(
                page=page_param, limit=limit_param, offset=offset_param, cursor=cursor_param
            )

        return None

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

        def get_context(point: Point) -> bytes:
            image = draw_point_on_image(screenshot, point)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return encode_image(buffer.getvalue())

        if sections := result.text_sections:
            response_to_return = None
            container = await self._plugin.get_parent_container(sections)
            for response in self._captured_responses:
                score = text_match_ratio(sections, response.value)
                if score < 0.5:
                    continue

                if response.request.type == "ssr" and container:
                    response.preprocessor = HTMLResponsePreprocessor(element_selector=container)

                response_to_return = response
                break

            skip = False
            if container and (last_child := await self._plugin.get_last_visible_child(container)):
                self._logger.info(
                    "run-step",
                    context=encode_image(screenshot),
                    step="skip-similar-content",
                    action="scroll",
                    target=last_child,
                )
                await self._plugin.scroll_to_element(last_child)
                skip = True

            if point := result.close_overlay_popup_coords:
                self._logger.info(
                    "run-step",
                    context=get_context(point),
                    step="close-overlay-popup",
                    action="click",
                    point=point.model_dump(),
                )
                await self._plugin.click_at_point(point)

            if skip or response_to_return:
                # If either similar element skip was performed or response was found, end the step
                return response_to_return

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
        pg_keys = prompts.schema.PaginationKeys()
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

            success_log_kwargs = {
                "request_type": response.request.type,
                "method": response.request.method,
                "url": response.request.url,
                "queries": response.request.queries,
                "data": response.request.post_data,
            }
            if response.preprocessor:
                success_log_kwargs["response_preprocessor"] = response.preprocessor.model_dump()

            self._logger.info(
                "analysis",
                action="run-step",
                step_count=step,
                status="success",
                **success_log_kwargs,
            )

            potential_pagination_parameters = get_potential_pagination_parameters(response.request)
            self._logger.info(
                "analysis",
                action="detect-pagination",
                potential_pagination_parameters=potential_pagination_parameters,
                status="pending",
            )
            if not potential_pagination_parameters:
                self._logger.info(
                    "analysis",
                    action="detect-pagination",
                    potential_pagination_parameters=potential_pagination_parameters,
                    status="failed",
                    reason="No pagination compatible parameters detected.",
                )
                await self._plugin.scroll_to_next_view()
                continue

            if not (pg_keys.page_number_key or pg_keys.cursor_key or pg_keys.offset_key):
                pg_keys = await self.detect_pagination_keys(potential_pagination_parameters)

            strategy = await self.detect_pagination_strategy(pg_keys, potential_pagination_parameters)
            if strategy is None:
                self._logger.info(
                    "analysis",
                    action="detect-pagination",
                    potential_pagination_parameters=potential_pagination_parameters,
                    status="failed",
                    reason="No pagination strategy detected. Trying again after collecting new responses.",
                )
                continue

            self._logger.info(
                "analysis",
                action="detect-pagination",
                potential_pagination_parameters=potential_pagination_parameters,
                status="success",
                strategy={"info": strategy.model_dump()},
            )
            break

        if not last_response:
            return None

        self._logger.info("analysis", action="code-generation", status="pending")
        response_value = last_response.value
        if last_response.preprocessor:
            response_value = last_response.preprocessor.run(response_value) or response_value

        code, default_limit = await self.get_extraction_code_and_default_limit(output_schema, response_value)
        if not code:
            self._logger.info(
                "analysis", action="code-generation", status="failed", reason="LLM failed to generate code."
            )
        else:
            self._logger.info("analysis", action="code-generation", status="success", code=code)

        for key in list(last_response.request.headers):
            if key.lstrip(":").lower() in HEADERS_TO_IGNORE:
                last_response.request.headers.pop(key)

        return Source(
            request=last_response.request,
            pagination_strategy=strategy,
            response_preprocessor=last_response.preprocessor,
            extraction_code=code,
            default_limit=default_limit or 1,
        )
