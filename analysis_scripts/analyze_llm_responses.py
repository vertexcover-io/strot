#!/usr/bin/env python3
"""
LLM Response Analysis Script
Analyzes all LLM responses to extract popup detection patterns and insights
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any

def analyze_response_file(file_path: Path) -> Dict[str, Any]:
    """Analyze a single LLM response file."""
    try:
        with open(file_path) as f:
            data = json.load(f)
        
        # Extract completion data
        completion_str = data.get('completion', '{}')
        try:
            completion = json.loads(completion_str)
        except json.JSONDecodeError:
            completion = {}
        
        analysis = {
            'file': file_path.name,
            'input_tokens': data.get('input_tokens', 0),
            'output_tokens': data.get('output_tokens', 0),
            'keywords': completion.get('keywords', []),
            'keywords_count': len(completion.get('keywords', [])),
            'popup_element_point': completion.get('popup_element_point'),
            'popup_area': completion.get('popup_area'),
            'background_overlay_point': completion.get('background_overlay_point'),
            'popup_type': completion.get('popup_type'),
            'navigation_element_point': completion.get('navigation_element_point'),
            'has_popup_data': any([
                completion.get('popup_element_point'),
                completion.get('popup_area'),
                completion.get('background_overlay_point'),
                completion.get('popup_type')
            ])
        }
        
        return analysis
    except Exception as e:
        return {
            'file': file_path.name,
            'error': str(e),
            'has_popup_data': False
        }

def main():
    import sys
    
    if len(sys.argv) > 1:
        session_name = sys.argv[1]
        if not session_name.startswith('session_'):
            session_name = f'session_{session_name}'
        session_dir = Path(f'logs/{session_name}')
    else:
        import os
        sessions = [d for d in os.listdir('logs') if d.startswith('session_')]
        print("Available sessions:")
        for session in sorted(sessions):
            print(f"  {session}")
        print("\nUsage: python analyze_llm_responses.py <session_name>")
        print("Example: python analyze_llm_responses.py session_20250716_002557")
        return
    
    llm_calls_dir = session_dir / 'llm_calls'
    
    if not llm_calls_dir.exists():
        print(f"❌ Directory not found: {llm_calls_dir}")
        return
    
    print("=== LLM RESPONSES ANALYSIS ===")
    print(f"Analyzing directory: {llm_calls_dir}")
    print()
    
    # Get all response files
    response_files = sorted(llm_calls_dir.glob('*_response.json'))
    
    print(f"Found {len(response_files)} response files")
    print()
    
    # Analyze each response
    analyses = []
    popup_detections = []
    
    for file_path in response_files:
        analysis = analyze_response_file(file_path)
        analyses.append(analysis)
        
        if analysis.get('has_popup_data'):
            popup_detections.append(analysis)
    
    # Summary
    print("=== SUMMARY ===")
    print(f"Total responses: {len(analyses)}")
    print(f"Responses with popup data: {len(popup_detections)}")
    print(f"Responses with keywords: {sum(1 for a in analyses if a.get('keywords_count', 0) > 0)}")
    print()
    
    # Popup detection analysis
    if popup_detections:
        print("=== POPUP DETECTIONS ===")
        for detection in popup_detections:
            print(f"File: {detection['file']}")
            print(f"  Popup type: {detection.get('popup_type', 'None')}")
            print(f"  Close button: {detection.get('popup_element_point', 'None')}")
            print(f"  Popup area: {detection.get('popup_area', 'None')}")
            print(f"  Background point: {detection.get('background_overlay_point', 'None')}")
            print(f"  Keywords found: {detection.get('keywords_count', 0)}")
            print()
    else:
        print("❌ NO POPUP DETECTIONS FOUND!")
    
    # Keywords timeline
    print("=== KEYWORDS TIMELINE ===")
    for analysis in analyses[:10]:  # First 10 responses
        if 'error' in analysis:
            print(f"{analysis['file']}: ERROR - {analysis['error']}")
        else:
            keywords = analysis.get('keywords', [])
            print(f"{analysis['file']}: {len(keywords)} keywords - {keywords[:3]}{'...' if len(keywords) > 3 else ''}")
    
    print()
    
    # Critical findings
    print("=== CRITICAL FINDINGS ===")
    
    # Check if first response has popup
    if analyses and analyses[0].get('has_popup_data'):
        print("✅ First response detected popup")
    else:
        print("❌ First response did NOT detect popup")
    
    # Check if popup persists
    popup_in_later_responses = sum(1 for a in analyses[3:] if a.get('has_popup_data'))
    if popup_in_later_responses > 0:
        print(f"🚨 POPUP PERSISTS: Found in {popup_in_later_responses} later responses")
        print("   This confirms popup was never dismissed!")
    
    # Token usage
    total_input = sum(a.get('input_tokens', 0) for a in analyses if 'error' not in a)
    total_output = sum(a.get('output_tokens', 0) for a in analyses if 'error' not in a)
    print(f"Total tokens used: {total_input + total_output} (input: {total_input}, output: {total_output})")

if __name__ == '__main__':
    main()