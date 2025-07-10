import json
from typing import Annotated

from cyclopts import App, Parameter, validators

import ayejax
from ayejax.helpers import normalize_filename
from ayejax.logging import FileHandlerConfig, get_logger, setup_logging

setup_logging()

app = App(name="ayejax", help="Get ajax call using natural language query")


@app.default
async def main(
    *,
    url: Annotated[str, Parameter(name=("-u", "--url"))],
    tag: Annotated[ayejax.Tag, Parameter(name=("-t", "--tag"))] = ayejax.Tag.reviews,
):
    """
    Find ajax call using natural language query

    Args:
        url: URL to find ajax call for
        tag: Tag to use
    """
    filename = normalize_filename(url)
    logger = get_logger(filename, file_handler_config=FileHandlerConfig(directory="."))

    output, metadata = await ayejax.find(url, tag, logger=logger)
    if output is None:
        raise ValueError("No relevant request found")

    with open(f"{filename}.json", "w") as f:
        json.dump(output.model_dump(), f)

    logger.info("calculate-total-cost", cost_in_usd=sum(c.calculate_cost(3.0, 15.0) for c in metadata.completions))


@app.command
def serve(
    *,
    host: Annotated[str, Parameter(name=("-h", "--host"))] = "0.0.0.0",  # noqa: S104
    port: Annotated[int, Parameter(name=("-p", "--port"), validator=validators.Number(gt=1024, lt=65535))] = 1337,
    watch: Annotated[bool, Parameter(name=("--watch"), show_default=False)] = False,
):
    """
    Serve the API

    Args:
        host: Host to serve on
        port: Port to serve on
        watch: Watch for changes and reload
    """
    import uvicorn

    uvicorn.run("ayejax._interface.api:app", host=host, port=port, reload=watch)
