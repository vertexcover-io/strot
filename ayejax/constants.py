EXCLUDE_KEYWORDS = {"analytics", "telemetry", "events", "collector", "track", "collect"}
"""URL filtering keywords"""

PROMPT_TEMPLATE_WITH_SECTION_NAVIGATION = """\
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

PROMPT_TEMPLATE_WITHOUT_SECTION_NAVIGATION = """\
Your task is to precisely extract keywords from the provided screenshot of a webpage that are directly relevant to the user's data scraping requirement. These keywords should represent the actual data being scraped and must exactly match those visible in the screenshot.

Strictly adhere to the following instructions:
- Inspect the screenshot for keywords that are directly relevant to the user's data scraping requirement below.
- Only extract keywords that represent the actual data content the user wants to scrape (e.g., product names, prices, descriptions, etc.).
- Ignore generic website elements like navigation, headers, footers, or unrelated content.
- If an overlay popup is visible in the screenshot, identify the "close" or "allow" clickable element's coordinates and assign them to "popup_element_point". If no overlay popup is present, set this to null.
- If and only if no suitable data-relevant keywords are found:
  - set "keywords" to an empty list.
  - ONLY look for pagination controls: Page numbers (1, 2, 3...), "Next" button, ">" arrow, "More" button, or pagination dots
  - Do NOT look for section navigation or content expansion elements
  - If a pagination control is found, assign its coordinates to "navigation_element_point"
  - If no pagination control is found, set "navigation_element_point" to null

Provide your response in JSON matching this schema:

{
  "keywords": ["<keyword1>", "<keyword2>", ...],
  "popup_element_point": {"x": <x>, "y": <y>} or null,
  "navigation_element_point": {"x": <x>, "y": <y>} or null
}

User Requirement: %s"""

HEADERS_TO_IGNORE = {
    "accept-encoding",
    "host",
    "method",
    "path",
    "scheme",
    "version",
    "authority",
    "protocol",
}
