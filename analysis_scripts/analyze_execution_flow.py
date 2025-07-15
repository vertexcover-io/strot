#!/usr/bin/env python3
"""
Execution Flow Analyzer for PopupDismisser Debug Tracking
Analyzes execution_flow.jsonl to track PopupDismisser lifecycle and identify hang points
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

class ExecutionFlowAnalyzer:
    def __init__(self, session_dir: str):
        self.session_dir = Path(session_dir)
        self.execution_flow_file = self.session_dir / 'execution_flow.jsonl'
        
    def parse_execution_flow(self) -> List[Dict[str, Any]]:
        """Parse execution_flow.jsonl into structured events."""
        if not self.execution_flow_file.exists():
            return []
        
        events = []
        with open(self.execution_flow_file) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    event = json.loads(line.strip())
                    event['line_number'] = line_num
                    events.append(event)
                except json.JSONDecodeError as e:
                    print(f"Warning: Could not parse line {line_num}: {e}")
        
        return events
    
    def analyze_popup_dismisser_lifecycle(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze PopupDismisser start/complete pairs to find incomplete attempts."""
        popup_events = [e for e in events if 'PopupDismisser' in e.get('component', '')]
        
        lifecycle_analysis = {
            'total_popup_events': len(popup_events),
            'start_events': [],
            'complete_events': [],
            'incomplete_attempts': [],
            'successful_completions': [],
            'hanging_attempts': []
        }
        
        start_events = []
        complete_events = []
        
        for event in popup_events:
            action = event.get('action', '')
            if action == 'dismiss_popup_start':
                start_events.append(event)
                lifecycle_analysis['start_events'].append(event)
            elif action == 'dismiss_popup_complete':
                complete_events.append(event)
                lifecycle_analysis['complete_events'].append(event)
        
        # Match start events with complete events
        unmatched_starts = start_events.copy()
        
        for complete_event in complete_events:
            # Find matching start event (closest preceding start)
            complete_time = datetime.fromisoformat(complete_event['timestamp'].replace('Z', '+00:00'))
            
            matching_start = None
            for start_event in unmatched_starts:
                start_time = datetime.fromisoformat(start_event['timestamp'].replace('Z', '+00:00'))
                if start_time < complete_time:
                    if matching_start is None or start_time > datetime.fromisoformat(matching_start['timestamp'].replace('Z', '+00:00')):
                        matching_start = start_event
            
            if matching_start:
                unmatched_starts.remove(matching_start)
                lifecycle_analysis['successful_completions'].append({
                    'start': matching_start,
                    'complete': complete_event,
                    'duration_seconds': (complete_time - datetime.fromisoformat(matching_start['timestamp'].replace('Z', '+00:00'))).total_seconds()
                })
        
        # Remaining unmatched starts are hanging attempts
        lifecycle_analysis['hanging_attempts'] = unmatched_starts
        lifecycle_analysis['incomplete_attempts'] = unmatched_starts  # Same thing
        
        return lifecycle_analysis
    
    def find_detailed_popup_logs(self) -> List[Dict[str, Any]]:
        """Search all session files for detailed popup-dismissal logs."""
        popup_logs = []
        
        # Search through all JSON files in the session
        for json_file in self.session_dir.rglob('*.json'):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                    
                # Check if this file contains popup logs
                if self._contains_popup_logs(data):
                    popup_logs.append({
                        'file': str(json_file.relative_to(self.session_dir)),
                        'data': data,
                        'popup_entries': self._extract_popup_entries(data)
                    })
            except (json.JSONDecodeError, Exception):
                continue
        
        return popup_logs
    
    def _contains_popup_logs(self, data: Any) -> bool:
        """Check if data contains popup-dismissal logs."""
        if isinstance(data, dict):
            for key, value in data.items():
                if 'popup' in str(key).lower() or 'popup' in str(value).lower():
                    return True
                if self._contains_popup_logs(value):
                    return True
        elif isinstance(data, list):
            for item in data:
                if self._contains_popup_logs(item):
                    return True
        elif isinstance(data, str):
            return 'popup-dismissal' in data or 'click_outside' in data or 'explicit_close' in data
        
        return False
    
    def _extract_popup_entries(self, data: Any) -> List[str]:
        """Extract popup-related log entries from data."""
        entries = []
        
        def extract_recursive(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    if isinstance(value, str) and ('popup-dismissal' in value or 'click_outside' in value):
                        entries.append(f"{new_path}: {value}")
                    extract_recursive(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    extract_recursive(item, f"{path}[{i}]")
        
        extract_recursive(data)
        return entries
    
    def analyze_debug_log_coverage(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze which debug log phases are present/missing."""
        expected_phases = [
            'taking_before_screenshot',
            'screenshot_phase_complete', 
            'entering_strategy_loop',
            'strategy_loop_complete',
            'running_final_verification',
            'result="completed"'
        ]
        
        found_phases = set()
        missing_phases = []
        
        # Check execution flow for popup dismisser events
        for event in events:
            component = event.get('component', '')
            action = event.get('action', '')
            
            if 'popup' in component.lower():
                for phase in expected_phases:
                    if phase in action:
                        found_phases.add(phase)
        
        # Find missing phases
        for phase in expected_phases:
            if phase not in found_phases:
                missing_phases.append(phase)
        
        return {
            'expected_phases': expected_phases,
            'found_phases': list(found_phases),
            'missing_phases': missing_phases,
            'coverage_percentage': (len(found_phases) / len(expected_phases)) * 100
        }
    
    def generate_diagnostic_report(self) -> str:
        """Generate comprehensive diagnostic report."""
        events = self.parse_execution_flow()
        lifecycle = self.analyze_popup_dismisser_lifecycle(events)
        popup_logs = self.find_detailed_popup_logs()
        debug_coverage = self.analyze_debug_log_coverage(events)
        
        report = []
        report.append("=" * 70)
        report.append("EXECUTION FLOW ANALYSIS REPORT")
        report.append("=" * 70)
        report.append("")
        
        # Executive Summary
        report.append("🔍 EXECUTIVE SUMMARY:")
        report.append(f"- Total PopupDismisser events: {lifecycle['total_popup_events']}")
        report.append(f"- Start attempts: {len(lifecycle['start_events'])}")
        report.append(f"- Completed attempts: {len(lifecycle['complete_events'])}")
        report.append(f"- 🚨 HANGING attempts: {len(lifecycle['hanging_attempts'])}")
        report.append(f"- Debug log coverage: {debug_coverage['coverage_percentage']:.1f}%")
        report.append("")
        
        # Hanging Analysis
        if lifecycle['hanging_attempts']:
            report.append("🚨 HANGING DISMISSAL ATTEMPTS:")
            for i, attempt in enumerate(lifecycle['hanging_attempts'], 1):
                report.append(f"{i}. Started at: {attempt['timestamp']}")
                report.append(f"   Line: {attempt.get('line_number', 'unknown')}")
                report.append(f"   Details: {attempt.get('details', {})}")
                report.append("")
            
            report.append("💡 DIAGNOSIS:")
            report.append("PopupDismisser starts but never completes - likely hanging in:")
            for phase in debug_coverage['missing_phases']:
                report.append(f"- {phase}")
            report.append("")
        
        # Successful Completions
        if lifecycle['successful_completions']:
            report.append("✅ SUCCESSFUL COMPLETIONS:")
            for completion in lifecycle['successful_completions']:
                report.append(f"Duration: {completion['duration_seconds']:.2f}s")
                start_details = completion['start'].get('details', {})
                complete_details = completion['complete'].get('details', {})
                report.append(f"Success: {complete_details.get('success', 'unknown')}")
                report.append(f"Strategy: {complete_details.get('successful_strategy', 'unknown')}")
                report.append("")
        
        # Debug Log Analysis
        report.append("🔧 DEBUG LOG ANALYSIS:")
        report.append(f"Found phases: {', '.join(debug_coverage['found_phases'])}")
        report.append(f"Missing phases: {', '.join(debug_coverage['missing_phases'])}")
        report.append("")
        
        # Detailed Popup Logs
        if popup_logs:
            report.append("📋 DETAILED POPUP LOGS FOUND:")
            for log_info in popup_logs:
                report.append(f"File: {log_info['file']}")
                report.append(f"Entries: {len(log_info['popup_entries'])}")
                for entry in log_info['popup_entries'][:3]:  # Show first 3 entries
                    report.append(f"  - {entry}")
                if len(log_info['popup_entries']) > 3:
                    report.append(f"  ... and {len(log_info['popup_entries']) - 3} more")
                report.append("")
        else:
            report.append("❌ NO DETAILED POPUP LOGS FOUND")
            report.append("This confirms PopupDismisser never reaches strategy execution")
            report.append("")
        
        # Recommendations
        report.append("🎯 RECOMMENDED ACTIONS:")
        if lifecycle['hanging_attempts']:
            report.append("1. Check for screenshot timeout issues")
            report.append("2. Add exception handling around screenshot capture")
            report.append("3. Verify page state before dismissal attempts")
            
        if 'taking_before_screenshot' not in debug_coverage['found_phases']:
            report.append("4. PopupDismisser hangs before screenshot phase")
            
        if 'entering_strategy_loop' not in debug_coverage['found_phases']:
            report.append("5. Issue is in presence check or screenshot capture")
        
        return "\n".join(report)

def main():
    import sys
    
    if len(sys.argv) > 1:
        session_name = sys.argv[1]
        if not session_name.startswith('session_'):
            session_name = f'session_{session_name}'
        session_dir = f'logs/{session_name}'
    else:
        import os
        sessions = [d for d in os.listdir('logs') if d.startswith('session_')]
        print("Available sessions:")
        for session in sorted(sessions):
            print(f"  {session}")
        print("\nUsage: python analyze_execution_flow.py <session_name>")
        print("Example: python analyze_execution_flow.py session_20250716_002557")
        return
    
    analyzer = ExecutionFlowAnalyzer(session_dir)
    print(analyzer.generate_diagnostic_report())

if __name__ == '__main__':
    main()