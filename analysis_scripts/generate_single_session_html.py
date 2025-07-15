#!/usr/bin/env python3
"""
Generate HTML report for a single Ayejax session with detailed analysis.
Usage: python generate_single_session_html.py <session_id>
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

def parse_llm_calls(session_path: Path) -> List[Dict[str, Any]]:
    """Parse LLM request/response pairs."""
    llm_calls_dir = session_path / "llm_calls"
    llm_calls = []
    
    if not llm_calls_dir.exists():
        return llm_calls
    
    # Get all request files and sort them
    request_files = sorted([f for f in llm_calls_dir.glob("*_request.json")])
    
    for request_file in request_files:
        call_num = request_file.stem.replace('_request', '')
        response_file = llm_calls_dir / f"{call_num}_response.json"
        
        call_data = {'call_number': call_num}
        
        # Parse request
        try:
            with open(request_file, 'r') as f:
                call_data['request'] = json.load(f)
        except json.JSONDecodeError:
            call_data['request'] = None
        
        # Parse response
        try:
            with open(response_file, 'r') as f:
                call_data['response'] = json.load(f)
        except json.JSONDecodeError:
            call_data['response'] = None
        
        llm_calls.append(call_data)
    
    return llm_calls

def parse_single_session_data(session_path: Path) -> Dict[str, Any]:
    """Parse comprehensive data for a single session."""
    session_data = {'session_id': session_path.name}
    
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
    
    # Parse LLM calls
    session_data['llm_calls'] = parse_llm_calls(session_path)
    
    # Collect screenshots with metadata
    screenshots_dir = session_path / "screenshots"
    screenshots = []
    if screenshots_dir.exists():
        for screenshot_file in sorted(screenshots_dir.glob("*.png")):
            base64_image = encode_image_to_base64(screenshot_file)
            if base64_image:
                # Extract step number from filename
                step_match = screenshot_file.stem.split('_')[0] if '_' in screenshot_file.stem else '0'
                
                # Find corresponding timeline entry
                timeline_entry = None
                try:
                    step_num = int(step_match)
                    if step_num <= len(session_data['timeline']):
                        timeline_entry = session_data['timeline'][step_num - 1]
                except:
                    pass
                
                screenshots.append({
                    'filename': screenshot_file.name,
                    'step': step_match,
                    'base64': base64_image,
                    'timeline_entry': timeline_entry,
                    'action': timeline_entry.get('action', 'unknown') if timeline_entry else 'unknown'
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
                    popup_info['step'] = popup_file.stem.split('_')[0] if '_' in popup_file.stem else '0'
                    popup_data.append(popup_info)
            except json.JSONDecodeError:
                pass
    session_data['popup_data'] = popup_data
    
    # Calculate duration
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

def generate_single_session_html_template() -> str:
    """Generate HTML template for single session report."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ayejax Session: {{SESSION_ID}}</title>
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
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
        }
        
        .session-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        
        .info-card {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 8px;
        }
        
        .info-label {
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .nav-tabs {
            display: flex;
            background: white;
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            flex-wrap: wrap;
        }
        
        .nav-tab {
            flex: 1;
            min-width: 120px;
            padding: 15px;
            text-align: center;
            cursor: pointer;
            border-radius: 5px;
            transition: all 0.3s ease;
            font-weight: 500;
            margin: 2px;
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
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        
        .tab-content.active {
            display: block;
        }
        
        .screenshots-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .screenshot-item {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            overflow: hidden;
            transition: transform 0.3s ease;
        }
        
        .screenshot-item:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }
        
        .screenshot-header {
            background: #f8f9fa;
            padding: 10px;
            border-bottom: 1px solid #e0e0e0;
        }
        
        .screenshot-step {
            font-weight: bold;
            color: #667eea;
        }
        
        .screenshot-action {
            color: #666;
            font-size: 14px;
        }
        
        .screenshot-image {
            width: 100%;
            height: 200px;
            object-fit: cover;
            cursor: pointer;
        }
        
        .timeline-item {
            border-left: 4px solid #667eea;
            padding: 20px;
            margin-bottom: 20px;
            background: #f8f9fa;
            border-radius: 0 8px 8px 0;
        }
        
        .timeline-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .timeline-step {
            background: #667eea;
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 12px;
        }
        
        .timeline-action {
            font-weight: bold;
            color: #333;
            font-size: 18px;
        }
        
        .timeline-timestamp {
            color: #666;
            font-size: 14px;
        }
        
        .timeline-details {
            background: white;
            padding: 15px;
            border-radius: 5px;
            margin-top: 10px;
        }
        
        .llm-call {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            margin-bottom: 20px;
            overflow: hidden;
        }
        
        .llm-call-header {
            background: #667eea;
            color: white;
            padding: 15px;
            font-weight: bold;
        }
        
        .llm-call-content {
            padding: 20px;
        }
        
        .llm-section {
            margin-bottom: 20px;
        }
        
        .llm-section h4 {
            color: #667eea;
            margin-bottom: 10px;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 5px;
        }
        
        .code-block {
            background: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            padding: 15px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            overflow-x: auto;
            max-height: 300px;
            overflow-y: auto;
        }
        
        .popup-item {
            border: 1px solid #ffeaa7;
            background: #fff3cd;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }
        
        .popup-header {
            font-weight: bold;
            color: #856404;
            margin-bottom: 10px;
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
            max-width: 95%;
            max-height: 95%;
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
        
        .modal-nav {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(0,0,0,0.7);
            color: white;
            border: none;
            padding: 20px 15px;
            cursor: pointer;
            font-size: 24px;
            font-weight: bold;
            transition: background 0.3s ease;
        }
        
        .modal-nav:hover {
            background: rgba(0,0,0,0.9);
        }
        
        .modal-nav:disabled {
            opacity: 0.3;
            cursor: not-allowed;
        }
        
        .modal-prev {
            left: 20px;
        }
        
        .modal-next {
            right: 20px;
        }
        
        .modal-counter {
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 14px;
        }
        
        .error-info {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 20px;
        }
        
        .error-info h3 {
            color: #721c24;
            margin-bottom: 10px;
        }
        
        .success-info {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 20px;
        }
        
        .success-info h3 {
            color: #155724;
            margin-bottom: 10px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .stat-item {
            text-align: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
        }
        
        .stat-number {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
        
        .stat-label {
            color: #666;
            font-size: 14px;
        }
        
        .json-viewer {
            background: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            padding: 15px;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Ayejax Session Report</h1>
            <h2>{{SESSION_ID}}</h2>
            <div class="session-info">
                <div class="info-card">
                    <div class="info-label">🔗 URL</div>
                    <div>{{URL}}</div>
                </div>
                <div class="info-card">
                    <div class="info-label">📊 Status</div>
                    <div>{{STATUS}}</div>
                </div>
                <div class="info-card">
                    <div class="info-label">⏱️ Duration</div>
                    <div>{{DURATION}} seconds</div>
                </div>
                <div class="info-card">
                    <div class="info-label">📋 Total Steps</div>
                    <div>{{TOTAL_STEPS}}</div>
                </div>
                <div class="info-card">
                    <div class="info-label">🏷️ Tag</div>
                    <div>{{TAG}}</div>
                </div>
            </div>
        </div>
        
        <div class="nav-tabs">
            <div class="nav-tab active" onclick="showTab('overview')">📊 Overview</div>
            <div class="nav-tab" onclick="showTab('timeline')">🕒 Timeline</div>
            <div class="nav-tab" onclick="showTab('screenshots')">📸 Screenshots</div>
            <div class="nav-tab" onclick="showTab('llm-calls')">🤖 LLM Calls</div>
            <div class="nav-tab" onclick="showTab('popups')">🔔 Popups</div>
            <div class="nav-tab" onclick="showTab('raw-data')">📄 Raw Data</div>
        </div>
        
        <div id="overview" class="tab-content active">
            {{OVERVIEW_CONTENT}}
        </div>
        
        <div id="timeline" class="tab-content">
            {{TIMELINE_CONTENT}}
        </div>
        
        <div id="screenshots" class="tab-content">
            {{SCREENSHOTS_CONTENT}}
        </div>
        
        <div id="llm-calls" class="tab-content">
            {{LLM_CALLS_CONTENT}}
        </div>
        
        <div id="popups" class="tab-content">
            {{POPUPS_CONTENT}}
        </div>
        
        <div id="raw-data" class="tab-content">
            {{RAW_DATA_CONTENT}}
        </div>
    </div>
    
    <div id="imageModal" class="modal">
        <span class="close">&times;</span>
        <button class="modal-nav modal-prev" id="prevBtn" onclick="navigateScreenshot(-1)">❮</button>
        <button class="modal-nav modal-next" id="nextBtn" onclick="navigateScreenshot(1)">❯</button>
        <div class="modal-content">
            <img id="modalImage" src="" alt="Screenshot">
        </div>
        <div class="modal-counter">
            <span id="modalCounter">1 / 1</span>
        </div>
    </div>
    
    <script>
        let currentImageIndex = 0;
        let screenshots = {{SCREENSHOTS_JS}};
        
        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            document.querySelectorAll('.nav-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
        }
        
        function openModal(imageSrc) {
            // Find the index of the clicked image
            currentImageIndex = screenshots.findIndex(img => img.base64 === imageSrc);
            if (currentImageIndex === -1) currentImageIndex = 0;
            
            updateModalImage();
            document.getElementById('imageModal').style.display = 'block';
        }
        
        function navigateScreenshot(direction) {
            currentImageIndex += direction;
            if (currentImageIndex < 0) currentImageIndex = screenshots.length - 1;
            if (currentImageIndex >= screenshots.length) currentImageIndex = 0;
            
            updateModalImage();
        }
        
        function updateModalImage() {
            if (screenshots.length === 0) return;
            
            const screenshot = screenshots[currentImageIndex];
            document.getElementById('modalImage').src = screenshot.base64;
            document.getElementById('modalCounter').textContent = `${currentImageIndex + 1} / ${screenshots.length}`;
            
            // Update navigation buttons
            document.getElementById('prevBtn').disabled = screenshots.length <= 1;
            document.getElementById('nextBtn').disabled = screenshots.length <= 1;
        }
        
        function closeModal() {
            document.getElementById('imageModal').style.display = 'none';
        }
        
        document.querySelector('.close').onclick = closeModal;
        document.getElementById('imageModal').onclick = function(event) {
            if (event.target === this) {
                closeModal();
            }
        };
        
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                closeModal();
            } else if (document.getElementById('imageModal').style.display === 'block') {
                if (event.key === 'ArrowLeft') {
                    navigateScreenshot(-1);
                } else if (event.key === 'ArrowRight') {
                    navigateScreenshot(1);
                }
            }
        });
    </script>
</body>
</html>'''

def generate_single_session_report(session_data: Dict[str, Any]) -> str:
    """Generate complete HTML report for a single session."""
    
    # Generate overview content
    overview_content = f'''
    <div class="stats-grid">
        <div class="stat-item">
            <div class="stat-number">{len(session_data['screenshots'])}</div>
            <div class="stat-label">Screenshots</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">{len(session_data['llm_calls'])}</div>
            <div class="stat-label">LLM Calls</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">{len(session_data['timeline'])}</div>
            <div class="stat-label">Timeline Steps</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">{len(session_data['popup_data'])}</div>
            <div class="stat-label">Popup Events</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">{len(session_data['execution_flow'])}</div>
            <div class="stat-label">Execution Events</div>
        </div>
    </div>
    
    {f'<div class="success-info"><h3>✅ Session Completed Successfully</h3><p>Final result obtained and processed.</p></div>' if session_data.get('status') == 'completed' else ''}
    {f'<div class="error-info"><h3>❌ Session Failed</h3><p>{session_data.get("error", "Unknown error")}</p></div>' if session_data.get('error') else ''}
    
    <h3>📋 Session Summary</h3>
    <p><strong>Started:</strong> {session_data.get('startTime', 'Unknown')}</p>
    <p><strong>Ended:</strong> {session_data.get('endTime', 'Unknown')}</p>
    <p><strong>Target URL:</strong> <a href="{session_data.get('url', '#')}" target="_blank">{session_data.get('url', 'Unknown')}</a></p>
    <p><strong>Final Result:</strong> {'Available' if session_data.get('finalResult') else 'Not available'}</p>
    '''
    
    # Generate timeline content
    timeline_content = ""
    for i, step in enumerate(session_data['timeline'], 1):
        action = step.get('action', 'unknown')
        status = step.get('status', 'unknown')
        timestamp = step.get('timestamp', '')
        
        details_html = ""
        if 'data' in step:
            data = step['data']
            details_html = f'<div class="timeline-details"><pre>{json.dumps(data, indent=2)}</pre></div>'
        
        timeline_content += f'''
        <div class="timeline-item">
            <div class="timeline-header">
                <div>
                    <span class="timeline-step">Step {i}</span>
                    <span class="timeline-action">{action.replace('_', ' ').title()}</span>
                </div>
                <span class="timeline-timestamp">{timestamp} | {status}</span>
            </div>
            {details_html}
        </div>'''
    
    # Generate screenshots content
    screenshots_content = f'''
    <h3>📸 Session Screenshots ({len(session_data['screenshots'])})</h3>
    <div class="screenshots-grid">
    '''
    
    for screenshot in session_data['screenshots']:
        action_text = screenshot['action'].replace('_', ' ').title()
        screenshots_content += f'''
        <div class="screenshot-item">
            <div class="screenshot-header">
                <div class="screenshot-step">Step {screenshot['step']}</div>
                <div class="screenshot-action">{action_text}</div>
            </div>
            <img src="{screenshot['base64']}" alt="Step {screenshot['step']}" 
                 class="screenshot-image" onclick="openModal('{screenshot['base64']}')">
        </div>'''
    
    screenshots_content += "</div>"
    
    # Generate LLM calls content
    llm_calls_content = f"<h3>🤖 LLM Interactions ({len(session_data['llm_calls'])})</h3>"
    
    for call in session_data['llm_calls']:
        request_data = call.get('request', {})
        response_data = call.get('response', {})
        
        llm_calls_content += f'''
        <div class="llm-call">
            <div class="llm-call-header">Call #{call['call_number']}</div>
            <div class="llm-call-content">
                <div class="llm-section">
                    <h4>📤 Request</h4>
                    <div class="code-block">{json.dumps(request_data, indent=2) if request_data else 'No request data'}</div>
                </div>
                <div class="llm-section">
                    <h4>📥 Response</h4>
                    <div class="code-block">{json.dumps(response_data, indent=2) if response_data else 'No response data'}</div>
                </div>
            </div>
        </div>'''
    
    # Generate popups content
    popups_content = f"<h3>🔔 Popup Events ({len(session_data['popup_data'])})</h3>"
    
    if session_data['popup_data']:
        for popup in session_data['popup_data']:
            popup_type = popup.get('popup_type', 'unknown')
            popups_content += f'''
            <div class="popup-item">
                <div class="popup-header">Step {popup['step']} - {popup['filename']}</div>
                <div><strong>Type:</strong> {popup_type}</div>
                <div class="code-block">{json.dumps(popup, indent=2)}</div>
            </div>'''
    else:
        popups_content += "<p>No popup events recorded in this session.</p>"
    
    # Generate raw data content
    raw_data_content = f'''
    <h3>📄 Raw Session Data</h3>
    <div class="json-viewer">
        {json.dumps(session_data, indent=2, default=str)}
    </div>'''
    
    # Load template and replace placeholders
    html_template = generate_single_session_html_template()
    
    # Clean tag name
    tag_name = str(session_data.get('tag', 'Unknown'))
    if 'ayejax.tag' in tag_name:
        tag_name = 'ayejax.tag'
    
    # Generate screenshots array for JavaScript
    screenshots_js = json.dumps([{
        'base64': screenshot['base64'],
        'step': screenshot['step'],
        'action': screenshot['action'],
        'filename': screenshot['filename']
    } for screenshot in session_data['screenshots']], indent=8)
    
    replacements = {
        '{{SESSION_ID}}': session_data['session_id'],
        '{{URL}}': session_data.get('url', 'Unknown'),
        '{{STATUS}}': session_data.get('status', 'Unknown'),
        '{{DURATION}}': f"{session_data.get('duration', 0):.1f}",
        '{{TOTAL_STEPS}}': str(session_data.get('totalSteps', 0)),
        '{{TAG}}': tag_name,
        '{{OVERVIEW_CONTENT}}': overview_content,
        '{{TIMELINE_CONTENT}}': timeline_content,
        '{{SCREENSHOTS_CONTENT}}': screenshots_content,
        '{{LLM_CALLS_CONTENT}}': llm_calls_content,
        '{{POPUPS_CONTENT}}': popups_content,
        '{{RAW_DATA_CONTENT}}': raw_data_content,
        '{{SCREENSHOTS_JS}}': screenshots_js
    }
    
    html_content = html_template
    for placeholder, value in replacements.items():
        html_content = html_content.replace(placeholder, value)
    
    return html_content

def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_single_session_html.py <session_id>")
        print("Example: python generate_single_session_html.py session_20250716_002557")
        sys.exit(1)
    
    session_id = sys.argv[1]
    
    # Find logs directory
    script_dir = Path(__file__).parent
    logs_dir = script_dir.parent / "logs"
    
    if not logs_dir.exists():
        print(f"Logs directory not found: {logs_dir}")
        sys.exit(1)
    
    # Find session directory
    session_dir = logs_dir / session_id
    if not session_dir.exists():
        print(f"Session directory not found: {session_dir}")
        print("Available sessions:")
        for d in logs_dir.iterdir():
            if d.is_dir() and d.name.startswith('session_'):
                print(f"  - {d.name}")
        sys.exit(1)
    
    # Parse session data
    try:
        session_data = parse_single_session_data(session_dir)
    except Exception as e:
        print(f"Error parsing session data: {e}")
        sys.exit(1)
    
    # Generate HTML report
    html_content = generate_single_session_report(session_data)
    
    # Create reports/html directory
    reports_dir = logs_dir.parent / "reports" / "html"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Write output file
    output_file = reports_dir / f"{session_id}_report.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Single session HTML report generated: {output_file}")
    print(f"Screenshots embedded: {len(session_data['screenshots'])}")
    print(f"LLM calls analyzed: {len(session_data['llm_calls'])}")
    print(f"Timeline steps: {len(session_data['timeline'])}")

if __name__ == "__main__":
    main()