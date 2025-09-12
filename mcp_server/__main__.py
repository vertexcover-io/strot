import sys
from typing import Annotated, Any

from cyclopts import App, Parameter
from fastmcp import Context
from fastmcp.server.server import Transport
from rich.console import Console

app = App(name="strotmcp", console=Console(), help_flags=[], version_flags=[])


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
        from json_schema_to_pydantic import create_model

        from strot import analyze

        source = await analyze(
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


def configure_and_run_mcp_server(transport: Transport, **kwargs: Any):
    from contextlib import asynccontextmanager
    from dataclasses import dataclass

    from fastmcp import FastMCP

    from strot import launch_browser

    from .exceptions import MissingEnvironmentVariablesError

    try:
        from .settings import settings
    except MissingEnvironmentVariablesError as e:
        from rich.panel import Panel
        from rich.text import Text

        title = Text("Missing Environment Variables", style="bold red")
        content = "\n".join([f"• {key}" for key in e.missing_keys])

        app.console.print(Panel(content, title=title, border_style="red", padding=(1, 2)))
        sys.exit(1)

    @dataclass
    class AppContext:
        browser: Any

    @asynccontextmanager
    async def app_lifespan(server: FastMCP):
        async with launch_browser(
            settings.BROWSER_MODE_OR_WS_URL,
        ) as browser:
            yield AppContext(browser=browser)

    mcp = FastMCP("strotmcp", lifespan=app_lifespan)
    mcp.tool(analyze_and_find_source)

    try:
        mcp.run(transport=transport, **kwargs)
    except Exception:
        app.console.print_exception()
        sys.exit(1)


@app.default
def show_help():
    app.help_print()


@app.command(name="stdio", help_flags=("-h", "--help"))
def run_stdio_server():
    """
    Start a stdio server.
    """
    configure_and_run_mcp_server("stdio")


@app.command(name="http", help_flags=("-h", "--help"))
def run_http_server(
    *,
    host: Annotated[str, Parameter(name=("-h", "--host"))] = "127.0.0.1",
    port: Annotated[int, Parameter(name=("-p", "--port"))] = 8000,
):
    """
    Start an http server.

    Args:
        host: The host to bind the server to.
        port: The port to bind the server to.
    """
    configure_and_run_mcp_server("http", host=host, port=port)


@app.command(name="sse", help_flags=("-h", "--help"))
def run_sse_server(
    *,
    host: Annotated[str, Parameter(name=("-h", "--host"))] = "127.0.0.1",
    port: Annotated[int, Parameter(name=("-p", "--port"))] = 8000,
):
    """
    Start an sse server.

    Args:
        host: The host to bind the server to.
        port: The port to bind the server to.
    """
    configure_and_run_mcp_server("sse", host=host, port=port)


@app.command(name="streamable-http", help_flags=("-h", "--help"))
def run_streamable_http_server(
    *,
    host: Annotated[str, Parameter(name=("-h", "--host"))] = "127.0.0.1",
    port: Annotated[int, Parameter(name=("-p", "--port"))] = 8000,
):
    """
    Start a streamable http server.

    Args:
        host: The host to bind the server to.
        port: The port to bind the server to.
    """
    configure_and_run_mcp_server("streamable-http", host=host, port=port)


if __name__ == "__main__":
    app()
