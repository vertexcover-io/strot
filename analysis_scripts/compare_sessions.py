#!/usr/bin/env python3
"""
Session Comparison Tool
Compares old vs new sessions to highlight differences in execution flow and debug logs
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from analyze_execution_flow import ExecutionFlowAnalyzer
from analyze_popup_logs import PopupLogsAnalyzer

class SessionComparator:
    def __init__(self, old_session_dir: str, new_session_dir: str):
        self.old_session_dir = Path(old_session_dir)
        self.new_session_dir = Path(new_session_dir)
        
        self.old_analyzer = ExecutionFlowAnalyzer(str(self.old_session_dir))
        self.new_analyzer = ExecutionFlowAnalyzer(str(self.new_session_dir))
        
        self.old_popup_analyzer = PopupLogsAnalyzer(str(self.old_session_dir))
        self.new_popup_analyzer = PopupLogsAnalyzer(str(self.new_session_dir))
    
    def compare_execution_flows(self) -> Dict[str, Any]:
        """Compare execution flows between sessions."""
        old_events = self.old_analyzer.parse_execution_flow()
        new_events = self.new_analyzer.parse_execution_flow()
        
        old_lifecycle = self.old_analyzer.analyze_popup_dismisser_lifecycle(old_events)
        new_lifecycle = self.new_analyzer.analyze_popup_dismisser_lifecycle(new_events)
        
        comparison = {
            'old_session': {
                'total_events': len(old_events),
                'popup_start_events': len(old_lifecycle['start_events']),
                'popup_complete_events': len(old_lifecycle['complete_events']),
                'hanging_attempts': len(old_lifecycle['hanging_attempts'])
            },
            'new_session': {
                'total_events': len(new_events),
                'popup_start_events': len(new_lifecycle['start_events']),
                'popup_complete_events': len(new_lifecycle['complete_events']),
                'hanging_attempts': len(new_lifecycle['hanging_attempts'])
            },
            'differences': {
                'event_count_change': len(new_events) - len(old_events),
                'start_events_change': len(new_lifecycle['start_events']) - len(old_lifecycle['start_events']),
                'complete_events_change': len(new_lifecycle['complete_events']) - len(old_lifecycle['complete_events']),
                'hanging_change': len(new_lifecycle['hanging_attempts']) - len(old_lifecycle['hanging_attempts'])
            },
            'improvements': [],
            'regressions': []
        }
        
        # Analyze improvements/regressions
        if comparison['differences']['complete_events_change'] > 0:
            comparison['improvements'].append("More popup dismissal completions")
        elif comparison['differences']['complete_events_change'] < 0:
            comparison['regressions'].append("Fewer popup dismissal completions")
        
        if comparison['differences']['hanging_change'] < 0:
            comparison['improvements'].append("Fewer hanging attempts")
        elif comparison['differences']['hanging_change'] > 0:
            comparison['regressions'].append("More hanging attempts")
        
        return comparison
    
    def compare_popup_logs(self) -> Dict[str, Any]:
        """Compare popup logs between sessions."""
        old_logs = self.old_popup_analyzer.search_all_popup_logs()
        new_logs = self.new_popup_analyzer.search_all_popup_logs()
        
        comparison = {
            'old_session': {
                'files_with_logs': len(old_logs['files_with_popup_logs']),
                'total_entries': old_logs['total_popup_log_entries'],
                'strategy_executions': len(old_logs['strategy_executions']),
                'verification_attempts': len(old_logs['verification_attempts']),
                'errors': len(old_logs['errors_and_exceptions'])
            },
            'new_session': {
                'files_with_logs': len(new_logs['files_with_popup_logs']),
                'total_entries': new_logs['total_popup_log_entries'],
                'strategy_executions': len(new_logs['strategy_executions']),
                'verification_attempts': len(new_logs['verification_attempts']),
                'errors': len(new_logs['errors_and_exceptions'])
            },
            'differences': {
                'log_files_change': len(new_logs['files_with_popup_logs']) - len(old_logs['files_with_popup_logs']),
                'entries_change': new_logs['total_popup_log_entries'] - old_logs['total_popup_log_entries'],
                'strategy_change': len(new_logs['strategy_executions']) - len(old_logs['strategy_executions']),
                'verification_change': len(new_logs['verification_attempts']) - len(old_logs['verification_attempts']),
                'error_change': len(new_logs['errors_and_exceptions']) - len(old_logs['errors_and_exceptions'])
            }
        }
        
        return comparison
    
    def compare_debug_coverage(self) -> Dict[str, Any]:
        """Compare debug log coverage between sessions."""
        old_events = self.old_analyzer.parse_execution_flow()
        new_events = self.new_analyzer.parse_execution_flow()
        
        old_coverage = self.old_analyzer.analyze_debug_log_coverage(old_events)
        new_coverage = self.new_analyzer.analyze_debug_log_coverage(new_events)
        
        comparison = {
            'old_coverage': old_coverage['coverage_percentage'],
            'new_coverage': new_coverage['coverage_percentage'],
            'coverage_improvement': new_coverage['coverage_percentage'] - old_coverage['coverage_percentage'],
            'new_phases_found': list(set(new_coverage['found_phases']) - set(old_coverage['found_phases'])),
            'lost_phases': list(set(old_coverage['found_phases']) - set(new_coverage['found_phases'])),
            'still_missing': new_coverage['missing_phases']
        }
        
        return comparison
    
    def compare_llm_responses(self) -> Dict[str, Any]:
        """Compare LLM responses between sessions."""
        old_responses = self._get_llm_responses(self.old_session_dir)
        new_responses = self._get_llm_responses(self.new_session_dir)
        
        comparison = {
            'old_session': {
                'total_responses': len(old_responses),
                'popup_detections': sum(1 for r in old_responses if r.get('has_popup_data', False)),
                'keyword_responses': sum(1 for r in old_responses if r.get('keywords_count', 0) > 0)
            },
            'new_session': {
                'total_responses': len(new_responses),
                'popup_detections': sum(1 for r in new_responses if r.get('has_popup_data', False)),
                'keyword_responses': sum(1 for r in new_responses if r.get('keywords_count', 0) > 0)
            },
            'popup_coordinates_comparison': self._compare_popup_coordinates(old_responses, new_responses)
        }
        
        return comparison
    
    def _get_llm_responses(self, session_dir: Path) -> List[Dict[str, Any]]:
        """Extract LLM responses from session."""
        responses = []
        llm_calls_dir = session_dir / 'llm_calls'
        
        if not llm_calls_dir.exists():
            return responses
        
        for response_file in llm_calls_dir.glob('*_response.json'):
            try:
                with open(response_file) as f:
                    data = json.load(f)
                
                completion_str = data.get('completion', '{}')
                try:
                    completion = json.loads(completion_str)
                    
                    response_info = {
                        'file': response_file.name,
                        'keywords': completion.get('keywords', []),
                        'keywords_count': len(completion.get('keywords', [])),
                        'popup_element_point': completion.get('popup_element_point'),
                        'popup_area': completion.get('popup_area'),
                        'background_overlay_point': completion.get('background_overlay_point'),
                        'popup_type': completion.get('popup_type'),
                        'has_popup_data': any([
                            completion.get('popup_element_point'),
                            completion.get('popup_area'),
                            completion.get('background_overlay_point'),
                            completion.get('popup_type')
                        ])
                    }
                    responses.append(response_info)
                except json.JSONDecodeError:
                    continue
            except Exception:
                continue
        
        return responses
    
    def _compare_popup_coordinates(self, old_responses: List[Dict], new_responses: List[Dict]) -> Dict[str, Any]:
        """Compare popup coordinates between sessions."""
        old_coords = []
        new_coords = []
        
        for response in old_responses:
            if response['popup_element_point']:
                old_coords.append(response['popup_element_point'])
            if response['background_overlay_point']:
                old_coords.append(response['background_overlay_point'])
        
        for response in new_responses:
            if response['popup_element_point']:
                new_coords.append(response['popup_element_point'])
            if response['background_overlay_point']:
                new_coords.append(response['background_overlay_point'])
        
        return {
            'old_coordinates_count': len(old_coords),
            'new_coordinates_count': len(new_coords),
            'coordinate_consistency': self._check_coordinate_consistency(old_coords, new_coords)
        }
    
    def _check_coordinate_consistency(self, old_coords: List[Dict], new_coords: List[Dict]) -> Dict[str, Any]:
        """Check if coordinates are consistent between sessions."""
        if not old_coords or not new_coords:
            return {'consistent': False, 'reason': 'Missing coordinates in one session'}
        
        # Compare first few coordinates
        consistent_count = 0
        total_comparisons = min(len(old_coords), len(new_coords), 3)
        
        for i in range(total_comparisons):
            old_coord = old_coords[i]
            new_coord = new_coords[i]
            
            if (abs(old_coord['x'] - new_coord['x']) <= 5 and 
                abs(old_coord['y'] - new_coord['y']) <= 5):
                consistent_count += 1
        
        consistency_ratio = consistent_count / total_comparisons if total_comparisons > 0 else 0
        
        return {
            'consistent': consistency_ratio >= 0.8,
            'consistency_ratio': consistency_ratio,
            'total_comparisons': total_comparisons,
            'consistent_count': consistent_count
        }
    
    def generate_comparison_report(self) -> str:
        """Generate comprehensive comparison report."""
        execution_comparison = self.compare_execution_flows()
        popup_logs_comparison = self.compare_popup_logs()
        debug_coverage_comparison = self.compare_debug_coverage()
        llm_comparison = self.compare_llm_responses()
        
        report = []
        report.append("=" * 80)
        report.append("SESSION COMPARISON REPORT")
        report.append("=" * 80)
        report.append(f"Old Session: {self.old_session_dir.name}")
        report.append(f"New Session: {self.new_session_dir.name}")
        report.append("")
        
        # Executive Summary
        total_improvements = len(execution_comparison['improvements'])
        total_regressions = len(execution_comparison['regressions'])
        
        report.append("🔍 EXECUTIVE SUMMARY:")
        if total_improvements > total_regressions:
            report.append("✅ Overall IMPROVEMENT detected")
        elif total_regressions > total_improvements:
            report.append("❌ Overall REGRESSION detected")
        else:
            report.append("➡️  No significant changes")
        
        report.append(f"- Improvements: {total_improvements}")
        report.append(f"- Regressions: {total_regressions}")
        report.append("")
        
        # Execution Flow Comparison
        report.append("🔄 EXECUTION FLOW COMPARISON:")
        report.append(f"Old: {execution_comparison['old_session']['popup_start_events']} starts, {execution_comparison['old_session']['popup_complete_events']} completions")
        report.append(f"New: {execution_comparison['new_session']['popup_start_events']} starts, {execution_comparison['new_session']['popup_complete_events']} completions")
        
        if execution_comparison['improvements']:
            report.append("✅ Improvements:")
            for improvement in execution_comparison['improvements']:
                report.append(f"  - {improvement}")
        
        if execution_comparison['regressions']:
            report.append("❌ Regressions:")
            for regression in execution_comparison['regressions']:
                report.append(f"  - {regression}")
        
        report.append("")
        
        # Debug Coverage Comparison
        report.append("📊 DEBUG LOG COVERAGE:")
        report.append(f"Old coverage: {debug_coverage_comparison['old_coverage']:.1f}%")
        report.append(f"New coverage: {debug_coverage_comparison['new_coverage']:.1f}%")
        report.append(f"Coverage change: {debug_coverage_comparison['coverage_improvement']:+.1f}%")
        
        if debug_coverage_comparison['new_phases_found']:
            report.append("✅ New debug phases found:")
            for phase in debug_coverage_comparison['new_phases_found']:
                report.append(f"  - {phase}")
        
        if debug_coverage_comparison['lost_phases']:
            report.append("❌ Lost debug phases:")
            for phase in debug_coverage_comparison['lost_phases']:
                report.append(f"  - {phase}")
        
        report.append("")
        
        # Popup Logs Comparison
        report.append("📋 POPUP LOGS COMPARISON:")
        report.append(f"Old: {popup_logs_comparison['old_session']['total_entries']} entries, {popup_logs_comparison['old_session']['strategy_executions']} strategy executions")
        report.append(f"New: {popup_logs_comparison['new_session']['total_entries']} entries, {popup_logs_comparison['new_session']['strategy_executions']} strategy executions")
        
        entries_change = popup_logs_comparison['differences']['entries_change']
        strategy_change = popup_logs_comparison['differences']['strategy_change']
        
        if entries_change > 0:
            report.append(f"✅ {entries_change} more popup log entries")
        elif entries_change < 0:
            report.append(f"❌ {abs(entries_change)} fewer popup log entries")
        
        if strategy_change > 0:
            report.append(f"✅ {strategy_change} more strategy executions")
        elif strategy_change < 0:
            report.append(f"❌ {abs(strategy_change)} fewer strategy executions")
        
        report.append("")
        
        # LLM Response Comparison
        report.append("🤖 LLM RESPONSE COMPARISON:")
        report.append(f"Old: {llm_comparison['old_session']['popup_detections']} popup detections")
        report.append(f"New: {llm_comparison['new_session']['popup_detections']} popup detections")
        
        coord_consistency = llm_comparison['popup_coordinates_comparison']['coordinate_consistency']
        if coord_consistency['consistent']:
            report.append("✅ Popup coordinates are consistent between sessions")
        else:
            report.append(f"❌ Popup coordinates inconsistent: {coord_consistency.get('reason', 'Unknown reason')}")
        
        report.append("")
        
        # Key Insights
        report.append("💡 KEY INSIGHTS:")
        
        if (execution_comparison['new_session']['popup_start_events'] > 0 and 
            execution_comparison['new_session']['popup_complete_events'] == 0):
            report.append("🚨 PopupDismisser starts but never completes in new session")
        
        if debug_coverage_comparison['coverage_improvement'] > 10:
            report.append("✅ Significantly improved debug logging")
        
        if popup_logs_comparison['differences']['strategy_change'] == 0:
            report.append("❌ No strategy executions in either session - dismisser not reaching strategies")
        
        # Recommendations
        report.append("")
        report.append("🎯 RECOMMENDATIONS:")
        
        if execution_comparison['new_session']['hanging_attempts'] > 0:
            report.append("1. Focus on hanging PopupDismisser attempts")
            
        if debug_coverage_comparison['still_missing']:
            report.append("2. Add missing debug phases:")
            for phase in debug_coverage_comparison['still_missing'][:3]:
                report.append(f"   - {phase}")
        
        if popup_logs_comparison['new_session']['strategy_executions'] == 0:
            report.append("3. PopupDismisser never reaches strategy execution - check earlier phases")
        
        return "\n".join(report)

def main():
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python compare_sessions.py <old_session_dir> <new_session_dir>")
        print("Example: python compare_sessions.py logs/session_20250715_232742 logs/session_20250715_235753")
        sys.exit(1)
    
    old_session = sys.argv[1]
    new_session = sys.argv[2]
    
    comparator = SessionComparator(old_session, new_session)
    print(comparator.generate_comparison_report())

if __name__ == '__main__':
    main()