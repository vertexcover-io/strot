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

RESPONSE FORMAT:
{output_schema}

USER REQUIREMENT:
{query}
"""

ANALYSIS_PROMPT_TEMPLATE_WITH_SECTION_NAVIGATION = """\
Your task is to precisely extract keywords from the provided screenshot of a webpage that are directly relevant to the user's data scraping requirement. These keywords should represent the actual data being scraped and must exactly match those visible in the screenshot.

Strictly adhere to the following instructions:
- Inspect the screenshot for keywords that are directly relevant to the user's data scraping requirement below.
- Only extract keywords that represent the actual data content the user wants to scrape (e.g., product names, prices, descriptions, etc.).
- Ignore generic website elements like navigation, headers, footers, or unrelated content.
- If an overlay popup is visible in the screenshot, identify the "close" or "allow" clickable element's coordinates and assign them to "popup_element_point". If no overlay popup is present, set this to null.
- If and only if no suitable data-relevant keywords are found:
  - set "keywords" to an empty list.
  - Look for user requirement relevant navigation elements in the following priority order:
    1. **Pagination controls**: Page numbers (1, 2, 3...), "Next" button, ">" arrow, "More" button, or pagination dots
    2. **Section navigation**: Element that lead to sections likely containing the required keywords
    3. **Content expansion**: "Show more", "Load more", "Expand", or accordion/dropdown toggles
  - Select the MOST RELEVANT navigation element that would likely lead to finding the required keywords
  - Assign the coordinates of this element to "navigation_element_point"
  - If no relevant navigation element is found, set this to null

Provide your response in JSON matching this schema:

{
  "keywords": ["<keyword1>", "<keyword2>", ...],
  "popup_element_point": {"x": <x>, "y": <y>} or null,
  "navigation_element_point": {"x": <x>, "y": <y>} or null
}

User Requirement: %s"""

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
