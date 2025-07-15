# Ayejax Evaluation Tools

## Overview
Evaluation tools for testing and debugging the ayejax workflow, particularly for screenshot analysis and batch processing.

## Tools

### `screenshot_workflow.py`
CLI tool for screenshot-based evaluation and debugging.

#### Commands

**Batch Processing**
```bash
# Process folder of screenshots
python screenshot_workflow.py batch ./screenshots_folder/ --output-file results.json

# Process with custom query
python screenshot_workflow.py batch ./screenshots/ --query "product reviews" --output-file analysis.json
```

**Single Screenshot Analysis**
```bash
# Analyze single screenshot file
python screenshot_workflow.py analyze ./screenshot.png

# Analyze folder of screenshots
python screenshot_workflow.py analyze ./screenshots_folder/

# Analyze URL (takes screenshot first)
python screenshot_workflow.py analyze https://example.com --save-screenshot
```

**Screenshot Capture**
```bash
# Take screenshot of URL
python screenshot_workflow.py screenshot https://example.com

# Save to custom directory
python screenshot_workflow.py screenshot https://example.com --output-dir ./my_screenshots/

# Headless mode
python screenshot_workflow.py screenshot https://example.com --browser-mode headless
```

**Partial Workflow Testing**
```bash
# Run limited workflow for debugging
python screenshot_workflow.py partial https://example.com --max-iterations 3

# Test with different tag
python screenshot_workflow.py partial https://example.com --tag reviews --browser-mode headless
```

**Interactive Mode**
```bash
# Step-by-step debugging
python screenshot_workflow.py interactive https://example.com
```

#### Output Structure
Results are saved as JSON with the following structure:
```json
{
  "folder": "./screenshots/",
  "total_screenshots": 10,
  "total_cost": 0.1234,
  "results": [
    {
      "screenshot_path": "./screenshots/example.png",
      "url": "https://example.com",
      "success": true,
      "result": {
        "keywords": ["review", "rating", "comment"],
        "navigation_element_point": {"x": 100, "y": 200},
        "popup_element_point": null
      },
      "cost": 0.0123
    }
  ]
}
```

#### Directory Structure
```
eval/
├── screenshot_workflow.py    # Main CLI tool
├── screenshots/              # Default screenshot storage
├── logs/                     # Analysis logs
├── results/                  # Batch processing results
└── review/                   # Original review evaluation
    ├── analyzer.py
    └── urls
```

### `review/analyzer.py`
Original evaluation script for batch processing URLs from a file.

```bash
# Run review analysis
cd review/
python analyzer.py
```

## Requirements
- All dependencies from main project
- `click` for CLI interface
- `playwright` for browser automation
- Access to Anthropic Claude API

## Usage Tips
- Use `--browser-mode headless` for faster processing
- Batch processing automatically handles cost tracking
- Screenshots are saved with descriptive filenames (domain_path_timestamp.png)
- Results include both success/failure status and detailed error information
- Interactive mode is useful for debugging specific websites