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
import ayejax
import os

url = "https://www.swiggy.com/instamart/category-listing?categoryName=Fresh+Vegetables&custom_back=true&taxonomyType=Speciality+taxonomy+1"

output = ayejax.find(
    url, "all the listed vegetables", llm_client=llm_client
)
for candidate in output.candidates:
    print("===============================================")
    print(candidate.request.as_curl_command(format="cmd"))
    print("===============================================")
```
