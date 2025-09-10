from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Any

from cyclopts import App, Parameter
from fastmcp import Context, FastMCP
from fastmcp.server.server import Transport
from json_schema_to_pydantic import create_model

import strot

from .settings import settings


@dataclass
class AppContext:
    browser: Any


@asynccontextmanager
async def app_lifespan(server: FastMCP):
    async with strot.launch_browser(
        settings.BROWSER_MODE_OR_WS_URL,
    ) as browser:
        try:
            yield AppContext(browser=browser)
        finally:
            pass


mcp = FastMCP("strotmcp", lifespan=app_lifespan)

app = App(name="strotmcp", version_flags=[])


@mcp.tool()
async def analyze_and_find_source(ctx: Context, url: str, query: str, output_schema: dict[str, Any]) -> str:
    """
    Analyze a web page to discover source of the expected data.
    Do not mention anything regarding finding the source in the query or output schema.

    Args:
        url: The target web page URL to analyze
        query: The query should be a description of the DATA we are looking for in the webpage
        output_schema: JSON schema to use for structured data extraction from responses. \
            The schema should be for a single DATA entity as analyzer treats the given schema as list of DATA entities. \
            Format should be: {\"type\": \"object\", \"properties\": {<user requested fields>}, \"required\": [...]}

    Returns:
        Source object containing all the information from replaying/making paginated requests to code for extracting structured data from the responses.
    """
    try:
        source = await strot.analyze(
            url=url,
            query=query,
            output_schema=create_model(output_schema),
            browser=ctx.request_context.lifespan_context.browser,
        )

        if source is None:
            await ctx.warning("Analysis completed but no relevant data found")
            return "Analysis failed: No relevant data found"

        await ctx.info("Analysis completed successfully")
    except Exception as e:
        await ctx.error(f"Error during analysis: {e!s}")
        raise Exception(f"Error during analysis: {e!s}") from e
    else:
        return source.model_dump_json(indent=2, exclude_none=True)


@app.default
def run(*, transport: Annotated[Transport, Parameter(name=("-t", "--transport"))] = "stdio"):
    mcp.run(transport=transport)


if __name__ == "__main__":
    app()
