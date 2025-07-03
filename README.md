<p align="center">Get ajax call using natural language query</p>

---

## Installation

> Make sure [uv](https://docs.astral.sh/uv/getting-started/installation/) is installed.

```bash
git clone git@github.com:vertexcover-io/ayejax.git
cd ayejax
uv sync
```

## Usage

### CLI

```
$ ayejax --help
Usage: ayejax COMMAND

Get ajax call using natural language query

╭─ Commands ─────────────────────────────────────────────────────╮
│ --help -h  Display this message and exit.                      │
│ --version  Display application version.                        │
╰────────────────────────────────────────────────────────────────╯
╭─ Parameters ───────────────────────────────────────────────────╮
│ *  --url    -u  URL to find ajax call for [required]           │
│ *  --query  -q  Natural language query [required]              │
╰────────────────────────────────────────────────────────────────╯
```

```bash
export ANTHROPIC_API_KEY=<YOUR_API_KEY>
ayejax --url "https://global.solawave.co/products/red-light-therapy-eye-mask?variant=43898414170288" --query "all the user reviews for the product"
```

### Library

Create a logger instance

```python
from ayejax.logging import setup_logging, get_logger

setup_logging()
logger = get_logger("ayejax")
```

Create an LLM client of your choice

> Available providers: `openai`, `anthropic`, `groq` and `open-router`

```python
from ayejax import llm

llm_client = llm.LLMClient(
    provider="anthropic", model="claude-3-7-sonnet-latest", api_key="YOUR_API_KEY", logger=logger
)
```

Call the `find` function with the URL, query and LLM client

```python
import ayejax

output = await ayejax.find(
    "https://global.solawave.co/products/red-light-therapy-eye-mask?variant=43898414170288",
    (
        "All the user reviews for the product. "
        "Ignore the summary of the reviews. "
        "The reviews are typically available as a list of reviews towards the bottom of the page"
    ),
    llm_client=llm_client,
    logger=logger,
)
```

Generate Python code

```python
from ayejax.codegen import PythonCode

request = output.candidates[0].request
python_code = PythonCode.from_request(request, template="httpx") # Available templates: httpx, requests
with open("scrape-solawave-eye-mask-reviews.py", "w") as f:
    f.write(python_code.render(caller_type="loop"))
```
