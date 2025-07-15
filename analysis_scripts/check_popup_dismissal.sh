#!/bin/bash

# Popup Dismissal Verification Script
SESSION_DIR="logs/session_20250715_232742"

echo "=== POPUP DISMISSAL ANALYSIS ==="
echo

# 1. Check if popup dismissal logs exist
echo "=== POPUP DISMISSAL LOGS ==="
popup_dir="$SESSION_DIR/popup"
if [ -d "$popup_dir" ]; then
    file_count=$(find "$popup_dir" -type f | wc -l)
    echo "Popup log files found: $file_count"
    
    if [ $file_count -eq 0 ]; then
        echo "🚨 CRITICAL ISSUE: NO POPUP DISMISSAL LOGS!"
        echo "   This means PopupDismisser.dismiss_popup() was never called"
        echo "   OR it failed silently without logging"
    else
        echo "✅ Popup dismissal logs found:"
        ls -la "$popup_dir"
    fi
else
    echo "❌ Popup directory doesn't exist: $popup_dir"
fi
echo

# 2. Check if any response has popup data
echo "=== POPUP DETECTION IN LLM RESPONSES ==="
llm_dir="$SESSION_DIR/llm_calls"
popup_responses=0

for file in "$llm_dir"/*_response.json; do
    if [ -f "$file" ]; then
        if grep -q "popup_element_point.*[0-9]" "$file"; then
            popup_responses=$((popup_responses + 1))
            response_num=$(basename "$file" | cut -d'_' -f1)
            echo "✅ Response $response_num: Popup detected"
            
            # Extract popup coordinates
            popup_point=$(grep -o '"popup_element_point": *{[^}]*}' "$file" | head -1)
            popup_type=$(grep -o '"popup_type": *"[^"]*"' "$file" | cut -d'"' -f4)
            echo "   Type: $popup_type"
            echo "   Close button: $popup_point"
        fi
    fi
done

echo
echo "Total responses with popup detection: $popup_responses"
echo

# 3. Verify popup persistence by checking screenshots
echo "=== POPUP PERSISTENCE CHECK ==="
screenshot_dir="$SESSION_DIR/screenshots"
if [ -d "$screenshot_dir" ]; then
    first_screenshot="$screenshot_dir/002_llm_analysis.png"
    last_screenshot="$screenshot_dir/025_llm_analysis.png"
    
    if [ -f "$first_screenshot" ] && [ -f "$last_screenshot" ]; then
        first_size=$(stat -c%s "$first_screenshot")
        last_size=$(stat -c%s "$last_screenshot")
        
        echo "First screenshot (002): $first_size bytes"
        echo "Last screenshot (025): $last_size bytes"
        
        if [ "$first_size" -eq "$last_size" ]; then
            echo "🚨 IDENTICAL SIZES: Popup likely never dismissed!"
        else
            echo "✅ Different sizes: Some change occurred"
        fi
        
        # Use diff to compare (will show if identical)
        if diff -q "$first_screenshot" "$last_screenshot" > /dev/null 2>&1; then
            echo "🚨 SCREENSHOTS IDENTICAL: Popup definitely not dismissed!"
        else
            echo "✅ Screenshots different: Some visual change occurred"
        fi
    fi
fi
echo

# 4. Check debug session logs for popup dismissal calls
echo "=== DEBUG SESSION ANALYSIS ==="
if [ -d "$SESSION_DIR" ]; then
    # Look for any files that might contain popup dismissal logs
    echo "Searching for popup-related debug logs..."
    find "$SESSION_DIR" -type f -name "*.json" -exec grep -l "popup.*dismiss\|PopupDismisser\|popup_dismissed" {} \; 2>/dev/null | head -5
    
    # Check if debug session captured popup dismissal events
    find "$SESSION_DIR" -type f -name "*.json" -exec grep -l "popup_dismissal\|popup_handling" {} \; 2>/dev/null | head -5
fi
echo

echo "=== ROOT CAUSE ANALYSIS ==="
echo "Based on the evidence:"
echo

if [ $popup_responses -gt 0 ]; then
    echo "✅ LLM detected popup with coordinates"
else
    echo "❌ LLM never detected popup"
fi

popup_log_count=$(find "$popup_dir" -type f 2>/dev/null | wc -l)
if [ $popup_log_count -eq 0 ]; then
    echo "❌ NO popup dismissal attempts logged"
    echo
    echo "🔍 LIKELY CAUSES:"
    echo "1. detect_popup_presence() returned False (verification.py:130)"
    echo "2. PopupDismisser.dismiss_popup() was never called"
    echo "3. Popup detection logic failed to identify the notification popup"
    echo "4. Bug in dismisser.py:55-60 early exit logic"
else
    echo "✅ Popup dismissal was attempted"
fi
echo