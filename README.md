<p align="center">Get ajax call using natural language query</p>

---

## Installation

> Make sure [uv](https://docs.astral.sh/uv/getting-started/installation/) is installed.

```bash
git clone https://github.com/vertexcover-io/ayejax.git
cd ayejax
uv sync
```

## Usage

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
