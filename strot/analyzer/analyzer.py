from __future__ import annotations

import asyncio
import contextlib
import io
import os
from collections.abc import Callable
from json import dumps as json_dumps
from typing import Any, cast

from patchright.async_api import Browser
from pydantic import BaseModel

from strot import llm
from strot.analyzer import prompts
from strot.browser import launch_browser
from strot.browser.tab import Tab
from strot.logging import LoggerType, get_logger, setup_logging
from strot.schema.pattern import Pattern
from strot.schema.point import Point
from strot.schema.request import Request, RequestDetail, pagination_info
from strot.schema.response import HTMLResponsePreprocessor, Response
from strot.schema.response.detail import ResponseDetail
from strot.schema.source import Source
from strot.type_adapter import TypeAdapter
from strot.utils.image import draw_point_on_image, encode_image
from strot.utils.request import (
    extract_potential_cursors,
    get_value,
)
from strot.utils.text import parse_python_code, text_match_ratio

setup_logging()

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
        analyzer = Analyzer(logger=logger)
        browser_ctx = await browser.new_context(bypass_csp=True)
        tab = Tab(browser_ctx, load_timeout=page_load_timeout)
        try:
            logger.info("analysis", action="begin", status="pending", url=url, query=query)
            await tab.goto(url)
            source = await analyzer(tab, query, output_schema, max_steps)
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
                    source_url=source.request_detail.request.url,
                )
        except Exception as e:
            logger.info("analysis", action="end", status="failed", url=url, query=query, reason=e)
            return None
        else:
            return source
        finally:
            with contextlib.suppress(Exception):
                await tab.reset()
                await browser_ctx.close()

    if browser is None:
        async with launch_browser("headed") as browser_instance:
            return await run(browser_instance)

    return await run(browser)


