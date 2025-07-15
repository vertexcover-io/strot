#!/bin/bash

# Master Analysis Runner Script
# Runs all analysis scripts in the correct order with enhanced debug tracking

echo "🔍 RUNNING ENHANCED SESSION ANALYSIS"
echo "====================================="
echo

# Configuration
if [ $# -eq 0 ]; then
    echo "Available sessions:"
    ls -1 logs/ | grep ^session_ | sort
    echo
    echo "Usage: $0 <session_name> [old_session_name]"
    echo "Example: $0 session_20250716_002557"
    echo "Example: $0 session_20250716_002557 session_20250715_232742"
    exit 1
fi

SESSION_NAME="$1"
if [[ ! "$SESSION_NAME" =~ ^session_ ]]; then
    SESSION_NAME="session_$SESSION_NAME"
fi
NEW_SESSION="logs/$SESSION_NAME"

if [ ! -d "$NEW_SESSION" ]; then
    echo "Session directory not found: $NEW_SESSION"
    exit 1
fi

# Optional old session for comparison
if [ $# -eq 2 ]; then
    OLD_SESSION_NAME="$2"
    if [[ ! "$OLD_SESSION_NAME" =~ ^session_ ]]; then
        OLD_SESSION_NAME="session_$OLD_SESSION_NAME"
    fi
    OLD_SESSION="logs/$OLD_SESSION_NAME"
else
    OLD_SESSION="" # Will skip comparison if not provided
fi

# Make scripts executable
chmod +x analysis_scripts/*.sh
chmod +x analysis_scripts/*.py

echo "📋 ANALYSIS TARGET SESSION:"
echo "- Target session: $NEW_SESSION"
if [ -n "$OLD_SESSION" ]; then
    echo "- Comparison session: $OLD_SESSION"
fi
echo

echo "1️⃣  BASIC STRUCTURE ANALYSIS"
echo "----------------------------"
./analysis_scripts/analyze_session_basic.sh "$SESSION_NAME"
echo
echo "=================================="
echo

echo "2️⃣  EXECUTION FLOW ANALYSIS (NEW)"
echo "--------------------------------"
echo "Analyzing PopupDismisser start/complete tracking..."
uv run analysis_scripts/analyze_execution_flow.py "$SESSION_NAME"
echo
echo "=================================="
echo

echo "3️⃣  POPUP LOGS DEEP DIVE (NEW)"
echo "-----------------------------"
echo "Searching ALL session files for popup dismissal logs..."
uv run analysis_scripts/analyze_popup_logs.py "$SESSION_NAME"
echo
echo "=================================="
echo

echo "4️⃣  SESSION COMPARISON (NEW)"
echo "---------------------------"
if [ -n "$OLD_SESSION" ]; then
    echo "Comparing old vs new session to identify changes..."
    uv run analysis_scripts/compare_sessions.py "$OLD_SESSION" "$NEW_SESSION"
else
    echo "Skipping comparison - no old session specified"
fi
echo
echo "=================================="
echo

echo "5️⃣  LLM RESPONSES ANALYSIS"
echo "--------------------------"
uv run analysis_scripts/analyze_llm_responses.py "$SESSION_NAME"
echo
echo "=================================="
echo

echo "6️⃣  POPUP DISMISSAL VERIFICATION"
echo "--------------------------------"
./analysis_scripts/check_popup_dismissal.sh "$SESSION_NAME"
echo
echo "=================================="
echo

echo "7️⃣  COMPREHENSIVE ROOT CAUSE ANALYSIS"
echo "------------------------------------"
uv run analysis_scripts/comprehensive_analysis.py "$SESSION_NAME"
echo

echo "✅ ENHANCED ANALYSIS COMPLETE!"
echo
echo "🔧 KEY FINDINGS TO LOOK FOR:"
echo "- Execution flow: Does PopupDismisser start but never complete?"
echo "- Debug phases: Which debug log phases are missing?"
echo "- Strategy execution: Are any strategies being called?"
echo "- Coordinate accuracy: Are LLM coordinates being used correctly?"
echo "- Session improvements: What changed between old and new sessions?"
echo
echo "📁 Enhanced Analysis Scripts:"
echo "   📊 analyze_execution_flow.py    - PopupDismisser lifecycle tracking"
echo "   🔍 analyze_popup_logs.py        - Deep search for all popup logs"
echo "   📈 compare_sessions.py          - Old vs new session comparison"
echo "   📋 analyze_session_basic.sh     - Directory structure analysis"
echo "   🤖 analyze_llm_responses.py     - LLM response patterns"  
echo "   ✅ check_popup_dismissal.sh     - Dismissal verification"
echo "   🎯 comprehensive_analysis.py    - Root cause analysis"
echo
echo "🎯 DIAGNOSIS WORKFLOW:"
echo "1. Check execution flow for hanging PopupDismisser attempts"
echo "2. Identify which debug phase is missing (screenshot, strategy loop, etc.)"
echo "3. Compare sessions to see if debug improvements are working"
echo "4. Look for actual strategy execution logs vs just starts"
echo "5. Verify coordinates are being passed correctly to strategies"