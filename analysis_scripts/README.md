# Enhanced Session Analysis Scripts

Advanced diagnostic tools for analyzing ayejax session logs to diagnose popup dismissal issues with comprehensive debug tracking.

## Quick Start

Run enhanced analysis suite:
```bash
cd /home/abhishek/Downloads/experiments/vertexcover/ayejax

# Analyze a specific session
./analysis_scripts/run_all_analysis.sh session_20250716_002557

# Compare with an older session
./analysis_scripts/run_all_analysis.sh session_20250716_002557 session_20250715_232742

# See available sessions
./analysis_scripts/run_all_analysis.sh
```

## 🆕 Enhanced Analysis Scripts

### 1. `analyze_execution_flow.py` ⭐ **NEW**
**Purpose**: Track PopupDismisser lifecycle and identify hang points  
**Usage**: `uv run analysis_scripts/analyze_execution_flow.py <session_name>`  
**Key Features**:
- Parses `execution_flow.jsonl` for start/complete pairs
- Identifies hanging PopupDismisser attempts
- Tracks debug log phase coverage
- Pinpoints exact failure location

**Output**:
- PopupDismisser start vs completion statistics
- Hanging attempt details with timestamps
- Missing debug phases diagnosis
- Execution timeline analysis

### 2. `analyze_popup_logs.py` ⭐ **NEW** 
**Purpose**: Deep search for popup dismissal logs across ALL session files  
**Usage**: `uv run analysis_scripts/analyze_popup_logs.py <session_name>`  
**Key Features**:
- Searches JSON, JSONL, and text files
- Extracts strategy execution logs
- Analyzes coordinate accuracy vs LLM data
- Identifies errors and exceptions

**Output**:
- Strategy execution detection (click_outside, explicit_close, etc.)
- Coordinate comparison (LLM vs actual usage)
- Verification attempt logs
- Error/exception catalog

### 3. `compare_sessions.py` ⭐ **NEW**
**Purpose**: Compare old vs new sessions to track improvements/regressions  
**Usage**: `uv run analysis_scripts/compare_sessions.py <old_session> <new_session>`  
**Key Features**:
- Execution flow comparison
- Debug log coverage improvements
- Strategy execution changes
- LLM response consistency

**Output**:
- Improvement/regression summary
- Debug coverage delta analysis
- Coordinate consistency verification
- Actionable recommendations

### 4. `analyze_session_basic.sh`
**Purpose**: Basic directory structure and file count analysis  
**Usage**: `./analysis_scripts/analyze_session_basic.sh <session_name>`  

### 5. `analyze_llm_responses.py`
**Purpose**: LLM response analysis for popup detection patterns  
**Usage**: `uv run analysis_scripts/analyze_llm_responses.py <session_name>`  

### 6. `check_popup_dismissal.sh`
**Purpose**: Traditional popup dismissal verification  
**Usage**: `./analysis_scripts/check_popup_dismissal.sh <session_name>`  

### 7. `comprehensive_analysis.py`
**Purpose**: Root cause analysis with actionable recommendations  
**Usage**: `uv run analysis_scripts/comprehensive_analysis.py <session_name>`  

### 8. `generate_html_report.py`
**Purpose**: Generate comprehensive HTML reports for all sessions  
**Usage**: `uv run analysis_scripts/generate_html_report.py [logs_dir]`  

### 9. `generate_session_csv.py`
**Purpose**: Export session data to CSV for analysis  
**Usage**: `uv run analysis_scripts/generate_session_csv.py [logs_dir]`  

### 10. `generate_single_session_html.py` ⭐ **ENHANCED**
**Purpose**: Generate detailed HTML report for a single session with keyboard navigation  
**Usage**: `uv run analysis_scripts/generate_single_session_html.py <session_name>`  
**Key Features**:
- Interactive screenshot viewer with keyboard navigation (←/→ arrow keys)
- 6 detailed tabs: Overview, Timeline, Screenshots, LLM Calls, Popups, Raw Data
- Embedded screenshots with modal zoom and counter
- Full LLM request/response pairs for debugging

📖 **[Report Generation Documentation](REPORT_GENERATION.md)** - Complete guide for all reporting features  

### 11. `run_all_analysis.sh` 🔄 **ENHANCED**
**Purpose**: Master script that runs all analysis automatically  
**Usage**: `./analysis_scripts/run_all_analysis.sh <session_name> [old_session_name]`

## 📊 Session Structure

```
logs/session_YYYYMMDD_HHMMSS/
├── execution_flow.jsonl    # PopupDismisser lifecycle tracking
├── llm_calls/              # LLM request/response pairs
├── popup/                  # Popup dismissal logs (may be empty)
├── screenshots/            # Screenshots at each step
└── network/               # Network activity logs (may be empty)
```

## 🎯 Quick Reference

| Analysis Type | Script | Purpose |
|---------------|--------|---------|
| **Execution Flow** | `analyze_execution_flow.py` | Track PopupDismisser lifecycle |
| **Popup Logs** | `analyze_popup_logs.py` | Search for strategy execution logs |
| **LLM Analysis** | `analyze_llm_responses.py` | Popup detection patterns |
| **Session Health** | `comprehensive_analysis.py` | Root cause analysis |
| **Comparison** | `compare_sessions.py` | Before/after improvements |
| **Reports** | `generate_html_report.py` | Visual session reports |
| **Data Export** | `generate_session_csv.py` | Export to spreadsheet |

For detailed popup troubleshooting, see [POPUP.md](POPUP.md)

## Example Usage

```bash
# Show available sessions (any script without parameters)
uv run analysis_scripts/analyze_execution_flow.py

# Quick hang detection
uv run analysis_scripts/analyze_execution_flow.py session_20250715_235753

# Deep strategy analysis  
uv run analysis_scripts/analyze_popup_logs.py session_20250715_235753

# Compare old vs new session
uv run analysis_scripts/compare_sessions.py session_20250715_232742 session_20250715_235753

# Generate HTML report for single session
uv run analysis_scripts/generate_single_session_html.py session_20250716_002557

# Generate CSV report for all sessions
uv run analysis_scripts/generate_session_csv.py

# Full analysis suite (non-interactive)
./analysis_scripts/run_all_analysis.sh session_20250716_002557

# Full analysis with comparison
./analysis_scripts/run_all_analysis.sh session_20250716_002557 session_20250715_232742
```

## Key Features

### 🔄 Non-Interactive Operation
- All scripts run automatically without user prompts
- Perfect for automated analysis workflows
- Clear progress indicators and section separators

### 📊 Flexible Session Selection
- All scripts accept session names with or without `session_` prefix
- Show available sessions when run without parameters
- Consistent parameter handling across all scripts

### 📈 Comprehensive Analysis
- **Execution Flow**: Track PopupDismisser lifecycle and hanging attempts
- **Popup Logs**: Deep search across all session files for dismissal logs
- **LLM Analysis**: Popup detection patterns and coordinate extraction
- **Session Comparison**: Before/after analysis for debugging improvements
- **HTML Reports**: Visual reports with embedded screenshots and navigation
- **CSV Export**: Structured data for spreadsheet analysis

## Requirements

- Python 3.8+ with `uv` package manager
- Bash shell for script execution
- Read access to session log directories
- All scripts are non-destructive (read-only analysis)