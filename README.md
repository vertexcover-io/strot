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
│    --query  -q  Natural language query                         │
╰────────────────────────────────────────────────────────────────╯
```

> If you don't provide a query, it will use the default review query

```bash
export ANTHROPIC_API_KEY=<YOUR_API_KEY>
ayejax --url "https://global.solawave.co/products/red-light-therapy-eye-mask?variant=43898414170288"
ayejax --url "https://www.getcleanpeople.com/product/fresh-clean-laundry-detergent/"
ayejax --url "https://antica-barberia.us/products/silver-brushed-aluminum-shaving-lather-brush-with-pure-bleached-bristle"
ayejax --url "https://farmersjuice.com/products/variety-juice-box"
```

### Library

Create a logger instance

```python
from ayejax.logging import setup_logging, get_logger

setup_logging()
logger = get_logger("ayejax")
```

Call the `find` function with the URL, query and logger

```python
import ayejax

output = await ayejax.find(
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
