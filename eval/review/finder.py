import json
import time
from base64 import b64encode
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import ayejax
from ayejax.llm import LLMClient
from ayejax.logging import FileHandlerConfig, get_logger, setup_logging

setup_logging()

ROOT_DIR = Path(__file__).parent
RESULTS_FILE = ROOT_DIR / "results.jsonl"

QUERY = (
    "All the user reviews for the product. "
    "Ignore the summary of the reviews. "
    "The reviews are typically available as a list of reviews towards the bottom of the page"
)


async def main():
    total_eval_cost = 0
    file_handler_config = FileHandlerConfig(
        directory=ROOT_DIR / "logs" / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    )
    for url in (ROOT_DIR / "urls").read_text().split("\n"):
        parsed_url = urlparse(url)
        logger_name = f"{parsed_url.netloc.replace('.', '_')}__{parsed_url.path.replace('/', '_')}"

        logger = get_logger(logger_name, file_handler_config=file_handler_config)
        llm_client = LLMClient(provider="anthropic", model="claude-3-7-sonnet-latest", logger=logger)

        try:
            output = await ayejax.find(
                url, QUERY, llm_client=llm_client, logger=logger, max_scrolls=50, max_candidates=7
            )
            if not output.candidates:
                raise ValueError("No candidates found")  # noqa: TRY301
        except Exception as e:
            logger.error("find", error=str(e))
            continue

        candidate = output.candidates[0]
        with RESULTS_FILE.open("a") as f:
            f.write(
                json.dumps({
                    "site": url,
                    "page_screenshot": b64encode(candidate.context.page_screenshot).decode("utf-8"),
                    "extracted_keywords": candidate.context.extracted_keywords,
                    "most_relevant_call": candidate.request.url,
                    "is_call_correct": "",
                })
                + "\n"
            )

        cost = sum(c.calculate_cost(3.0, 15.0) for c in output.completions)
        total_eval_cost += cost
        logger.info("calculate-total-cost", cost_in_usd=cost)

        time.sleep(10)  # add some sleep time

    print("Total Evaluation cost (USD):", total_eval_cost)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
