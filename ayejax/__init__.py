from pathlib import Path
from typing import Literal

from playwright.sync_api import Browser, Page
from playwright.sync_api import Response as PWResponse
from pydantic import BaseModel

from . import har, llm
from .har.builder import HarBuilder
from .helpers import keyword_match_ratio
from .logging import LoggerType

__all__ = ("find",)


EXCLUDE_KEYWORDS = {"analytics", "telemetry", "events", "collector", "track", "collect"}
"""URL filtering keywords"""

PROMPT_TEMPLATE = """\
Your task is to extract relevant keywords from the provided screenshot of the webpage based on the given user requirements.
The keywords must strictly adhere to user requirements and must be an exact match to those available in the screenshot.

If no relevant keywords can be extracted:
- set "keywords" to an empty list
- provide an appropriate message in "error".
- if the screenshot shows a pagination control (e.g., page numbers, “Next” or “>” arrow, dots indicating multiple pages), set "pagination_element_point" to the coordinates of the pagination control; otherwise set it to null
- if the screenshot shows a popup, identify the coordinates of the close button and set "popup_close_button_point" to those coordinates; otherwise set it to null

Provide your response in valid JSON matching this schema:

{
  "keywords":  ["<keyword1>", "<keyword2>", ...],
  "error":     "<error message or empty string>",
  "pagination_element_point": {"x": <x>, "y": <y>} or null,
  "popup_close_button_point": {"x": <x>, "y": <y>} or null
}

User Requirements: %s"""


class Value(BaseModel):
    keywords: list[str] = []
    error: str = ""
    pagination_element_point: dict[str, int] | None = None
    popup_close_button_point: dict[str, int] | None = None


class Candidate(BaseModel):
    request: har.Request
    relevance_score: float


class Output(BaseModel):
    candidates: list[Candidate]
    completions: list[llm.LLMCompletion]


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

    def _eval(self, expr: str) -> bool:
        if not self.page.evaluate("() => window.ayejaxScriptAttached === true"):
            _ = self.page.add_script_tag(path=Path(__file__).parent / "inject.js")

        try:
            self.logger.info("page", action="eval", expr=expr, status="pending")
            result = bool(self.page.evaluate(expr))

            self.logger.info("page", action="wait", timeout=self.wait_timeout)
            self.page.wait_for_load_state("domcontentloaded", timeout=self.wait_timeout)

            self.logger.info("page", action="eval", expr=expr, status="completed", result=result)
        except Exception as e:
            if f"Timeout {self.wait_timeout}ms exceeded" not in str(e):
                self.logger.error("page", action="wait", error=str(e))
                return False
            else:
                self.logger.info("page", action="eval", expr=expr, status="unknown")
                return True

        return result

    def scroll_elements_in_view(self) -> bool:
        return self._eval("() => scrollElements(getScrollableElements())")

    def scroll_to_next_view(self) -> bool:
        return self._eval("() => scrollViewport()")

    def scroll(self) -> bool:
        status = self.scroll_elements_in_view()
        self.logger.info("scroll", type="elements-in-view", status=status)
        if status:
            return True
        status = self.scroll_to_next_view()
        self.logger.info("scroll", type="next-view", status=status)
        return status


def click_at_point(page: Page, x: int, y: int, delay: float | None = None) -> None:
    viewport = page.viewport_size or {"width": 0, "height": 0}
    if not (0 <= x <= viewport["width"] and 0 <= y <= viewport["height"]):
        raise ValueError(f"Point ({x}, {y}) is outside of the current viewport {viewport}. Consider scrolling first.")

    # Move cursor first (helps with some UIs that depend on hover state) then click.
    page.mouse.move(x, y)
    page.mouse.click(x, y)

    delay = delay or 2.0
    page.wait_for_timeout(int(delay * 1000))


def find(  # noqa: C901
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
    url_to_response: dict[str, str] = {}
    keywords_list: list[list[str]] = []
    url_to_score: dict[str, float] = {}

    prompt = PROMPT_TEMPLATE % query
    har_buidler = HarBuilder(browser=browser, filter_keywords=EXCLUDE_KEYWORDS, filter_mode="exclude")
    output = Output(candidates=[], completions=[])

    def perform_matching() -> bool:
        for url, text in url_to_response.items():
            for kwds in keywords_list:
                score = keyword_match_ratio(kwds, text)
                logger.info("matching", url=url, score=score)
                if score < relevance_threshold:
                    continue

                url_to_score[url] = score

        return len(url_to_score) > 0

    def process_current_state(page: Page) -> bool:
        logger.info("process-current-state", action="screenshot", type="png")
        screenshot = page.screenshot(type="png")
        llm_input = llm.LLMInput(prompt=prompt, image=screenshot)
        try:
            completion = llm_client.get_completion(llm_input, json=True)
            logger.info("process-current-state", action="llm-completion", status="completed", result=completion.value)
            output.completions.append(completion)
        except Exception as e:
            logger.error("process-current-state", action="llm-completion", status="failed", error=str(e))
            return False

        try:
            value = Value.model_validate_json(completion.value)
        except Exception as e:
            logger.error("process-current-state", action="llm-completion", status="failed", error=str(e))
            return False

        if value.error:
            logger.error("process-current-state", status="failed", error=value.error)

        if value.keywords:
            logger.info("process-current-state", status="success", keywords=value.keywords)
            keywords_list.append(value.keywords)

        if value.pagination_element_point:
            logger.info(
                "process-current-state", action="click", pagination_element_point=value.pagination_element_point
            )
            click_at_point(page, value.pagination_element_point["x"], value.pagination_element_point["y"])

        if value.popup_close_button_point:
            logger.info(
                "process-current-state", action="click", popup_close_button_point=value.popup_close_button_point
            )
            click_at_point(page, value.popup_close_button_point["x"], value.popup_close_button_point["y"])

        return True

    def on_response(response: PWResponse):
        if (url := response.request.url) in url_to_response:
            return
        try:
            logger.info("on-response", action="capture", url=url)
            url_to_response[url] = response.text()
        except Exception as e:
            logger.error("on-response", action="capture", url=url, error=str(e))

    def page_callback(page: Page):
        nonlocal max_scrolls

        scroller = PageScroller(
            page=page,
            logger=logger,
            wait_timeout=wait_timeout,
        )

        while len(url_to_score) < max_candidates and max_scrolls > 0:
            if not process_current_state(page):
                continue

            if len(keywords_list) and perform_matching():
                break

            logger.info("scroll", responses_before=len(url_to_response))
            if not scroller.scroll():
                break

            logger.info("scroll", responses_after=len(url_to_response))
            max_scrolls -= 1

    har_data = har_buidler.run(
        url=url,
        wait_timeout=wait_timeout,
        on_response=on_response,
        page_callback=page_callback,
        logger=logger,
    )

    for url, score in url_to_score.items():
        for entry in har_data.log.entries:
            if entry.request.url != url:
                continue

            output.candidates.append(
                Candidate(
                    request=har.Request(**entry.request.model_dump()),
                    relevance_score=score,
                )
            )
            break

    output.candidates.sort(key=lambda c: c.relevance_score, reverse=True)
    return output
