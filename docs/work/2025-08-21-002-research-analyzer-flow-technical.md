# Strot Analyzer Flow - Technical Deep Dive

## Overview

The analyzer flow (`strot/analyzer/__init__.py`) implements an intelligent web analysis system that uses LLM vision to navigate web pages and discover extraction metadata. The analysis process identifies and returns a `Source` object containing:

- **Request metadata** (HTTP method, URL, headers, parameters)
- **Pagination strategy** (detected pagination patterns and parameters)
- **Response preprocessor** (content filtering and preprocessing rules)
- **Extraction code** (Python function for parsing response data)

This metadata is used later for structured data extraction operations.

## Analysis Flow Architecture

### 1. Entry Point: `analyze()` Function

```python
async def analyze(
    url: str,
    query: str,
    output_schema: type[BaseModel],
    max_steps: int = 30
) -> Source | None
```

**Flow:**

1. Creates browser context with CSP bypass
2. Initializes `_AnalyzerContext` with page and logger
3. Loads target URL with 5-second stabilization wait
4. Executes analysis loop via `run_ctx(query, output_schema, max_steps)`
5. Returns `Source` object with extraction code and pagination strategy

### 2. Core Analysis Engine: `_AnalyzerContext`

#### Initialization

- **LLM Client**: Claude Sonnet 4 with cost tracking ($3/1M input, $15/1M output)
- **Plugin System**: Browser interaction layer with JS injection
- **Response Capture**: Monitors network traffic for AJAX/XHR and SSR responses
- **Filtering**: Excludes analytics/telemetry URLs and JS files during initial load

#### Response Interception System

**AJAX Response Handler (`handle_ajax_response`)**:

- Captures XHR/fetch requests only
- Filters out analytics URLs (`analytics`, `telemetry`, `events`, etc.)
- Extracts request metadata (method, URL, headers, post data)
- Stores response text for content matching

**SSR Handler (`handle_server_side_rendering`)**:

- Captures page HTML content on load events
- Stores as GET request with current page URL and query parameters

### 3. Step-by-Step Analysis Loop

#### Main Analysis Flow (`__call__` method)

```python
for step in range(1, max_steps + 1):
    response = await self.run_step(query)
    if response and has_pagination_parameters(response):
        strategy = await detect_pagination_strategy(response)
        if strategy:
            break  # Found viable source
```

#### Individual Step Process (`run_step`)

**1. Vision Analysis**

- Takes page screenshot (1280x800 viewport)
- Sends to LLM with structured prompt template
- Receives `StepResult` with action coordinates and text sections

**2. Content Detection Algorithm**

- **Text Matching**: Uses fuzzy matching to find captured responses containing identified text sections
- **Similarity Threshold**: Requires >50% text match ratio using Unicode-aware tokenization
- **Container Detection**: Finds parent DOM container for detected content sections
- **Response Preprocessing**: Adds content filtering rules for SSR responses

**3. Page Interaction Logic** (Priority Order):

1. **Close Overlay Popups**: Clicks dismiss buttons for cookie banners, modals
2. **Load More Content**: Clicks pagination controls (Next, More, page numbers)
3. **Skip to Content**: Navigates to sections likely containing relevant data
4. **Fallback Scroll**: Moves to next viewport when no specific action identified

**4. Smart Navigation Features**

- **Similar Content Skip**: Detects repeated content patterns and scrolls past them
- **Last Visible Child**: Identifies pagination boundaries within containers
- **Context Logging**: Screenshots with action overlays for debugging

### 4. Pagination Detection System

#### Parameter Extraction (`get_potential_pagination_parameters`)

Scans request queries and POST data for:

- **Numeric values**: Potential page/limit/offset parameters
- **Cursor patterns**: Base64, timestamps, alphanumeric tokens (min 8 chars)

#### Key Detection (`detect_pagination_keys`)

Uses LLM to classify parameters into:

- `page_number_key`: Page-based pagination (`page`, `page_no`)
- `limit_key`: Items per page (`limit`, `per_page`, `page_size`)
- `offset_key`: Skip count (`offset`, `skip`)
- `cursor_key`: Position tokens (`cursor`, `next_cursor`, `after`)

#### Strategy Generation (`detect_pagination_strategy`)

**Cursor Pattern Analysis**:

1. Extracts potential sub-cursors from cursor values
2. Finds best matching response containing cursor components
3. Generates regex patterns for cursor extraction using `generate_patterns()`
4. Creates pattern map for different cursor contexts

**Parameter Object Creation**:

- **NumberParameter**: For page/limit/offset with default values
- **CursorParameter**: For cursor-based with pattern extraction rules
- **PaginationStrategy**: Combined strategy object

### 5. Code Generation System

#### Extraction Code Generation (`get_extraction_code_and_default_limit`)

1. **Schema Processing**: Converts Pydantic model to JSON schema for LLM
2. **Code Generation**: LLM creates Python extraction function
3. **Validation Loop**: Tests generated code against actual response data
4. **Retry Logic**: Up to 3 attempts with different generated code
5. **Default Limit**: Counts extracted items to determine pagination size

#### Generated Code Pattern:

```python
def extract_data(response_text: str) -> list[dict]:
    # LLM-generated parsing logic
    return parsed_items
```

### 6. Key Algorithms

#### Text Matching (`text_match_ratio`)

- **Unicode Normalization**: NFKC normalization with case folding
- **Language-Agnostic Tokenization**: Unicode-aware word extraction
- **Multi-threaded Fuzzy Matching**: Parallel processing with 80% similarity threshold
- **Exact + Fuzzy Hybrid**: Combines substring and fuzzy word matching

#### Pattern Generation (`generate_patterns`)

- **Right-to-Left Search**: Prioritizes rightmost cursor occurrences
- **Context Extraction**: Captures before/after delimiters around cursors
- **Variable Delimiter Length**: Tests 1-20 character context windows
- **Duplicate Prevention**: Maintains unique pattern collection

#### Response Filtering

- **URL Exclusion**: Analytics, telemetry, tracking endpoints
- **Header Cleanup**: Removes protocol headers before final source creation
- **Content Type Filtering**: XHR/fetch only, excludes scripts/stylesheets

### 7. Output Structure: `Source` Object

The analysis process produces a `Source` object containing all metadata needed for data extraction:

- **Request**: HTTP metadata (method, URL, headers, queries, POST data)
- **Pagination Strategy**: Detected pagination parameters and patterns
- **Response Preprocessor**: Content filtering and preprocessing rules
- **Extraction Code**: Python function for parsing response data
- **Default Limit**: Recommended pagination size

### 8. Error Handling & Resilience

- **LLM Retry Logic**: 3 attempts for code generation and pagination detection
- **Browser Reconnection**: Automatic reconnection via ResilientBrowser
- **Step Timeout**: 2.5s sleep between failed steps
- **Exception Isolation**: Individual step failures don't abort entire analysis
- **Graceful Degradation**: Returns partial results when possible

### 9. Logging & Observability

**Structured Logging Events**:

- `analysis` → `begin/end` with success/failure status
- `run-step` → Individual step execution with context screenshots
- `llm-completion` → Token usage, cost tracking, response validation
- `detect-pagination` → Parameter detection and strategy creation
- `code-generation` → Extraction function creation and testing

**Context Preservation**:

- Screenshot logging with action overlays
- Request/response metadata tracking
- Cost accounting per LLM call
- Step-by-step decision audit trail

This architecture enables fully automated discovery of extraction metadata with minimal configuration, using computer vision and language models to understand page structure and identify the necessary components for data extraction.
