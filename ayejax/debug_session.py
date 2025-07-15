import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ayejax.helpers import normalize_filename


class DebugSession:
    """Manages debug logging and file generation for ayejax sessions."""
    
    def __init__(self, url: str, tag: str):
        self.url = url
        self.tag = tag
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_dir = Path("logs") / self.session_id
        self.step_counter = 0
        self.timeline: List[Dict[str, Any]] = []
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.s3_enabled = os.getenv('AYEJAX_S3_UPLOAD', 'false').lower() == 'true'
        self.status = "running"
        self.error: Optional[str] = None
        self.final_result: Optional[Any] = None
        
    def setup_directories(self) -> None:
        """Create session directory structure."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        (self.session_dir / "screenshots").mkdir(exist_ok=True)
        (self.session_dir / "llm_calls").mkdir(exist_ok=True)
        (self.session_dir / "network").mkdir(exist_ok=True)
        
    def log_event(
        self, 
        action: str, 
        data: Dict[str, Any], 
        screenshot: Optional[bytes] = None,
        status: str = "success"
    ) -> int:
        """Log an event to the timeline and optionally save screenshot."""
        self.step_counter += 1
        
        event = {
            "step": self.step_counter,
            "action": action,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "status": status,
            "data": data
        }
        
        if screenshot:
            screenshot_path = self.save_screenshot(screenshot, action)
            event["screenshot"] = screenshot_path
            
        self.timeline.append(event)
        return self.step_counter
        
    def save_screenshot(self, screenshot: bytes, action: str) -> str:
        """Save screenshot and return relative path."""
        filename = f"{self.step_counter:03d}_{action}.png"
        filepath = self.session_dir / "screenshots" / filename
        
        with open(filepath, "wb") as f:
            f.write(screenshot)
            
        return f"screenshots/{filename}"
        
    def save_llm_call(
        self, 
        step: int, 
        request_data: Dict[str, Any], 
        response_data: Dict[str, Any]
    ) -> tuple[str, str]:
        """Save LLM request/response files and return paths."""
        request_filename = f"{step:03d}_request.json"
        response_filename = f"{step:03d}_response.json"
        
        request_path = self.session_dir / "llm_calls" / request_filename
        response_path = self.session_dir / "llm_calls" / response_filename
        
        with open(request_path, "w") as f:
            json.dump(request_data, f, indent=2)
            
        with open(response_path, "w") as f:
            json.dump(response_data, f, indent=2)
            
        return f"llm_calls/{request_filename}", f"llm_calls/{response_filename}"
        
    def save_network_request(self, step: int, request_data: Dict[str, Any]) -> str:
        """Save network request data and return path."""
        filename = f"{step:03d}_{request_data.get('method', 'unknown').lower()}.json"
        filepath = self.session_dir / "network" / filename
        
        with open(filepath, "w") as f:
            json.dump(request_data, f, indent=2)
            
        return f"network/{filename}"
        
    def update_timeline_event(self, step: int, updates: Dict[str, Any]) -> None:
        """Update an existing timeline event with additional data."""
        for event in self.timeline:
            if event["step"] == step:
                event.update(updates)
                break
                
    def save_session_json(self) -> None:
        """Save session metadata to session.json."""
        # Convert final_result to serializable format
        final_result_serializable = None
        if self.final_result:
            try:
                # Try to convert to dict if it has model_dump method (Pydantic)
                if hasattr(self.final_result, 'model_dump'):
                    final_result_serializable = self.final_result.model_dump()
                elif hasattr(self.final_result, '__dict__'):
                    final_result_serializable = str(self.final_result)
                else:
                    final_result_serializable = str(self.final_result)
            except Exception:
                final_result_serializable = str(self.final_result)
        
        session_data = {
            "id": self.session_id,
            "url": self.url,
            "tag": self.tag,
            "startTime": self.start_time.isoformat(),
            "endTime": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "error": self.error,
            "totalSteps": self.step_counter,
            "finalResult": final_result_serializable
        }
        
        with open(self.session_dir / "session.json", "w") as f:
            json.dump(session_data, f, indent=2, default=str)
            
    def save_timeline_json(self) -> None:
        """Save timeline events to timeline.json."""
        with open(self.session_dir / "timeline.json", "w") as f:
            json.dump(self.timeline, f, indent=2, default=str)
            
    def finalize(self, result: Any = None, error: str = None) -> Optional[str]:
        """Finalize session and optionally upload to S3."""
        self.end_time = datetime.now()
        self.final_result = result
        self.error = error
        self.status = "failed" if error else "completed"
        
        # Save session files
        self.save_session_json()
        self.save_timeline_json()
        
        dashboard_url = None
        
        if self.s3_enabled:
            try:
                dashboard_url = self._upload_to_s3()
                print(f"🔗 Debug Dashboard: {dashboard_url}")
            except Exception as e:
                print(f"⚠️  S3 upload failed: {e}")
                
        return dashboard_url
        
    def _upload_to_s3(self) -> str:
        """Upload session to S3 and return dashboard URL."""
        # TODO: Implement S3 upload
        # For now, return a placeholder URL
        bucket = os.getenv('AYEJAX_S3_BUCKET', 'ayejax-logs')
        return f"https://{bucket}.s3.amazonaws.com/{self.session_id}/index.html"
        
    def get_session_summary(self) -> Dict[str, Any]:
        """Get session summary for logging."""
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            
        return {
            "session_id": self.session_id,
            "url": self.url,
            "tag": self.tag,
            "status": self.status,
            "total_steps": self.step_counter,
            "duration_seconds": duration,
            "error": self.error,
            "has_result": self.final_result is not None
        }