# Parameter Detection for Dynamic API Requests

## The Problem

Current analysis detects pagination parameters but ignores user-controllable dynamic parameters that customize API requests. This limits the system's ability to generate truly dynamic data extraction:

- **Missing Dynamic Control**: Users cannot specify sorting, filtering, search terms, or category selections
- **Separate Detection Logic**: Pagination and dynamic parameters are handled independently, creating complexity
- **Limited Request Customization**: Generated sources only support limit/offset, not business logic parameters
- **Manual Parameter Mapping**: Multiple keys for the same logical parameter (e.g., `page_num` in query, `page` in POST data) require manual handling

### Example: E-commerce API with Dynamic Parameters

**Current Analysis Result:**

```python
# Only pagination detected
source.generate_data(limit=10, offset=0)  # Fixed to first page, default sorting
```

**Desired Analysis Result:**

```python
# Both pagination + dynamic parameters detected
source.generate_data(
    limit=10,
    offset=0,
    sortBy="price",         # Dynamic: sort products by price
    category="electronics", # Dynamic: filter to electronics category
    searchTerm="laptop"     # Dynamic: search for laptops
)
```

## The Solution

Implement **Unified Parameter Detection** that combines pagination and dynamic parameter analysis into a single LLM task, generating code that handles all parameter types uniformly.

### Core Innovation

**Single Generated Function Handles All Parameters:**

```python
def apply_parameters(request: dict[str, Any], **kwargs) -> dict[str, Any]:
    def apply(dst: dict[str, Any], key: str):
        value = kwargs.get(key)
        if value is None:
            dst.pop(key, None)
        else:
            dst[key] = value

    # Handle pagination parameters
    if 'page' in kwargs:
        apply(request['queries'], 'page_num')
        apply(request['post_data']['pagination'], 'page')

    if 'limit' in kwargs:
        apply(request['queries'], 'limit')
        apply(request['post_data']['pagination'], 'size')

    # Handle dynamic parameters
    if 'sortBy' in kwargs:
        apply(request['queries'], 'sort')
        apply(request['post_data']['filters'], 'sortBy')

    if 'category' in kwargs:
        apply(request['queries'], 'cat')

    return request
```

**Benefits:**

- **Unified Interface**: Single function handles pagination + dynamic parameters
- **Multiple Key Mapping**: Same logical parameter applied to multiple request locations
- **Complex Parameter Logic**: Handles nested objects and different key names
- **LLM-Generated**: Tailored to specific API patterns discovered during analysis

## Technical Architecture

### New Analysis Flow

**Current Flow:**

1. Request Detection → Find API request
2. Pagination Detection → Find pagination parameters + build pagination strategy
3. Response Code Generation → Parse responses into structured data

**New Flow:**

1. Request Detection → Find API request
2. **Unified Parameter Detection** → Detect pagination and other dynamic parameters + generate code to populate values + build pagination strategy
3. Response Code Generation → Parse responses into structured data

### LLM Detection Process

**Input to LLM:**

- JSON Dumped API request to be analyzed

**LLM Prompt:**

````
You are an expert at analyzing API requests to identify both pagination and dynamic parameters, then generating Python code to apply these parameters.

API REQUEST TO ANALYZE:
{{ request_data }}

ANALYSIS TASKS:
1. Identify pagination parameter keys
   - When looking for cursor key, look for value as a whole - in some cases cursor values can be a whole nested object/array
2. Identify dynamic parameter keys (sorting, filtering, search, etc.)
3. Generate apply_parameters function code

PAGINATION KEY CANDIDATES FOR REFERENCE:
- Page keys: 'page', 'page_no', 'page_number', 'page_index', 'data_page'
- Limit keys: 'limit', 'take', 'page_size', 'per_page'
- Offset keys: 'offset'
- Cursor keys: 'cursor', 'page_after', 'f.req', 'next_cursor', 'after'

