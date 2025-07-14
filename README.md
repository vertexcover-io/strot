<p align="center">Discover API endpoints with natural language</p>

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
Usage: ayejax COMMAND [OPTIONS]

Discover API endpoints with natural language

╭─ Commands ───────────────────────────────────────────────────────────╮
│ serve      Serve the API                                             │
│ --help -h  Display this message and exit.                            │
│ --version  Display application version.                              │
╰──────────────────────────────────────────────────────────────────────╯
╭─ Parameters ─────────────────────────────────────────────────────────╮
│ *  --url  -u  URL to find ajax call for [required]                   │
│    --tag  -t  Tag to use [choices: reviews] [default: reviews]       │
╰──────────────────────────────────────────────────────────────────────╯
```

```bash
export ANTHROPIC_API_KEY=<YOUR_API_KEY>
ayejax --url "https://global.solawave.co/products/red-light-therapy-eye-mask?variant=43898414170288"
ayejax --url "https://www.getcleanpeople.com/product/fresh-clean-laundry-detergent/"
ayejax --url "https://antica-barberia.us/products/silver-brushed-aluminum-shaving-lather-brush-with-pure-bleached-bristle"
ayejax --url "https://farmersjuice.com/products/variety-juice-box"
```

### API

```
$ ayejax serve --help
Usage: ayejax serve [OPTIONS]

Serve the API

╭─ Parameters ──────────────────────────────────────╮
│ --host  -h  Host to serve on [default: 0.0.0.0]   │
│ --port  -p  Port to serve on [default: 1337]      │
╰───────────────────────────────────────────────────╯
```

Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY=<YOUR_API_KEY>
```

Start postgres and minio services locally and serve the API

```bash
docker-compose up -d
AYEJAX_ENV=local AYEJAX_API_KEY=<YOUR_API_KEY> ANTHROPIC_API_KEY=<YOUR_API_KEY> uv run ayejax serve
```

Or, Connect to a different postgres and s3-compatible storage services

```bash
AYEJAX_ENV=prod AYEJAX_API_KEY=<YOUR_API_KEY> ANTHROPIC_API_KEY=<YOUR_API_KEY> AYEJAX_POSTGRES_USER=... AYEJAX_POSTGRES_PASSWORD=... AYEJAX_POSTGRES_DB=... AYEJAX_POSTGRES_HOST=... AYEJAX_POSTGRES_PORT=... AYEJAX_AWS_ACCESS_KEY_ID=... AYEJAX_AWS_SECRET_ACCESS_KEY=... AYEJAX_AWS_REGION=... AYEJAX_AWS_S3_LOG_BUCKET=... AYEJAX_AWS_S3_ENDPOINT_URL=... uv run ayejax serve
```

### Library

Create a logger instance

```python
from ayejax.logging import setup_logging, get_logger

setup_logging()
logger = get_logger("ayejax")
```

Call the `analyze` function with the URL, query/tag and logger

```python
import ayejax

output = await ayejax.analyze(
    "https://global.solawave.co/products/red-light-therapy-eye-mask?variant=43898414170288",
    (
        "All the user reviews for the product. "
        "Ignore the summary of the reviews. "
        "The reviews are typically available as a list of reviews towards the bottom of the page"
    ),
    logger=logger,
)
```

Generate Python code

```python
from ayejax.codegen import generate_python_code

with open("scrape-solawave-eye-mask-reviews.py", "w") as f:
    f.write(generate_python_code(output))
```
