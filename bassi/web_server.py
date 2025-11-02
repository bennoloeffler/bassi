"""
FastAPI web server for bassi web UI

Provides:
- Static file serving (HTML, CSS, JS)
- WebSocket endpoint for bidirectional chat
- Health check endpoint
"""

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from bassi import __version__

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """
    Track state for a single WebSocket session using Append-Only architecture.

    Each session maintains counters for generating unique IDs for content blocks.
    IDs follow the pattern: msg-{message_counter}-{type}-{sequence}

    Examples:
        - msg-1-text-0: First text block in first message
        - msg-1-tool-0: First tool call in first message
        - msg-2-text-0: First text block in second message
    """

    message_counter: int = 0
    text_block_counter: int = 0
    tool_counter: int = 0
    current_text_block_id: str | None = None
    tool_name_to_id: dict[str, str] = field(default_factory=dict)

    def new_message(self):
        """Reset counters for a new assistant message"""
        self.message_counter += 1
        self.text_block_counter = 0
        self.tool_counter = 0
        self.current_text_block_id = None
        self.tool_name_to_id.clear()

    def create_text_block_id(self) -> str:
        """
        Create a new text block ID and track it as current.

        Returns:
            ID string like "msg-1-text-0"
        """
        text_id = f"msg-{self.message_counter}-text-{self.text_block_counter}"
        self.text_block_counter += 1
        self.current_text_block_id = text_id
        return text_id

    def get_or_create_text_block_id(self) -> str:
        """
        Get current text block ID or create new one if none exists.

        This allows multiple text_delta events to append to the same block.
        """
        if self.current_text_block_id is None:
            return self.create_text_block_id()
        return self.current_text_block_id

    def create_tool_id(self, tool_name: str) -> str:
        """
        Create a new tool ID and map it to the tool name.

        Args:
            tool_name: Name of the tool being called

        Returns:
            ID string like "msg-1-tool-0"
        """
        tool_id = f"msg-{self.message_counter}-tool-{self.tool_counter}"
        self.tool_counter += 1
        self.tool_name_to_id[tool_name] = tool_id
        # Reset text block ID so next text starts a new block
        self.current_text_block_id = None
        return tool_id

    def get_tool_id(self, tool_name: str) -> str | None:
        """
        Get the ID for a tool by its name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool ID if found, None otherwise
        """
        return self.tool_name_to_id.get(tool_name)


def convert_event_to_messages(
    event: Any, state: SessionState
) -> list[dict[str, Any]]:
    """
    Convert agent event to WebSocket messages with unique IDs.

    This is the core of the Append-Only architecture - every message has an ID
    that allows the client to create or update content blocks.

    Args:
        event: Event from agent.chat() stream
        state: Session state for ID generation

    Returns:
        List of WebSocket messages to send to client
    """
    event_class_name = type(event).__name__
    messages = []

    # Handle typed event objects from agent.py
    if event_class_name == "ContentDeltaEvent":
        # Text content - append to current text block or create new one
        text_block_id = state.get_or_create_text_block_id()
        messages.append(
            {
                "type": "text_delta",
                "id": text_block_id,
                "text": event.text,
            }
        )

    elif event_class_name == "ToolCallStartEvent":
        # Tool call starting - create new tool block
        tool_id = state.create_tool_id(event.tool_name)
        messages.append(
            {
                "type": "tool_start",
                "id": tool_id,
                "tool_name": event.tool_name,
                "input": event.input_data,
            }
        )

    elif event_class_name == "ToolCallEndEvent":
        # Tool call completed - update existing tool block
        tool_id = state.get_tool_id(event.tool_name)
        if tool_id:
            messages.append(
                {
                    "type": "tool_end",
                    "id": tool_id,
                    "output": event.output_data,
                    "success": event.success,
                }
            )
        else:
            logger.warning(
                f"Received tool_end for {event.tool_name} but no ID found"
            )

    elif event_class_name == "MessageCompleteEvent":
        # Message finished - send usage stats
        messages.append(
            {
                "type": "message_complete",
                "usage": {
                    "input_tokens": event.input_tokens,
                    "output_tokens": event.output_tokens,
                    "cost_usd": event.cost_usd,
                    "duration_ms": event.duration_ms,
                },
            }
        )

    elif event_class_name == "StatusUpdateEvent":
        # Status update (e.g., "Thinking...")
        messages.append(
            {
                "type": "status",
                "message": event.message,
            }
        )

    # Fallback: Handle raw SDK messages for compatibility
    elif event_class_name == "StreamEvent":
        event_data = getattr(event, "event", {})
        if event_data.get("type") == "content_block_delta":
            delta = event_data.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")
                text_block_id = state.get_or_create_text_block_id()
                messages.append(
                    {
                        "type": "text_delta",
                        "id": text_block_id,
                        "text": text,
                    }
                )

    elif event_class_name == "ToolUseBlock":
        tool_id = state.create_tool_id(getattr(event, "name", "unknown"))
        messages.append(
            {
                "type": "tool_start",
                "id": tool_id,
                "tool_name": getattr(event, "name", "unknown"),
                "input": getattr(event, "input", {}),
            }
        )

    elif event_class_name == "ResultMessage":
        usage = getattr(event, "usage", None)
        if usage:
            messages.append(
                {
                    "type": "message_complete",
                    "usage": {
                        "input_tokens": getattr(usage, "input_tokens", 0),
                        "output_tokens": getattr(usage, "output_tokens", 0),
                        "cost_usd": 0.0,
                        "duration_ms": 0,
                    },
                }
            )

    return messages


