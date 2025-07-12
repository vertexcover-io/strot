import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import ayejax
from ayejax.codegen import generate_python_code
from ayejax.logging import FileHandlerConfig, get_logger, setup_logging

setup_logging()

ROOT_DIR = Path(__file__).parent
RESULTS_FILE = ROOT_DIR / "results.jsonl"


async def main():
    total_eval_cost = 0
    file_handler_config = FileHandlerConfig(
        directory=ROOT_DIR / "logs" / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    )
    for url in (ROOT_DIR / "urls").read_text().split("\n"):
        parsed_url = urlparse(url)
        logger_name = f"{parsed_url.netloc.replace('.', '_')}__{parsed_url.path.replace('/', '_')}"

        logger = get_logger(logger_name, file_handler_config=file_handler_config)

        try:
            output, metadata = await ayejax.analyze(url, "reviews", logger=logger)
            if output is None:
                logger.error("find", error="No relevant request found")
                continue
        except Exception as e:
            logger.error("find", error=str(e))
            continue

        with RESULTS_FILE.open("a") as f:
            f.write(
                json.dumps({
                    "site": url,
                    "extracted_keywords": metadata.extracted_keywords,
                    "most_relevant_call": output.request.url,
                    "is_call_correct": "",
                    "python_code": generate_python_code(output),
                })
                + "\n"
            )

        cost = sum(c.calculate_cost(3.0, 15.0) for c in metadata.completions)
        total_eval_cost += cost
        logger.info("calculate-total-cost", cost_in_usd=cost)

        time.sleep(10)  # add some sleep time

    print("Total Evaluation cost (USD):", total_eval_cost)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
