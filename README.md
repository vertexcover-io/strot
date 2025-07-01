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
ayejax --url "https://www.swiggy.com/instamart/category-listing?categoryName=Fresh+Vegetables&custom_back=true&taxonomyType=Speciality+taxonomy+1" \
       --query "all the listed vegetables"
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
    "https://www.swiggy.com/instamart/category-listing?categoryName=Fresh+Vegetables&custom_back=true&taxonomyType=Speciality+taxonomy+1",
    "all the listed vegetables",
    llm_client=llm_client,
    logger=logger,
)
```

Generate Python Requests code

```python
from ayejax.codegen import PythonRequestsCode

request = output.candidates[0].request
python_code = PythonRequestsCode.from_request(request)
with open("scrape-swiggy-category.py", "w") as f:
    f.write(python_code.render())
```

Generate Bash Curl script

```python
from ayejax.codegen import BashCurlCode

request = output.candidates[0].request
bash_code = BashCurlCode.from_request(request)
with open("scrape-swiggy-category.sh", "w") as f:
    f.write(bash_code.render())
```
