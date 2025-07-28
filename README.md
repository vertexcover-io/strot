# Strot

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
3. **Figures out pagination** (limit/offset, cursors, page numbers)
4. **Generates extraction code** to parse the JSON response
5. **Returns a Source** that replicates the website's own API calls

## 🐳 Try It Now - No Setup Required!

Get the full Strot experience (Web UI + API) instantly:

```bash
export STROT_ANTHROPIC_API_KEY=your_key
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

    # Use the same API call the website uses, with your own pagination
    async for review in source.generate_data(limit=500, offset=100):
        print(f"{review.rating}⭐ by {review.username}: {review.comment}")

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

    # Paginate through all products using the discovered API
    async for product in source.generate_data(limit=100, offset=0):
        print(f"{product.name}: ${product.price} ({product.rating}⭐)")

if __name__ == "__main__":
    asyncio.run(get_products())
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
