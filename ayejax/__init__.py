import re
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from tempfile import gettempdir
from typing import Literal
from urllib.parse import urlparse

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from playwright.sync_api import Response as PWResponse
from pydantic import BaseModel

from . import llm
from .helpers import keyword_match_ratio
from .logging import Logger
from .request import Request, read_har

URL_FILTER_KEYWORDS = {"analytics", "telemetry", "events", "collector", "track", "collect"}
"""URL filtering keywords"""

URL_FILTER_PATTERN = re.compile(rf"^(?!https?:\/\/[^?]*\b(?:{'|'.join(URL_FILTER_KEYWORDS)})\b).+", re.IGNORECASE)
"""URL filtering regex pattern"""

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
    request: Request
    relevance_score: float


class Output(BaseModel):
    candidates: list[Candidate]
    completions: list[llm.LLMCompletion]


def scroll_to_id(page, element_id: str):
    """
    Scrolls to the element with the specified ID using scrollIntoView.
    """
    page.evaluate(
        """
        (id) => {
            const el = document.getElementById(id);
            if (el) el.scrollIntoView({ behavior: 'auto', block: 'end' });
        }
    """,
        element_id,
    )


class _Finder(Logger, cls_name="Finder"):
    def __init__(
        self,
        *,
        llm_client: llm.LLMClientInterface,
        browser: Browser | Literal["headless", "headed"],
        relevance_threshold: float,
    ) -> None:
        super().__init__()
        self.llm_client = llm_client
        self.browser = browser
        self.relevance_threshold = relevance_threshold

        # Store response text directly, not response objects
        self.url_to_response: dict[str, str] = {}

        self.output = Output(candidates=[], completions=[])
        self.keywords_list: list[list[str]] = []

        self.url_to_score: dict[str, float] = {}

    def response_handler(self, response: PWResponse):
        resource_type = response.request.resource_type
        if resource_type not in ("xhr", "fetch"):
            return

        req_url = response.request.url

        if (u := urlparse(req_url)).scheme.lower() not in ("http", "https"):
            return

        url = u.netloc + u.path
        if any(w in url.lower() for w in URL_FILTER_KEYWORDS):
            return

        if req_url not in self.url_to_response:
            self.logger.info(f"Captured response | url={req_url!r}")
            try:
                self.url_to_response[req_url] = response.text()
            except Exception as e:
                self.logger.error(f"Error reading response body: {e}")

    def fetch_keywords(self, prompt: str, page: Page):
        self.logger.info("Taking page screenshot | type='png'")
        llm_input = llm.LLMInput(prompt=prompt, image=page.screenshot(type="png"))
        try:
            self.logger.info("Analysing screenshot for keyword generation")
            completion = self.llm_client.get_completion(llm_input, json=True)
        except Exception as e:
            raise Exception(f"completion error: {e}") from e

        self.output.completions.append(completion)

        self.logger.info(f"Raw completion | value={completion.value!r}")
        try:
            value = Value.model_validate_json(completion.value)
        except Exception as e:
            self.logger.error(f"Error validating LLM response: {e}")
            raise Exception(f"Error validating LLM response: {e}") from e

        if value.error:
            self.logger.error(f"Error from LLM: {value.error}")

        if value.keywords:
            self.logger.info(f"Extracted keywords | keywords={value.keywords!r}")
            self.keywords_list.append(value.keywords)
        else:
            self.logger.info("No keywords extracted")

    def map_relevant_urls(self) -> bool:
        if len(self.keywords_list) == 0:
            self.logger.info("No keywords available for matching")
            return False

        self.logger.info("Finding relevant requests")
        for url, text in self.url_to_response.items():
            for kwds in self.keywords_list:
                score = keyword_match_ratio(kwds, text)
                self.logger.info(f"url={url!r} | score={score:.2f}")
                if score < self.relevance_threshold:
                    continue

                self.url_to_score[url] = score

        return len(self.url_to_score) > 0

    def scroll(self, page: Page):  # noqa: C901
        def _eval(expr: str) -> bool:
            if not page.evaluate("() => window.ayejaxScriptAttached === true"):
                _ = page.add_script_tag(path=Path(__file__).parent / "inject.js")

            self.logger.debug(f"Evaluating expression | expr={expr!r}")
            result = bool(page.evaluate(expr))

            self.logger.debug("Waiting for scroll completion")
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception as e:
                if f"Timeout {5000}ms exceeded" not in str(e):
                    self.logger.error(f"Error waiting for scroll completion: {e}")

            self.logger.debug(f"Evaluation completed | status={result}")
            return result

        elem_scroll_cnt = 0
        while True:
            if elem_scroll_cnt < 5:
                len_before = len(self.url_to_response)
                self.logger.info(f"Scrolling elements in view | responses_before={len_before}")
                if _eval("() => scrollElements(getScrollableElements())"):
                    elem_scroll_cnt += 1
                    self.logger.info(f"Scrolling completed | responses_after={len(self.url_to_response)}")
                    if len(self.url_to_response) > len_before:
                        self.logger.debug("Got new responses")
                        self.map_relevant_urls()
                        break
                    else:
                        self.logger.debug("No new responses, continuing scrolling")
                        continue
            else:
                self.logger.debug("Reset element scroll count")
                elem_scroll_cnt = 0

            len_before = len(self.url_to_response)
            self.logger.info(f"Scrolling the view | responses_before={len_before}")
            if _eval("() => scrollViewport()"):
                self.logger.info(f"Scrolling completed | responses_after={len(self.url_to_response)}")
                if len(self.url_to_response) > len_before:
                    self.logger.info("Got new responses")
                    self.map_relevant_urls()
                    break
                else:
                    self.logger.debug("No new responses, continuing scrolling")
                    continue
            else:
                # Both scrolling methods returned False, exit the loop
                break

    @contextmanager
    def _create_browser_context(self, *, har_file_path: Path | None = None) -> Generator[BrowserContext, None, None]:
        is_browser_provided = isinstance(self.browser, Browser)
        if not is_browser_provided:
            p = sync_playwright().start()
            b = p.chromium.launch(headless=self.browser == "headless")
        else:
            p, b = None, self.browser

        if har_file_path:
            ctx = b.new_context(
                bypass_csp=True,
                record_har_path=har_file_path,
                record_har_mode="full",
                record_har_url_filter=URL_FILTER_PATTERN,
            )
        else:
            ctx = b.new_context(bypass_csp=True)

        yield ctx
        ctx.close(reason="done")
        if not is_browser_provided:
            b.close(reason="done")
            p.stop()

    def __call__(self, *, url: str, query: str, max_scrolls: int, load_state_timeout: float | None):
        prompt = PROMPT_TEMPLATE % query
        datetime_fmt = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        har_file_path = Path(gettempdir()) / f"{datetime_fmt}--ayejax.har"

        with self._create_browser_context(har_file_path=har_file_path) as browser_ctx:
            self.logger.info(f"Creating new page | url={url!r}")
            page = browser_ctx.new_page()

            self.logger.info("Waiting for page to load")
            page.goto(url, timeout=load_state_timeout, wait_until="domcontentloaded")
            time.sleep(2.5)

            page.on("response", self.response_handler)

            self.logger.info("Performing initial scroll")
            self.scroll(page)  # Scroll first to fetch some ajax responses
            max_scrolls -= 1
            self.logger.info(f"Initial scroll complete | response_count={len(self.url_to_response)}")

            while len(self.url_to_score) == 0 and max_scrolls > 0:
                try:
                    self.fetch_keywords(prompt, page)
                except Exception as e:
                    self.logger.error(f"Error fetching keywords: {e}")
                    continue  # Skip to next iteration if keywords fetch fails

                if self.map_relevant_urls():
                    break

                self.scroll(page)
                max_scrolls -= 1

        har_data = read_har(har_file_path)
        har_file_path.unlink()

        self.logger.info(f"Building candidates from HAR record | requests={len(self.url_to_score)}")
        for url, score in self.url_to_score.items():
            for entry in har_data.log.entries:
                if str(entry.request.url) != url:
                    continue

                self.output.candidates.append(
                    Candidate(request=Request(**entry.request.model_dump()), relevance_score=score)
                )
                break

        self.output.candidates.sort(key=lambda c: c.relevance_score, reverse=True)
        return self.output


def find(
    url: str,
    query: str,
    max_scrolls: int = 10,
    *,
    llm_client: llm.LLMClientInterface,
    browser: Browser | Literal["headless", "headed"] = "headed",
    relevance_threshold: float = 0.4,
    load_state_timeout: float | None = None,
):
    finder = _Finder(llm_client=llm_client, browser=browser, relevance_threshold=relevance_threshold)
    return finder(url=url, query=query, max_scrolls=max_scrolls, load_state_timeout=load_state_timeout)
