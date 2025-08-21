# Strot Package Architecture

## Overview

The `strot` package is a web scraping and analysis tool that uses browser automation and LLM intelligence to extract structured data from web pages with automatic pagination detection.

## Core Components

### 1. Browser Management (`browser.py`)

- **ResilientBrowser**: Auto-reconnecting browser wrapper with retry logic
- Supports headed, headless, and WebSocket connection modes
- Handles connection failures gracefully with exponential backoff
- Built on top of `patchright` (Playwright fork)

### 2. LLM Integration (`llm.py`)

- **LLMClient**: Multi-provider LLM client (Anthropic, OpenAI, Groq, OpenRouter)
- **LLMInput/LLMCompletion**: Type-safe request/response models
- Cost tracking per request with token counting
- Support for text + image inputs (multimodal)

### 3. Analysis Engine (`analyzer/__init__.py`)

- **analyze()**: Main entry point for web page analysis
- **\_AnalyzerContext**: Core analysis orchestrator that:
  - Captures network responses (AJAX/XHR and SSR)
  - Uses LLM vision to navigate pages and find content
  - Detects pagination patterns automatically
  - Generates Python extraction code for structured data

### 4. Schema System (`analyzer/schema/`)

- **Request**: HTTP request metadata (method, URL, headers, post data)
- **Response**: HTTP response with preprocessing capabilities
- **PaginationStrategy**: Detected pagination patterns (page, offset, cursor)
- **Source**: Final output with extraction code and pagination info

### 5. Plugin System (`analyzer/_meta/plugin/`)

- Browser interaction plugin with JavaScript injection
- DOM manipulation and element interaction
- Scroll management and overlay handling

### 6. Type Adapter (`type_adapter/`)

- Pydantic schema generation utilities
- JSON schema conversion for LLM prompts

### 7. Logging System (`logging/`)

- Structured logging with file and S3 handlers
- Analysis step tracking and debugging

## Key Features

### Automated Web Analysis

1. **Page Navigation**: Uses LLM vision to understand page layout
2. **Content Detection**: Identifies relevant data sections
3. **Interaction Handling**: Clicks load-more buttons, closes popups
4. **Response Capture**: Monitors network traffic for API calls

### Pagination Detection

1. **Parameter Identification**: Detects page/offset/cursor parameters
2. **Strategy Classification**: Determines pagination type automatically
3. **Pattern Extraction**: Analyzes response data for cursor patterns
4. **Code Generation**: Creates extraction functions with pagination support

### Multi-Modal LLM Usage

1. **Vision Analysis**: Screenshot analysis for UI understanding
2. **Code Generation**: Python extraction code creation
3. **Data Validation**: Schema-based output validation
4. **Cost Optimization**: Token usage tracking across providers

## Dependencies

- `patchright`: Browser automation (Playwright fork)
- `anthropic`/`openai`: LLM providers
- `pydantic`: Data validation and schema generation
- `jinja2`: Template rendering for prompts
- Standard library: `asyncio`, `contextlib`, `json`, `urllib`

## Usage Pattern

```python
from strot import analyze
from pydantic import BaseModel

class ProductSchema(BaseModel):
    name: str
    price: float

source = await analyze(
    url="https://example.com/products",
    query="Extract product listings",
    output_schema=ProductSchema,
    max_steps=30
)
```

## Architecture Strengths

- **Resilient**: Auto-reconnecting browser, LLM retry logic
- **Intelligent**: LLM-driven navigation and content detection
- **Automated**: No manual pagination configuration needed
- **Type-Safe**: Pydantic schemas throughout the pipeline
- **Observable**: Comprehensive structured logging
