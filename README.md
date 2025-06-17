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

Create an LLM client of your choice

> Available providers: `openai`, `anthropic`, `groq` and `open-router`

```python
from ayejax import llm

llm_client = llm.LLMClient(
    provider="openai", model="gpt-4o", api_key="YOUR_API_KEY"
)
```

Call the `find` function with the URL, query and LLM client

```python
import os

import ayejax
from ayejax.codegen import BashCurlCode

output = ayejax.find(
    "https://www.swiggy.com/instamart/category-listing?categoryName=Fresh+Vegetables&custom_back=true&taxonomyType=Speciality+taxonomy+1",
    "all the listed vegetables",
    llm_client=ayejax.llm.LLMClient(
        provider="openai", model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY")
    ),
)
if output.candidates:
    request = output.candidates[0].request
    bash_code = BashCurlCode.from_request(request)
    with open("scrape-swiggy-category.sh", "w") as f:
        f.write(bash_code.render())
```

https://github.com/user-attachments/assets/790f57fc-a9a7-4991-b2fb-489bf47d8509
