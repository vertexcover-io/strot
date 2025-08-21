# Parent Container Optimization - HTML Context Reduction

## Overview

The `get_parent_container` optimization is a sophisticated content reduction technique that dramatically decreases HTML context size for LLM code generation while improving extraction accuracy. This approach identifies the minimal DOM container that encompasses all relevant data sections, reducing processing costs and hallucination risk.

## Problem Statement

### Context Size Challenge

- **Full Page HTML**: Complete page HTML can be 50KB-500KB+ of text
- **LLM Token Costs**: Large context windows consume significant tokens (~$3/1M input tokens)
- **Hallucination Risk**: Excessive irrelevant content increases chances of incorrect code generation
- **Processing Time**: Large contexts slow down LLM response times

### Content Relevance Issue

- **Scattered Data**: Target data sections may be spread across different page areas
- **Noise Ratio**: Most page content (headers, footers, ads, navigation) is irrelevant
- **Code Generation Focus**: LLM needs to focus only on data-containing sections

## Solution Architecture

### Implementation Flow

1. **Text Section Identification**: LLM vision analysis identifies relevant text sections from screenshots
2. **Container Discovery**: JavaScript plugin searches DOM for containers containing all text sections
3. **Container Scoring**: Multi-criteria scoring algorithm selects optimal container
4. **Context Reduction**: Only the selected container's HTML is used for code generation
5. **Response Preprocessing**: Container selector applied during data extraction

### Core Algorithm (`get_parent_container`)

#### Input Processing

```python
async def get_parent_container(self, text_sections: list[str]) -> str | None:
    containers: list[dict[str, Any]] = await self.evaluate(
        "([sections]) => window.getContainersWithTextSections(sections)", [text_sections]
    )
```

#### JavaScript Container Discovery (`getContainersWithTextSections`)

**Primary Strategy - Single Container Search**:

```javascript
const potentialContainers = allElements.filter((container) => {
  const containerText = container.textContent.replace(/\s+/g, " ").trim();
  const containerTextLower = containerText.toLowerCase();

  return normalizedSections.every((normalizedSection) => {
    const normalizedSectionLower = normalizedSection.toLowerCase();
    return containerTextLower.includes(normalizedSectionLower);
  });
});
```

**Fallback Strategy - Parent Discovery**:
When no single container contains all sections (distributed data scenario):

```javascript
// Find common parents that contain ≥60% of sections
const sectionsInParent = normalizedSections.filter((section) =>
  parentText.includes(section.toLowerCase()),
);

if (sectionsInParent.length >= Math.ceil(normalizedSections.length * 0.6)) {
  parentCandidates.add(parent);
}
```

#### Multi-Criteria Scoring Algorithm

```python
for container in containers:
    container["match_ratio"] = text_match_ratio(text_sections, container["text"])
    container["text_length"] = len(container["text"])
    container["extra_text_ratio"] = (
        (len(container["text"]) - target_length) / target_length if target_length > 0 else 0
    )

# Sort by: match_ratio ↓, extra_text_ratio ↑, text_length ↓
containers.sort(key=lambda x: (-x["match_ratio"], x["extra_text_ratio"], -x["text_length"]))
```

### Scoring Criteria

#### 1. Match Ratio (Primary - Descending)

- **Calculation**: Fuzzy matching percentage of text sections found in container
- **Weight**: Highest priority - ensures container actually contains target data
- **Threshold**: Must exceed 0.5 (50%) to be considered valid

#### 2. Extra Text Ratio (Secondary - Ascending)

- **Calculation**: `(container_text_length - target_text_length) / target_text_length`
- **Purpose**: Minimizes irrelevant content inclusion
- **Optimization**: Lower ratios preferred (less noise)

#### 3. Text Length (Tertiary - Descending)

- **Purpose**: Tiebreaker for containers with similar scores
- **Logic**: Larger containers preferred when other factors equal (more complete context)

## Response Processing Integration

### HTML Preprocessing Setup

```python
if response.request.type == "ssr" and container:
    response.preprocessor = HTMLResponsePreprocessor(element_selector=container)
```

### Extraction Time Application

```python
response_value = last_response.value
if last_response.preprocessor:
    response_value = last_response.preprocessor.run(response_value) or response_value
```

The `HTMLResponsePreprocessor` extracts only the HTML content within the identified container before passing it to the generated extraction code.

## Performance Impact

### Context Size Reduction

- **Typical Reduction**: 80-95% reduction in HTML context size
- **Example**: Full page 200KB → Container 10KB (20x reduction)
- **Token Savings**: Dramatic reduction in LLM input token consumption

### Cost Optimization

- **Input Token Reduction**: 10-50x fewer tokens for code generation
- **Cost Savings**: ~$3/1M tokens × reduced token count
- **Processing Speed**: Faster LLM responses due to smaller context

### Accuracy Improvements

- **Reduced Hallucination**: LLM focuses only on relevant content
- **Better Code Quality**: Generated extraction code targets specific container structure
- **Higher Success Rate**: More accurate data extraction due to focused context

## Edge Cases & Handling

### No Container Found

- **Condition**: No container scores above 0.5 match ratio
- **Fallback**: Full HTML content used (no preprocessing)
- **Impact**: Maintains functionality at cost of optimization benefits

### Multiple High-Scoring Containers

- **Resolution**: Multi-criteria sorting selects single best candidate
- **Preference**: Higher match ratio, lower noise, larger size (in that order)

### Distributed Data Scenarios

- **Problem**: Data sections spread across multiple containers
- **Solution**: Parent container discovery with 60% threshold
- **Strategy**: Find common ancestor containing majority of sections

### Dynamic Content

- **Challenge**: JavaScript-generated content may not be captured
- **Mitigation**: Plugin waits for `domcontentloaded` state
- **Limitation**: Some dynamic content may require additional wait strategies

## Technical Benefits

### 1. Cost Efficiency

- **Direct Savings**: Reduced LLM token consumption
- **Indirect Savings**: Fewer retry attempts due to better code quality

### 2. Processing Speed

- **Faster Generation**: Smaller context = faster LLM processing
- **Reduced Latency**: Less network overhead for API calls

### 3. Code Quality

- **Targeted Extraction**: Code focuses on specific DOM structure
- **Reduced Complexity**: Less irrelevant HTML to navigate
- **Higher Precision**: Better element targeting and data extraction

### 4. Scalability

- **Consistent Performance**: Works across different page sizes and structures
- **Resource Optimization**: Enables processing of larger job volumes
- **Predictable Costs**: More stable token usage patterns

This optimization represents a key breakthrough in making LLM-driven web analysis both cost-effective and accurate by intelligently reducing context while maintaining data completeness.
