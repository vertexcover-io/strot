# Popup Issues Diagnosis Guide

This guide explains common popup dismissal issues and how to diagnose them using the analysis scripts.

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

## 🚨 Troubleshooting Examples

### Example 1: Popup Dismisser Never Starts
```bash
# Check if PopupDismisser was called at all
./analysis_scripts/analyze_session_basic.sh session_20250716_002557

# Look for popup detection in LLM responses
uv run analysis_scripts/analyze_llm_responses.py session_20250716_002557
```

**Common Causes**:
- LLM didn't detect popup
- `detect_popup_presence()` returned False
- Bug in main workflow integration

### Example 2: Popup Dismisser Hangs
```bash
# Check for hanging attempts
uv run analysis_scripts/analyze_execution_flow.py session_20250716_002557

# Look for missing debug phases
uv run analysis_scripts/comprehensive_analysis.py session_20250716_002557
```

**Common Causes**:
- Screenshot capture timeout
- Browser interaction failure
- Strategy loop never reached

### Example 3: Strategies Execute But Popup Remains
```bash
# Check strategy execution logs
uv run analysis_scripts/analyze_popup_logs.py session_20250716_002557

# Compare coordinates
uv run analysis_scripts/analyze_popup_logs.py session_20250716_002557 | grep -A 10 "COORDINATE ANALYSIS"
```

**Common Causes**:
- Wrong click coordinates
- Popup element changed after detection
- Verification selectors don't match popup structure

## 🔄 Session Comparison for Debugging

When implementing fixes, use session comparison to verify improvements:

```bash
# Compare before and after implementing fixes
uv run analysis_scripts/compare_sessions.py session_20250715_232742 session_20250716_002557
```

This will show:
- Changes in PopupDismisser completion rates
- New debug phases being logged
- Improvements in strategy execution
- Coordinate accuracy changes

## 📈 Monitoring Progress

Use the comprehensive analysis to track overall health:

```bash
# Generate HTML report to visualize progress
uv run analysis_scripts/generate_html_report.py

# Export to CSV for trend analysis
uv run analysis_scripts/generate_session_csv.py
```

## 🎯 Quick Reference

| Issue | First Script to Run | Key Indicators |
|-------|-------------------|----------------|
| No popup detected | `analyze_llm_responses.py` | Zero popup detections |
| Dismisser never starts | `analyze_execution_flow.py` | No `dismiss_popup_start` events |
| Dismisser hangs | `analyze_execution_flow.py` | Start events but no completions |
| Strategies fail | `analyze_popup_logs.py` | No strategy execution logs |
| Coordinates wrong | `analyze_popup_logs.py` | Coordinate mismatch analysis |
| Overall health | `comprehensive_analysis.py` | Root cause summary |