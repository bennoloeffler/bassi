"""
Web server V3 - Built on Claude Agent SDK.

This module provides the FastAPI web server that connects the web UI
to BassiAgentSession (which wraps ClaudeSDKClient from claude-agent-sdk).

Key differences from V2 web_server.py:
- Uses BassiAgentSession instead of BassiAgent
- Uses message_converter to transform Agent SDK messages
- Simpler architecture (no custom event system needed)
"""

import asyncio
import logging
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import (
    FastAPI,
    File,
    Form,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig
from bassi.core_v3.interactive_questions import InteractiveQuestionService
from bassi.core_v3.message_converter import convert_message_to_websocket
from bassi.core_v3.session_index import SessionIndex
from bassi.core_v3.session_naming import SessionNamingService
from bassi.core_v3.session_workspace import SessionWorkspace
from bassi.core_v3.tools import create_bassi_tools
from bassi.core_v3.upload_service import (
    FileTooLargeError,
    InvalidFilenameError,
    UploadService,
)
from bassi.shared.mcp_registry import create_mcp_registry
from bassi.shared.permission_config import get_permission_mode
from bassi.shared.sdk_loader import create_sdk_mcp_server
from bassi.shared.sdk_types import SystemMessage, ToolResultBlock, UserMessage

from bassi.core_v3.services.error_recovery_service import (
    ErrorRecoveryService,
    get_error_recovery_service,
)

# Logging configured by entry point (cli.py)
logger = logging.getLogger(__name__)


class WebUIServerV3:
    """
    Web UI server using FastAPI and Agent SDK.

    Each WebSocket connection gets its own BassiAgentSession instance,
    ensuring complete isolation between conversations.
    """

    def __init__(
        self,
        session_factory: Callable[
            [InteractiveQuestionService, SessionWorkspace], BassiAgentSession
        ],
        host: str = "localhost",
        port: int = 8765,
        workspace_base_path: Optional[Path] = None,
    ):
        """
        Initialize web server.

        Args:
            session_factory: Factory function to create BassiAgentSession instances
                           Takes InteractiveQuestionService and SessionWorkspace as parameters
            host: Server hostname
            port: Server port
            workspace_base_path: Base directory for session workspaces (default: "chats")
        """
        self.session_factory = session_factory
        self.host = host
        self.port = port
        self.app = FastAPI(title="Bassi Web UI V3")

        # Track active WebSocket connections
        self.active_connections: list[WebSocket] = []
        # connection_id -> BassiAgentSession
        self.active_sessions: dict[str, BassiAgentSession] = {}
        # connection_id -> InteractiveQuestionService
        self.question_services: dict[str, InteractiveQuestionService] = {}

        # Session workspace infrastructure
        self.upload_service = UploadService()
        self.workspace_base_path = workspace_base_path or Path("chats")
        self.session_index = SessionIndex(base_path=self.workspace_base_path)
        self.naming_service = SessionNamingService()
        # session_id -> SessionWorkspace (active workspaces)
        self.workspaces: dict[str, SessionWorkspace] = {}

        self._setup_routes()

    def _setup_routes(self):
        """Set up FastAPI routes"""

        # Add cache-control middleware for development (enables browser hot reload)
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

        # Serve static files (HTML, CSS, JS)
        static_dir = Path(__file__).parent.parent / "static"
        if static_dir.exists():
            self.app.mount(
                "/static", StaticFiles(directory=static_dir), name="static"
            )

            # Serve index.html at root
            @self.app.get("/", response_class=HTMLResponse)
            async def root():
                with open(static_dir / "index.html") as f:
                    return HTMLResponse(content=f.read())

        # Health check
        @self.app.get("/health")
        async def health():
            return JSONResponse(
                {
                    "status": "ok",
                    "service": "bassi-web-ui-v3",
                    "active_sessions": len(self.active_sessions),
                }
            )

        # Capabilities endpoint - provides session metadata
        @self.app.get("/api/capabilities")
        async def get_capabilities():
            """
            Get session capabilities via discovery + SDK.

            Returns available tools, MCP servers, slash commands,
            skills, and agents for the current session.

            This is a REST endpoint separate from WebSocket to provide
            semantic clarity (capabilities are metadata, not conversation).
            """
            try:
                from bassi.core_v3.discovery import BassiDiscovery

                # Get filesystem discovery data
                discovery = BassiDiscovery()
                summary = discovery.get_summary()

                # Transform MCP servers with status field
                mcp_servers = []
                for name, config in summary.get("mcp_servers", {}).items():
                    mcp_servers.append(
                        {
                            "name": name,
                            "status": "configured",  # Could be enhanced to check if running
                            **config,
                        }
                    )

                # Initialize with discovery data (will be overridden by SDK if available)
                slash_commands = []
                for source, commands in summary.get(
                    "slash_commands", {}
                ).items():
                    slash_commands.extend(commands)

                skills = summary.get("skills", [])

                # Get SDK tools and agents
                # Tools are only available during an active conversation,
                # so we need to send a query to trigger tool discovery
                tools = []
                agents = []

                temp_service = InteractiveQuestionService()
                temp_workspace = SessionWorkspace(
                    "capabilities-discovery", create=True
                )
                temp_session = self.session_factory(
                    temp_service, temp_workspace
                )
                try:
                    await temp_session.connect()

                    # Send a minimal query to trigger tool discovery
                    # The SDK will respond with available tools in SystemMessage
                    tools_found = []

                    logger.info("🔍 Starting tool discovery query...")
                    async for message in temp_session.query(
                        "ready", session_id="capabilities-discovery"
                    ):
                        # Extract tool names from system message
                        if isinstance(message, SystemMessage):
                            logger.info(
                                f"✅ Found SystemMessage with subtype: {message.subtype}"
                            )

                            # Extract data from SystemMessage.data
                            if isinstance(message.data, dict):
                                # Get tools (list of dicts with 'name' key)
                                sdk_tools = message.data.get("tools", [])
                                for tool in sdk_tools:
                                    if (
                                        isinstance(tool, dict)
                                        and "name" in tool
                                    ):
                                        tools_found.append(tool["name"])
                                    elif isinstance(tool, str):
                                        tools_found.append(tool)

                                # Extract agents
                                sdk_agents = message.data.get("agents", [])
                                if sdk_agents:
                                    agents = sdk_agents

                                # Extract slash commands from SDK (overrides discovery)
                                sdk_slash_commands = message.data.get(
                                    "slash_commands", []
                                )
                                if sdk_slash_commands:
                                    slash_commands = sdk_slash_commands

                                # Extract skills from SDK (overrides discovery)
                                sdk_skills = message.data.get("skills", [])
                                if sdk_skills:
                                    skills = sdk_skills

                                logger.info(
                                    f"✅ Extracted {len(tools_found)} tools, {len(slash_commands)} commands, {len(agents)} agents"
                                )
                            else:
                                logger.warning(
                                    "⚠️ SystemMessage.data is not a dict!"
                                )

                            break  # Stop after getting system message

                    logger.info(
                        f"✅ Tool discovery complete. Found {len(tools_found)} tools"
                    )
                    tools = tools_found

                    await temp_session.disconnect()
                except Exception as sdk_error:
                    logger.warning(
                        f"Could not fetch SDK tools: {sdk_error}",
                        exc_info=True,
                    )
                    # Continue without SDK tools - discovery data still works

                return JSONResponse(
                    {
                        "tools": tools,
                        "mcp_servers": mcp_servers,
                        "slash_commands": slash_commands,
                        "skills": skills,
                        "agents": agents,
                    }
                )
            except Exception as e:
                logger.error(
                    f"Error fetching capabilities: {e}", exc_info=True
                )
                return JSONResponse({"error": str(e)}, status_code=500)

        # File upload endpoint (session-aware)
        @self.app.post("/api/upload")
        async def upload_file(
            session_id: str = Form(...),
            file: UploadFile = File(...),
        ):
            """
            Upload a file to session-specific workspace.

            Args:
                session_id: Session ID for workspace isolation
                file: Uploaded file from multipart/form-data

            Returns:
                JSON with file metadata: path, size, media_type, filename
            """
            try:
                # Get workspace for this session
                workspace = self.workspaces.get(session_id)
                if not workspace:
                    return JSONResponse(
                        {"error": f"Session not found: {session_id}"},
                        status_code=404,
                    )

                # Upload file using UploadService
                file_path = await self.upload_service.upload_to_session(
                    file, workspace
                )

                # Get file info
                file_info = self.upload_service.get_upload_info(
                    file_path, workspace
                )

                logger.info(
                    f"📁 Uploaded to session {session_id[:8]}: "
                    f"{file.filename} -> {file_info['path']}"
                )

                return JSONResponse(file_info)

            except FileTooLargeError as e:
                logger.warning(f"File too large: {file.filename} - {e}")
                return JSONResponse(
                    {"error": str(e)},
                    status_code=413,
                )

            except InvalidFilenameError as e:
                logger.warning(f"Invalid filename: {e}")
                return JSONResponse(
                    {"error": str(e)},
                    status_code=400,
                )

            except Exception as e:
                logger.error(f"File upload failed: {e}", exc_info=True)
                return JSONResponse(
                    {"error": f"Upload failed: {str(e)}"},
                    status_code=500,
                )

        # Session management endpoints
        @self.app.get("/api/sessions")
        async def list_sessions(
            limit: int = 100,
            offset: int = 0,
            sort_by: str = "last_activity",
            order: str = "desc",
        ):
            """
            List all sessions with pagination and sorting.

            Args:
                limit: Maximum number of sessions to return (default 100)
                offset: Number of sessions to skip (default 0)
                sort_by: Field to sort by (created_at, last_activity, display_name)
                order: Sort order (asc, desc)

            Returns:
                JSON with sessions list and metadata
            """
            try:
                # Get all sessions from index (without pagination at this level)
                all_sessions = list(
                    self.session_index.index["sessions"].values()
                )

                # Sort sessions
                reverse = order == "desc"
                if sort_by == "created_at":
                    all_sessions.sort(
                        key=lambda s: s.get("created_at", ""),
                        reverse=reverse,
                    )
                elif sort_by == "last_activity":
                    all_sessions.sort(
                        key=lambda s: s.get("last_activity", ""),
                        reverse=reverse,
                    )
                elif sort_by == "display_name":
                    all_sessions.sort(
                        key=lambda s: s.get("display_name", ""),
                        reverse=reverse,
                    )

                # Apply pagination
                total = len(all_sessions)
                sessions = all_sessions[offset : offset + limit]

                return JSONResponse(
                    {
                        "sessions": sessions,
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                    }
                )

            except Exception as e:
                logger.error(f"Failed to list sessions: {e}", exc_info=True)
                return JSONResponse(
                    {"error": f"Failed to list sessions: {str(e)}"},
                    status_code=500,
                )

        @self.app.get("/api/sessions/{session_id}")
        async def get_session(session_id: str):
            """
            Get detailed information about a specific session.

            Args:
                session_id: Session ID to retrieve

            Returns:
                JSON with session details
            """
            try:
                # Try to get workspace from active sessions
                workspace = self.workspaces.get(session_id)

                # If not active, try to load from disk
                if not workspace:
                    if not SessionWorkspace.exists(session_id):
                        return JSONResponse(
                            {"error": f"Session not found: {session_id}"},
                            status_code=404,
                        )
                    workspace = SessionWorkspace.load(session_id)

                # Get session stats
                stats = workspace.get_stats()

                return JSONResponse(stats)

            except Exception as e:
                logger.error(
                    f"Failed to get session {session_id}: {e}",
                    exc_info=True,
                )
                return JSONResponse(
                    {"error": f"Failed to get session: {str(e)}"},
                    status_code=500,
                )

        # 🗑️ PHASE 2.2: Session deletion endpoint
        @self.app.delete("/api/sessions/{session_id}")
        async def delete_session(session_id: str):
            """
            Delete a session and all its data.

            Args:
                session_id: Session ID to delete

            Returns:
                JSON with success status

            Raises:
                400: Cannot delete active session
                404: Session not found
                500: Deletion failed
            """
            try:
                # Don't allow deleting active session
                if session_id in self.active_sessions:
                    logger.warning(
                        f"❌ Cannot delete active session: {session_id[:8]}..."
                    )
                    return JSONResponse(
                        {"error": "Cannot delete active session"},
                        status_code=400,
                    )

                # Check if session exists
                if not SessionWorkspace.exists(session_id):
                    logger.warning(
                        f"❌ Session not found: {session_id[:8]}..."
                    )
                    return JSONResponse(
                        {"error": "Session not found"},
                        status_code=404,
                    )

                # Load workspace to delete
                workspace = SessionWorkspace.load(session_id)

                # Remove from index first
                self.session_index.remove_session(session_id)

                # Delete workspace (removes files + symlink)
                workspace.delete()

                logger.info(f"🗑️  Deleted session: {session_id[:8]}...")

                return JSONResponse(
                    {"success": True, "session_id": session_id}
                )

            except Exception as e:
                logger.error(
                    f"Failed to delete session {session_id}: {e}",
                    exc_info=True,
                )
                return JSONResponse(
                    {"error": f"Failed to delete session: {str(e)}"},
                    status_code=500,
                )

        # Session files listing endpoint
        @self.app.get("/api/sessions/{session_id}/files")
        async def list_session_files(session_id: str):
            """
            List all uploaded files for a session.

            Args:
                session_id: Session ID to list files for

            Returns:
                JSON with list of files and their metadata
            """
            try:
                # Get workspace for this session
                workspace = self.workspaces.get(session_id)
                if not workspace:
                    return JSONResponse(
                        {"error": f"Session not found: {session_id}"},
                        status_code=404,
                    )

                # Get DATA_FROM_USER directory
                data_dir = workspace.physical_path / "DATA_FROM_USER"
                if not data_dir.exists():
                    return JSONResponse({"files": []})

                # List all files
                files = []
                for file_path in sorted(data_dir.iterdir()):
                    if file_path.is_file():
                        file_info = self.upload_service.get_upload_info(
                            file_path, workspace
                        )
                        files.append(file_info)

                return JSONResponse({"files": files})

            except Exception as e:
                logger.error(
                    f"Failed to list files for session {session_id}: {e}",
                    exc_info=True,
                )
                return JSONResponse(
                    {"error": f"Failed to list files: {str(e)}"},
                    status_code=500,
                )

        # Session messages endpoint
        @self.app.get("/api/sessions/{session_id}/messages")
        async def get_session_messages(session_id: str):
            """
            Load message history from history.md file.

            Args:
                session_id: Session ID to load messages for

            Returns:
                JSON with list of messages [{role, content, timestamp}]
            """
            try:
                # Check if session exists
                if not SessionWorkspace.exists(session_id):
                    return JSONResponse(
                        {"error": f"Session not found: {session_id}"},
                        status_code=404,
                    )

                # Load workspace
                workspace = self.workspaces.get(session_id)
                if not workspace:
                    workspace = SessionWorkspace.load(session_id)

                # Read history.md file
                history_path = workspace.physical_path / "history.md"
                if not history_path.exists():
                    return JSONResponse({"messages": []})

                # Parse history.md
                messages = []
                current_message = None

                with open(history_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.rstrip()

                        # Skip title line
                        if line.startswith("# Chat History:"):
                            continue

                        # Parse message header: ## Role - Timestamp
                        if line.startswith("## "):
                            # Save previous message if exists
                            if (
                                current_message
                                and current_message["content"].strip()
                            ):
                                messages.append(current_message)

                            # Parse new message header
                            parts = line[3:].split(" - ", 1)
                            if len(parts) == 2:
                                role, timestamp = parts
                                current_message = {
                                    "role": role.strip().lower(),
                                    "content": "",
                                    "timestamp": timestamp.strip(),
                                }
                        # Accumulate content lines
                        elif current_message is not None:
                            if current_message["content"]:
                                current_message["content"] += "\n"
                            current_message["content"] += line

                # Don't forget the last message
                if current_message and current_message["content"].strip():
                    messages.append(current_message)

                return JSONResponse({"messages": messages})

            except Exception as e:
                logger.error(
                    f"Failed to load messages for session {session_id}: {e}",
                    exc_info=True,
                )
                return JSONResponse(
                    {"error": f"Failed to load messages: {str(e)}"},
                    status_code=500,
                )

        # WebSocket endpoint
        @self.app.websocket("/ws")
        async def websocket_endpoint(
            websocket: WebSocket, session_id: Optional[str] = None
        ):
            await self._handle_websocket(websocket, session_id)

    async def _handle_websocket(
        self, websocket: WebSocket, requested_session_id: Optional[str] = None
    ):
        """
        Handle WebSocket connection with isolated agent session.

        Args:
            websocket: WebSocket connection
            requested_session_id: Optional session ID to resume (from query param)
        """
        # Determine session ID: use provided if valid, otherwise create new
        if requested_session_id and SessionWorkspace.exists(
            requested_session_id, base_path=self.workspace_base_path
        ):
            connection_id = requested_session_id
            logger.info(f"🔷 [WS] Resuming session: {connection_id[:8]}...")
        else:
            connection_id = str(uuid.uuid4())
            logger.info(
                f"🔷 [WS] Generated new connection ID: {connection_id[:8]}..."
            )

        # Create or load session workspace
        if SessionWorkspace.exists(
            connection_id, base_path=self.workspace_base_path
        ):
            workspace = SessionWorkspace.load(
                connection_id, base_path=self.workspace_base_path
            )
            logger.info(
                f"✅ Loaded existing workspace: {connection_id[:8]}... "
                f"(files: {workspace.metadata.get('file_count', 0)})"
            )
        else:
            workspace = SessionWorkspace(
                connection_id, base_path=self.workspace_base_path, create=True
            )
            workspace.update_display_name(f"Session {connection_id[:8]}")
            self.session_index.add_session(workspace)
            logger.info(f"✅ Created new workspace: {connection_id[:8]}...")

        self.workspaces[connection_id] = workspace

        # Create interactive question service for this session
        logger.info("🔷 [WS] Creating InteractiveQuestionService...")
        question_service = InteractiveQuestionService()
        question_service.websocket = websocket
        self.question_services[connection_id] = question_service
        logger.info("🔷 [WS] InteractiveQuestionService created")

        # Create dedicated agent session with question service and workspace
        logger.info("🔷 [WS] Creating agent session via factory...")
        session = self.session_factory(question_service, workspace)
        self.active_sessions[connection_id] = session
        logger.info(f"🔷 [WS] Agent session created: {type(session)}")

        # CRITICAL FIX: Restore conversation history for existing sessions
        if requested_session_id and SessionWorkspace.exists(
            requested_session_id, base_path=self.workspace_base_path
        ):
            logger.info(
                "🔷 [WS] Loading conversation history from workspace..."
            )
            history = workspace.load_conversation_history()
            if history:
                session.restore_conversation_history(history)
                logger.info(
                    f"✅ [WS] Restored {len(history)} messages to SDK context"
                )
            else:
                logger.info("ℹ️ [WS] No conversation history to restore")

        logger.info("🔷 [WS] Accepting WebSocket connection...")
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("🔷 [WS] WebSocket accepted")

        logger.info(
            f"New session: {connection_id[:8]}... | Total connections: {len(self.active_connections)}"
        )

        try:
            # Send status update before connecting
            await websocket.send_json(
                {
                    "type": "status",
                    "message": "🔌 Connecting to Claude Agent SDK...",
                }
            )

            # Connect agent session
            logger.info("🔷 [WS] Calling session.connect()...")
            await session.connect()
            logger.info("🔷 [WS] session.connect() completed")

            # Send status update after connecting
            await websocket.send_json(
                {
                    "type": "status",
                    "message": "✅ Claude Agent SDK connected successfully",
                }
            )

            # Send connected event to trigger welcome box
            logger.info("🔷 [WS] Sending 'connected' event to client...")
            await websocket.send_json(
                {
                    "type": "connected",
                    "session_id": connection_id,
                }
            )
            logger.info("🔷 [WS] 'connected' event sent successfully")

            # NOTE: Capabilities are now fetched via REST endpoint /api/capabilities
            # (removed confusing empty query startup hack)

            # Listen for messages
            # We need to handle messages concurrently so we don't block
            # when waiting for tool responses (like AskUserQuestion)
            async def message_receiver():
                """Continuously receive and process WebSocket messages"""
                try:
                    while True:
                        data = await websocket.receive_json()
                        # Process message without awaiting to avoid blocking
                        asyncio.create_task(
                            self._process_message(
                                websocket, data, connection_id
                            )
                        )
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.error(
                        f"Message receiver error: {e}", exc_info=True
                    )

            # Start message receiver as background task and keep connection alive
            receiver_task = asyncio.create_task(message_receiver())
            await receiver_task

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {connection_id[:8]}...")
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
        finally:
            # Cancel any pending questions
            if connection_id in self.question_services:
                question_service = self.question_services[connection_id]
                question_service.cancel_all()
                del self.question_services[connection_id]

            # 🧹 PHASE 3: Auto-cleanup empty sessions
            # Delete session if no messages were exchanged
            workspace = self.workspaces.get(connection_id)
            if workspace and workspace.metadata.get("message_count", 0) == 0:
                logger.info(
                    f"🧹 Deleting empty session: {connection_id[:8]}..."
                )
                try:
                    self.session_index.remove_session(connection_id)
                    workspace.delete()
                except Exception as e:
                    logger.error(f"Failed to cleanup empty session: {e}")

            # Clean up session
            if connection_id in self.active_sessions:
                try:
                    session = self.active_sessions[connection_id]
                    await session.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting session: {e}")
                del self.active_sessions[connection_id]

            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

            logger.info(
                f"Session ended: {connection_id[:8]}... | Remaining: {len(self.active_connections)}"
            )

    async def _process_message(
        self, websocket: WebSocket, data: dict[str, Any], connection_id: str
    ):
        """Process incoming message from client"""
        msg_type = data.get("type")

        # Get session
        session = self.active_sessions.get(connection_id)
        if not session:
            return

        if msg_type == "user_message":
            # User sent a chat message
            content = data.get("content", "")

            # Normalize content to content blocks array
            # Support both string (backward compatible) and array (multimodal)
            if isinstance(content, str):
                # Text-only message (backward compatible)
                content_blocks = (
                    [{"type": "text", "text": content}] if content else []
                )
                echo_content = content
            elif isinstance(content, list):
                # Multimodal content blocks
                content_blocks = content
                # Extract text for echo (for UI display)
                text_blocks = [b for b in content if b.get("type") == "text"]
                echo_content = (
                    text_blocks[0].get("text", "") if text_blocks else ""
                )
            else:
                logger.error(f"Invalid content type: {type(content)}")
                return

            # Process and save images if present
            await self._process_images(content_blocks)

            # IMPORTANT: Echo user's message back so it appears in conversation history
            await websocket.send_json(
                {
                    "type": "user_message_echo",
                    "content": echo_content,
                }
            )

            # Handle /help command - show available capabilities
            if echo_content.strip().lower() in ["/help", "help", "/?"]:
                from bassi.core_v3.discovery import BassiDiscovery

                discovery = BassiDiscovery(
                    Path(__file__).parent.parent.parent
                )
                discovery_summary = discovery.get_summary()

                # Format help message with better structure
                mcp_servers = discovery_summary.get("mcp_servers", {})
                project_cmds = discovery_summary["slash_commands"]["project"]
                personal_cmds = discovery_summary["slash_commands"][
                    "personal"
                ]
                skills = discovery_summary.get("skills", [])

                help_message = """<div class="help-container">
<h1>🎯 Bassi Help Guide</h1>

<div class="help-intro">
<p>Bassi gives you access to multiple types of capabilities. Here's what you have available and how to use them:</p>
</div>

<div class="help-section">
<h2>📚 Understanding the Different Types</h2>

<div class="concept-box">
<h3>🔌 MCP Servers (Model Context Protocol)</h3>
<p><strong>What:</strong> External services that provide specialized tools and data access</p>
<p><strong>When:</strong> Database queries, email access, web automation, external APIs</p>
<p><strong>How:</strong> Just ask me naturally - I'll use the right MCP tools automatically</p>
<p><strong>Example:</strong> <em>"Show me all companies in the PostgreSQL database"</em> → I use the <code>postgresql</code> MCP server</p>
</div>

<div class="concept-box">
<h3>💻 Slash Commands</h3>
<p><strong>What:</strong> Pre-defined workflows that extract data and perform complex tasks</p>
<p><strong>When:</strong> Structured data entry, multi-step processes, guided workflows</p>
<p><strong>How:</strong> Type the command name starting with <code>/</code></p>
<p><strong>Example:</strong> <code>/crm Add company TechStart GmbH in Berlin</code> → Extracts data and creates CRM records</p>
</div>

<div class="concept-box">
<h3>🎯 Skills</h3>
<p><strong>What:</strong> Knowledge libraries with schemas, workflows, and domain expertise</p>
<p><strong>When:</strong> Working with databases, documents, specialized domains</p>
<p><strong>How:</strong> I load them automatically when needed - you don't call them directly</p>
<p><strong>Example:</strong> When you use <code>/crm</code>, I automatically load the <code>crm-db</code> skill for database schema knowledge</p>
</div>

<div class="concept-box">
<h3>🤖 Agents (Sub-agents)</h3>
<p><strong>What:</strong> Specialized AI assistants for specific complex tasks</p>
<p><strong>When:</strong> Code review, testing, debugging, long-running analysis</p>
<p><strong>How:</strong> I can spawn them as needed for specialized work</p>
<p><strong>Example:</strong> <em>"Review this code for security issues"</em> → I might spawn a security-auditor agent</p>
</div>
</div>

<div class="help-section">
<h2>📡 MCP Servers ({len(mcp_servers)})</h2>
"""

                # Add each MCP server in a nice box
                mcp_descriptions = {
                    "ms365": {
                        "desc": "Microsoft 365 integration - emails, calendar, contacts",
                        "tools": [
                            "read emails",
                            "send emails",
                            "schedule meetings",
                            "list contacts",
                        ],
                        "example": '"Check my emails from today"',
                    },
                    "playwright": {
                        "desc": "Web browser automation and testing",
                        "tools": [
                            "navigate websites",
                            "take screenshots",
                            "fill forms",
                            "click elements",
                        ],
                        "example": '"Take a screenshot of example.com"',
                    },
                    "postgresql": {
                        "desc": "PostgreSQL database access for CRM data",
                        "tools": [
                            "query database",
                            "list tables",
                            "insert records",
                            "update records",
                        ],
                        "example": '"Show all companies in the database"',
                    },
                }

                for name, config in mcp_servers.items():
                    desc_info = mcp_descriptions.get(
                        name,
                        {"desc": "MCP server", "tools": [], "example": ""},
                    )
                    help_message += f"""
<div class="mcp-box">
<h3 class="mcp-name">{name}</h3>
<p class="mcp-desc">{desc_info['desc']}</p>
<div class="mcp-tools">
<strong>Available tools:</strong> {', '.join(desc_info['tools']) if desc_info['tools'] else 'Multiple tools available'}
</div>
<div class="mcp-example">
<strong>Example:</strong> <em>{desc_info['example'] if desc_info['example'] else f'Use the {name} server'}</em>
</div>
</div>
"""

                help_message += """
</div>

<div class="help-section">
<h2>💻 Slash Commands ({len(project_cmds) + len(personal_cmds)})</h2>
"""

                # Command descriptions
                cmd_descriptions = {
                    "/crm": {
                        "desc": "Extract CRM data from text and manage database records",
                        "example": "<code>/crm New company: TechStart GmbH, Berlin, Software Development industry</code>",
                    },
                    "/epct": {
                        "desc": "Personal command for EPCT-related tasks",
                        "example": "<code>/epct [your command]</code>",
                    },
                    "/crm-analyse-customer": {
                        "desc": "Analyze customer data and generate insights",
                        "example": "<code>/crm-analyse-customer CompanyName</code>",
                    },
                }

                if project_cmds:
                    help_message += "<h3>Project Commands:</h3>"
                    for cmd in project_cmds:
                        cmd_info = cmd_descriptions.get(
                            cmd["name"],
                            {"desc": "Command", "example": cmd["name"]},
                        )
                        help_message += f"""
<div class="command-box">
<h4 class="command-name">{cmd['name']}</h4>
<p class="command-desc">{cmd_info['desc']}</p>
<div class="command-example">
<strong>Example:</strong> {cmd_info['example']}
</div>
</div>
"""

                if personal_cmds:
                    help_message += "<h3>Personal Commands:</h3>"
                    for cmd in personal_cmds:
                        cmd_info = cmd_descriptions.get(
                            cmd["name"],
                            {
                                "desc": "Personal command",
                                "example": cmd["name"],
                            },
                        )
                        help_message += f"""
<div class="command-box">
<h4 class="command-name">{cmd['name']}</h4>
<p class="command-desc">{cmd_info['desc']}</p>
<div class="command-example">
<strong>Example:</strong> {cmd_info['example']}
</div>
</div>
"""

                help_message += f"""
</div>

<div class="help-section">
<h2>🎯 Skills ({len(skills)})</h2>
<p class="skills-intro">Skills are automatically loaded when needed - you don't need to call them directly!</p>
"""

                # Skill descriptions
                skill_descriptions = {
                    "crm-db": {
                        "desc": "CRM database schema and query knowledge",
                        "used_by": "Automatically loaded by /crm command",
                    },
                    "xlsx": {
                        "desc": "Excel spreadsheet creation and editing",
                        "used_by": "When working with .xlsx files",
                    },
                    "pdf": {
                        "desc": "PDF document creation and manipulation",
                        "used_by": "When working with .pdf files",
                    },
                    "docx": {
                        "desc": "Word document creation and editing",
                        "used_by": "When working with .docx files",
                    },
                    "pptx": {
                        "desc": "PowerPoint presentation creation",
                        "used_by": "When working with .pptx files",
                    },
                }

                for skill in skills:
                    skill_info = skill_descriptions.get(
                        skill["name"],
                        {"desc": "Skill", "used_by": "As needed"},
                    )
                    help_message += f"""
<div class="skill-box">
<h4 class="skill-name">{skill['name']}</h4>
<p class="skill-desc">{skill_info['desc']}</p>
<div class="skill-usage">
<strong>Automatically used:</strong> {skill_info['used_by']}
</div>
</div>
"""

                help_message += """
</div>

<div class="help-section">
<h2>💡 Quick Start Examples</h2>

<div class="example-box">
<h3>Database Operations (MCP + Skill + Command)</h3>
<p><strong>You type:</strong> <code>/crm New contact: Maria Schmidt, maria@tech.de, CTO at TechStart GmbH</code></p>
<p><strong>What happens:</strong></p>
<ol>
<li>The <code>/crm</code> slash command activates</li>
<li>It loads the <code>crm-db</code> skill for database schema</li>
<li>It uses the <code>postgresql</code> MCP server to insert data</li>
<li>You get confirmation with the new record ID</li>
</ol>
</div>

<div class="example-box">
<h3>Email Check (Pure MCP)</h3>
<p><strong>You type:</strong> <em>"Check my emails from today"</em></p>
<p><strong>What happens:</strong></p>
<ol>
<li>I use the <code>ms365</code> MCP server directly</li>
<li>Fetch today's emails from your account</li>
<li>Show you a summary</li>
</ol>
</div>

<div class="example-box">
<h3>Document Creation (Skill)</h3>
<p><strong>You type:</strong> <em>"Create a PDF report with Q4 sales data"</em></p>
<p><strong>What happens:</strong></p>
<ol>
<li>I automatically load the <code>pdf</code> skill</li>
<li>Generate the document structure</li>
<li>Save it to a file</li>
</ol>
</div>
</div>

<div class="help-footer">
<h3>🚀 Pro Tips</h3>
<ul>
<li>I have full access to all capabilities - no permission prompts needed</li>
<li>Mix and match: Commands can use MCPs, MCPs can work with Skills</li>
<li>Just ask naturally - I'll figure out which tools to use</li>
<li>Type <code>/help</code> anytime to see this again</li>
</ul>
</div>

</div>"""

                await websocket.send_json(
                    {
                        "type": "assistant_message",
                        "content": help_message,
                    }
                )

                # Don't process further - help is handled
                return  # Exit this message processing

            # Track message ID counter for web UI
            message_counter = 0
            text_block_counter = 0
            tool_counter = 0
            current_text_block_id = None
            tool_id_map = {}  # tool_use_id -> display_id

            # Track content for auto-naming (after first exchange)
            user_message_text = echo_content  # Captured from line 663
            assistant_response_text = (
                ""  # Will accumulate from text_delta events
            )

            # 💾 PHASE 1.1: Save user message to workspace
            workspace = session.workspace
            workspace.save_message("user", user_message_text)
            logger.info(
                f"💾 Saved user message (count: {workspace.metadata['message_count']})"
            )

            # Update session index with new message count
            self.session_index.update_session(workspace)

            print("🔄 Starting query...", flush=True)

            try:
                # Stream response from agent session
                # Pass content_blocks (supports both string and array)
                async for message in session.query(
                    content_blocks, session_id=connection_id
                ):
                    msg_type_name = type(message).__name__
                    print(f"📦 Got message: {msg_type_name}", flush=True)

                    # Debug content blocks
                    if hasattr(message, "content"):
                        if isinstance(message.content, list):
                            blocks = [
                                type(b).__name__ for b in message.content
                            ]
                            print(f"   Content blocks: {blocks}", flush=True)
                        else:
                            print(
                                f"   Content: {type(message.content).__name__}",
                                flush=True,
                            )

                    if isinstance(message, UserMessage):
                        # Check if this UserMessage contains ToolResultBlock
                        has_tool_result = False
                        if hasattr(message, "content") and isinstance(
                            message.content, list
                        ):
                            has_tool_result = any(
                                isinstance(block, ToolResultBlock)
                                for block in message.content
                            )

                        if not has_tool_result:
                            # Plain user message - skip it (we already showed it in UI)
                            print(
                                "   ⏩ Skipping plain UserMessage", flush=True
                            )
                            continue
                        else:
                            # UserMessage with tool results - keep it!
                            print(
                                "   ✅ UserMessage contains ToolResultBlock - processing",
                                flush=True,
                            )

                    # Convert Agent SDK message to web UI events
                    events = convert_message_to_websocket(message)
                    logger.info(
                        f"   📤 Generated {len(events)} events: {[e.get('type') for e in events]}"
                    )

                    # Enhance events with IDs for web UI
                    for event in events:
                        event_type = event.get("type")

                        if event_type == "text_delta":
                            # Create or reuse text block ID
                            if current_text_block_id is None:
                                current_text_block_id = f"msg-{message_counter}-text-{text_block_counter}"
                                text_block_counter += 1
                            event["id"] = current_text_block_id

                            # Accumulate assistant response for auto-naming
                            delta_text = event.get("text", "")
                            assistant_response_text += delta_text

                        elif event_type == "tool_start":
                            # Create tool block ID
                            tool_use_id = event.get(
                                "id"
                            )  # Agent SDK's tool_use_id
                            display_id = (
                                f"msg-{message_counter}-tool-{tool_counter}"
                            )
                            tool_counter += 1
                            tool_id_map[tool_use_id] = display_id
                            event["id"] = display_id
                            logger.info(
                                f"🛠️ tool_start - tool_use_id: {tool_use_id} → display_id: {display_id}"
                            )
                            # Reset text block so next text starts new block
                            current_text_block_id = None

                            # Track tool for error recovery context
                            error_recovery_service = get_error_recovery_service()
                            error_recovery_service.set_last_tool_info(
                                event.get("tool_name"), event.get("input")
                            )

                        elif event_type == "tool_end":
                            # Map Agent SDK tool_use_id to our display ID
                            tool_use_id = event.get("id")
                            logger.info(
                                f"🔧 tool_end - tool_use_id: {tool_use_id}, tool_id_map: {tool_id_map}"
                            )
                            display_id = tool_id_map.get(tool_use_id)
                            if display_id:
                                event["id"] = display_id
                                logger.info(
                                    f"✅ Mapped to display_id: {display_id}"
                                )
                            else:
                                logger.warning(
                                    f"❌ No display ID for tool_use_id: {tool_use_id}"
                                )

                            # Auto-escalation: Track tool success/failure
                            is_error = event.get("is_error", False)
                            browser_session = self.browser_session_manager.get_session_by_chat_id(
                                connection_id
                            )
                            if (
                                browser_session
                                and browser_session.model_tracker
                            ):
                                if is_error:
                                    logger.warning(
                                        "⚠️ Tool error detected - tracking for auto-escalation"
                                    )
                                    new_level = (
                                        browser_session.model_tracker.on_failure()
                                    )
                                    if new_level:
                                        # Escalation triggered!
                                        await self._handle_model_escalation(
                                            websocket,
                                            session,
                                            browser_session,
                                            new_level,
                                        )
                                else:
                                    # Success - reset failure counter
                                    browser_session.model_tracker.on_success()

                        elif event_type == "thinking":
                            # Create thinking block ID
                            thinking_id = f"msg-{message_counter}-thinking-0"
                            event["id"] = thinking_id

                        elif event_type == "system":
                            # Handle system messages based on subtype
                            subtype = event.get("subtype", "")

                            # 'init' subtype = metadata (tools, MCP servers, etc.) - SKIP
                            if subtype == "init":
                                logger.debug(
                                    "⏩ Skipping 'init' system message (metadata only)"
                                )
                                continue  # Skip metadata messages

                            # 'compaction_start' = important status - SHOW
                            # Add user-friendly message for compaction
                            if "compact" in subtype.lower():
                                event["content"] = (
                                    "⚡ **Auto-Compaction Started**\n\n"
                                    "The Claude Agent SDK is automatically summarizing older parts of the conversation "
                                    "to make room for new interactions. This preserves recent code modifications, "
                                    "current objectives, and project structure.\n\n"
                                    "_Compaction happens automatically when context approaches ~95% capacity._"
                                )
                                logger.info(f"📦 Compaction event: {subtype}")

                            # Other subtypes: Check if they have displayable content
                            else:
                                has_content = any(
                                    key in event and event[key]
                                    for key in ["content", "message", "text"]
                                )
                                if not has_content:
                                    # No standard content fields - try to format the data
                                    # This handles system commands like /cost, /todos, /context, etc.
                                    logger.info(
                                        f"📋 System message without standard content field: subtype={subtype}, event keys={list(event.keys())}"
                                    )

                                    # Extract all data except type/subtype
                                    data_fields = {
                                        k: v
                                        for k, v in event.items()
                                        if k not in ["type", "subtype"]
                                    }

                                    if data_fields:
                                        # Format the data as a readable message
                                        import json

                                        formatted_content = f"**{subtype.replace('_', ' ').title()}**\n\n"
                                        formatted_content += "```json\n"
                                        formatted_content += json.dumps(
                                            data_fields, indent=2
                                        )
                                        formatted_content += "\n```"
                                        event["content"] = formatted_content
                                        logger.info(
                                            f"✅ Formatted system message with data: {list(data_fields.keys())}"
                                        )
                                    else:
                                        # No data at all - skip this message
                                        logger.debug(
                                            f"⏩ Skipping system message with no displayable data: subtype={subtype}"
                                        )
                                        continue

                        # Send event to client
                        await websocket.send_json(event)

                # ✅ Send completion signal when query loop finishes
                await websocket.send_json({"type": "message_complete"})
                logger.info("✅ Query completed, sent message_complete")

                # 💾 PHASE 1.2: Save assistant response to workspace
                workspace = session.workspace
                if assistant_response_text.strip():
                    workspace.save_message(
                        "assistant", assistant_response_text
                    )
                    logger.info(
                        f"💾 Saved assistant response (count: {workspace.metadata['message_count']})"
                    )

                    # Update session index with new message count
                    self.session_index.update_session(workspace)
                else:
                    logger.warning("⚠️  No assistant response text to save")

                # 🏷️  Auto-naming: Generate session name after first exchange
                message_count = workspace.metadata.get("message_count", 0)
                current_state = workspace.state
                logger.info(
                    f"🏷️  Auto-naming check: state={current_state}, count={message_count}"
                )

                # Check if we should auto-name (first exchange completed)
                if self.naming_service.should_auto_name(
                    current_state, message_count
                ):
                    logger.info(
                        f"🏷️  Auto-naming triggered (state={current_state}, messages={message_count})"
                    )

                    try:
                        # Generate session name using LLM
                        generated_name = (
                            await self.naming_service.generate_session_name(
                                user_message_text, assistant_response_text
                            )
                        )

                        # Update workspace with new name
                        workspace.update_display_name(generated_name)
                        workspace.update_state("AUTO_NAMED")

                        # Update session index
                        self.session_index.update_session(workspace)

                        logger.info(
                            f"✅ Session auto-named: {generated_name}"
                        )

                        # Notify frontend to refresh session list
                        await websocket.send_json(
                            {
                                "type": "session_renamed",
                                "session_id": workspace.session_id,
                                "new_name": generated_name,
                            }
                        )

                    except Exception as e:
                        logger.error(
                            f"❌ Auto-naming failed: {e}", exc_info=True
                        )
                        # Continue gracefully - naming is not critical

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error processing message: {e}", exc_info=True)
                print(f"❌ ERROR: {error_msg}", flush=True)

                await websocket.send_json(
                    {
                        "type": "error",
                        "message": error_msg,
                    }
                )

                # Use ErrorRecoveryService for intelligent error handling
                try:
                    print("🔍 Analyzing error for recovery...", flush=True)
                    error_recovery_service = get_error_recovery_service()
                    # Pass the original task so recovery can reference it
                    error_context = error_recovery_service.analyze_error(
                        e, original_task=user_message_text
                    )

                    print(
                        f"🔍 Error analyzed: category={error_context.category.value}, "
                        f"tool={error_context.tool_name}",
                        flush=True,
                    )

                    # Check if automatic recovery should be attempted
                    if error_recovery_service.should_attempt_recovery(error_context):
                        print(
                            f"🔄 Attempting INVISIBLE recovery for {error_context.category.value} error",
                            flush=True,
                        )

                        # Generate rich recovery prompt with full context
                        recovery_prompt = (
                            error_recovery_service.generate_recovery_prompt(
                                error_context
                            )
                        )
                        print(
                            f"📝 Recovery prompt generated ({len(recovery_prompt)} chars)",
                            flush=True,
                        )

                        # NOTE: Recovery is INVISIBLE - we do NOT send the prompt to frontend
                        # The agent receives it but the user only sees the agent's actions

                        try:
                            # Reset message tracking for recovery response
                            message_counter = 0
                            text_block_counter = 0
                            tool_counter = 0
                            current_text_block_id = None
                            tool_id_map = {}

                            # Clear tool tracking after recovery prompt is generated
                            error_recovery_service.clear_last_tool_info()

                            print("🔄 Querying agent with recovery prompt...", flush=True)
                            async for message in session.query(
                                recovery_prompt, session_id=connection_id
                            ):
                                # Same message processing logic as main query
                                events = convert_message_to_websocket(message)
                                for event in events:
                                    event_type = event.get("type")
                                    if event_type == "text_delta":
                                        if current_text_block_id is None:
                                            current_text_block_id = f"recovery-{message_counter}-text-{text_block_counter}"
                                            text_block_counter += 1
                                        event["id"] = current_text_block_id
                                    elif event_type == "tool_start":
                                        tool_use_id = event.get("id")
                                        display_id = f"recovery-{message_counter}-tool-{tool_counter}"
                                        tool_counter += 1
                                        tool_id_map[tool_use_id] = display_id
                                        event["id"] = display_id
                                        current_text_block_id = None
                                    elif event_type == "tool_end":
                                        tool_use_id = event.get("id")
                                        display_id = tool_id_map.get(tool_use_id)
                                        if display_id:
                                            event["id"] = display_id
                                    await websocket.send_json(event)

                            await websocket.send_json({"type": "message_complete"})
                            print(
                                f"✅ Recovery message processed for "
                                f"{error_context.category.value} error",
                                flush=True,
                            )

                        except Exception as recovery_error:
                            print(
                                f"❌ Recovery query failed: {recovery_error}",
                                flush=True,
                            )
                            logger.error(
                                f"❌ Recovery also failed: {recovery_error}",
                                exc_info=True,
                            )
                            await websocket.send_json(
                                {
                                    "type": "error",
                                    "message": f"Recovery failed: {recovery_error}",
                                }
                            )
                    else:
                        print(
                            f"⚠️ Non-recoverable error: {error_context.category.value} - "
                            f"user intervention may be required",
                            flush=True,
                        )

                except Exception as analysis_error:
                    print(
                        f"❌ Error analysis failed: {analysis_error}",
                        flush=True,
                    )
                    logger.error(
                        f"Error analysis failed: {analysis_error}",
                        exc_info=True,
                    )

        elif msg_type == "interrupt":
            # User requested to interrupt agent execution
            logger.info("Interrupt request received")
            try:
                await session.interrupt()
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

        elif msg_type == "hint":
            # User sent a hint while agent is working
            hint_content = data.get("content", "")
            logger.info(f"💡 Hint received: {hint_content}")

            try:
                # Format the hint with special context for Claude
                formatted_hint = f"""Task was interrupted. Received this hint:

{hint_content}

Now continue with the interrupted task/plan/intention. Go on..."""

                logger.debug(f"Formatted hint: {formatted_hint[:100]}...")

                # Track message ID counter for web UI (same as user_message)
                message_counter = 0
                text_block_counter = 0
                tool_counter = 0
                current_text_block_id = None
                tool_id_map = {}  # tool_use_id -> display_id

                # Stream response from agent (same pattern as user_message)
                async for message in session.query(
                    prompt=formatted_hint,
                    session_id=connection_id,
                ):
                    # Convert SDK message to WebSocket events (returns list)
                    events = convert_message_to_websocket(message)
                    logger.info(
                        f"   💡 Generated {len(events)} hint events: {[e.get('type') for e in events]}"
                    )

                    # Enhance events with IDs for web UI (same as user_message)
                    for event in events:
                        event_type = event.get("type")

                        if event_type == "text_delta":
                            # Create or reuse text block ID
                            if current_text_block_id is None:
                                current_text_block_id = f"msg-{message_counter}-text-{text_block_counter}"
                                text_block_counter += 1
                            event["id"] = current_text_block_id

                        elif event_type == "tool_start":
                            # Create tool block ID
                            tool_use_id = event.get(
                                "id"
                            )  # Agent SDK's tool_use_id
                            display_id = (
                                f"msg-{message_counter}-tool-{tool_counter}"
                            )
                            tool_counter += 1
                            tool_id_map[tool_use_id] = display_id
                            event["id"] = display_id
                            logger.info(
                                f"🛠️ tool_start - tool_use_id: {tool_use_id} → display_id: {display_id}"
                            )
                            # Reset text block so next text starts new block
                            current_text_block_id = None

                        elif event_type == "tool_end":
                            # Map Agent SDK tool_use_id to our display ID
                            tool_use_id = event.get("id")
                            logger.info(
                                f"🔧 tool_end - tool_use_id: {tool_use_id}, tool_id_map: {tool_id_map}"
                            )
                            display_id = tool_id_map.get(tool_use_id)
                            if display_id:
                                event["id"] = display_id
                                logger.info(
                                    f"✅ Mapped to display_id: {display_id}"
                                )
                            else:
                                logger.warning(
                                    f"❌ No display ID for tool_use_id: {tool_use_id}"
                                )

                            # Auto-escalation: Track tool success/failure
                            is_error = event.get("is_error", False)
                            browser_session = self.browser_session_manager.get_session_by_chat_id(
                                connection_id
                            )
                            if (
                                browser_session
                                and browser_session.model_tracker
                            ):
                                if is_error:
                                    logger.warning(
                                        "⚠️ Tool error detected - tracking for auto-escalation"
                                    )
                                    new_level = (
                                        browser_session.model_tracker.on_failure()
                                    )
                                    if new_level:
                                        # Escalation triggered!
                                        await self._handle_model_escalation(
                                            websocket,
                                            session,
                                            browser_session,
                                            new_level,
                                        )
                                else:
                                    # Success - reset failure counter
                                    browser_session.model_tracker.on_success()

                        elif event_type == "thinking":
                            # Create thinking block ID
                            thinking_id = f"msg-{message_counter}-thinking-0"
                            event["id"] = thinking_id

                        elif event_type == "system":
                            # Handle system message filtering
                            subtype = event.get("subtype", "")

                            # Skip 'init' system messages
                            if subtype == "init":
                                logger.debug(
                                    "⏩ Skipping 'init' system message (metadata only)"
                                )
                                continue

                            # Add user-friendly message for compaction
                            if "compact" in subtype.lower():
                                event["content"] = (
                                    "⚡ **Auto-Compaction Started**\n\n"
                                    "The Claude Agent SDK is automatically summarizing older parts of the conversation "
                                    "to make room for new interactions. This preserves recent code modifications, "
                                    "current objectives, and project structure.\n\n"
                                    "_Compaction happens automatically when context approaches ~95% capacity._"
                                )
                                logger.info(f"📦 Compaction event: {subtype}")

                            # Other subtypes: Check if they have displayable content
                            else:
                                has_content = any(
                                    key in event and event[key]
                                    for key in ["content", "message", "text"]
                                )
                                if not has_content:
                                    # No standard content fields - try to format the data
                                    # This handles system commands like /cost, /todos, /context, etc.
                                    logger.info(
                                        f"📋 System message without standard content field: subtype={subtype}, event keys={list(event.keys())}"
                                    )

                                    # Extract all data except type/subtype
                                    data_fields = {
                                        k: v
                                        for k, v in event.items()
                                        if k not in ["type", "subtype"]
                                    }

                                    if data_fields:
                                        # Format the data as a readable message
                                        import json

                                        formatted_content = f"**{subtype.replace('_', ' ').title()}**\n\n"
                                        formatted_content += "```json\n"
                                        formatted_content += json.dumps(
                                            data_fields, indent=2
                                        )
                                        formatted_content += "\n```"
                                        event["content"] = formatted_content
                                        logger.info(
                                            f"✅ Formatted system message with data: {list(data_fields.keys())}"
                                        )
                                    else:
                                        # No data at all - skip this message
                                        logger.debug(
                                            f"⏩ Skipping system message with no displayable data: subtype={subtype}"
                                        )
                                        continue

                        # Send event to client
                        await websocket.send_json(event)

                # ✅ Send completion signal when hint processing finishes
                await websocket.send_json({"type": "message_complete"})
                logger.info("✅ Hint processed successfully")

            except Exception as e:
                logger.error(f"❌ Error processing hint: {e}", exc_info=True)
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Failed to process hint: {str(e)}",
                    }
                )

        elif msg_type == "config_change":
            # User changed configuration (e.g., thinking mode toggle)
            thinking_mode = data.get("thinking_mode")
            logger.info(
                f"⚙️ Config change received: thinking_mode={thinking_mode}"
            )

            if thinking_mode is not None:
                try:
                    # Thinking mode requires agent swap (SDK limitation:
                    # max_thinking_tokens cannot be changed at runtime)
                    # Use browser_session_manager to swap agents while
                    # preserving chat context
                    if hasattr(self, "browser_session_manager"):
                        # New architecture: use agent swap
                        browser_session = self.browser_session_manager.get_session_by_chat_id(
                            connection_id
                        )
                        if browser_session:
                            success = await self.browser_session_manager.swap_agent_for_thinking_mode(
                                browser_session.browser_id,
                                thinking_mode,
                            )
                            if success:
                                # Update session reference to new agent
                                session = browser_session.agent
                                await websocket.send_json(
                                    {
                                        "type": "config_updated",
                                        "thinking_mode": thinking_mode,
                                    }
                                )
                                logger.info(
                                    f"✅ Thinking mode updated to: {thinking_mode}"
                                )
                            else:
                                raise RuntimeError("Agent swap failed")
                        else:
                            # Fallback: old method (may fail with task error)
                            logger.warning(
                                "⚠️ Browser session not found, "
                                "using legacy update method"
                            )
                            await session.update_thinking_mode(thinking_mode)
                            await websocket.send_json(
                                {
                                    "type": "config_updated",
                                    "thinking_mode": thinking_mode,
                                }
                            )
                    else:
                        # Legacy path (old architecture without pool)
                        await session.update_thinking_mode(thinking_mode)
                        await websocket.send_json(
                            {
                                "type": "config_updated",
                                "thinking_mode": thinking_mode,
                            }
                        )
                        logger.info(
                            f"✅ Thinking mode updated to: {thinking_mode}"
                        )
                except Exception as e:
                    logger.error(
                        f"❌ Error updating thinking mode: {e}", exc_info=True
                    )
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"Failed to update thinking mode: {str(e)}",
                        }
                    )

        elif msg_type == "get_server_info":
            # User requested server info (commands, MCP tools, agents, etc.)
            logger.info("Server info request received")
            try:
                info = await session.get_server_info()
                await websocket.send_json(
                    {
                        "type": "server_info",
                        "data": info,
                    }
                )
                logger.info("Server info sent successfully")
            except Exception as e:
                logger.error(f"Failed to get server info: {e}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Failed to get server info: {str(e)}",
                    }
                )

        elif msg_type == "answer":
            # User answered an interactive question
            question_id = data.get("question_id")
            answers = data.get("answers", {})
            logger.info(f"Question answer received: {question_id}")
            logger.info(f"Answers: {answers}")

            # Get the question service for this connection
            question_service = self.question_services.get(connection_id)
            if question_service:
                question_service.submit_answer(question_id, answers)
                logger.info("Answer submitted to question service")
            else:
                logger.error(
                    f"No question service found for connection {connection_id}"
                )

        elif msg_type == "permission_response":
            # User responded to permission request
            tool_name = data.get("tool_name")
            scope = data.get("scope")
            logger.info(
                f"Permission response received: {tool_name} → {scope}"
            )

            # Handle the permission response
            self.permission_manager.handle_permission_response(
                tool_name, scope
            )

        elif msg_type == "permission_change":
            # User changed global permission setting
            bypass_enabled = data.get("bypass_permissions", False)
            new_mode = "bypassPermissions" if bypass_enabled else "default"
            logger.info(
                f"🔐 Permission change received: bypass={bypass_enabled}, mode={new_mode}"
            )

            try:
                await session.set_permission_mode(new_mode)
                await websocket.send_json(
                    {
                        "type": "permission_updated",
                        "mode": new_mode,
                        "bypass_enabled": bypass_enabled,
                    }
                )
                logger.info(f"✅ Permission mode updated to: {new_mode}")
            except Exception as e:
                logger.error(
                    f"❌ Failed to update permission mode: {e}", exc_info=True
                )
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Failed to update permission mode: {str(e)}",
                    }
                )

        elif msg_type == "model_change":
            # User changed model level
            from bassi.core_v3.services.model_service import get_model_info

            model_level = data.get("model_level", 1)
            logger.info(f"🤖 Model change received: level={model_level}")

            try:
                # Get browser session from manager
                browser_session = (
                    self.browser_session_manager.get_session_by_chat_id(
                        connection_id
                    )
                )
                if browser_session and browser_session.model_tracker:
                    browser_session.model_tracker.set_level(model_level)
                    model_info = get_model_info(model_level)

                    await websocket.send_json(
                        {
                            "type": "model_changed",
                            "model_level": model_level,
                            "model_name": model_info.name,
                            "reason": "user_selection",
                        }
                    )
                    logger.info(
                        f"✅ Model level updated to: {model_level} ({model_info.name})"
                    )
                else:
                    logger.warning(
                        "⚠️ No browser session found for model change"
                    )
            except Exception as e:
                logger.error(
                    f"❌ Failed to update model level: {e}", exc_info=True
                )
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Failed to update model: {str(e)}",
                    }
                )

        else:
            logger.warning(f"Unknown message type: {msg_type}")

    async def _process_images(self, content_blocks: list[dict[str, Any]]):
        """
        Process and save images from content blocks to _DATA_FROM_USER/ folder.

        Args:
            content_blocks: List of content blocks (may contain image blocks)
        """
        import base64
        import time

        for block in content_blocks:
            if block.get("type") != "image":
                continue

            source = block.get("source", {})
            if source.get("type") != "base64":
                logger.warning(
                    f"Unsupported image source type: {source.get('type')}"
                )
                continue

            base64_data = source.get("data", "")
            media_type = source.get("media_type", "image/png")
            filename = block.get("filename", f"image_{int(time.time())}.png")

            if not base64_data:
                logger.warning("Empty image data, skipping")
                continue

            try:
                # Decode base64
                image_bytes = base64.b64decode(base64_data)

                # Save to _DATA_FROM_USER/
                data_dir = Path.cwd() / "_DATA_FROM_USER"
                data_dir.mkdir(exist_ok=True)

                save_path = data_dir / filename
                save_path.write_bytes(image_bytes)

                logger.info(
                    f"📷 Saved image: {save_path} ({len(image_bytes)} bytes, {media_type})"
                )

                # Update block with saved path (for reference)
                block["saved_path"] = str(save_path)

            except Exception as e:
                logger.error(f"Failed to save image {filename}: {e}")

    async def _handle_model_escalation(
        self,
        websocket: WebSocket,
        session: "BassiAgentSession",
        browser_session: "BrowserSession",
        new_level: int,
    ) -> None:
        """
        Handle model escalation triggered by consecutive tool failures.

        This method:
        1. Changes the model via SDK (no reconnection needed)
        2. Sends notification to user about the escalation

        Args:
            websocket: WebSocket connection to send notifications
            session: Agent session for model switching
            browser_session: Browser session with model tracker state
            new_level: The new model level (2=Sonnet, 3=Opus)
        """
        from bassi.core_v3.services.model_service import (
            get_model_id,
            get_model_info,
        )

        try:
            # Get model info for display
            model_info = get_model_info(new_level)
            model_id = get_model_id(new_level)
            old_level = new_level - 1
            old_model_info = get_model_info(old_level)

            logger.warning(
                f"🚨 Auto-escalating model: {old_model_info.name} → {model_info.name} "
                f"(after 3 consecutive tool failures)"
            )

            # Change model via SDK (no reconnection needed!)
            await session.set_model(model_id)

            # Notify user about escalation
            await websocket.send_json(
                {
                    "type": "model_escalated",
                    "old_level": old_level,
                    "new_level": new_level,
                    "old_model_name": old_model_info.name,
                    "new_model_name": model_info.name,
                    "reason": "auto_escalation",
                    "message": (
                        f"⚠️ Auto-escalated to {model_info.name} after 3 "
                        f"consecutive tool failures"
                    ),
                }
            )

            # Also send as status update for visibility in chat
            await websocket.send_json(
                {
                    "type": "status",
                    "message": (
                        f"🔄 Model upgraded: {old_model_info.name} → {model_info.name} "
                        f"(auto-escalation after tool failures)"
                    ),
                }
            )

            logger.info(
                f"✅ Model escalation complete: now using {model_info.name}"
            )

        except Exception as e:
            logger.error(
                f"❌ Failed to escalate model to level {new_level}: {e}",
                exc_info=True,
            )
            # Don't fail silently - notify user of the issue
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Failed to auto-escalate model: {str(e)}",
                }
            )

    async def run(self, reload: bool = False):
        """
        Run the web server.

        Args:
            reload: Enable hot reload for development
        """

        import uvicorn

        logger.info(
            f"Starting Bassi Web UI V3 on http://{self.host}:{self.port}"
        )

        if reload:
            logger.info(
                "🔥 Hot reload enabled - server will restart on file changes"
            )
            logger.info("   Watching: bassi/core_v3/**/*.py")
            logger.info("   Watching: bassi/static/*.{html,css,js}")
            logger.info("")
            logger.info(
                "💡 Tip: Edit files and they'll auto-reload in ~2-3 seconds"
            )
            logger.info("")

            # Use uvicorn CLI for proper reload support with watchfiles
            # Can't use uvicorn.Config programmatically because it requires
            # module path string for reload to work properly
            reload_dir = str(Path(__file__).parent.parent)
            try:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "bassi.core_v3.web_server_v3:get_app",
                        "--factory",
                        "--host",
                        self.host,
                        "--port",
                        str(self.port),
                        "--reload",
                        "--reload-dir",
                        reload_dir,
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Failed to start web server: {e}")
                logger.error("")
                logger.error(
                    f"💡 Port {self.port} may already be in use. Try:"
                )
                logger.error("   • pkill -9 -f bassi-web")
                logger.error(
                    f"   • lsof -i :{self.port}  (to see what's using the port)"
                )
                logger.error("")
                raise
        else:
            config = uvicorn.Config(
                app=self.app,
                host=self.host,
                port=self.port,
                log_level="info",
            )
            server = uvicorn.Server(config)
            await server.serve()


