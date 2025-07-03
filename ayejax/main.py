import re
from typing import Annotated
from urllib.parse import urlparse

from cyclopts import App, Parameter

import ayejax
from ayejax.codegen import PythonCode
from ayejax.llm import LLMClient
from ayejax.logging import FileHandlerConfig, get_logger, setup_logging

setup_logging()

app = App(name="ayejax", help="Get ajax call using natural language query")


def normalize_filename(url: str) -> str:
    """
    Normalize URL to safe filename
    
    Args:
        url: URL to normalize
        
    Returns:
        Safe filename string
    """
    parsed_url = urlparse(url)
    clean_netloc = parsed_url.netloc.replace('.', '_')
    clean_path = parsed_url.path.replace('/', '_')
    
    # Remove special characters, keep only alphanumeric, underscore, hyphen
    clean_netloc = re.sub(r'[^\w\-]', '', clean_netloc)
    clean_path = re.sub(r'[^\w\-]', '', clean_path)
    
    # Remove trailing underscores
    clean_path = clean_path.strip('_')
    
    return f"{clean_netloc}__{clean_path}" if clean_path else clean_netloc


@app.default
async def main(
    url: Annotated[str, Parameter(name=("-u", "--url"))],
    query: Annotated[str, Parameter(name=("-q", "--query"))],
):
    """
    Find ajax call using natural language query

    Args:
        url: URL to find ajax call for
        query: Natural language query
    """
    filename = normalize_filename(url)

    logger = get_logger(filename, file_handler_config=FileHandlerConfig(directory="."))
    llm_client = LLMClient(provider="anthropic", model="claude-3-7-sonnet-latest", logger=logger)

    output = await ayejax.find(url, query, llm_client=llm_client, logger=logger, max_scrolls=40, max_candidates=7)
    if not output.candidates:
        raise ValueError("No candidates found")

    request = output.candidates[0].request

    python_code = PythonCode.from_request(request, template="httpx")
    with open(f"{filename}.py", "w") as f:
        f.write(python_code.render(caller_type="loop"))

    logger.info("calculate-total-cost", cost_in_usd=sum(c.calculate_cost(3.0, 15.0) for c in output.completions))


if __name__ == "__main__":
    app()