class WebUIServer:
    """Web UI server using FastAPI"""

    def __init__(
        self,
        agent_factory: Callable,
        host: str = "localhost",
        port: int = 8765,
    ):
        self.agent_factory = agent_factory
        self.host = host
        self.port = port
        self.app = FastAPI(title="bassi Web UI")

        # Track active WebSocket connections and their agents
        self.active_connections: list[WebSocket] = []
        # connection_id -> {"agent": agent, "state": SessionState}
        self.active_sessions: dict[str, dict[str, Any]] = {}

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes"""

        # Add cache-control middleware for all responses (no-cache in development)
        @self.app.middleware("http")
        async def add_cache_headers(request, call_next):
            response = await call_next(request)
            # Disable caching for static files and HTML in development
            if (
                request.url.path.startswith("/static/")
                or request.url.path == "/"
            ):
                response.headers["Cache-Control"] = (
                    "no-cache, no-store, must-revalidate"
                )
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
            return response

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
                # Inject version number into HTML
                html_content = index_path.read_text()
                html_content = html_content.replace(
                    "{{VERSION}}", __version__
                )
                return HTMLResponse(content=html_content)
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
        """Handle WebSocket connection with isolated agent instance"""
        # Generate unique connection ID
        connection_id = str(uuid.uuid4())

        # Create dedicated agent instance and session state
        agent = self.agent_factory()
        state = SessionState()
        self.active_sessions[connection_id] = {"agent": agent, "state": state}

        await websocket.accept()
        self.active_connections.append(websocket)

        logger.info(
            f"New session: {connection_id[:8]}... | Total connections: {len(self.active_connections)}"
        )

        try:
            # Send welcome message with session ID
            await websocket.send_json(
                {
                    "type": "connected",
                    "session_id": connection_id,
                    "message": "Connected to bassi",
                }
            )

            # Listen for messages
            while True:
                data = await websocket.receive_json()
                await self._process_message(websocket, data, connection_id)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {connection_id[:8]}...")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            # Clean up agent and session
            if connection_id in self.active_sessions:
                try:
                    session = self.active_sessions[connection_id]
                    await session["agent"].cleanup()
                except Exception as e:
                    logger.error(f"Error cleaning up agent: {e}")
                del self.active_sessions[connection_id]

            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

            logger.info(
                f"Session ended: {connection_id[:8]}... | Remaining connections: {len(self.active_connections)}"
            )

    async def _process_message(
        self, websocket: WebSocket, data: dict[str, Any], connection_id: str
    ):
        """Process incoming message from client using dedicated agent instance"""
        msg_type = data.get("type")

        # Get session data
        session = self.active_sessions.get(connection_id)
        if not session:
            logger.error(
                f"No session found for connection {connection_id[:8]}..."
            )
            return

        agent = session["agent"]
        state = session["state"]

        if msg_type == "user_message":
            # User sent a chat message
            content = data.get("content", "")
            logger.info(f"User message: {content[:100]}...")

            # Start new assistant message (resets counters)
            state.new_message()

            # Stream response from THIS agent instance only
            try:
                async for event in agent.chat(content):
                    # Convert agent event to WebSocket messages with IDs
                    ws_messages = convert_event_to_messages(event, state)

                    # Send all messages from this event
                    for ws_message in ws_messages:
                        msg_type = ws_message.get("type", "unknown")
                        if msg_type == "tool_end":
                            logger.info(
                                f"📤 Sending tool_end: {ws_message.get('id')} "
                                f"(success={ws_message.get('success')})"
                            )
                        await websocket.send_json(ws_message)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_json(
                    {"type": "error", "message": str(e)}
                )

        elif msg_type == "interrupt":
            # User requested to interrupt agent execution
            logger.info("Interrupt request received")
            try:
                await agent.interrupt()
                await websocket.send_json(
                    {
                        "type": "interrupted",
                        "message": "Agent execution stopped",
                    }
                )
                logger.info("Agent interrupted successfully")
            except Exception as e:
                logger.error(f"Failed to interrupt agent: {e}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Failed to interrupt: {str(e)}",
                    }
                )

        else:
            logger.warning(f"Unknown message type: {msg_type}")

    async def run(self, reload: bool = False):
        """
        Run the web server

        Args:
            reload: Enable hot reload for development (watches Python files)
        """

        import uvicorn

        logger.info(
            f"Starting web UI server on http://{self.host}:{self.port}"
        )

        if reload:
            logger.info(
                "🔥 Hot reload enabled - server will restart on file changes"
            )
            logger.info("   Watching Python: bassi/**/*.py")
            logger.info("   Watching Static: bassi/static/*.{html,css,js}")
            logger.info("")
            logger.info(
                "💡 Tip: Edit files and they'll auto-reload in ~2-3 seconds"
            )
            logger.info("")

        if reload:
            # For hot reload to work, we need to use uvicorn CLI
            # which spawns a reloader subprocess that watches files
            import sys

            bassi_dir = Path(__file__).parent.parent

            # Build uvicorn command
            # Let uvicorn use its defaults (*.py) - don't override
            cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                "bassi.web_server:create_app",
                "--factory",
                "--host",
                self.host,
                "--port",
                str(self.port),
                "--reload",
                "--reload-dir",
                str(bassi_dir),
            ]

            logger.info(f"Starting uvicorn with command: {' '.join(cmd)}")

            # Run uvicorn in a subprocess (don't wait for it to finish)
            import anyio

            process = await anyio.open_process(cmd)
            logger.info(f"Uvicorn process started with PID: {process.pid}")

            # Wait for the process (it will run forever in reload mode)
            await process.wait()
        else:
            # Production mode - use Server.serve()
            config = uvicorn.Config(
                app=self.app,
                host=self.host,
                port=self.port,
                log_level="info",
            )
            server = uvicorn.Server(config)
            await server.serve()


def create_app() -> FastAPI:
    """
    Factory function to create FastAPI app instance.
    Used by uvicorn reload mode.

    IMPORTANT: This must be standalone (no runtime globals) because
    uvicorn spawns a new Python process on reload that won't have
    runtime globals set.
    """
    # Import here to avoid circular imports
    import os

    from bassi.agent import BassiAgent

    # Read config from environment variables (set by start_web_server)
    host = os.getenv("BASSI_HOST", "localhost")
    port = int(os.getenv("BASSI_PORT", "8765"))

    # Display tools once at startup (when uvicorn loads the app)
    # Create a temporary agent just to display the tools list
    _display_agent = BassiAgent(
        status_callback=None,
        resume_session_id=None,
        display_tools=True,  # Show tools once at startup
    )
    # Note: We don't clean up this agent since cleanup() is async
    # It will be garbage collected and its resources released naturally

    # Create default agent factory - each connection gets its own agent
    def agent_factory():
        return BassiAgent(
            status_callback=None,
            resume_session_id=None,
            display_tools=False,  # Suppress tools display for web UI agents
        )

    server = WebUIServer(agent_factory, host, port)
    return server.app


async def start_web_server(
    agent_factory: Callable,
    host: str = "localhost",
    port: int = 8765,
    reload: bool = False,
):
    """
    Start the web UI server

    Args:
        agent_factory: Factory function to create BassiAgent instances
        host: Server host
        port: Server port
        reload: Enable hot reload for development
    """
    import os

    # Set config in environment variables for reload mode
    # (uvicorn spawns new process that needs these)
    os.environ["BASSI_HOST"] = host
    os.environ["BASSI_PORT"] = str(port)

    server = WebUIServer(agent_factory, host, port)
    await server.run(reload=reload)