def create_default_session_factory() -> (
    Callable[
        [InteractiveQuestionService, SessionWorkspace], BassiAgentSession
    ]
):
    """
    Create default session factory for web UI.

    Returns:
        Factory function that creates BassiAgentSession instances
        with interactive question support and workspace awareness
    """

    def factory(
        question_service: InteractiveQuestionService,
        workspace: SessionWorkspace,
    ):
        # Create Bassi interactive tools (including AskUserQuestion)
        bassi_tools = create_bassi_tools(question_service)
        bassi_mcp_server = create_sdk_mcp_server(
            name="bassi-interactive", version="1.0.0", tools=bassi_tools
        )

        # Create complete MCP registry:
        # - SDK servers (bash, web, task_automation) from shared module
        # - External servers from .mcp.json with env var substitution
        # - Custom bassi-interactive server for questions
        mcp_config_path = Path(__file__).parent.parent.parent / ".mcp.json"
        mcp_servers = create_mcp_registry(
            include_sdk=True,  # Include bash, web, task_automation
            config_path=mcp_config_path,
            custom_servers={"bassi-interactive": bassi_mcp_server},
        )

        # Generate workspace context for agent awareness
        workspace_context = workspace.get_workspace_context()

        permission_mode = get_permission_mode()
        logger.info(f"🔐 Web session permission mode: {permission_mode}")

        config = SessionConfig(
            allowed_tools=[
                "*"
            ],  # Allow ALL tools including MCP, Skills, SlashCommands
            system_prompt=workspace_context,  # Inject workspace awareness
            permission_mode=permission_mode,
            mcp_servers=mcp_servers,
            setting_sources=[
                "project",
                "local",
            ],  # Enable skills from project and local
        )
        session = BassiAgentSession(config)
        # Attach workspace to session for later access
        session.workspace = workspace
        return session

    return factory


async def start_web_server_v3(
    session_factory: (
        Callable[[InteractiveQuestionService], BassiAgentSession] | None
    ) = None,
    host: str = "localhost",
    port: int = 8765,
    reload: bool = False,
):
    """
    Start the web UI server V3.

    Args:
        session_factory: Factory to create BassiAgentSession instances.
                        Takes InteractiveQuestionService as parameter.
                        If None, uses default factory.
        host: Server hostname
        port: Server port
        reload: Enable hot reload for development
    """
    if session_factory is None:
        session_factory = create_default_session_factory()

    server = WebUIServerV3(session_factory, host, port)
    await server.run(reload=reload)


# Global app instance for uvicorn CLI reload mode
# This is only used when --reload is enabled
_app_instance = None


def get_app():
    """Get or create the FastAPI app instance for uvicorn CLI"""
    global _app_instance
    if _app_instance is None:
        session_factory = create_default_session_factory()
        server = WebUIServerV3(session_factory, "localhost", 8765)
        _app_instance = server.app
    return _app_instance