DYNAMIC PARAMETER IDENTIFICATION:
Look for keys that control:
- Sorting: 'sort', 'sortBy', 'orderBy', 'order', 'sortOrder', etc.
- Filtering: 'filter', 'category', 'type', 'status', 'brand', 'region', etc.
- Search: 'search', 'query', 'q', 'searchTerm', 'keyword', etc.
- Business logic: Any other user-controllable parameters

RULES:
1. Examine all parameter keys in the request (including nested keys)
2. Pagination keys control data retrieval pagination (page number, items per page, cursor position)
3. Dynamic keys control data filtering, sorting, searching, or other business logic
4. Set pagination keys to null if not found
5. Include only keys that appear to accept variable user input

CODE GENERATION REQUIREMENTS:
1. Function name: apply_parameters
2. Signature: apply_parameters(request: dict[str, Any], **kwargs) -> dict[str, Any]
3. Analyze the request structure to determine where each parameter should be applied
4. Handle same logical parameter going to multiple locations with different key names
5. Use conditional checks: if 'key' in kwargs: (then proceed)
6. Return modified request dictionary

CODE GENERATION PATTERNS:
```python
from typing import Any

def apply_parameters(request: dict[str, Any], **kwargs) -> dict[str, Any]:
    def apply(dst: dict[str, Any], key: str, value: Any | None):
        if value is None:
            dst.pop(key, None)
        else:
            dst[key] = value

    if 'page' in kwargs:
        apply(request['queries'], 'page_num', kwargs['page'])
        apply(request['post_data']['pagination'], 'page', kwargs['page'])

    if 'sortBy' in kwargs:
        apply(request['queries'], 'sort', kwargs['sortBy'])
        apply(request['post_data']['filters'], 'sortBy', kwargs['sortBy'])

    if 'category' in kwargs:
        apply(request['queries'], 'cat', kwargs['category'])

    return request
````

Return the analysis results in exact JSON format matching the schema.

````
**Output from LLM:**
1. **Generated Code**: `apply_parameters` function that handles all parameter types
2. **Pagination Keys**: Traditional pagination parameter names (for PaginationStrategy)
3. **Dynamic Parameter Keys**: User-controllable business logic parameters

**Example LLM Output:**
```json
{
  "apply_parameters_code": "...t",
  "pagination_keys": {
    "page_number_key": null,
    "limit_key": "limit",
    "offset_key": null,
    "cursor_key": "lastEvaluated"
  },
  "dynamic_parameter_keys": ["orderBy"]
}
````

## Evaluation Strategy

### Separate Parameter Category Evaluation

Evaluate pagination and dynamic parameters independently to identify category-specific accuracy:

Input

