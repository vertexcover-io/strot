import time
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlparse, urlsplit

from playwright.async_api import Browser, Page
from playwright.async_api import Response as PWResponse

from . import llm
from .helpers import keyword_match_ratio
from .logging import LoggerType
from .page_worker import PageWorker
from .types import (
    Candidate,
    CapturedRequest,
    CapturedResponse,
    Context,
    LLMValue,
    Output,
)

__all__ = ("find",)


EXCLUDE_KEYWORDS = {"analytics", "telemetry", "events", "collector", "track", "collect"}
"""URL filtering keywords"""

PROMPT_TEMPLATE = """\
Your task is to precisely extract keywords from the provided screenshot of a webpage. These keywords must fully comply with the specified user requirements and should exactly match those visible in the screenshot.

Strictly adhere to the following instructions:
- Inspect the screenshot for keywords that meet the user-specified criteria.
- If an overlay popup is visible in the screenshot, identify the "close" or "allow" clickable element's coordinates and assign them to "popup_element_point". If no overlay popup is present, set this to null.
- If and only if no suitable keywords are found:
  - set "keywords" to an empty list.
  - Look for user requirement relevant navigation elements in the following priority order:
    1. **Pagination controls**: Page numbers (1, 2, 3...), "Next" button, ">" arrow, "More" button, or pagination dots
    2. **Section navigation**: Menu items, tabs, category links, or filter options that lead to sections likely containing the required keywords
    3. **Content expansion**: "Show more", "Load more", "Expand", or accordion/dropdown toggles
  - Select the MOST RELEVANT navigation element that would likely lead to finding the required keywords
  - Assign the coordinates of this element to "navigation_element_point"
  - If no relevant navigation element is found, set this to null

Provide your response in JSON matching this schema:

{
  "keywords": ["<keyword1>", "<keyword2>", ...],
  "popup_element_point": {"x": <x>, "y": <y>} or null,
  "navigation_element_point": {"x": <x>, "y": <y>} or null
}

User Requirement: %s"""


class PageScroller:
    def __init__(
        self,
        *,
        page: Page,
        logger: LoggerType,
        wait_timeout: float | None,
    ) -> None:
        self.page = page
        self.logger = logger
        self.wait_timeout = wait_timeout or 5000

    async def _eval(self, expr: str, args=None) -> bool:
        if not await self.page.evaluate("() => window.ayejaxScriptAttached === true"):
            _ = await self.page.add_script_tag(path=Path(__file__).parent / "inject.js")

        try:
            self.logger.info("page", action="eval", expr=expr, status="pending")
            result = bool(await self.page.evaluate(expr, args))

            self.logger.info("page", action="wait", timeout=self.wait_timeout)
            await self.page.wait_for_load_state("domcontentloaded", timeout=self.wait_timeout)

            self.logger.info("page", action="eval", expr=expr, status="completed", result=result)
        except Exception as e:
            if f"Timeout {self.wait_timeout}ms exceeded" not in str(e):
                self.logger.error("page", action="wait", error=str(e))
                return False
            else:
                self.logger.info("page", action="eval", expr=expr, status="unknown")
                return True

        return result

    async def scroll_elements_in_view(self) -> bool:
        return await self._eval("() => scrollElements(getScrollableElements())")

    async def scroll_to_next_view(self, direction: Literal["up", "down"] = "down") -> bool:
        return await self._eval("([direction]) => scrollViewport({ direction })", [direction])

    async def scroll(self) -> bool:
        # status = await self.scroll_elements_in_view()
        # self.logger.info("scroll", type="elements-in-view", status=status)
        # if status:
        #     return True
        status = await self.scroll_to_next_view()
        self.logger.info("scroll", type="next-view", status=status)
        return status


async def click_at_point(page: Page, x: int, y: int, delay: float | None = None) -> bool:
    """Click the element located at the given *viewport* coordinates."""

    viewport = page.viewport_size or {"width": 0, "height": 0}
    if not (0 <= x <= viewport["width"] and 0 <= y <= viewport["height"]):
        raise ValueError(f"Point ({x}, {y}) is outside of the current viewport {viewport}. Consider scrolling first.")

    click_succeeded: bool = await page.evaluate(
        "([x, y]) => {\n"
        "  const el = document.elementFromPoint(x, y);\n"
        "  if (!el) return false;\n"
        "  try {\n"
        "    if (typeof el.click === 'function') {\n"
        "      el.click();\n"
        "      return true;\n"
        "    }\n"
        "    return false;\n"
        "  } catch {\n"
        "    return false;\n"
        "  }\n"
        "}",
        [x, y],
    )

    # Fallback to a direct mouse click if DOM click did not succeed.
    if not click_succeeded:
        await page.mouse.move(x, y)
        await page.mouse.click(x, y)

    delay = delay or 2.0
    await page.wait_for_timeout(int(delay * 1000))

    return click_succeeded or True  # Always True if no exceptions occurred


