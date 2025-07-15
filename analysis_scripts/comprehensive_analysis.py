#!/usr/bin/env python3
"""
Comprehensive Session Analysis Script
Combines all analysis to provide actionable insights and root cause determination
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple
import hashlib

class SessionAnalyzer:
    def __init__(self, session_dir: str):
        self.session_dir = Path(session_dir)
        self.llm_calls_dir = self.session_dir / 'llm_calls'
        self.popup_dir = self.session_dir / 'popup'
        self.screenshots_dir = self.session_dir / 'screenshots'
        self.network_dir = self.session_dir / 'network'
        
    def analyze_directory_structure(self) -> Dict[str, Any]:
        """Analyze the basic structure and file counts."""
        structure = {}
        
        for subdir in [self.llm_calls_dir, self.popup_dir, self.screenshots_dir, self.network_dir]:
            if subdir.exists():
                files = list(subdir.glob('*'))
                structure[subdir.name] = {
                    'exists': True,
                    'file_count': len(files),
                    'files': [f.name for f in files[:10]]  # First 10 files
                }
            else:
                structure[subdir.name] = {'exists': False, 'file_count': 0}
                
        return structure
    
    def analyze_llm_responses(self) -> Dict[str, Any]:
        """Analyze all LLM responses for popup detection patterns."""
        if not self.llm_calls_dir.exists():
            return {'error': 'LLM calls directory not found'}
        
        response_files = sorted(self.llm_calls_dir.glob('*_response.json'))
        
        analyses = []
        popup_detections = []
        
        for file_path in response_files:
            try:
                with open(file_path) as f:
                    data = json.load(f)
                
                completion_str = data.get('completion', '{}')
                try:
                    completion = json.loads(completion_str)
                except json.JSONDecodeError:
                    completion = {}
                
                analysis = {
                    'file': file_path.name,
                    'step': int(file_path.stem.split('_')[0]),
                    'input_tokens': data.get('input_tokens', 0),
                    'output_tokens': data.get('output_tokens', 0),
                    'keywords': completion.get('keywords', []),
                    'popup_element_point': completion.get('popup_element_point'),
                    'popup_area': completion.get('popup_area'),
                    'background_overlay_point': completion.get('background_overlay_point'),
                    'popup_type': completion.get('popup_type'),
                    'navigation_element_point': completion.get('navigation_element_point'),
                }
                
                # Determine if this response has popup data
                has_popup = any([
                    completion.get('popup_element_point'),
                    completion.get('popup_area'),
                    completion.get('background_overlay_point'),
                    completion.get('popup_type')
                ])
                
                analysis['has_popup_data'] = has_popup
                analyses.append(analysis)
                
                if has_popup:
                    popup_detections.append(analysis)
                    
            except Exception as e:
                analyses.append({
                    'file': file_path.name,
                    'error': str(e),
                    'has_popup_data': False
                })
        
        return {
            'total_responses': len(analyses),
            'responses_with_popup': len(popup_detections),
            'popup_detections': popup_detections,
            'first_popup_step': popup_detections[0]['step'] if popup_detections else None,
            'last_popup_step': popup_detections[-1]['step'] if popup_detections else None,
            'popup_persistence': len(popup_detections) > 1,
            'all_analyses': analyses
        }
    
    def analyze_popup_dismissal_logs(self) -> Dict[str, Any]:
        """Check for popup dismissal attempt logs."""
        if not self.popup_dir.exists():
            return {'error': 'Popup directory not found'}
        
        log_files = list(self.popup_dir.glob('*'))
        
        return {
            'popup_dir_exists': True,
            'log_files_count': len(log_files),
            'log_files': [f.name for f in log_files],
            'dismissal_attempted': len(log_files) > 0
        }
    
    def analyze_screenshots(self) -> Dict[str, Any]:
        """Analyze screenshots for visual changes."""
        if not self.screenshots_dir.exists():
            return {'error': 'Screenshots directory not found'}
        
        screenshot_files = sorted(self.screenshots_dir.glob('*.png'))
        
        if len(screenshot_files) < 2:
            return {'error': 'Insufficient screenshots for comparison'}
        
        # Compare first and last screenshots
        first_screenshot = screenshot_files[0]
        last_screenshot = screenshot_files[-1]
        
        # Get file sizes
        first_size = first_screenshot.stat().st_size
        last_size = last_screenshot.stat().st_size
        
        # Simple hash comparison
        def get_file_hash(file_path):
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        
        first_hash = get_file_hash(first_screenshot)
        last_hash = get_file_hash(last_screenshot)
        
        return {
            'total_screenshots': len(screenshot_files),
            'first_screenshot': first_screenshot.name,
            'last_screenshot': last_screenshot.name,
            'first_size': first_size,
            'last_size': last_size,
            'size_identical': first_size == last_size,
            'content_identical': first_hash == last_hash,
            'visual_change_occurred': first_hash != last_hash
        }
    
    def determine_root_cause(self) -> Dict[str, Any]:
        """Determine the root cause based on all evidence."""
        structure = self.analyze_directory_structure()
        llm_analysis = self.analyze_llm_responses()
        popup_logs = self.analyze_popup_dismissal_logs()
        screenshots = self.analyze_screenshots()
        
        # Evidence collection
        evidence = {
            'popup_detected_by_llm': llm_analysis.get('responses_with_popup', 0) > 0,
            'popup_persists_across_responses': llm_analysis.get('popup_persistence', False),
            'dismissal_logs_exist': popup_logs.get('dismissal_attempted', False),
            'screenshots_identical': screenshots.get('content_identical', False),
            'popup_dir_empty': popup_logs.get('log_files_count', 0) == 0,
            'network_dir_empty': structure.get('network', {}).get('file_count', 0) == 0
        }
        
        # Root cause determination
        root_causes = []
        
        if evidence['popup_detected_by_llm'] and evidence['popup_dir_empty']:
            root_causes.append({
                'cause': 'PopupDismisser never executed',
                'confidence': 'HIGH',
                'explanation': 'LLM detected popup but no dismissal logs exist',
                'location': 'dismisser.py:55-60 or main workflow integration'
            })
        
        if evidence['popup_persists_across_responses']:
            root_causes.append({
                'cause': 'Popup detection verification failed',
                'confidence': 'HIGH',
                'explanation': 'detect_popup_presence() likely returned False',
                'location': 'verification.py:130-142'
            })
        
        if evidence['screenshots_identical']:
            root_causes.append({
                'cause': 'No visual changes occurred',
                'confidence': 'MEDIUM',
                'explanation': 'Screenshots are identical, confirming popup not dismissed',
                'location': 'Browser interaction level'
            })
        
        # Specific analysis for the notification popup
        popup_detections = llm_analysis.get('popup_detections', [])
        if popup_detections:
            first_detection = popup_detections[0]
            if first_detection.get('popup_type') == 'notification':
                root_causes.append({
                    'cause': 'Notification popup not in verification selectors',
                    'confidence': 'HIGH',
                    'explanation': 'verification.py DOM selectors may not match notification popup structure',
                    'location': 'verification.py:25-39'
                })
        
        return {
            'evidence': evidence,
            'root_causes': root_causes,
            'recommended_fixes': self._generate_recommendations(root_causes, evidence)
        }
    
    def _generate_recommendations(self, root_causes: List[Dict], evidence: Dict) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if evidence['popup_dir_empty']:
            recommendations.append(
                "Add debug logging to verify PopupDismisser.dismiss_popup() is called"
            )
            recommendations.append(
                "Check if detect_popup_presence() correctly identifies notification popups"
            )
        
        recommendations.append(
            "Add notification-specific selectors to verification.py:25-39"
        )
        recommendations.append(
            "Increase wait time after popup click (currently 2s in strategies.py:35)"
        )
        recommendations.append(
            "Add fallback logic if DOM-based verification fails"
        )
        
        return recommendations
    
    def generate_report(self) -> str:
        """Generate a comprehensive analysis report."""
        structure = self.analyze_directory_structure()
        llm_analysis = self.analyze_llm_responses()
        popup_logs = self.analyze_popup_dismissal_logs()
        screenshots = self.analyze_screenshots()
        root_cause = self.determine_root_cause()
        
        report = []
        report.append("=" * 60)
        report.append("COMPREHENSIVE SESSION ANALYSIS REPORT")
        report.append("=" * 60)
        report.append("")
        
        # Summary
        report.append("EXECUTIVE SUMMARY:")
        report.append(f"- LLM detected popup: {'✅' if llm_analysis.get('responses_with_popup', 0) > 0 else '❌'}")
        report.append(f"- Dismissal attempted: {'✅' if popup_logs.get('dismissal_attempted', False) else '❌'}")
        report.append(f"- Popup persisted: {'🚨' if screenshots.get('content_identical', False) else '✅'}")
        report.append("")
        
        # Evidence
        report.append("KEY EVIDENCE:")
        for key, value in root_cause['evidence'].items():
            status = "✅" if value else "❌"
            report.append(f"  {status} {key}: {value}")
        report.append("")
        
        # Root causes
        report.append("ROOT CAUSES:")
        for i, cause in enumerate(root_cause['root_causes'], 1):
            report.append(f"{i}. {cause['cause']} ({cause['confidence']} confidence)")
            report.append(f"   Location: {cause['location']}")
            report.append(f"   Explanation: {cause['explanation']}")
            report.append("")
        
        # Recommendations
        report.append("RECOMMENDED FIXES:")
        for i, rec in enumerate(root_cause['recommended_fixes'], 1):
            report.append(f"{i}. {rec}")
        
        return "\n".join(report)

def main():
    analyzer = SessionAnalyzer('logs/session_20250715_232742')
    
    print(analyzer.generate_report())

if __name__ == '__main__':
    main()