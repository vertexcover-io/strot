from typing import Literal

from playwright.sync_api import Browser, Page
from playwright.sync_api import Response as PWResponse
from pydantic import BaseModel

from .. import har
from ..har.builder import HarBuilder
from ..logging import LoggerType

__all__ = ("find_shopify_reviews",)

INCLUDE_KEYWORDS = {"bazaarvoice.com/data/reviews.json"}


class Candidate(BaseModel):
    request: har.Request
    relevance_score: float


def find_shopify_reviews(
    url: str,
    *,
    wait_timeout: float | None = None,
    browser: Browser | Literal["headless", "headed"] = "headed",
    logger: LoggerType,
):
    candidate_urls = []

    har_buidler = HarBuilder(browser=browser, filter_keywords=INCLUDE_KEYWORDS, filter_mode="include")

    def on_response(response: PWResponse):
        try:
            logger.info("on-response", action="capture", url=url)
            candidate_urls.append(response.request.url)
        except Exception as e:
            logger.error("on-response", action="capture", url=url, error=str(e))

    def page_callback(page: Page):
        try:
            logger.info("page", action="reload", url=url)
            page.reload(timeout=wait_timeout or 10000, wait_until="networkidle")
        except Exception as e:
            logger.error("page", action="reload", url=url, error=str(e))

    har_data = har_buidler.run(
        url=url,
        wait_timeout=wait_timeout,
        on_response=on_response,
        page_callback=page_callback,
        logger=logger,
    )

    candidates: list[Candidate] = []
    for url in candidate_urls:
        for entry in har_data.log.entries:
            if entry.request.url != url:
                continue

            candidates.append(Candidate(request=har.Request(**entry.request.model_dump()), relevance_score=1))
            break

    candidates.sort(key=lambda c: c.relevance_score, reverse=True)
    return candidates
