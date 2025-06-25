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
│ llm        Configure LLM client                                │
│ --help -h  Display this message and exit.                      │
│ --version  Display application version.                        │
╰────────────────────────────────────────────────────────────────╯
╭─ Parameters ───────────────────────────────────────────────────╮
│ *  --url    -u  URL to find ajax call for [required]           │
│ *  --query  -q  Natural language query [required]              │
╰────────────────────────────────────────────────────────────────╯
```

```bash
export OPENAI_API_KEY=<YOUR_API_KEY>
ayejax --url "https://www.swiggy.com/instamart/category-listing?categoryName=Fresh+Vegetables&custom_back=true&taxonomyType=Speciality+taxonomy+1" \
       --query "all the listed vegetables" \
       llm --provider "openai" --model "gpt-4o"
```

### Library

Create a logger instance

```python
from ayejax.logging import create_logger

logger = create_logger(
    name="ayejax",
    file_handler_config=FileHandlerConfig(
        directory=".",
    )
)
```

#### Find using natural language

Create an LLM client of your choice

> Available providers: `openai`, `anthropic`, `groq` and `open-router`

```python
from ayejax import llm

llm_client = llm.LLMClient(
    provider="openai", model="gpt-4o", api_key="YOUR_API_KEY", logger=logger
)
```

Call the `find` function with the URL, query and LLM client

```python
import ayejax

output = ayejax.find_using_natural_language(
    "https://www.swiggy.com/instamart/category-listing?categoryName=Fresh+Vegetables&custom_back=true&taxonomyType=Speciality+taxonomy+1",
    "all the listed vegetables",
    llm_client=llm_client,
    logger=logger,
)
```

#### Find Shopify reviews

```python
import ayejax

output = ayejax.find_shopify_reviews(
    "https://www.vitalproteins.com/products/collagen-gummies",
    logger=logger,
)
```

#### Generate code

Python Requests code

```python
from ayejax.codegen import PythonRequestsCode

request = output.candidates[0].request
python_code = PythonRequestsCode.from_request(request)
with open("scrape-swiggy-category.py", "w") as f:
    f.write(python_code.render())
```

Bash Curl script

```python
from ayejax.codegen import BashCurlCode

request = output.candidates[0].request
bash_code = BashCurlCode.from_request(request)
with open("scrape-swiggy-category.sh", "w") as f:
    f.write(bash_code.render())
```
