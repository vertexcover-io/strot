#!/usr/bin/env python3
"""
Generate CSV report from Ayejax session logs for analysis.
Provides URL, tag info, and detailed stage breakdown for each session.
"""

import json
import csv
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

def parse_session_json(session_path: Path) -> Optional[Dict[str, Any]]:
    """Parse session.json file if it exists."""
    session_file = session_path / "session.json"
    if session_file.exists():
        try:
            with open(session_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None
    return None

def parse_timeline_json(session_path: Path) -> List[Dict[str, Any]]:
    """Parse timeline.json file if it exists."""
    timeline_file = session_path / "timeline.json"
    if timeline_file.exists():
        try:
            with open(timeline_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def parse_execution_flow(session_path: Path) -> List[Dict[str, Any]]:
    """Parse execution_flow.jsonl file if it exists."""
    flow_file = session_path / "execution_flow.jsonl"
    flow_data = []
    if flow_file.exists():
        try:
            with open(flow_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        flow_data.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return flow_data

def count_files_in_directory(session_path: Path, subdir: str) -> int:
    """Count files in a specific subdirectory."""
    dir_path = session_path / subdir
    if dir_path.exists() and dir_path.is_dir():
        return len([f for f in dir_path.iterdir() if f.is_file()])
    return 0

def extract_popup_info(session_path: Path) -> Dict[str, Any]:
    """Extract popup dismissal information from popup directory."""
    popup_dir = session_path / "popup"
    popup_info = {
        'total_popup_files': 0,
        'popup_debug_files': 0,
        'popup_dismissal_files': 0,
        'popup_types': []
    }
    
    if popup_dir.exists() and popup_dir.is_dir():
        popup_files = list(popup_dir.glob("*.json"))
        popup_info['total_popup_files'] = len(popup_files)
        
        for popup_file in popup_files:
            if 'debug' in popup_file.name:
                popup_info['popup_debug_files'] += 1
            elif 'dismissal' in popup_file.name:
                popup_info['popup_dismissal_files'] += 1
                
            # Try to extract popup type from the file
            try:
                with open(popup_file, 'r') as f:
                    popup_data = json.load(f)
                    if isinstance(popup_data, dict) and 'popup_type' in popup_data:
                        popup_type = popup_data['popup_type']
                        if popup_type and popup_type not in popup_info['popup_types']:
                            popup_info['popup_types'].append(popup_type)
            except:
                pass
    
    return popup_info

def analyze_session(session_path: Path) -> Dict[str, Any]:
    """Analyze a single session directory and extract key information."""
    session_id = session_path.name
    
    # Parse session data
    session_data = parse_session_json(session_path)
    timeline_data = parse_timeline_json(session_path)
    execution_flow = parse_execution_flow(session_path)
    
    # Count various file types
    screenshot_count = count_files_in_directory(session_path, "screenshots")
    llm_call_count = count_files_in_directory(session_path, "llm_calls")
    network_count = count_files_in_directory(session_path, "network")
    
    # Extract popup information
    popup_info = extract_popup_info(session_path)
    
    # Extract basic session info
    url = session_data.get('url', 'Unknown') if session_data else 'Unknown'
    tag = str(session_data.get('tag', 'Unknown')) if session_data else 'Unknown'
    start_time = session_data.get('startTime', 'Unknown') if session_data else 'Unknown'
    end_time = session_data.get('endTime', 'Unknown') if session_data else 'Unknown'
    status = session_data.get('status', 'Unknown') if session_data else 'Unknown'
    total_steps = session_data.get('totalSteps', 0) if session_data else 0
    
    # Calculate session duration
    duration_seconds = 0
    if session_data and start_time != 'Unknown' and end_time != 'Unknown':
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            duration_seconds = (end_dt - start_dt).total_seconds()
        except:
            pass
    
    # Analyze stages from timeline
    stages = []
    popup_dismissal_attempts = 0
    llm_analysis_count = 0
    
    for step in timeline_data:
        action = step.get('action', '')
        step_status = step.get('status', '')
        
        if action == 'popup_dismissal':
            popup_dismissal_attempts += 1
        elif action == 'llm_analysis':
            llm_analysis_count += 1
            
        stages.append(f"{action}:{step_status}")
    
    # Extract final result status
    has_final_result = bool(session_data.get('finalResult')) if session_data else False
    error_info = session_data.get('error') if session_data else None
    
    return {
        'session_id': session_id,
        'url': url,
        'tag': tag.split("'")[1].split('/')[-1] if "'" in tag else tag,  # Clean up tag path
        'start_time': start_time,
        'end_time': end_time,
        'duration_seconds': round(duration_seconds, 2),
        'status': status,
        'total_steps': total_steps,
        'screenshot_count': screenshot_count,
        'llm_call_count': llm_call_count // 2,  # Each call has request/response pair
        'network_count': network_count,
        'popup_dismissal_attempts': popup_dismissal_attempts,
        'llm_analysis_count': llm_analysis_count,
        'popup_files_total': popup_info['total_popup_files'],
        'popup_debug_files': popup_info['popup_debug_files'],
        'popup_dismissal_files': popup_info['popup_dismissal_files'],
        'popup_types': ','.join(popup_info['popup_types']) if popup_info['popup_types'] else '',
        'has_final_result': has_final_result,
        'has_error': bool(error_info),
        'error_message': str(error_info) if error_info else '',
        'stages_summary': ' → '.join(stages[:10]),  # First 10 stages
        'execution_flow_events': len(execution_flow)
    }

def generate_csv_report(logs_dir: Path, output_file: Path):
    """Generate CSV report from all session logs."""
    session_dirs = [d for d in logs_dir.iterdir() if d.is_dir() and d.name.startswith('session_')]
    session_dirs.sort(key=lambda x: x.name)
    
    all_sessions = []
    for session_dir in session_dirs:
        try:
            session_info = analyze_session(session_dir)
            all_sessions.append(session_info)
        except Exception as e:
            print(f"Error analyzing {session_dir.name}: {e}")
            continue
    
    if not all_sessions:
        print("No session data found")
        return
    
    # Define CSV columns
    fieldnames = [
        'session_id', 'url', 'tag', 'start_time', 'end_time', 'duration_seconds',
        'status', 'total_steps', 'screenshot_count', 'llm_call_count', 'network_count',
        'popup_dismissal_attempts', 'llm_analysis_count', 'popup_files_total',
        'popup_debug_files', 'popup_dismissal_files', 'popup_types',
        'has_final_result', 'has_error', 'error_message', 'stages_summary',
        'execution_flow_events'
    ]
    
    # Write CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_sessions)
    
    print(f"CSV report generated: {output_file}")
    print(f"Total sessions analyzed: {len(all_sessions)}")

def main():
    if len(sys.argv) > 1:
        logs_dir = Path(sys.argv[1])
    else:
        # Default to logs directory relative to script location
        script_dir = Path(__file__).parent
        logs_dir = script_dir.parent / "logs"
    
    if not logs_dir.exists():
        print(f"Logs directory not found: {logs_dir}")
        sys.exit(1)
    
    output_file = logs_dir.parent / "session_analysis.csv"
    generate_csv_report(logs_dir, output_file)

if __name__ == "__main__":
    main()