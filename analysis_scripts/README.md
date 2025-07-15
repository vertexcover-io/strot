# Enhanced Session Analysis Scripts

Advanced diagnostic tools for analyzing ayejax session logs to diagnose popup dismissal issues with comprehensive debug tracking.

## Quick Start

Run enhanced analysis suite:
```bash
cd /home/abhishek/Downloads/experiments/vertexcover/ayejax
./analysis_scripts/run_all_analysis.sh
```

## 🆕 Enhanced Analysis Scripts

### 1. `analyze_execution_flow.py` ⭐ **NEW**
**Purpose**: Track PopupDismisser lifecycle and identify hang points  
**Usage**: `uv run analysis_scripts/analyze_execution_flow.py [session_dir]`  
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
**Usage**: `uv run analysis_scripts/analyze_popup_logs.py [session_dir]`  
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
**Usage**: `./analysis_scripts/analyze_session_basic.sh`  

### 5. `analyze_llm_responses.py`
**Purpose**: LLM response analysis for popup detection patterns  
**Usage**: `uv run analysis_scripts/analyze_llm_responses.py`  

### 6. `check_popup_dismissal.sh`
**Purpose**: Traditional popup dismissal verification  
**Usage**: `./analysis_scripts/check_popup_dismissal.sh`  

### 7. `comprehensive_analysis.py`
**Purpose**: Root cause analysis with actionable recommendations  
**Usage**: `uv run analysis_scripts/comprehensive_analysis.py`  

### 8. `run_all_analysis.sh` 🔄 **ENHANCED**
**Purpose**: Master script with enhanced debug tracking workflow  
**Usage**: `./analysis_scripts/run_all_analysis.sh`

## 🔍 Enhanced Debug Tracking

The new scripts can detect and analyze these debug log phases:

```
✅ PopupDismisser Entry       → dismiss_popup_start
❓ Screenshot Phase          → taking_before_screenshot → screenshot_phase_complete  
❓ Strategy Loop             → entering_strategy_loop → strategy_loop_complete
❓ Individual Strategies     → strategy="click_outside" action="clicking_background"
❓ Verification Phase        → running_final_verification → result="completed"
```

## 📊 Session Structure (Enhanced)

```
logs/session_YYYYMMDD_HHMMSS/
├── execution_flow.jsonl    # 🆕 PopupDismisser lifecycle tracking
├── llm_calls/              # LLM request/response pairs
├── popup/                  # Popup dismissal logs (may be empty)
├── screenshots/            # Screenshots at each step
└── network/               # Network activity logs (may be empty)
```

## 🎯 Diagnostic Workflow

1. **Execution Flow Analysis**: Check if PopupDismisser starts but never completes
2. **Debug Phase Detection**: Identify which phase causes hanging (screenshot, strategy loop, verification)
3. **Strategy Execution Verification**: Confirm if strategies are actually being called with correct coordinates
4. **Session Comparison**: Compare before/after debug improvements
5. **Root Cause Determination**: Pinpoint exact code location causing issues

## 🔧 Common Issues Detected

### Issue: PopupDismisser Hangs
**Symptoms**: 
- `dismiss_popup_start` logs present
- No `dismiss_popup_complete` logs
- Empty `popup/` directory

**Diagnosis**: Use `analyze_execution_flow.py` to find hanging attempts and missing debug phases

**Common Causes**:
- Screenshot timeout (missing `screenshot_phase_complete`)
- Strategy loop never reached (missing `entering_strategy_loop`)  
- Verification failure (missing `result="completed"`)

### Issue: Strategies Not Executing
**Symptoms**:
- PopupDismisser completes but popup remains
- No `click_outside` or `explicit_close` action logs

**Diagnosis**: Use `analyze_popup_logs.py` to search for strategy execution logs

### Issue: Coordinate Mismatch
**Symptoms**:
- Strategies execute but clicks miss popup
- Popup coordinates provided by LLM but different coordinates used

**Diagnosis**: Use coordinate analysis in `analyze_popup_logs.py`

## 💡 Pro Tips

- **Quick Diagnosis**: Run `analyze_execution_flow.py` first to see if PopupDismisser is hanging
- **Deep Dive**: Use `analyze_popup_logs.py` when execution completes but popup remains  
- **Before/After**: Use `compare_sessions.py` to verify debug improvements are working
- **Full Suite**: Run `run_all_analysis.sh` for comprehensive analysis

## Example Usage

```bash
# Quick hang detection
uv run analysis_scripts/analyze_execution_flow.py logs/session_20250715_235753

# Deep strategy analysis  
uv run analysis_scripts/analyze_popup_logs.py logs/session_20250715_235753

# Compare old vs new session
uv run analysis_scripts/compare_sessions.py logs/session_20250715_232742 logs/session_20250715_235753

# Full analysis suite
./analysis_scripts/run_all_analysis.sh
```

## Requirements

- Python 3.8+ with `uv` package manager
- Bash shell for script execution
- Read access to session log directories
- All scripts are non-destructive (read-only analysis)