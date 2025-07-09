import json
from typing import Annotated

from cyclopts import App, Parameter

import ayejax
from ayejax.helpers import normalize_filename
from ayejax.logging import FileHandlerConfig, get_logger, setup_logging

setup_logging()

app = App(name="ayejax", help="Get ajax call using natural language query")

QUERY = (
    "All the user reviews for the product. "
    "Ignore the summary of the reviews. "
    "The reviews are typically available as a list of reviews towards the bottom of the page"
)


@app.default
async def main(
    *,
    url: Annotated[str, Parameter(name=("-u", "--url"))],
    query: Annotated[str, Parameter(name=("-q", "--query"), show_default=False)] = QUERY,
):
    """
    Find ajax call using natural language query

    Args:
        url: URL to find ajax call for
        query: Natural language query
    """
    filename = normalize_filename(url)
    logger = get_logger(filename, file_handler_config=FileHandlerConfig(directory="."))

    output, metadata = await ayejax.find(url, query, logger=logger)
    if output is None:
        raise ValueError("No relevant request found")

    with open(f"{filename}.json", "w") as f:
        json.dump(output.model_dump(), f)

    logger.info("calculate-total-cost", cost_in_usd=sum(c.calculate_cost(3.0, 15.0) for c in metadata.completions))


if __name__ == "__main__":
    app()