class Analyzer:
    def __init__(self, logger: LoggerType) -> None:
        self._logger = logger
        self._llm_client = llm.LLMClient(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key=os.getenv("STROT_ANTHROPIC_API_KEY"),
            cost_per_1m_input=3.0,
            cost_per_1m_output=15.0,
        )

    async def request_llm_completion(
        self,
        event: str,
        input: llm.LLMInput,
        json: bool,
        validator: Callable[[str], Any],
    ) -> Any:
        self._logger.info(
            event,
            action="llm-completion",
            provider=self._llm_client.provider,
            model=self._llm_client.model,
            status="pending",
        )
        try:
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
            return validator(completion.value)
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

    async def run_step(self, tab: Tab, query: str) -> Response | None:  # noqa: C901
        screenshot = await tab.plugin.take_screenshot(type="png")
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
            container = await tab.plugin.get_parent_container(sections)
            for idx, response in enumerate(list(tab.responses)):
                score = text_match_ratio(sections, response.value)
                if score < 0.5:
                    continue

                if response.request.type == "ssr" and container:
                    response.preprocessor = HTMLResponsePreprocessor(element_selector=container)

                response_to_return = response
                tab.responses.pop(idx)
                break

            skip = False
            if container and (last_child := await tab.plugin.get_last_visible_child(container)):
                self._logger.info(
                    "run-step",
                    context=encode_image(screenshot),
                    step="skip-similar-content",
                    action="scroll",
                    target=last_child,
                )
                await tab.plugin.scroll_to_element(last_child)
                skip = True

            if point := result.close_overlay_popup_coords:
                self._logger.info(
                    "run-step",
                    context=get_context(point),
                    step="close-overlay-popup",
                    action="click",
                    point=point.model_dump(),
                )
                await tab.plugin.click_at_point(point)

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
            if await tab.plugin.click_at_point(point):
                return

        if point := result.load_more_content_coords:
            self._logger.info(
                "run-step",
                context=get_context(point),
                step="load-more-content",
                action="click",
                point=point.model_dump(),
            )
            if await tab.plugin.click_at_point(point):
                return

        if point := result.skip_to_content_coords:
            self._logger.info(
                "run-step", context=get_context(point), step="skip-to-content", action="click", point=point.model_dump()
            )
            if await tab.plugin.click_at_point(point):
                return

        self._logger.info(
            "run-step", context=encode_image(screenshot), step="fallback", action="scroll", target="next-view"
        )
        await tab.plugin.scroll_to_next_view()

    async def discover_relevant_response(self, tab: Tab, query: str, max_steps: int | MutableRange) -> Response | None:
        for step in range(0, max_steps) if isinstance(max_steps, int) else max_steps:
            try:
                self._logger.info("request-detection", step_count=step, action="run-step", status="pending")
                response = await self.run_step(tab, query)
            except Exception as e:
                self._logger.info("request-detection", step_count=step, action="run-step", status="failed", reason=e)
                response = None

            if not response:
                self._logger.info(
                    "request-detection",
                    step_count=step,
                    action="run-step",
                    status="failed",
                    reason="No response on this step.",
                )
                await asyncio.sleep(2.5)
                continue

            # Log detailed success information
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
                "request-detection", step_count=step, action="run-step", status="success", **success_log_kwargs
            )
            return response

    def build_pagination_info(  # noqa: C901
        self, request: Request, keys: prompts.schema.PaginationKeys, *responses: Response
    ) -> pagination_info.PaginationInfo | None:
        if not (keys.page_number_key or keys.cursor_key or keys.offset_key):
            return None

        page_param = None
        if keys.page_number_key:
            page_param = pagination_info.NumberParameter(
                key=keys.page_number_key,
                default_value=int(get_value(request, keys.page_number_key) or 0),
            )

        cursor_param = None
        if (
            (cursor_key := keys.cursor_key)
            and (cursor := get_value(request, cursor_key))
            and (potential_sub_cursors := extract_potential_cursors(cursor))
        ):
            best_match_count, best_response_text = 0, None

            for response in responses:
                if get_value(response.request, cursor_key) is not None:
                    match_count = sum(1 for v in potential_sub_cursors if v in response.value)
                    if match_count >= best_match_count:
                        best_match_count = match_count
                        best_response_text = response.value

            if best_response_text and best_match_count > 0:
                pattern_map = {}
                for value in potential_sub_cursors:
                    if patterns := Pattern.generate_multiple(best_response_text, value):
                        pattern_map[value] = patterns

                if pattern_map:
                    cursor_param = pagination_info.CursorParameter(
                        key=cursor_key, default_value=str(cursor), pattern_map=pattern_map
                    )

        offset_param = None
        if keys.offset_key:
            offset_param = pagination_info.NumberParameter(
                key=keys.offset_key,
                default_value=int(get_value(request, keys.offset_key) or 0),
            )

        limit_param = None
        if keys.limit_key:
            limit_param = pagination_info.NumberParameter(
                key=keys.limit_key,
                default_value=int(get_value(request, keys.limit_key) or 1),
            )

        if page_param or offset_param or cursor_param:
            strategy = pagination_info.PaginationInfo(
                page=page_param, limit=limit_param, offset=offset_param, cursor=cursor_param
            )
            return strategy

        return None

    async def build_request_detail(self, request: Request, *responses: Response) -> RequestDetail:
        """
        Detect both pagination and dynamic parameters, generating parameter application code.
        """
        type_adapter = TypeAdapter(prompts.schema.ParameterDetectionResult)
        schema = type_adapter.generate_schema(drop_titles=True)
        schema.pop("description", None)

        llm_input = llm.LLMInput(
            prompt=prompts.PARAMETER_DETECTION_PROMPT_TEMPLATE.render(
                request_data=json_dumps(request.model_dump(), indent=2),
                output_schema=json_dumps(schema, indent=2),
            )
        )

        def validate(x):
            result = type_adapter.validate_json(x)

            namespace = {}
            exec(result.apply_parameters_code, namespace)  # noqa: S102
            if "apply_parameters" not in namespace:
                raise ValueError("Generated code missing apply_parameters function")

            return result

        self._logger.info(
            "parameter-detection",
            request=request.model_dump(),
            status="pending",
        )

        result = None
        for _ in range(3):
            try:
                result = cast(
                    prompts.schema.ParameterDetectionResult,
                    await self.request_llm_completion(
                        event="parameter-detection",
                        input=llm_input,
                        json=True,
                        validator=validate,
                    ),
                )
                break
            except Exception:  # noqa: S112
                continue

        if result is None:
            self._logger.info(
                "parameter-detection",
                request=request.model_dump(),
                status="failed",
                reason="Failed to detect pagination and dynamic parameters",
            )
            return RequestDetail(request=request)

        self._logger.info(
            "parameter-detection",
            request=request.model_dump(),
            status="success",
            pagination_keys=result.pagination_keys.model_dump(exclude_none=True),
            dynamic_parameter_keys=result.dynamic_parameter_keys,
            apply_parameters_code=result.apply_parameters_code,
        )
        return RequestDetail(
            request=request,
            pagination_info=self.build_pagination_info(request, result.pagination_keys, *responses),
            dynamic_parameters={k: get_value(request, k) for k in result.dynamic_parameter_keys},
            code_to_apply_parameters=result.apply_parameters_code,
        )

    async def build_response_detail(self, response: Response, output_schema: type[BaseModel]) -> ResponseDetail:
        self._logger.info(
            "structured-extraction",
            response_length=len(response.value),
            preprocessor=response.preprocessor.model_dump() if response.preprocessor else None,
            status="pending",
        )
        response_text = response.value
        if response.preprocessor:
            response_text = response.preprocessor.run(response_text) or response_text

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

            raise ValueError("Code parsing failed")

        response_detail = ResponseDetail(preprocessor=response.preprocessor)
        for _ in range(3):
            try:
                code, entity_count = cast(
                    tuple[str, int],
                    await self.request_llm_completion(
                        event="structured-extraction",
                        input=llm_input,
                        json=False,
                        validator=validate,
                    ),
                )
                response_detail.code_to_extract_data = code
                response_detail.default_entity_count = entity_count
                break
            except Exception:  # noqa: S112
                continue

        if response_detail.code_to_extract_data is None:
            self._logger.info(
                "structured-extraction",
                response_length=len(response.value),
                preprocessor=response.preprocessor.model_dump() if response.preprocessor else None,
                status="failed",
                reason="Could not generate extraction code and determine default entity count.",
            )
        else:
            self._logger.info(
                "structured-extraction",
                response_length=len(response.value),
                preprocessor=response.preprocessor.model_dump() if response.preprocessor else None,
                status="success",
                code=response_detail.code_to_extract_data,
                default_entity_count=response_detail.default_entity_count,
            )
        return response_detail

    async def __call__(
        self,
        tab: Tab,
        query: str,
        output_schema: type[BaseModel],
        max_steps: int = 30,
    ) -> Source | None:
        steps = MutableRange(0, max_steps)
        captured_responses = []
        request_detail, response = None, None
        while True:
            self._logger.info("analysis", action="request-detection", status="pending")
            response = await self.discover_relevant_response(tab, query, steps)
            if not response:
                self._logger.info(
                    "analysis", action="request-detection", status="failed", reason="No relevant response detected."
                )
                break

            captured_responses.append(response)
            self._logger.info("analysis", action="request-detection", status="success")

            self._logger.info("analysis", action="parameter-detection", status="pending")
            request_detail = await self.build_request_detail(response.request, *(tab.responses + captured_responses))
            if request_detail.pagination_info is None:
                self._logger.info(
                    "analysis", action="parameter-detection", status="failed", reason="No pagination detected."
                )
                continue

            self._logger.info("analysis", action="parameter-detection", status="success")
            break

        if not response or not request_detail:
            return None

        self._logger.info("analysis", action="structured-extraction", status="pending")
        response_detail = await self.build_response_detail(response, output_schema)
        if not response_detail.code_to_extract_data:
            self._logger.info(
                "analysis", action="structured-extraction", status="failed", reason="LLM failed to generate code."
            )
        else:
            self._logger.info("analysis", action="structured-extraction", status="success")

        for key in list(request_detail.request.headers):
            if key.lstrip(":").lower() in HEADERS_TO_IGNORE:
                request_detail.request.headers.pop(key)

        return Source(request_detail=request_detail, response_detail=response_detail)


class MutableRange:
    def __init__(self, start: int, stop: int, step: int = 1):
        if step == 0:
            raise ValueError("step argument must not be zero")
        self._current = start
        self._stop = stop
        self._step = step

    def __iter__(self):
        if self._step > 0:
            # Positive step: current < stop
            while self._current < self._stop:
                value = self._current
                self._current += self._step
                yield value
        else:
            # Negative step: current > stop
            while self._current > self._stop:
                value = self._current
                self._current += self._step  # Adding negative step decreases current
                yield value
