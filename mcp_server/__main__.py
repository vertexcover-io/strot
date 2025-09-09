import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastmcp import Context, FastMCP
from json_schema_to_pydantic import create_model

import strot


@dataclass
class AppContext:
    browser: Any


@asynccontextmanager
async def app_lifespan(server: FastMCP):
    async with strot.launch_browser("headed") as browser:
        try:
            yield AppContext(browser=browser)
        finally:
            pass


app = FastMCP("strot-mcp", lifespan=app_lifespan)


@app.tool()
async def analyze(url: str, query: str, output_schema: dict[str, Any], ctx: Context) -> str:
    """
    Analyze a web page to discover source of the requested data.

    Args:
        url: The target web page URL to analyze
        query: The query defining what kind of data to look for in the webpage
        output_schema: JSON schema to use for structured data extraction from captured api response. This only contains the fields that the user requested from the api response. Format: {\"type\": \"object\", \"properties\": {<user requested fields>}, \"required\": [...]}

    Returns:
        Data containing source request and response details
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
        return json.dumps(source.model_dump(), indent=2)


def run():
    app.run(transport="stdio")


if __name__ == "__main__":
    run()