```json
[
  {
    "request": {
      "method": "GET",
      "url": "https://5i27ysv3j8.execute-api.us-west-2.amazonaws.com/prod/stores/09598bdf-4693-43bc-9e20-d7576d9a4c44/products/shopify-746644897882/reviews",
      "type": "ajax",
      "queries": {
        "limit": "5",
        "orderBy": "date desc",
        "lastEvaluated": "{\"subscriberId_collectionId\":\"09598bdf-4693-43bc-9e20-d7576d9a4c44:d1db8590-7e9a-4740-8803-a8902a943cd6\",\"dateCreated\":\"2025-08-18T16:41:30.853Z\",\"reviewId\":\"9d603f5e-e3b0-44f2-8efb-efa7519d02e2\"}"
      },
      "headers": {},
      "post_data": null
    },
    "expected_pagination_keys": ["limit", "lastEvaluated"],
    "expected_dynamic_keys": ["orderBy"]
  },
  {
    "request": {
      "method": "GET",
      "url": "https://fast.a.klaviyo.com/reviews/api/client_reviews/all/",
      "type": "ajax",
      "queries": {
        "tz": "UTC",
        "sort": "3",
        "type": "reviews",
        "limit": "5",
        "media": "false",
        "offset": "0",
        "company_id": "RFfzm5",
        "product_id": "all",
        "preferred_country": "US"
      },
      "headers": {},
      "post_data": null
    },
    "expected_pagination_keys": ["limit", "offset"],
    "expected_dynamic_keys": [
      "tz",
      "sort",
      "type",
      "media",
      "company_id",
      "product_id",
      "preferred_country"
    ]
  },
  {
    "request": {
      "method": "GET",
      "url": "https://baseballamerica.myshopify.com/collections/magazines",
      "type": "ssr",
      "queries": {
        "page": "2",
        "phcursor": "eyJhbGciOiJIUzI1NiJ9.eyJzayI6InBvc2l0aW9uIiwic3YiOjIyLCJkIjoiZiIsInVpZCI6MjkxMTAxNjcyNzM1MzIsImwiOjIwLCJvIjowLCJyIjoiQ0RQIiwidiI6MSwicCI6Mn0.SlBHUUwhSqqqy64NRwe4R3na2G6N1hiUWIsq6msJU20"
      },
      "headers": {},
      "post_data": null
    },
    "expected_pagination_keys": ["page", "phcursor"],
    "expected_dynamic_keys": []
  },
  {
    "request": {
      "method": "POST",
      "url": "https://www.swiggy.com/api/instamart/category-listing/filter",
      "type": "ajax",
      "queries": {
        "type": "Speciality taxonomy 1",
        "limit": "20",
        "offset": "20",
        "pageNo": "1",
        "storeId": "1374258",
        "filterId": "6822eeeded32000001e25aa2",
        "filterName": "Fresh Vegetables",
        "categoryName": "Fresh Vegetables",
        "primaryStoreId": "1374258",
        "secondaryStoreId": "1392421"
      },
      "headers": {},
      "post_data": {
        "facets": {},
        "sortAttribute": ""
      }
    },
    "expected_pagination_keys": ["limit", "offset", "pageNo"],
    "expected_dynamic_keys": [
      "type",
      "storeId",
      "filterId",
      "filterName",
      "categoryName",
      "primaryStoreId",
      "secondaryStoreId"
    ]
  },
  {
    "request": {
      "method": "GET",
      "url": "https://api.olx.in/relevance/v4/search",
      "type": "ajax",
      "queries": {
        "lang": "en-IN",
        "page": "1",
        "size": "40",
        "user": "04029046994689771",
        "category": "1587",
        "location": "2001177",
        "platform": "web-desktop",
        "pttEnabled": "true",
        "facet_limit": "1000",
        "relaxedFilters": "true",
        "location_facet_limit": "40"
      },
      "headers": {},
      "post_data": null
    },
    "expected_pagination_keys": ["page", "size"],
    "expected_dynamic_keys": [
      "lang",
      "user",
      "category",
      "location",
      "platform",
      "pttEnabled",
      "facet_limit",
      "relaxedFilters",
      "location_facet_limit"
    ]
  },
  {
    "request": {
      "method": "GET",
      "url": "https://api-cdn.yotpo.com/v3/storefront/store/MvDwYwPz05ViJwpjCchu8kRX4uKDysGAMcjXP17a/product/10582914760726/reviews",
      "type": "ajax",
      "queries": {
        "page": "1",
        "sort": "smart_optimistic,date,images,badge,rating",
        "perPage": "5"
      },
      "headers": {
        "accept": "application/json",
        "origin": "https://tartecosmetics.com",
        "referer": "https://tartecosmetics.com/",
        "sec-ch-ua": "\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "content-type": "application/json",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Linux\""
      },
      "post_data": null
    },
    "expected_pagination_keys": ["page", "perPage"],
    "expected_dynamic_keys": ["sort"]
  }
]
```

Output

<iframe class="airtable-embed" src="https://airtable.com/embed/appI7Z4xNPnLbAnPR/shrZvMXz8mn1VQYu5?viewControls=on" frameborder="0" onmousewheel="" width="100%" height="533" style="background: transparent; border: 1px solid #ccc;"></iframe>
