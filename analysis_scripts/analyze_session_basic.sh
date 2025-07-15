#!/bin/bash

# Basic Session Log Analysis Script
if [ $# -eq 0 ]; then
    echo "Available sessions:"
    ls -1 logs/ | grep ^session_ | sort
    echo
    echo "Usage: $0 <session_name>"
    echo "Example: $0 session_20250716_002557"
    exit 1
fi

SESSION_NAME="$1"
if [[ ! "$SESSION_NAME" =~ ^session_ ]]; then
    SESSION_NAME="session_$SESSION_NAME"
fi
SESSION_DIR="logs/$SESSION_NAME"

if [ ! -d "$SESSION_DIR" ]; then
    echo "Session directory not found: $SESSION_DIR"
    exit 1
fi

echo "=== SESSION LOG ANALYSIS ==="
echo "Session Directory: $SESSION_DIR"
echo

# Check directory structure
echo "=== DIRECTORY STRUCTURE ==="
find "$SESSION_DIR" -type d | sort
echo

# Count files in each directory
echo "=== FILE COUNTS ==="
for dir in "$SESSION_DIR"/*; do
    if [ -d "$dir" ]; then
        count=$(find "$dir" -type f | wc -l)
        echo "$(basename "$dir"): $count files"
    fi
done
echo

# Check for empty directories (critical issue)
echo "=== EMPTY DIRECTORIES (CRITICAL) ==="
for dir in "$SESSION_DIR"/*; do
    if [ -d "$dir" ]; then
        count=$(find "$dir" -type f | wc -l)
        if [ $count -eq 0 ]; then
            echo "❌ EMPTY: $(basename "$dir")"
        else
            echo "✅ HAS FILES: $(basename "$dir")"
        fi
    fi
done
echo

# LLM calls analysis
echo "=== LLM CALLS SUMMARY ==="
if [ -d "$SESSION_DIR/llm_calls" ]; then
    request_count=$(find "$SESSION_DIR/llm_calls" -name "*request.json" | wc -l)
    response_count=$(find "$SESSION_DIR/llm_calls" -name "*response.json" | wc -l)
    echo "Requests: $request_count"
    echo "Responses: $response_count"
    
    # Check if first few responses contain popup data
    echo
    echo "=== FIRST FEW RESPONSES (popup detection) ==="
    for i in {002..005}; do
        file="$SESSION_DIR/llm_calls/${i}_response.json"
        if [ -f "$file" ]; then
            echo "--- Response $i ---"
            if grep -q "popup_element_point" "$file"; then
                echo "✅ Contains popup_element_point"
            else
                echo "❌ No popup_element_point"
            fi
            if grep -q "popup_type" "$file"; then
                popup_type=$(grep "popup_type" "$file" | cut -d'"' -f4)
                echo "✅ Popup type: $popup_type"
            else
                echo "❌ No popup_type"
            fi
        fi
    done
fi
echo

# Screenshot analysis
echo "=== SCREENSHOTS TIMELINE ==="
if [ -d "$SESSION_DIR/screenshots" ]; then
    ls -la "$SESSION_DIR/screenshots/" | grep -E "\.png$" | head -10
fi
echo

echo "=== CRITICAL FINDINGS ==="
popup_files=$(find "$SESSION_DIR/popup" -type f | wc -l)
if [ $popup_files -eq 0 ]; then
    echo "🚨 CRITICAL: NO POPUP DISMISSAL LOGS FOUND!"
    echo "   This suggests popup dismisser never ran or failed silently"
fi

network_files=$(find "$SESSION_DIR/network" -type f | wc -l)
if [ $network_files -eq 0 ]; then
    echo "⚠️  WARNING: No network logs found"
fi

echo
echo "=== RECOMMENDED NEXT STEPS ==="
echo "1. Run analyze_llm_responses.py to check popup detection patterns"
echo "2. Check if popup dismisser code was actually called"
echo "3. Verify popup detection logic in verification.py"