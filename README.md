<p align="center">
  <strong>Reverse-engineer any website's internal API with natural language</strong>
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10+-brightgreen.svg" alt="Python"></a>
</p>

---

## The Problem

Modern websites load data through hidden AJAX calls:

- Data isn't in the HTML - it's fetched via internal APIs
- You have to manually inspect network requests
- Complex pagination logic buried in JavaScript
- APIs change endpoints and parameters frequently

## The Solution

Strot analyzes websites and discovers their internal API calls for you.

**What Strot actually does:**

1. **Analyzes the webpage** to understand what data you want
2. **Captures the AJAX request** that fetches that data
3. **Detects all parameters** - pagination (limit/offset, cursors, page numbers) AND dynamic parameters (sorting, filtering, search)
4. **Generates extraction code** to parse the JSON response
5. **Returns a Source** that replicates the website's own API calls with full parameter control

## 🐳 Try It Now - No Setup Required!

Get the full Strot experience (Web UI + API) instantly:

Using [Patchright](https://github.com/synacktra/patchright-headless-server) browser

```bash
docker run -d --name browser-server -p 5678:5678 synacktra/patchright-headless-server
STROT_ANTHROPIC_API_KEY=sk-ant-apiXXXXXX \
  docker compose -f https://raw.githubusercontent.com/vertexcover-io/strot/refs/heads/main/docker-compose.yml up
```

Or, using [Steel](https://steel.dev/) browser

```bash
STROT_BROWSER_WS_URL=wss://connect.steel.dev?apiKey=ste-XXXXXX STROT_ANTHROPIC_API_KEY=sk-ant-apiXXXXXX \
  docker compose -f https://raw.githubusercontent.com/vertexcover-io/strot/refs/heads/main/docker-compose.yml up
```

Then visit:

- 🌐 **Web Dashboard**: http://localhost:3000 - Visual interface for analyzing websites
- 🔌 **REST API**: http://localhost:1337 - Programmatic access

## 🐍 Python Library

### Installation

```bash
pip install strot
```

Or using `uv`:

```bash
uv pip install strot
```

### Example 1: Reverse-Engineer Review API

```python
import strot
import asyncio
from pydantic import BaseModel

class Review(BaseModel):
    title: str | None = None
    username: str | None = None
    rating: float | None = None
    comment: str | None = None
    date: str | None = None

async def get_reviews():
    # Strot discovers the internal API that loads reviews
    source = await strot.analyze(
        url="https://www.getcleanpeople.com/product/fresh-clean-laundry-detergent/",
        query="Customer reviews with ratings and comments",
        output_schema=Review
    )

    # Use the same API call the website uses, with full parameter control
    async for reviews in source.generate_data(limit=500, offset=100, sortBy="date desc"):
        for review in reviews:
            print(f"{review['rating']}⭐ by {review['username']}: {review['comment']}")

if __name__ == "__main__":
    asyncio.run(get_reviews())
```

### Example 2: Capture Product Listing API

```python
import strot
import asyncio
from pydantic import BaseModel

class Product(BaseModel):
    name: str | None = None
    price: float | None = None
    rating: float | None = None
    availability: str | None = None
    description: str | None = None

async def get_products():
    # Strot finds the AJAX endpoint that loads product listings
    source = await strot.analyze(
        url="https://blinkit.com/cn/fresh-vegetables/cid/1487/1489",
        query="Listed products with names and prices.",
        output_schema=Product
    )

    # Access all products with custom filtering and sorting
    async for products in source.generate_data(limit=100, offset=0, category="vegetables", sortBy="price"):
        for product in products:
            print(f"{product['name']}: ${product['price']} ({product['rating']}⭐)")

if __name__ == "__main__":
    asyncio.run(get_products())
```

## 🔌 MCP Server

Strot provides an MCP (Model Context Protocol) server that enables MCP clients like Claude to analyze websites and discover their internal APIs directly.

### Setup

```bash
git clone https://github.com/vertexcover-io/strot.git
cd strot && uv sync --group mcp
```

Set environment variables:

```bash
export STROT_ANTHROPIC_API_KEY=sk-ant-apiXXXXXX
export STROT_BROWSER_MODE_OR_WS_URL=headless  # or 'headed' or ws://browser-url
```

If you want to use a hosted browser, you could do the following:

Run a headless server inside docker

```bash
docker run -d --name browser-server -p 5678:5678 synacktra/patchright-headless-server
export STROT_BROWSER_MODE_OR_WS_URL=ws://localhost:5678/patchright
```

Or, connect to a remote browser server:

```bash
export STROT_BROWSER_MODE_OR_WS_URL=wss://...
```

### Usage

```
$ uv run strotmcp --help
Usage: strotmcp [OPTIONS]

╭─ Commands ──────────────────────────────────────────────────────────────────────╮
│ --help -h  Display this message and exit.                                       │
╰─────────────────────────────────────────────────────────────────────────────────╯
╭─ Parameters ────────────────────────────────────────────────────────────────────╮
│ --transport  -t  [choices: stdio, http, sse, streamable-http] [default: stdio]  │
╰─────────────────────────────────────────────────────────────────────────────────╯
```

#### With Claude Code

- `stdio` transport

  ```bash
  claude mcp add strot-mcp "uv run strotmcp" --transport stdio \
    --env STROT_ANTHROPIC_API_KEY=$STROT_ANTHROPIC_API_KEY STROT_BROWSER_MODE_OR_WS_URL=$STROT_BROWSER_MODE_OR_WS_URL
  ```

- `sse`, `http`, `streamable-http` transports

  Run the MCP server with the desired transport in separate terminal:

  ```bash
  uv run strotmcp -t sse
  ```

  Add the MCP server to Claude:

  ```bash
  claude mcp add strot-mcp http://127.0.0.1:8000/sse --transport sse
  ```

## 🧪 Evaluation

Test and validate Strot's analysis accuracy across different websites and individual components. The evaluation system supports five input types:

- **existing jobs** (evaluate completed jobs by ID),
- **new jobs** (create and evaluate full analysis tasks),
- **request detection** (test URL and query combinations),
- **parameter detection** (test individual request parameter analysis - both pagination and dynamic parameters),
- **structured extraction** (test response parsing with specific schemas).

It compares actual results against expected outcomes, tracking metrics like source URL matching, pagination key detection, dynamic parameter detection, and entity count accuracy. All evaluations and their detailed analysis steps are stored in Airtable.

### Setup

```bash
git clone https://github.com/vertexcover-io/strot.git
cd strot && uv sync --group eval
```

#### Setup Airtable

1. **Create a new Airtable base:**

   - Go to [Workspaces](https://airtable.com/workspaces)
   - Click on `Create` button on your desired workspace
   - Select `Build an app on your own`
   - Copy the Base ID from the URL (e.g. `appXXXXXXXXXXXXXX`)

2. **Create a Personal Access Token:**

   - Go to [`/create/tokens`](https://airtable.com/create/tokens)
   - Add the following scopes:
     - `data.records:read`
     - `data.records:write`
     - `schema.bases:read`
     - `schema.bases:write`
   - Give access to the base you created in step 1
   - Press `Create token` and copy the token (e.g. `patXXXXXXXXXXXXXX`)

3. **Set environment variables:**

   ```bash
   export STROT_AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX
   export STROT_AIRTABLE_TOKEN=patXXXXXXXXXXXXXX

   # set the following if you wish to evaluate separate tasks
   export STROT_ANTHROPIC_API_KEY=sk-ant-apiXXXXXX
   ```

> **Note**: Required tables are automatically created with proper schema when you run evaluations.

### Usage

```
$ uv run stroteval
Usage: stroteval [OPTIONS]

Evaluate multiple job-based or task-based inputs from a file or stdin.

╭─ Parameters ──────────────────────────────────────────────────────────────────╮
│ --file  -f  Path to the JSON/JSONL file. If not provided, reads from stdin.   │
╰───────────────────────────────────────────────────────────────────────────────╯
```

> Make sure the API server is running If you're evaluating job-based inputs.

```bash
echo '[
  {
    "job_id": "existing-job-uuid",
    "expected_source": "https://api.example.com/reviews",
    "expected_pagination_keys": ["cursor", "limit"],
    "expected_dynamic_keys": ["sortBy", "category"],
    "expected_entity_count": 243
  },
  {
    "site_url": "https://example.com/category/abc",
    "query": "Listed products with name and prices",
    "expected_source": "https://api.example.com/products",
    "expected_pagination_keys": ["limit", "offset"],
    "expected_dynamic_keys": ["category", "sortBy"],
    "expected_entity_count": 100
  },
  {
    "request": {
      "method": "GET",
      "url": "https://example.com/api/products",
      "type": "ajax",
      "queries": {"page": "2", "limit": "50", "sortBy": "price", "category": "electronics"}
    },
    "expected_pagination_keys": ["page", "limit"],
    "expected_dynamic_keys": ["sortBy", "category"]
  },
  {
    "response": {
      "value": "",
      "request": {
        "method": "GET",
        "url": "https://example.com/api/reviews",
        "type": "ajax"
      },
      "preprocessor": {"element_selector": ".reviews-container"}
    },
    "output_schema_file": "review_schema.json",
    "expected_entity_count": 10
  }
]' | uv run stroteval
```

## 🆘 Need Help?

- 💬 [GitHub Discussions](https://github.com/vertexcover-io/strot/discussions) - Ask questions
- 🐛 [Report Issues](https://github.com/vertexcover-io/strot/issues) - Found a bug?

## 📄 License

MIT License - Use it however you want!

---

<p align="center">
  Made with ❤️ by <a href="https://vertexcover.io">Vertexcover Labs</a>
</p>