async def find(  # noqa: C901
    url: str,
    query: str,
    *,
    max_scrolls: int = 25,
    max_candidates: int = 10,
    relevance_threshold: float = 0.4,
    wait_timeout: float | None = None,
    browser: Browser | Literal["headless", "headed"] = "headed",
    llm_client: llm.LLMClientInterface,
    logger: LoggerType,
):
    response_map: dict[str, CapturedResponse] = {}
    keywords_list: list[list[str]] = []
    last_screenshot: bytes
    candidate_map: dict[str, Candidate] = {}

    prompt = PROMPT_TEMPLATE % query
    output = Output(candidates=[], completions=[])
    page_worker = PageWorker(browser=browser, filter_keywords=EXCLUDE_KEYWORDS, filter_mode="exclude")

    def perform_matching() -> bool:
        nonlocal last_screenshot
        for url, response in response_map.items():
            for kwds in list(keywords_list):
                score = keyword_match_ratio(kwds, response.value)
                logger.info("matching", url=url, score=score)
                if score < relevance_threshold or (
                    url in candidate_map and candidate_map[url].context.relevance_score > score
                ):
                    continue

                candidate_map[url] = Candidate(
                    request=response.request,
                    context=Context(
                        page_screenshot=last_screenshot,
                        extracted_keywords=kwds,
                        relevance_score=score,
                    ),
                )
                keywords_list.remove(kwds)

        return len(candidate_map) > 0

    async def process_current_state(page: Page, from_navigation: bool = False, from_popup: bool = False) -> bool:
        nonlocal last_screenshot
        logger.info("process-current-state", action="screenshot", type="png")

        last_screenshot = await page.screenshot(type="png")
        llm_input = llm.LLMInput(prompt=prompt, image=last_screenshot)
        try:
            completion = llm_client.get_completion(llm_input, json=True)
            logger.info("process-current-state", action="llm-completion", status="completed", result=completion.value)
            output.completions.append(completion)
        except Exception as e:
            logger.error("process-current-state", action="llm-completion", status="failed", error=str(e))
            return False

        try:
            value = LLMValue.model_validate_json(completion.value)
        except Exception as e:
            logger.error("process-current-state", action="llm-completion", status="failed", error=str(e))
            return False

        if value.keywords:
            logger.info("process-current-state", status="success", keywords=value.keywords)
            keywords_list.append(value.keywords)

        if not from_navigation and value.navigation_element_point:
            logger.info(
                "process-current-state", action="click", navigation_element_point=value.navigation_element_point
            )
            if await click_at_point(page, value.navigation_element_point["x"], value.navigation_element_point["y"]):
                await process_current_state(page, from_navigation=True)

        if not from_popup and value.popup_element_point:
            logger.info("process-current-state", action="click", popup_element_point=value.popup_element_point)
            if await click_at_point(page, value.popup_element_point["x"], value.popup_element_point["y"]):
                await process_current_state(page, from_popup=True)

        return True

    ignore_js = True

    async def on_response(response: PWResponse):
        if (url := response.request.url) in response_map:
            return

        nonlocal ignore_js
        if ignore_js and urlparse(url).path.endswith(".js"):
            # Some sites load the first set of data from source code instead of making AJAX call
            return

        try:
            logger.info("on-response", action="capture", url=url)
            split = urlsplit(url)
            response_map[url] = CapturedResponse(
                value=await response.text(),
                request=CapturedRequest(
                    method=response.request.method,
                    url=f"{split.scheme}://{split.netloc}{split.path}",
                    queries=dict(parse_qsl(split.query)),
                    headers=await response.request.all_headers(),
                    post_data=response.request.post_data_json,
                ),
            )
        except Exception as e:
            logger.error("on-response", action="capture", url=url, error=str(e))

    async def page_callback(page: Page):
        await page.wait_for_timeout(4000)

        scroller = PageScroller(
            page=page,
            logger=logger,
            wait_timeout=wait_timeout,
        )

        nonlocal max_scrolls, ignore_js
        ignore_js = False

        while len(candidate_map) < max_candidates and max_scrolls > 0:
            time.sleep(2.5)
            if not (await process_current_state(page)):
                continue

            if len(keywords_list) and perform_matching():
                break

            logger.info("scroll", responses_before=len(response_map))
            if not (await scroller.scroll()):
                break

            logger.info("scroll", responses_after=len(response_map))
            max_scrolls -= 1

    await page_worker.run(
        url=url,
        wait_timeout=wait_timeout,
        on_response=on_response,
        page_callback=page_callback,
        logger=logger,
    )

    output.candidates = sorted(candidate_map.values(), key=lambda c: c.context.relevance_score, reverse=True)
    return output
