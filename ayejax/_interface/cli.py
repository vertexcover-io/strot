import json
from typing import Annotated

from cyclopts import App, Parameter, validators

import ayejax
from ayejax import TagLiteral
from ayejax.helpers import normalize_filename
from ayejax.logging import get_logger, setup_logging
from ayejax.logging.handlers import FileHandlerConfig

setup_logging()

app = App(name="ayejax", help="Discover API endpoints with natural language")


@app.default
async def main(
    *,
    url: Annotated[str, Parameter(name=("-u", "--url"))],
    tag: Annotated[TagLiteral, Parameter(name=("-t", "--tag"))] = "reviews",
):
    """
    Discover API endpoints with natural language

    Args:
        url: URL to find ajax call for
        tag: Tag to use
    """
    filename = normalize_filename(url)
    logger = get_logger(filename, FileHandlerConfig(directory="logs"))

    output, metadata = await ayejax.analyze(url, tag, logger=logger)
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
):
    """
    Serve the API

    Args:
        host: Host to serve on
        port: Port to serve on
    """
    import uvicorn

    uvicorn.run("ayejax._interface.api.main:app", host=host, port=port)
