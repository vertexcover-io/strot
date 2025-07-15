#!/usr/bin/env python3
"""
Popup Logs Analyzer
Searches ALL session files for popup-dismissal logs and analyzes strategy execution
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

class PopupLogsAnalyzer:
    def __init__(self, session_dir: str):
        self.session_dir = Path(session_dir)
        
    def search_all_popup_logs(self) -> Dict[str, Any]:
        """Search all files in session for popup-dismissal related logs."""
        popup_logs = {
            'files_with_popup_logs': [],
            'total_popup_log_entries': 0,
            'strategy_executions': [],
            'verification_attempts': [],
            'coordinate_mismatches': [],
            'errors_and_exceptions': []
        }
        
        # Search all files recursively
        for file_path in self.session_dir.rglob('*'):
            if file_path.is_file():
                try:
                    popup_entries = self._extract_popup_logs_from_file(file_path)
                    if popup_entries:
                        popup_logs['files_with_popup_logs'].append({
                            'file': str(file_path.relative_to(self.session_dir)),
                            'entries': popup_entries,
                            'entry_count': len(popup_entries)
                        })
                        popup_logs['total_popup_log_entries'] += len(popup_entries)
                        
                        # Analyze specific log types
                        self._analyze_log_entries(popup_entries, popup_logs)
                        
                except Exception as e:
                    # Skip files that can't be read/parsed
                    continue
        
        return popup_logs
    
    def _extract_popup_logs_from_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract popup logs from a single file."""
        popup_entries = []
        
        try:
            # Try reading as JSON first
            if file_path.suffix in ['.json', '.jsonl']:
                popup_entries.extend(self._extract_from_json_file(file_path))
            
            # Try reading as text file for any missed logs
            popup_entries.extend(self._extract_from_text_file(file_path))
            
        except Exception:
            pass
        
        return popup_entries
    
    def _extract_from_json_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract popup logs from JSON files."""
        entries = []
        
        try:
            if file_path.suffix == '.jsonl':
                # Handle JSONL files (one JSON object per line)
                with open(file_path) as f:
                    for line_num, line in enumerate(f, 1):
                        try:
                            data = json.loads(line.strip())
                            if self._contains_popup_data(data):
                                entries.append({
                                    'file': str(file_path.name),
                                    'line': line_num,
                                    'type': 'jsonl_entry',
                                    'data': data
                                })
                        except json.JSONDecodeError:
                            continue
            else:
                # Handle regular JSON files
                with open(file_path) as f:
                    data = json.load(f)
                    if self._contains_popup_data(data):
                        entries.append({
                            'file': str(file_path.name),
                            'type': 'json_file',
                            'data': data
                        })
        except Exception:
            pass
        
        return entries
    
    def _extract_from_text_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract popup logs from text files using regex patterns."""
        entries = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Look for popup-dismissal log patterns
                popup_patterns = [
                    r'popup-dismissal.*?action="([^"]*)"',
                    r'popup-dismissal.*?strategy="([^"]*)"',
                    r'popup-dismissal.*?coordinates=\{[^}]*\}',
                    r'popup-verification.*?method="([^"]*)"',
                    r'click_outside.*?action="([^"]*)"',
                    r'explicit_close.*?result="([^"]*)"'
                ]
                
                for pattern in popup_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        entries.append({
                            'file': str(file_path.name),
                            'type': 'text_match',
                            'pattern': pattern,
                            'match': match.group(0),
                            'position': match.start()
                        })
        except Exception:
            pass
        
        return entries
    
    def _contains_popup_data(self, data: Any) -> bool:
        """Check if data contains popup-related information."""
        if isinstance(data, dict):
            # Check keys and values
            for key, value in data.items():
                key_str = str(key).lower()
                value_str = str(value).lower()
                
                if any(term in key_str or term in value_str for term in [
                    'popup', 'dismiss', 'click_outside', 'explicit_close',
                    'popup-dismissal', 'popup-verification', 'background_overlay'
                ]):
                    return True
                
                if self._contains_popup_data(value):
                    return True
        elif isinstance(data, list):
            return any(self._contains_popup_data(item) for item in data)
        elif isinstance(data, str):
            return any(term in data.lower() for term in [
                'popup-dismissal', 'click_outside', 'explicit_close',
                'popup-verification', 'background_overlay_point'
            ])
        
        return False
    
    def _analyze_log_entries(self, entries: List[Dict], popup_logs: Dict):
        """Analyze log entries for specific patterns."""
        for entry in entries:
            data = entry.get('data', {})
            
            # Look for strategy executions
            if self._is_strategy_execution(data):
                popup_logs['strategy_executions'].append(entry)
            
            # Look for verification attempts
            if self._is_verification_attempt(data):
                popup_logs['verification_attempts'].append(entry)
            
            # Look for coordinate data
            if self._has_coordinate_data(data):
                popup_logs['coordinate_mismatches'].append(entry)
            
            # Look for errors
            if self._is_error_log(data):
                popup_logs['errors_and_exceptions'].append(entry)
    
    def _is_strategy_execution(self, data: Any) -> bool:
        """Check if this is a strategy execution log."""
        if isinstance(data, dict):
            action = data.get('action', '')
            component = data.get('component', '')
            return ('strategy' in str(data).lower() or 
                   'click_outside' in str(data).lower() or
                   'explicit_close' in str(data).lower())
        elif isinstance(data, str):
            return any(term in data.lower() for term in [
                'strategy="', 'click_outside', 'explicit_close', 'escape_key'
            ])
        return False
    
    def _is_verification_attempt(self, data: Any) -> bool:
        """Check if this is a verification attempt log."""
        data_str = str(data).lower()
        return any(term in data_str for term in [
            'popup-verification', 'verify_popup_dismissed', 'detect_popup_presence'
        ])
    
    def _has_coordinate_data(self, data: Any) -> bool:
        """Check if this contains coordinate information."""
        data_str = str(data).lower()
        return any(term in data_str for term in [
            'coordinates=', '"x":', '"y":', 'popup_element_point', 'background_overlay_point'
        ])
    
    def _is_error_log(self, data: Any) -> bool:
        """Check if this is an error or exception log."""
        data_str = str(data).lower()
        return any(term in data_str for term in [
            'error', 'exception', 'failed', 'timeout', 'strategy_exception'
        ])
    
    def analyze_coordinate_accuracy(self, popup_logs: Dict) -> Dict[str, Any]:
        """Analyze if strategies are using correct LLM-provided coordinates."""
        coordinate_analysis = {
            'llm_coordinates_found': [],
            'strategy_coordinates_used': [],
            'coordinate_matches': [],
            'coordinate_mismatches': []
        }
        
        # Extract LLM coordinates from response files
        llm_coords = self._extract_llm_coordinates()
        coordinate_analysis['llm_coordinates_found'] = llm_coords
        
        # Extract strategy coordinates from logs
        strategy_coords = self._extract_strategy_coordinates(popup_logs)
        coordinate_analysis['strategy_coordinates_used'] = strategy_coords
        
        # Compare coordinates
        for llm_coord in llm_coords:
            for strategy_coord in strategy_coords:
                if self._coordinates_match(llm_coord, strategy_coord):
                    coordinate_analysis['coordinate_matches'].append({
                        'llm': llm_coord,
                        'strategy': strategy_coord
                    })
                else:
                    coordinate_analysis['coordinate_mismatches'].append({
                        'llm': llm_coord,
                        'strategy': strategy_coord,
                        'difference': self._calculate_coordinate_difference(llm_coord, strategy_coord)
                    })
        
        return coordinate_analysis
    
    def _extract_llm_coordinates(self) -> List[Dict[str, Any]]:
        """Extract coordinates from LLM response files."""
        coords = []
        
        llm_calls_dir = self.session_dir / 'llm_calls'
        if not llm_calls_dir.exists():
            return coords
        
        for response_file in llm_calls_dir.glob('*_response.json'):
            try:
                with open(response_file) as f:
                    data = json.load(f)
                    
                completion_str = data.get('completion', '{}')
                try:
                    completion = json.loads(completion_str)
                    
                    if completion.get('popup_element_point'):
                        coords.append({
                            'file': response_file.name,
                            'type': 'popup_element_point',
                            'coordinates': completion['popup_element_point']
                        })
                    
                    if completion.get('background_overlay_point'):
                        coords.append({
                            'file': response_file.name,
                            'type': 'background_overlay_point',
                            'coordinates': completion['background_overlay_point']
                        })
                except json.JSONDecodeError:
                    continue
            except Exception:
                continue
        
        return coords
    
    def _extract_strategy_coordinates(self, popup_logs: Dict) -> List[Dict[str, Any]]:
        """Extract coordinates used by strategies."""
        coords = []
        
        for file_info in popup_logs['files_with_popup_logs']:
            for entry in file_info['entries']:
                data = entry.get('data', {})
                
                # Look for coordinate usage in strategy logs
                data_str = str(data)
                coord_matches = re.finditer(r'coordinates=\{[^}]*"x":\s*([^,}]*)[^}]*"y":\s*([^,}]*)', data_str)
                
                for match in coord_matches:
                    try:
                        x = float(match.group(1).strip())
                        y = float(match.group(2).strip())
                        coords.append({
                            'file': entry['file'],
                            'type': 'strategy_usage',
                            'coordinates': {'x': x, 'y': y},
                            'context': match.group(0)
                        })
                    except ValueError:
                        continue
        
        return coords
    
    def _coordinates_match(self, llm_coord: Dict, strategy_coord: Dict, tolerance: float = 5.0) -> bool:
        """Check if coordinates match within tolerance."""
        llm_x = llm_coord['coordinates']['x']
        llm_y = llm_coord['coordinates']['y']
        strat_x = strategy_coord['coordinates']['x']
        strat_y = strategy_coord['coordinates']['y']
        
        return (abs(llm_x - strat_x) <= tolerance and abs(llm_y - strat_y) <= tolerance)
    
    def _calculate_coordinate_difference(self, llm_coord: Dict, strategy_coord: Dict) -> Dict[str, float]:
        """Calculate difference between coordinates."""
        llm_x = llm_coord['coordinates']['x']
        llm_y = llm_coord['coordinates']['y']
        strat_x = strategy_coord['coordinates']['x']
        strat_y = strategy_coord['coordinates']['y']
        
        return {
            'x_diff': abs(llm_x - strat_x),
            'y_diff': abs(llm_y - strat_y),
            'distance': ((llm_x - strat_x)**2 + (llm_y - strat_y)**2)**0.5
        }
    
    def generate_report(self) -> str:
        """Generate comprehensive popup logs analysis report."""
        popup_logs = self.search_all_popup_logs()
        coordinate_analysis = self.analyze_coordinate_accuracy(popup_logs)
        
        report = []
        report.append("=" * 70)
        report.append("POPUP LOGS ANALYSIS REPORT")
        report.append("=" * 70)
        report.append("")
        
        # Summary
        report.append("📊 SUMMARY:")
        report.append(f"- Files with popup logs: {len(popup_logs['files_with_popup_logs'])}")
        report.append(f"- Total popup log entries: {popup_logs['total_popup_log_entries']}")
        report.append(f"- Strategy executions: {len(popup_logs['strategy_executions'])}")
        report.append(f"- Verification attempts: {len(popup_logs['verification_attempts'])}")
        report.append(f"- Errors/exceptions: {len(popup_logs['errors_and_exceptions'])}")
        report.append("")
        
        # Files with popup logs
        if popup_logs['files_with_popup_logs']:
            report.append("📁 FILES WITH POPUP LOGS:")
            for file_info in popup_logs['files_with_popup_logs']:
                report.append(f"- {file_info['file']}: {file_info['entry_count']} entries")
        else:
            report.append("❌ NO POPUP LOGS FOUND!")
            report.append("This confirms PopupDismisser never executes strategies")
            report.append("")
        
        # Strategy executions
        if popup_logs['strategy_executions']:
            report.append("🎯 STRATEGY EXECUTIONS:")
            for i, execution in enumerate(popup_logs['strategy_executions'][:5], 1):
                report.append(f"{i}. File: {execution['file']}")
                data = execution.get('data', {})
                report.append(f"   Details: {str(data)[:100]}...")
        else:
            report.append("❌ NO STRATEGY EXECUTIONS FOUND")
        
        report.append("")
        
        # Coordinate analysis
        report.append("🎯 COORDINATE ANALYSIS:")
        report.append(f"- LLM coordinates found: {len(coordinate_analysis['llm_coordinates_found'])}")
        report.append(f"- Strategy coordinates used: {len(coordinate_analysis['strategy_coordinates_used'])}")
        report.append(f"- Coordinate matches: {len(coordinate_analysis['coordinate_matches'])}")
        report.append(f"- Coordinate mismatches: {len(coordinate_analysis['coordinate_mismatches'])}")
        
        if coordinate_analysis['llm_coordinates_found']:
            report.append("\nLLM Coordinates:")
            for coord in coordinate_analysis['llm_coordinates_found'][:3]:
                report.append(f"  {coord['type']}: {coord['coordinates']}")
        
        if coordinate_analysis['strategy_coordinates_used']:
            report.append("\nStrategy Coordinates:")
            for coord in coordinate_analysis['strategy_coordinates_used'][:3]:
                report.append(f"  {coord['type']}: {coord['coordinates']}")
        
        # Errors
        if popup_logs['errors_and_exceptions']:
            report.append("\n❌ ERRORS AND EXCEPTIONS:")
            for error in popup_logs['errors_and_exceptions'][:3]:
                report.append(f"- File: {error['file']}")
                report.append(f"  Error: {str(error.get('data', {}))[:150]}...")
        
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
        print("\nUsage: python analyze_popup_logs.py <session_name>")
        print("Example: python analyze_popup_logs.py session_20250716_002557")
        return
    
    analyzer = PopupLogsAnalyzer(session_dir)
    print(analyzer.generate_report())

if __name__ == '__main__':
    main()