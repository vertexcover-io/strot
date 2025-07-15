#!/usr/bin/env python3
"""
Generate HTML report from Ayejax session logs with screenshots and visualizations.
Provides multiple visualization approaches for session analysis.
"""

import json
import base64
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import mimetypes

def encode_image_to_base64(image_path: Path) -> Optional[str]:
    """Encode image file to base64 string for embedding in HTML."""
    if not image_path.exists():
        return None
    
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        mime_type, _ = mimetypes.guess_type(str(image_path))
        if not mime_type or not mime_type.startswith('image/'):
            mime_type = 'image/png'
        
        base64_data = base64.b64encode(image_data).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"
    except Exception as e:
        print(f"Error encoding image {image_path}: {e}")
        return None

def parse_session_data(session_path: Path) -> Dict[str, Any]:
    """Parse all session data including screenshots."""
    session_data = {}
    
    # Parse session.json
    session_file = session_path / "session.json"
    if session_file.exists():
        try:
            with open(session_file, 'r') as f:
                session_data.update(json.load(f))
        except json.JSONDecodeError:
            pass
    
    # Parse timeline.json
    timeline_file = session_path / "timeline.json"
    if timeline_file.exists():
        try:
            with open(timeline_file, 'r') as f:
                session_data['timeline'] = json.load(f)
        except json.JSONDecodeError:
            session_data['timeline'] = []
    else:
        session_data['timeline'] = []
    
    # Parse execution_flow.jsonl
    flow_file = session_path / "execution_flow.jsonl"
    execution_flow = []
    if flow_file.exists():
        try:
            with open(flow_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        execution_flow.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    session_data['execution_flow'] = execution_flow
    
    # Collect screenshots
    screenshots_dir = session_path / "screenshots"
    screenshots = []
    if screenshots_dir.exists():
        for screenshot_file in sorted(screenshots_dir.glob("*.png")):
            base64_image = encode_image_to_base64(screenshot_file)
            if base64_image:
                screenshots.append({
                    'filename': screenshot_file.name,
                    'path': str(screenshot_file),
                    'base64': base64_image,
                    'step': screenshot_file.stem.split('_')[0] if '_' in screenshot_file.stem else '0'
                })
    session_data['screenshots'] = screenshots
    
    # Collect popup data
    popup_dir = session_path / "popup"
    popup_data = []
    if popup_dir.exists():
        for popup_file in sorted(popup_dir.glob("*.json")):
            try:
                with open(popup_file, 'r') as f:
                    popup_info = json.load(f)
                    popup_info['filename'] = popup_file.name
                    popup_data.append(popup_info)
            except json.JSONDecodeError:
                pass
    session_data['popup_data'] = popup_data
    
    # Basic session info
    session_data['session_id'] = session_path.name
    session_data['url'] = session_data.get('url', 'Unknown')
    session_data['status'] = session_data.get('status', 'Unknown')
    session_data['duration'] = 0
    
    start_time = session_data.get('startTime')
    end_time = session_data.get('endTime')
    if start_time and end_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            session_data['duration'] = (end_dt - start_dt).total_seconds()
        except:
            pass
    
    return session_data

def generate_html_template() -> str:
    """Generate the base HTML template with CSS and JavaScript."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ayejax Session Analysis Report</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f7fa;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            text-align: center;
        }
        
        .nav-tabs {
            display: flex;
            background: white;
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .nav-tab {
            flex: 1;
            padding: 15px;
            text-align: center;
            cursor: pointer;
            border-radius: 5px;
            transition: all 0.3s ease;
            font-weight: 500;
        }
        
        .nav-tab.active {
            background: #667eea;
            color: white;
        }
        
        .nav-tab:hover:not(.active) {
            background: #f0f0f0;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .session-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        
        .session-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
            border-left: 4px solid #667eea;
        }
        
        .session-card:hover {
            transform: translateY(-5px);
        }
        
        .session-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .session-id {
            font-weight: bold;
            color: #667eea;
        }
        
        .status-badge {
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .status-completed {
            background: #d4edda;
            color: #155724;
        }
        
        .status-failed {
            background: #f8d7da;
            color: #721c24;
        }
        
        .status-unknown {
            background: #fff3cd;
            color: #856404;
        }
        
        .session-info {
            margin-bottom: 15px;
        }
        
        .info-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            padding: 5px 0;
            border-bottom: 1px solid #eee;
        }
        
        .info-label {
            font-weight: 500;
            color: #666;
        }
        
        .info-value {
            color: #333;
        }
        
        .screenshots-container {
            margin-top: 15px;
        }
        
        .screenshots-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }
        
        .screenshot-thumb {
            position: relative;
            border-radius: 5px;
            overflow: hidden;
            cursor: pointer;
            transition: transform 0.3s ease;
        }
        
        .screenshot-thumb:hover {
            transform: scale(1.05);
        }
        
        .screenshot-thumb img {
            width: 100%;
            height: 80px;
            object-fit: cover;
        }
        
        .screenshot-label {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 2px 5px;
            font-size: 10px;
            text-align: center;
        }
        
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
        }
        
        .modal-content {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            max-width: 90%;
            max-height: 90%;
        }
        
        .modal-content img {
            max-width: 100%;
            max-height: 100%;
            border-radius: 5px;
        }
        
        .close {
            position: absolute;
            top: 10px;
            right: 25px;
            color: white;
            font-size: 35px;
            font-weight: bold;
            cursor: pointer;
        }
        
        .timeline-view {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        
        .timeline-item {
            display: flex;
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        
        .timeline-step {
            background: #667eea;
            color: white;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            margin-right: 15px;
            flex-shrink: 0;
        }
        
        .timeline-content {
            flex: 1;
        }
        
        .timeline-action {
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }
        
        .timeline-details {
            color: #666;
            font-size: 14px;
        }
        
        .summary-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }
        
        .stat-number {
            font-size: 2rem;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }
        
        .stat-label {
            color: #666;
            font-size: 14px;
        }
        
        .popup-info {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 5px;
            padding: 10px;
            margin-top: 10px;
        }
        
        .popup-info h4 {
            color: #856404;
            margin-bottom: 5px;
        }
        
        .error-info {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 5px;
            padding: 10px;
            margin-top: 10px;
        }
        
        .error-info h4 {
            color: #721c24;
            margin-bottom: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Ayejax Session Analysis Report</h1>
            <p>Comprehensive analysis of web scraping sessions with popup handling and LLM interactions</p>
            <p>Generated: {{GENERATION_TIME}}</p>
        </div>
        
        <div class="nav-tabs">
            <div class="nav-tab active" onclick="showTab('overview')">📊 Overview</div>
            <div class="nav-tab" onclick="showTab('sessions')">📋 Session Details</div>
            <div class="nav-tab" onclick="showTab('timeline')">🕒 Timeline View</div>
        </div>
        
        <div id="overview" class="tab-content active">
            <div class="summary-stats">
                {{SUMMARY_STATS}}
            </div>
            {{OVERVIEW_CONTENT}}
        </div>
        
        <div id="sessions" class="tab-content">
            <div class="session-grid">
                {{SESSION_CARDS}}
            </div>
        </div>
        
        <div id="timeline" class="tab-content">
            {{TIMELINE_CONTENT}}
        </div>
    </div>
    
    <div id="imageModal" class="modal">
        <span class="close">&times;</span>
        <div class="modal-content">
            <img id="modalImage" src="" alt="Screenshot">
        </div>
    </div>
    
    <script>
        function showTab(tabName) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Remove active class from all nav tabs
            document.querySelectorAll('.nav-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabName).classList.add('active');
            
            // Add active class to clicked nav tab
            event.target.classList.add('active');
        }
        
        function openModal(imageSrc) {
            document.getElementById('modalImage').src = imageSrc;
            document.getElementById('imageModal').style.display = 'block';
        }
        
        function closeModal() {
            document.getElementById('imageModal').style.display = 'none';
        }
        
        // Close modal when clicking on close button or outside the image
        document.querySelector('.close').onclick = closeModal;
        document.getElementById('imageModal').onclick = function(event) {
            if (event.target === this) {
                closeModal();
            }
        };
        
        // Close modal on escape key
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                closeModal();
            }
        });
    </script>
</body>
</html>'''

def generate_session_card(session: Dict[str, Any]) -> str:
    """Generate HTML for a single session card."""
    status_class = f"status-{session['status'].lower()}" if session['status'] != 'Unknown' else "status-unknown"
    
    # Generate screenshots HTML
    screenshots_html = ""
    if session['screenshots']:
        screenshots_html = '''
        <div class="screenshots-container">
            <h4>📸 Screenshots ({count})</h4>
            <div class="screenshots-grid">
                {screenshot_items}
            </div>
        </div>'''.format(
            count=len(session['screenshots']),
            screenshot_items=''.join([f'''
                <div class="screenshot-thumb" onclick="openModal('{screenshot['base64']}')">
                    <img src="{screenshot['base64']}" alt="{screenshot['filename']}">
                    <div class="screenshot-label">Step {screenshot['step']}</div>
                </div>
            ''' for screenshot in session['screenshots'][:8]])  # Limit to first 8 screenshots
        )
    
    # Generate popup info
    popup_html = ""
    if session['popup_data']:
        popup_types = set()
        for popup in session['popup_data']:
            if popup.get('popup_type'):
                popup_types.add(popup['popup_type'])
        
        if popup_types:
            popup_html = f'''
            <div class="popup-info">
                <h4>🔔 Popup Information</h4>
                <p>Types detected: {', '.join(popup_types)}</p>
                <p>Total popup files: {len(session['popup_data'])}</p>
            </div>'''
    
    # Generate error info
    error_html = ""
    if session.get('error'):
        error_html = f'''
        <div class="error-info">
            <h4>❌ Error Information</h4>
            <p>{session['error']}</p>
        </div>'''
    
    # Clean tag name
    tag_name = str(session.get('tag', 'Unknown'))
    if 'ayejax.tag' in tag_name:
        tag_name = 'ayejax.tag'
    
    return f'''
    <div class="session-card">
        <div class="session-header">
            <div class="session-id">{session['session_id']}</div>
            <div class="status-badge {status_class}">{session['status']}</div>
        </div>
        
        <div class="session-info">
            <div class="info-row">
                <span class="info-label">🔗 URL:</span>
                <span class="info-value">{session['url'][:50]}{'...' if len(session['url']) > 50 else ''}</span>
            </div>
            <div class="info-row">
                <span class="info-label">🏷️ Tag:</span>
                <span class="info-value">{tag_name}</span>
            </div>
            <div class="info-row">
                <span class="info-label">⏱️ Duration:</span>
                <span class="info-value">{session['duration']:.1f}s</span>
            </div>
            <div class="info-row">
                <span class="info-label">📋 Steps:</span>
                <span class="info-value">{session.get('totalSteps', 0)}</span>
            </div>
            <div class="info-row">
                <span class="info-label">🤖 LLM Calls:</span>
                <span class="info-value">{len(session.get('timeline', []))}</span>
            </div>
        </div>
        
        {screenshots_html}
        {popup_html}
        {error_html}
    </div>'''

def generate_timeline_view(sessions: List[Dict[str, Any]]) -> str:
    """Generate timeline view for all sessions."""
    timeline_html = ""
    
    for session in sessions:
        if not session.get('timeline'):
            continue
            
        session_timeline = f'''
        <div class="timeline-view">
            <h3>🔍 {session['session_id']}</h3>
            <p><strong>URL:</strong> {session['url']}</p>
            <p><strong>Status:</strong> {session['status']} | <strong>Duration:</strong> {session['duration']:.1f}s</p>
            <br>
        '''
        
        for i, step in enumerate(session['timeline'], 1):
            action = step.get('action', 'unknown')
            status = step.get('status', 'unknown')
            timestamp = step.get('timestamp', '')
            
            # Get additional details
            details = []
            if 'data' in step:
                data = step['data']
                if action == 'llm_analysis':
                    details.append(f"Template: {data.get('template_type', 'N/A')}")
                    details.append(f"Screenshot size: {data.get('screenshot_size', 0):,} bytes")
                elif action == 'popup_dismissal':
                    details.append(f"Popup detected: {data.get('popup_detected', False)}")
                    details.append(f"Popup type: {data.get('popup_type', 'N/A')}")
                    details.append(f"Success: {data.get('success', False)}")
            
            session_timeline += f'''
            <div class="timeline-item">
                <div class="timeline-step">{i}</div>
                <div class="timeline-content">
                    <div class="timeline-action">🔄 {action.replace('_', ' ').title()}</div>
                    <div class="timeline-details">
                        Status: {status} | Time: {timestamp}<br>
                        {' | '.join(details) if details else 'No additional details'}
                    </div>
                </div>
            </div>'''
        
        session_timeline += "</div><br>"
        timeline_html += session_timeline
    
    return timeline_html

def generate_summary_stats(sessions: List[Dict[str, Any]]) -> str:
    """Generate summary statistics."""
    total_sessions = len(sessions)
    completed_sessions = len([s for s in sessions if s['status'] == 'completed'])
    total_screenshots = sum(len(s['screenshots']) for s in sessions)
    total_duration = sum(s['duration'] for s in sessions)
    sessions_with_popups = len([s for s in sessions if s['popup_data']])
    
    return f'''
    <div class="stat-card">
        <div class="stat-number">{total_sessions}</div>
        <div class="stat-label">Total Sessions</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{completed_sessions}</div>
        <div class="stat-label">Completed Sessions</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{total_screenshots}</div>
        <div class="stat-label">Total Screenshots</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{total_duration:.0f}s</div>
        <div class="stat-label">Total Duration</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{sessions_with_popups}</div>
        <div class="stat-label">Sessions with Popups</div>
    </div>'''

def generate_html_report(logs_dir: Path, output_file: Path):
    """Generate comprehensive HTML report."""
    session_dirs = [d for d in logs_dir.iterdir() if d.is_dir() and d.name.startswith('session_')]
    session_dirs.sort(key=lambda x: x.name, reverse=True)  # Most recent first
    
    sessions = []
    for session_dir in session_dirs:
        try:
            session_data = parse_session_data(session_dir)
            sessions.append(session_data)
        except Exception as e:
            print(f"Error processing {session_dir.name}: {e}")
            continue
    
    if not sessions:
        print("No session data found")
        return
    
    # Generate HTML components
    summary_stats = generate_summary_stats(sessions)
    session_cards = '\n'.join([generate_session_card(session) for session in sessions])
    timeline_content = generate_timeline_view(sessions)
    
    # Generate overview content
    overview_content = f'''
    <div class="timeline-view">
        <h3>📋 Session Summary</h3>
        <p>This report analyzes {len(sessions)} Ayejax sessions, showing detailed information about each web scraping execution including screenshots, popup handling, and LLM interactions.</p>
        
        <h4>🎯 Key Insights:</h4>
        <ul style="margin: 15px 0; padding-left: 20px;">
            <li><strong>Success Rate:</strong> {len([s for s in sessions if s['status'] == 'completed'])}/{len(sessions)} ({100*len([s for s in sessions if s['status'] == 'completed'])/len(sessions):.1f}%) sessions completed successfully</li>
            <li><strong>Average Duration:</strong> {sum(s['duration'] for s in sessions)/len(sessions):.1f} seconds per session</li>
            <li><strong>Popup Handling:</strong> {len([s for s in sessions if s['popup_data']])} sessions encountered popups</li>
            <li><strong>Screenshot Coverage:</strong> {sum(len(s['screenshots']) for s in sessions)} total screenshots captured</li>
        </ul>
        
        <h4>🔍 Recent Sessions:</h4>
        <ul style="margin: 15px 0; padding-left: 20px;">
    '''
    
    for session in sessions[:5]:  # Show last 5 sessions
        overview_content += f'<li><strong>{session["session_id"]}</strong>: {session["status"]} - {session["duration"]:.1f}s</li>'
    
    overview_content += '''
        </ul>
    </div>'''
    
    # Load template and replace placeholders
    html_template = generate_html_template()
    html_content = html_template.replace('{{GENERATION_TIME}}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    html_content = html_content.replace('{{SUMMARY_STATS}}', summary_stats)
    html_content = html_content.replace('{{OVERVIEW_CONTENT}}', overview_content)
    html_content = html_content.replace('{{SESSION_CARDS}}', session_cards)
    html_content = html_content.replace('{{TIMELINE_CONTENT}}', timeline_content)
    
    # Write HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"HTML report generated: {output_file}")
    print(f"Total sessions analyzed: {len(sessions)}")
    print(f"Total screenshots embedded: {sum(len(s['screenshots']) for s in sessions)}")

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
    
    output_file = logs_dir.parent / "session_analysis_report.html"
    generate_html_report(logs_dir, output_file)

if __name__ == "__main__":
    main()