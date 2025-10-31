"""
FastAPI web server for bassi web UI

Provides:
- Static file serving (HTML, CSS, JS)
- WebSocket endpoint for bidirectional chat
- Health check endpoint
"""

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


class WebUIServer:
    """Web UI server using FastAPI"""

    def __init__(self, agent, host: str = "localhost", port: int = 8765):
        self.agent = agent
        self.host = host
        self.port = port
        self.app = FastAPI(title="bassi Web UI")

        # Track active WebSocket connections
        self.active_connections: list[WebSocket] = []

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes"""

        # Serve static files
        static_dir = Path(__file__).parent / "static"
        if static_dir.exists():
            self.app.mount(
                "/static",
                StaticFiles(directory=str(static_dir)),
                name="static",
            )

        # Root route - serve index.html
        @self.app.get("/")
        async def root():
            static_dir = Path(__file__).parent / "static"
            index_path = static_dir / "index.html"
            if index_path.exists():
                return HTMLResponse(content=index_path.read_text())
            return HTMLResponse(
                content="<h1>bassi Web UI</h1><p>Static files not found. Please create bassi/static/index.html</p>"
            )

        # Health check
        @self.app.get("/health")
        async def health():
            return JSONResponse({"status": "ok", "service": "bassi-web-ui"})

        # WebSocket endpoint
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)

    async def _handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"WebSocket connected. Total connections: {len(self.active_connections)}"
        )

        try:
            # Send welcome message
            await websocket.send_json(
                {"type": "connected", "message": "Connected to bassi"}
            )

            # Listen for messages
            while True:
                data = await websocket.receive_json()
                await self._process_message(websocket, data)

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            logger.info(
                f"Remaining connections: {len(self.active_connections)}"
            )

    async def _process_message(
        self, websocket: WebSocket, data: dict[str, Any]
    ):
        """Process incoming message from client"""
        msg_type = data.get("type")

        if msg_type == "user_message":
            # User sent a chat message
            content = data.get("content", "")
            logger.info(f"User message: {content[:100]}...")

            # Stream response from agent
            try:
                async for event in self.agent.chat(content):
                    # Convert agent event to WebSocket message
                    ws_message = self._agent_event_to_ws_message(event)
                    if ws_message:
                        await websocket.send_json(ws_message)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_json(
                    {"type": "error", "message": str(e)}
                )

        else:
            logger.warning(f"Unknown message type: {msg_type}")

    def _agent_event_to_ws_message(self, event: Any) -> dict[str, Any] | None:
        """
        Convert agent event to WebSocket message format

        This converts Claude SDK messages to our web UI protocol
        """
        # Handle event objects (after we add them to agent.py)
        if hasattr(event, "type"):
            event_type = (
                event.type.value
                if hasattr(event.type, "value")
                else str(event.type)
            )

            if event_type == "content_delta":
                return {"type": "content_delta", "text": event.text}

            elif event_type == "tool_call_start":
                return {
                    "type": "tool_call_start",
                    "tool_name": event.tool_name,
                    "input": event.input_data,
                }

            elif event_type == "tool_call_end":
                return {
                    "type": "tool_call_end",
                    "tool_name": event.tool_name,
                    "output": event.output_data,
                    "success": event.success,
                }

            elif event_type == "message_complete":
                return {
                    "type": "message_complete",
                    "usage": {
                        "input_tokens": event.input_tokens,
                        "output_tokens": event.output_tokens,
                        "cost_usd": event.cost_usd,
                        "duration_ms": event.duration_ms,
                    },
                }

            elif event_type == "status_update":
                return {"type": "status", "message": event.message}

        # Handle raw SDK messages (current implementation)
        msg_class_name = type(event).__name__

        # StreamEvent with content_block_delta
        if msg_class_name == "StreamEvent":
            event_data = getattr(event, "event", {})
            if event_data.get("type") == "content_block_delta":
                delta = event_data.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    return {"type": "content_delta", "text": text}

        # ToolUseBlock
        elif msg_class_name == "ToolUseBlock":
            return {
                "type": "tool_call_start",
                "tool_name": getattr(event, "name", "unknown"),
                "input": getattr(event, "input", {}),
            }

        # ResultMessage with usage
        elif msg_class_name == "ResultMessage":
            usage = getattr(event, "usage", None)
            if usage:
                return {
                    "type": "message_complete",
                    "usage": {
                        "input_tokens": getattr(usage, "input_tokens", 0),
                        "output_tokens": getattr(usage, "output_tokens", 0),
                        "cost_usd": 0.0,  # Calculate based on token counts
                        "duration_ms": 0,
                    },
                }

        return None

    async def run(self):
        """Run the web server"""
        import uvicorn

        logger.info(
            f"Starting web UI server on http://{self.host}:{self.port}"
        )

        config = uvicorn.Config(
            app=self.app, host=self.host, port=self.port, log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


async def start_web_server(agent, host: str = "localhost", port: int = 8765):
    """
    Start the web UI server

    Args:
        agent: BassiAgent instance
        host: Server host
        port: Server port
    """
    server = WebUIServer(agent, host, port)
    await server.run()
