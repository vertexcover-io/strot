#!/bin/bash

# Master Analysis Runner Script
# Runs all analysis scripts in the correct order with enhanced debug tracking

echo "🔍 RUNNING ENHANCED SESSION ANALYSIS"
echo "====================================="
echo

# Configuration
OLD_SESSION="logs/session_20250715_232742"
NEW_SESSION="logs/session_20250715_235753"

# Make scripts executable
chmod +x analysis_scripts/*.sh
chmod +x analysis_scripts/*.py

echo "📋 ANALYSIS TARGET SESSIONS:"
echo "- Old session (baseline): $OLD_SESSION"
echo "- New session (with fixes): $NEW_SESSION"
echo

echo "1️⃣  BASIC STRUCTURE ANALYSIS"
echo "----------------------------"
./analysis_scripts/analyze_session_basic.sh
echo
echo "Press Enter to continue..."
read

echo "2️⃣  EXECUTION FLOW ANALYSIS (NEW)"
echo "--------------------------------"
echo "Analyzing PopupDismisser start/complete tracking..."
uv run analysis_scripts/analyze_execution_flow.py $NEW_SESSION
echo
echo "Press Enter to continue..."
read

echo "3️⃣  POPUP LOGS DEEP DIVE (NEW)"
echo "-----------------------------"
echo "Searching ALL session files for popup dismissal logs..."
uv run analysis_scripts/analyze_popup_logs.py $NEW_SESSION
echo
echo "Press Enter to continue..."
read

echo "4️⃣  SESSION COMPARISON (NEW)"
echo "---------------------------"
echo "Comparing old vs new session to identify changes..."
uv run analysis_scripts/compare_sessions.py $OLD_SESSION $NEW_SESSION
echo
echo "Press Enter to continue..."
read

echo "5️⃣  LLM RESPONSES ANALYSIS"
echo "--------------------------"
uv run analysis_scripts/analyze_llm_responses.py
echo
echo "Press Enter to continue..."
read

echo "6️⃣  POPUP DISMISSAL VERIFICATION"
echo "--------------------------------"
./analysis_scripts/check_popup_dismissal.sh
echo
echo "Press Enter to continue..."
read

echo "7️⃣  COMPREHENSIVE ROOT CAUSE ANALYSIS"
echo "------------------------------------"
uv run analysis_scripts/comprehensive_analysis.py
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