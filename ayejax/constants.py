EXCLUDE_KEYWORDS = {"analytics", "telemetry", "events", "collector", "track", "collect"}
"""URL filtering keywords"""

ANALYSIS_PROMPT_TEMPLATE = """
TASK: Extract text sections from webpage screenshot that match the user's data scraping requirement.

CRITICAL INSTRUCTIONS:
1. ONLY extract text sections that are DIRECTLY RELEVANT to the user requirement
2. Text sections must be EXACT MATCHES visible in the screenshot
3. Each text entry should not be more than 15 words
4. These text sections will be used to find matching AJAX API responses

WHAT TO EXTRACT:
- Product names, prices, descriptions, reviews, titles, etc. (actual data content)
- Text that represents the specific data the user wants to scrape

WHAT TO IGNORE:
- Headers, footers, breadcrumbs
- Login/signup forms, search bars, generic buttons
- Advertisements, cookie banners, unrelated content

ACTIONS TO CHOOSE FROM (ORDERED BY PRIORITY):
1. If you find pagination controls (Next, More, page numbers) that could load more relevant content:
   → Set "load_more_content_coords" to the pagination element coordinates
   → Leave other fields null

2. If you find relevant text sections:
   → Set "text_sections" to the list of extracted text
   → Leave coordinate fields null

3. If you see an overlay popup (cookie banner, newsletter signup, login modal) that blocks content (Ignore If popup body contains relevant content):
   → Set "close_overlay_popup_coords" to the dismiss/close button coordinates
   → Leave other fields null

4. If you find a clickable element or button that could lead to page sections likely containing relevant content:
   → Set "skip_to_content_coords" to the element coordinates
   → Leave other fields null

OUTPUT_SCHEMA:
{output_schema}

USER REQUIREMENT:
{query}
"""

PAGINATION_KEYS_IDENTIFICATION_PROMPT_TEMPLATE = """
You are an expert at identifying pagination parameter keys in API requests. Given the following request parameters, identify which TOP-LEVEL keys are used for pagination.

REQUEST PARAMETERS:
{parameters}

PAGINATION KEY CANDIDATES FOR REFERENCE:
- Page keys: 'page', 'page_no', 'page_number', 'page_index', 'data_page'
- Limit keys: 'limit', 'take', 'page_size', 'per_page'
- Offset keys: 'offset'
- Cursor keys: 'cursor', 'page_after', 'next_cursor', 'after'

IMPORTANT: Only look at TOP-LEVEL keys in the request parameters. Do not look inside nested objects or arrays.

RULES:
1. Only examine keys at the root level of the request parameters
2. A key is a pagination key if its entire value (whether simple or complex) is used for pagination
3. For cursor keys, the entire value of the key (even if it's an object) serves as the cursor
4. For limit/offset/page keys, look for numeric values that control pagination
5. Set a key to null if it is not found

OUTPUT_SCHEMA:
{output_schema}

Return only the top-level key names that are used for pagination purposes.
"""

EXTRACTION_CODE_GENERATION_PROMPT_TEMPLATE = """\
Your task is to generate robust Python code that extracts and transforms data from an API response into the specified schema format.

## Requirements:
1. **Parse the API response** (JSON, HTML, XML, or plain text)
2. **Extract relevant data** matching the schema fields
3. **Handle edge cases** (missing fields, different data types, nested structures)
4. **Return clean, structured data** that matches the schema exactly

## Code Structure:
```python
import json
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup  # if HTML parsing needed

def extract_data(response: str):
    \"\"\"
    Extract and transform API response data to match the target schema.

    Args:
        response: Raw API response as string

    Returns:
        Structured data matching the schema
    \"\"\"
    try:
        # Parse the response (adapt based on response format)
        if response.strip().startswith('{') or response.strip().startswith('['):
            data = json.loads(response)
        elif '<html' in response.lower() or '<div' in response.lower():
            soup = BeautifulSoup(response, 'html.parser')
            # Extract from HTML
        else:
            # Handle plain text or other formats
            pass

        # Extract and transform data according to schema
        result = {}

        # TODO: Implement extraction logic based on schema fields
        # Only extract data that matches the schema requirements

        return result

    except Exception as e:
        # Return empty structure matching schema on error
        return {}
```

## Important Guidelines:
- **Parse the response format correctly** (JSON, HTML, XML, plain text)
- **Map response fields to schema fields** where there's a clear match
- **Handle missing or null values** gracefully
- **Use appropriate parsing libraries** (json, BeautifulSoup, re)
- **Return data types that match the schema** (strings, numbers, lists, etc.)
- **Include error handling** to prevent crashes
- **Extract arrays/lists** when schema expects multiple items
- **Clean and normalize text** (strip whitespace, handle encoding)
- **Only return data that is actually present and relevant** in the response

## Schema (target output format):
%s

## API Response (input data):
%s

Generate production-ready Python code that extracts the relevant data from this response based on the provided schema.
"""

HEADERS_TO_IGNORE = {
    "accept-encoding",
    "host",
    "method",
    "path",
    "scheme",
    "version",
    "authority",
    "protocol",
    "content-length",
}
