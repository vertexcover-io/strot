"""
Simplified streaming server that connects to existing Tab instances for human intervention.
"""

from __future__ import annotations

import asyncio
import base64
import json
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader

if TYPE_CHECKING:
    from patchright.async_api import CDPSession, Page

    from strot.browser.tab import Tab


# Setup Jinja2 templates
TEMPLATE_DIR = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)


@dataclass
class NavigationState:
    """Navigation history state"""

    current: int = 0
    max_navigation: int = 0


@dataclass
class SessionState:
    """State for a streaming session"""

    tab: Tab
    cdp: CDPSession
    reason: str
    frame_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=3))
    capture_task: asyncio.Task | None = None
    accessed: bool = False  # Track if user has accessed the session
    latest_frame: bytes | None = None  # Store latest frame for verification
    navigation_state: NavigationState = field(default_factory=NavigationState)
    websockets: list[WebSocket] = field(default_factory=list)


class StreamingServer:
    """Server that manages streaming sessions for human intervention"""

    def __init__(self, port: int = 8004, host: str = "0.0.0.0"):  # noqa: S104
        self.port = port
        self.host = host
        self.sessions: dict[str, SessionState] = {}
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:  # noqa: C901
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            yield
            # Cleanup on shutdown
            for session in self.sessions.values():
                if session.capture_task and not session.capture_task.done():
                    session.capture_task.cancel()
            self.sessions.clear()

        app = FastAPI(title="Browser Intervention Stream", lifespan=lifespan)

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/", response_class=HTMLResponse)
        async def index(session: str = "default"):
            """Serve the HTML client"""
            session_state = self.sessions.get(session)
            if not session_state:
                return "<h1>Session not found</h1>"

            # Mark session as accessed
            if not session_state.accessed:
                session_state.accessed = True

            return self._get_html_client(session, session_state.reason)

        @app.get("/stream")
        async def stream(session: str = "default"):
            """MJPEG stream endpoint"""
            session_state = self.sessions.get(session)
            if not session_state:
                return HTMLResponse("Session not found", status_code=404)

            async def generate():
                try:
                    while True:
                        frame_data = await asyncio.wait_for(session_state.frame_queue.get(), timeout=120.0)
                        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame_data + b"\r\n")
                except TimeoutError:
                    pass

            return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket, session: str = "default"):
            """WebSocket endpoint for control commands"""
            await websocket.accept()

            session_state = self.sessions.get(session)
            if not session_state:
                await websocket.close()
                return

            # Track this websocket
            session_state.websockets.append(websocket)

            cdp = session_state.cdp
            page = session_state.tab.page

            # Send initial navigation state
            await websocket.send_json({
                "type": "navigation_state",
                "current": session_state.navigation_state.current,
                "max_navigation": session_state.navigation_state.max_navigation,
            })

            try:
                with suppress(WebSocketDisconnect):
                    while True:
                        data = await websocket.receive_text()
                        message = json.loads(data)
                        msg_type = message.get("type")

                        if msg_type == "mouse":
                            await self._handle_mouse(cdp, message)
                        elif msg_type == "keyboard":
                            await self._handle_keyboard(cdp, message)
                        elif msg_type == "navigate":
                            await self._handle_navigate(page, message, session_state)
            except Exception as e:
                print(e)
            finally:
                if websocket in session_state.websockets:
                    session_state.websockets.remove(websocket)

        return app

    async def register_session(self, session_id: str, tab: Tab, reason: str):
        """Register a new Tab for streaming"""
        cdp = await tab.browser_context.new_cdp_session(tab.page)
        await cdp.send("Page.enable")
        await cdp.send("Runtime.enable")

        session_state = SessionState(tab=tab, cdp=cdp, reason=reason)
        self.sessions[session_id] = session_state

        # Start capture immediately so frames are ready when page loads
        session_state.capture_task = asyncio.create_task(self._capture_frames(session_state))

    async def unregister_session(self, session_id: str):
        """Unregister a session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if session.capture_task and not session.capture_task.done():
                session.capture_task.cancel()
            del self.sessions[session_id]

    def is_session_accessed(self, session_id: str) -> bool:
        """Check if a session has been accessed by the user"""
        if session_id in self.sessions:
            return self.sessions[session_id].accessed
        return False

    def get_latest_frame(self, session_id: str) -> bytes | None:
        """Get the latest frame for a session (for verification)"""
        if session_id in self.sessions:
            return self.sessions[session_id].latest_frame
        return None

    async def _capture_frames(self, session: SessionState):
        """Capture frames from CDP"""
        cdp = session.cdp

        def on_frame(params):
            session_id = params.get("sessionId")
            data = params.get("data", "")

            if session_id:
                asyncio.create_task(  # noqa: RUF006
                    cdp.send("Page.screencastFrameAck", {"sessionId": session_id})
                )

            if data:
                with suppress(Exception):
                    frame_bytes = base64.b64decode(data)
                    # Store latest frame for verification
                    session.latest_frame = frame_bytes
                    # Add to queue for streaming
                    if session.frame_queue.full():
                        session.frame_queue.get_nowait()
                    session.frame_queue.put_nowait(frame_bytes)

        cdp.on("Page.screencastFrame", on_frame)
        await cdp.send(
            "Page.startScreencast",
            {
                "format": "jpeg",
                "quality": 85,
                "maxWidth": session.tab.viewport_size["width"],
                "maxHeight": session.tab.viewport_size["height"],
                "everyNthFrame": 1,
            },
        )

        try:
            # Keep task alive
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            with suppress(Exception):
                await cdp.send("Page.stopScreencast")
            raise

    async def _handle_mouse(self, cdp: CDPSession, message: dict[str, Any]):
        """Handle mouse events"""
        action = message.get("action")
        x, y = message.get("x", 0), message.get("y", 0)

        button_map = {0: "left", 1: "middle", 2: "right"}

        if action in ["mousedown", "mouseup"]:
            await cdp.send(
                "Input.dispatchMouseEvent",
                {
                    "type": "mousePressed" if action == "mousedown" else "mouseReleased",
                    "x": x,
                    "y": y,
                    "button": button_map.get(message.get("button", 0), "left"),
                    "clickCount": 1,
                },
            )
        elif action == "mousemove":
            await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        elif action == "wheel":
            await cdp.send(
                "Input.dispatchMouseEvent",
                {
                    "type": "mouseWheel",
                    "x": x,
                    "y": y,
                    "deltaX": message.get("deltaX", 0),
                    "deltaY": message.get("deltaY", 0),
                },
            )

    async def _handle_keyboard(self, cdp: CDPSession, message: dict[str, Any]):
        """Handle keyboard events with proper special character support"""
        action = message.get("action")
        key = message.get("key", "")
        code = message.get("code", "")
        ctrl = message.get("ctrl", False)
        shift = message.get("shift", False)
        alt = message.get("alt", False)
        meta = message.get("meta", False)

        modifiers = 0
        if alt:
            modifiers |= 1
        if ctrl:
            modifiers |= 2
        if meta:
            modifiers |= 4
        if shift:
            modifiers |= 8

        params: dict[str, Any] = {
            "type": "keyDown" if action == "keydown" else "keyUp",
            "key": key,
            "code": code,
            "modifiers": modifiers,
        }

        # Special keys mapping
        KEY_CODES = {
            "Backspace": 8,
            "Tab": 9,
            "Enter": 13,
            "Escape": 27,
            "Space": 32,
            "PageUp": 33,
            "PageDown": 34,
            "End": 35,
            "Home": 36,
            "ArrowLeft": 37,
            "ArrowUp": 38,
            "ArrowRight": 39,
            "ArrowDown": 40,
            "Delete": 46,
            "F1": 112,
            "F2": 113,
            "F3": 114,
            "F4": 115,
            "F5": 116,
            "F6": 117,
            "F7": 118,
            "F8": 119,
            "F9": 120,
            "F10": 121,
            "F11": 122,
            "F12": 123,
        }

        # Add virtual key code
        if key in KEY_CODES:
            params["windowsVirtualKeyCode"] = KEY_CODES[key]
            params["nativeVirtualKeyCode"] = KEY_CODES[key]
        elif len(key) == 1:
            # For single characters, use proper virtual key code
            if key.isalpha():
                key_code = ord(key.upper())
            else:
                # For numbers and symbols, use their character code
                key_code = ord(key.upper()) if key.isdigit() else self._get_symbol_keycode(key)
            params["windowsVirtualKeyCode"] = key_code
            params["nativeVirtualKeyCode"] = key_code

        # Add text only for keyDown of single printable characters (no ctrl/alt/meta modifiers)
        if action == "keydown" and len(key) == 1 and not (ctrl or alt or meta):
            params["text"] = key

        await cdp.send("Input.dispatchKeyEvent", params)

    def _get_symbol_keycode(self, key: str) -> int:
        """Get the Windows virtual key code for symbol characters"""
        # Map symbols to their base key codes (unshifted position)
        symbol_map = {
            # Number row symbols (shifted)
            "!": 49,
            "@": 50,
            "#": 51,
            "$": 52,
            "%": 53,
            "^": 54,
            "&": 55,
            "*": 56,
            "(": 57,
            ")": 48,
            # Number keys (unshifted)
            "1": 49,
            "2": 50,
            "3": 51,
            "4": 52,
            "5": 53,
            "6": 54,
            "7": 55,
            "8": 56,
            "9": 57,
            "0": 48,
            # Other common symbols
            "-": 189,
            "_": 189,
            "=": 187,
            "+": 187,
            "[": 219,
            "{": 219,
            "]": 221,
            "}": 221,
            "\\": 220,
            "|": 220,
            ";": 186,
            ":": 186,
            "'": 222,
            '"': 222,
            ",": 188,
            "<": 188,
            ".": 190,
            ">": 190,
            "/": 191,
            "?": 191,
            "`": 192,
            "~": 192,
        }
        return symbol_map.get(key, ord(key))

    async def _handle_navigate(self, page: Page, message: dict[str, Any], session_state: SessionState):
        """Handle navigation commands"""
        action = message.get("action")
        nav_state = session_state.navigation_state

        if action == "back":
            if nav_state.current > 0:
                await page.go_back()
                nav_state.current -= 1
                await self._broadcast_navigation_state(session_state)
        elif action == "forward":
            if nav_state.current < nav_state.max_navigation:
                await page.go_forward()
                nav_state.current += 1
                await self._broadcast_navigation_state(session_state)
        elif action == "reload":
            await page.reload()
        elif action == "goto":
            url = message.get("url", "")
            if url:
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                await page.goto(url, wait_until="domcontentloaded")
                # New navigation - increment both
                nav_state.current += 1
                nav_state.max_navigation = nav_state.current
                await self._broadcast_navigation_state(session_state)

    async def _broadcast_navigation_state(self, session_state: SessionState):
        """Broadcast navigation state to all connected websockets"""
        message = {
            "type": "navigation_state",
            "current": session_state.navigation_state.current,
            "max_navigation": session_state.navigation_state.max_navigation,
        }
        for ws in session_state.websockets:
            with suppress(Exception):
                await ws.send_json(message)

    async def notify_task_completed(self, session_id: str):
        """Notify frontend that task is completed"""
        if session_id in self.sessions:
            session_state = self.sessions[session_id]
            message = {"type": "task_completed", "reason": session_state.reason}
            for ws in session_state.websockets:
                with suppress(Exception):
                    await ws.send_json(message)

    def _get_html_client(self, session_id: str, reason: str) -> str:
        """Generate HTML client for streaming using Jinja template"""
        session = self.sessions[session_id]
        template = jinja_env.get_template("intervention.html")
        return template.render(
            session_id=session_id,
            reason=reason,
            viewport_width=session.tab.viewport_size["width"],
            viewport_height=session.tab.viewport_size["height"],
        )

    async def start(self):
        """Start the server"""
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="warning")
        server = uvicorn.Server(config)
        await server.serve()
