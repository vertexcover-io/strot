# Report Generation Documentation

This directory contains scripts for generating comprehensive reports from Ayejax session logs.

## Scripts Overview

### 1. `generate_session_csv.py`
Generates CSV report for all sessions with key metrics and stage information.

**Usage:**
```bash
uv run analysis_scripts/generate_session_csv.py
```

**Output:** `reports/csv/session_analysis.csv`

**Columns:**
- `session_id`, `url`, `tag`, `start_time`, `end_time`, `duration_seconds`
- `status`, `total_steps`, `screenshot_count`, `llm_call_count`
- `popup_dismissal_attempts`, `llm_analysis_count`, `popup_types`
- `has_final_result`, `has_error`, `error_message`, `stages_summary`

### 2. `generate_html_report.py`
Generates comprehensive HTML report for all sessions with embedded screenshots.

**Usage:**
```bash
uv run analysis_scripts/generate_html_report.py
```

**Output:** `reports/html/session_analysis_report.html`

**Features:**
- **3 Visualization Approaches:**
  1. **Overview Dashboard** - Summary stats and key insights
  2. **Session Cards** - Grid view with embedded screenshots
  3. **Timeline View** - Chronological step-by-step breakdown
- Interactive tabs
- Embedded screenshots (click to zoom)
- Popup handling details
- Success/failure analysis

### 3. `generate_single_session_html.py`
Generates detailed HTML report for a specific session.

**Usage:**
```bash
uv run analysis_scripts/generate_single_session_html.py <session_id>
```

**Example:**
```bash
uv run analysis_scripts/generate_single_session_html.py session_20250716_002557
```

**Output:** `reports/html/{session_id}_report.html`

**Features:**
- **6 Detailed Tabs:**
  1. **Overview** - Session summary with statistics
  2. **Timeline** - Step-by-step execution flow
  3. **Screenshots** - All screenshots with keyboard navigation
  4. **LLM Calls** - Full request/response pairs
  5. **Popups** - Popup dismissal details
  6. **Raw Data** - Complete session JSON
- **Keyboard Navigation** for screenshots:
  - `←` Previous screenshot
  - `→` Next screenshot
  - `Escape` Close modal
- Interactive screenshot viewer with counter (e.g., "3 / 13")

## Report Structure

```
reports/
├── csv/
│   └── session_analysis.csv
└── html/
    ├── session_analysis_report.html        # All sessions
    └── session_YYYYMMDD_HHMMSS_report.html # Individual sessions
```

## Session Data Structure

Each session directory contains:
- `session.json` - Basic session metadata
- `timeline.json` - Step-by-step execution timeline
- `execution_flow.jsonl` - Detailed execution events
- `screenshots/` - Screenshots for each step
- `llm_calls/` - LLM request/response pairs
- `popup/` - Popup dismissal debug info
- `network/` - Network request logs

## Key Metrics Tracked

- **Performance**: Duration, steps, LLM calls
- **Success Rate**: Completion status, errors
- **User Experience**: Popup handling, screenshot coverage
- **Debugging**: Detailed logs, raw data export

## Common Use Cases

1. **Performance Analysis**: Use CSV for spreadsheet analysis
2. **Success Rate Monitoring**: Overview dashboard in HTML report
3. **Debugging Failed Sessions**: Single session detailed view
4. **Visual Inspection**: Screenshot navigation for UI issues
5. **LLM Optimization**: Request/response analysis

## Getting Started

1. Run a session to generate logs in `logs/session_*`
2. Generate reports:
   ```bash
   # CSV for analysis
   uv run analysis_scripts/generate_session_csv.py
   
   # HTML overview
   uv run analysis_scripts/generate_html_report.py
   
   # Detailed single session
   uv run analysis_scripts/generate_single_session_html.py <session_id>
   ```
3. Open HTML reports in browser for interactive analysis

## Available Sessions

To see available sessions:
```bash
ls logs/session_*
```

Reports are automatically organized in `reports/` directory with proper folder structure.