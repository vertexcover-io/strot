from typing import Annotated

from cyclopts import App, Parameter

import ayejax
from ayejax.codegen import BashCurlCode, PythonRequestsCode
from ayejax.llm import LLMClient, LLMProvider

app = App(name="ayejax", help="Get ajax call using natural language query")


@app.command(name="llm")
def configure_llm_client(
    *,
    provider: Annotated[LLMProvider, Parameter(name=("-p", "--provider"))],
    model: Annotated[str, Parameter(name=("-m", "--model"))],
):
    """
    Configure LLM client

    Args:
        provider: LLM provider
        model: LLM model
    """
    return LLMClient(provider=provider, model=model)


@app.meta.default
def main(
    *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
    url: Annotated[str, Parameter(name=("-u", "--url"))],
    query: Annotated[str, Parameter(name=("-q", "--query"))],
):
    """
    Find ajax call using natural language query

    Args:
        url: URL to find ajax call for
        query: Natural language query
    """
    llm_client = app(tokens=tokens) if tokens else LLMClient(provider="openai", model="gpt-4o")

    output = ayejax.find(url, query, llm_client=llm_client)
    if not output.candidates:
        raise ValueError("No candidates found")

    request = output.candidates[0].request

    bash_code = BashCurlCode.from_request(request)
    with open("new.sh", "w") as f:
        f.write(bash_code.render(caller_type="loop"))

    python_code = PythonRequestsCode.from_request(request)
    with open("new.py", "w") as f:
        f.write(python_code.render(caller_type="loop"))


if __name__ == "__main__":
    app.meta()
