from pathlib import Path
from typing import Literal

from playwright.sync_api import Browser, Page
from playwright.sync_api import Response as PWResponse
from pydantic import BaseModel

from ... import har, llm
from ...har.builder import HarBuilder
from ...helpers import keyword_match_ratio
from ...logging import LoggerType

__all__ = ("find_using_natural_language",)


EXCLUDE_KEYWORDS = {"analytics", "telemetry", "events", "collector", "track", "collect"}
"""URL filtering keywords"""

PROMPT_TEMPLATE = """\
Your task is to extract relevant keywords from the provided screenshot of the webpage based on the given user requirements.
The keywords must strictly adhere to user requirements and must be an exact match to those available in the screenshot.

If no relevant keywords can be extracted, set "keywords" to an empty list and provide an appropriate message in "error".

Provide your response in valid JSON matching this schema:

{
  "keywords":  ["<keyword1>", "<keyword2>", ...],
  "error":     "<error message or empty string>"
}

User Requirements: %s"""


class Value(BaseModel):
    keywords: list[str]
    error: str


class Candidate(BaseModel):
    request: har.Request
    relevance_score: float


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
            self.logger.debug("page", action="eval", expr=expr, status="pending")
            result = bool(self.page.evaluate(expr))

            self.logger.debug("page", action="wait", timeout=self.wait_timeout)
            self.page.wait_for_load_state("networkidle", timeout=self.wait_timeout)

            self.logger.debug("page", action="eval", expr=expr, status="completed", result=result)
        except Exception as e:
            if f"Timeout {self.wait_timeout}ms exceeded" not in str(e):
                self.logger.error("page", action="wait", error=str(e))
            else:
                self.logger.debug("page", action="eval", expr=expr, status="failed")
            return False

        return result

    def scroll_elements_in_view(self) -> bool:
        return self._eval("() => scrollElements(getScrollableElements())")

    def scroll_to_next_view(self) -> bool:
        return self._eval("() => scrollViewport()")


def find_using_natural_language(  # noqa: C901
    url: str,
    query: str,
    *,
    max_scrolls: int = 15,
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

    def perform_matching() -> bool:
        if len(keywords_list) == 0:
            return False

        for url, text in url_to_response.items():
            for kwds in keywords_list:
                score = keyword_match_ratio(kwds, text)
                logger.info("matching", url=url, score=score)
                if score < relevance_threshold:
                    continue

                url_to_score[url] = score

        return len(url_to_score) > 0

    def perform_scrolling(scroller: PageScroller) -> bool:
        elem_scroll_cnt = 0
        while True:
            if elem_scroll_cnt < 5:
                len_before = len(url_to_response)
                logger.info("scroll", responses_before=len_before)
                if scroller.scroll_elements_in_view():
                    elem_scroll_cnt += 1
                    logger.info("scroll", responses_after=len(url_to_response))
                    if len(url_to_response) > len_before:
                        perform_matching()
                        break
                    else:
                        continue
            else:
                elem_scroll_cnt = 0

            len_before = len(url_to_response)
            logger.info("scroll", responses_before=len_before)
            if scroller.scroll_to_next_view():
                logger.info("scroll", responses_after=len(url_to_response))
                if len(url_to_response) > len_before:
                    perform_matching()
                    break
                else:
                    continue
            else:
                break

    def perform_keywords_extraction(page: Page):
        logger.info("extract-keywords", action="screenshot", type="png")
        llm_input = llm.LLMInput(prompt=prompt, image=page.screenshot(type="png"))
        try:
            logger.info("extract-keywords", action="llm-completion", status="pending")
            completion = llm_client.get_completion(llm_input, json=True)
        except Exception as e:
            raise Exception(f"completion error: {e}") from e

        logger.info("extract-keywords", action="llm-completion", status="completed", result=completion.value)
        try:
            value = Value.model_validate_json(completion.value)
        except Exception as e:
            raise Exception(f"Error validating LLM response: {e}") from e

        if value.error:
            logger.error("extract-keywords", status="failed", error=value.error)

        if value.keywords:
            logger.info("extract-keywords", status="success", keywords=value.keywords)
            keywords_list.append(value.keywords)

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

        while len(url_to_score) == 0 and max_scrolls > 0:
            perform_scrolling(scroller)
            max_scrolls -= 1
            try:
                perform_keywords_extraction(page)
            except Exception as e:
                logger.error("page", action="keywords-extraction", error=str(e))
                continue  # Skip to next iteration if keywords fetch fails

            if perform_matching():
                break

    har_data = har_buidler.run(
        url=url,
        wait_timeout=wait_timeout,
        on_response=on_response,
        page_callback=page_callback,
        logger=logger,
    )

    candidates: list[Candidate] = []
    for url, score in url_to_score.items():
        for entry in har_data.log.entries:
            if entry.request.url != url:
                continue

            candidates.append(Candidate(request=har.Request(**entry.request.model_dump()), relevance_score=score))
            break

    candidates.sort(key=lambda c: c.relevance_score, reverse=True)
    return candidates
