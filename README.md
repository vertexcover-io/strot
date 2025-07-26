<p align="center">Discover API endpoints with natural language</p>

---

## Installation

```bash
pip install strot
```

## Usage

```python
import strot
from pydantic import BaseModel

class ReviewSchema(BaseModel):
    title: str | None = None
    username: str | None = None
    rating: float | None = None
    comment: str | None = None
    location: str | None = None
    date: str | None = None

async def main():
    source = await strot.analyze(
        url="https://example.com/page-to-analyze",
        query="All the user reviews for the product.",
        output_schema=ReviewSchema,
    )
    async for data in source.generate_data(limit=500, offset=150):
        # Process data
        ...

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Access it through the API & Web UI

Set your Anthropic API key and run with docker-compose:

```bash
export STROT_ANTHROPIC_API_KEY=<YOUR_API_KEY>
docker-compose up
```

This will start:

- API server on http://localhost:1337
- Web UI on http://localhost:3000
