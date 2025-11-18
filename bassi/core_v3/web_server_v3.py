"""
Web Server V3 - FastAPI app wiring and coordination ONLY.

This module is responsible for:
1. FastAPI app creation and configuration
2. Route registration (delegates to route modules)
3. WebSocket endpoint (delegates to ConnectionManager)
4. Dependency injection and wiring

All business logic has been extracted to:
- routes/: HTTP endpoint handlers
- services/: Business logic (sessions, capabilities, etc.)
- websocket/: WebSocket connection and message handling

BLACK BOX PRINCIPLE:
This file should be <200 lines - just wiring and coordination.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig
from bassi.core_v3.routes import (
    capability_routes,
    create_session_router,
    file_routes,
    settings,
)
from bassi.core_v3.services.agent_pool_service import (
    AgentPoolService,
    PoolConfig,
)
from bassi.core_v3.services.capability_service import CapabilityService
from bassi.core_v3.services.config_service import ConfigService
from bassi.core_v3.services.permission_manager import PermissionManager
from bassi.core_v3.session_index import SessionIndex
from bassi.core_v3.upload_service import UploadService
from bassi.core_v3.websocket.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


class WebUIServerV3:
    """FastAPI server for bassi web UI (V3 architecture)."""

    def __init__(
        self,
        workspace_base_path: str = "_DATA_FROM_USER",
        session_factory: Optional[Callable] = None,
        enable_agent_pool: bool = False,  # DISABLED - use single agent
        pool_config: Optional[PoolConfig] = None,
    ):
        """
        Initialize web server.

        Args:
            workspace_base_path: Base directory for session workspaces
            session_factory: Factory function to create agent sessions
                           (injected for testing)
            enable_agent_pool: DEPRECATED - always False (single agent mode)
            pool_config: DEPRECATED - not used
        """
        from pathlib import Path

        # Convert to Path for internal use
        self.workspace_base_path = Path(workspace_base_path)
        self.session_factory = (
            session_factory or self._default_session_factory
        )

        # Single agent instance (replaces pool)
        self.single_agent: Optional[BassiAgentSession] = None
        self.agent_pool: Optional[AgentPoolService] = None  # Keep for compatibility, always None

        # Initialize services
        self.session_index = SessionIndex(self.workspace_base_path)
        self.upload_service = UploadService()
        self.capability_service = CapabilityService(self.session_factory)
        self.config_service = ConfigService()
        self.permission_manager = PermissionManager(self.config_service)

        # Initialize connection manager (will use single_agent)
        self.connection_manager = ConnectionManager(
            session_factory=self.session_factory,
            session_index=self.session_index,
            workspace_base_path=self.workspace_base_path,
            agent_pool=None,  # No pool, using single agent
            single_agent_provider=lambda: self.single_agent,  # Provide single agent
            permission_manager=self.permission_manager,  # Permission management
        )

        # TEMPORARY: Bridge for old _process_message compatibility
        # TODO: Remove when message processors are fully extracted
        self.active_sessions = self.connection_manager.active_sessions
        self.question_services = self.connection_manager.question_services
        self.workspaces = (
            self.connection_manager.workspaces
        )  # For auto-naming

        # Import and initialize naming service (needed by old _process_message)
        from bassi.core_v3.session_naming import SessionNamingService

        self.naming_service = SessionNamingService()

        # Create FastAPI app
        self.app = self._create_app()

        # Register routes
        self._register_routes()

    async def _process_images(self, content_blocks: list[dict[str, Any]]):
        """
        Process and save images from content blocks to _DATA_FROM_USER/ folder.

        TEMPORARY BRIDGE METHOD - copied from web_server_v3_old.py
        TODO: Extract to proper message processor when refactoring is complete

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

    async def _create_single_agent(self) -> BassiAgentSession:
        """Create the single shared agent instance."""
        from pathlib import Path

        from bassi.shared.mcp_registry import create_mcp_registry
        from bassi.shared.permission_config import get_permission_mode

        # Create complete MCP registry
        mcp_config_path = Path(__file__).parent.parent.parent / ".mcp.json"
        mcp_servers = create_mcp_registry(
            include_sdk=True,  # Include bash, web, task_automation
            config_path=mcp_config_path,
        )

        permission_mode = get_permission_mode()
        logger.info(f"🔐 Creating single agent with permission_mode: {permission_mode}")

        config = SessionConfig(
            allowed_tools=["*"],  # Allow ALL tools
            permission_mode=permission_mode,
            mcp_servers=mcp_servers,
            setting_sources=["project", "local"],
            can_use_tool=self.permission_manager.can_use_tool_callback,  # Permission callback
        )

        session = BassiAgentSession(config)
        await session.connect()
        logger.info("✅ Single agent connected to SDK")

        return session

    def _default_session_factory(self, question_service, workspace):
        """
        Default factory for creating agent sessions.
        
        This is called by capability_service to get capabilities.
        Creates a minimal session for capability detection.
        """
        from bassi.core_v3.agent_session import SessionConfig
        
        # Create minimal config for capability detection
        config = SessionConfig(
            permission_mode="bypassPermissions",
        )
        session = BassiAgentSession(config)
        session.workspace = workspace
        return session

    def _create_app(self) -> FastAPI:
        """Create and configure FastAPI application."""
        app = FastAPI(title="Bassi Web UI", version="3.0.0")

        # CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Static files (with cache busting for development)
        static_dir = Path(__file__).parent.parent / "static"
        app.mount(
            "/static",
            StaticFiles(directory=str(static_dir)),
            name="static",
        )

        # Startup event: Create single agent
        @app.on_event("startup")
        async def startup():
            logger.info("🤖 [SERVER] Creating single agent instance...")
            self.single_agent = await self._create_single_agent()
            logger.info("✅ [SERVER] Single agent ready")

        # Shutdown event: Cleanup single agent
        @app.on_event("shutdown")
        async def shutdown():
            if self.single_agent:
                logger.info("🤖 [SERVER] Disconnecting agent...")
                await self.single_agent.disconnect()
                logger.info("✅ [SERVER] Agent disconnected")

        # Health check endpoint
        @app.get("/health")
        async def health():
            health_data = {
                "status": "healthy",
                "active_connections": len(
                    self.connection_manager.active_connections
                ),
                "active_sessions": len(
                    self.connection_manager.active_sessions
                ),
                "single_agent_connected": (
                    self.single_agent._connected if self.single_agent else False
                ),
            }
            return JSONResponse(health_data)

        # Serve index.html for root
        @app.get("/")
        async def serve_index():
            index_file = static_dir / "index.html"
            return FileResponse(index_file)

        return app

    def _register_routes(self):
        """Register all route modules."""
        # Session routes (with workspace_base_path injected)
        session_router = create_session_router(
            workspace_base_path=self.workspace_base_path
        )
        self.app.include_router(session_router)

        # File routes (requires dependency injection)
        file_router = file_routes.create_file_router(
            workspaces=self.connection_manager.workspaces,
            upload_service=self.upload_service,
        )
        self.app.include_router(file_router)

        # Capability routes (requires dependency injection)
        capability_router = capability_routes.create_capability_router(
            capability_service=self.capability_service
        )
        self.app.include_router(capability_router)

        # Settings routes
        self.app.include_router(settings.router)

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
        Handle WebSocket connection.

        Delegates to ConnectionManager for lifecycle management.
        Creates a MessageHandler with a temporary processor for now
        (TODO: extract all message processors into separate files).
        """

        # For now, we keep the message processor inline
        # (TODO: Extract to websocket/message_processors/)
        async def process_message(
            websocket: WebSocket, data: dict, connection_id: str
        ):
            """
            Temporary inline message processor.

            TODO: This should be split into:
            - websocket/message_processors/user_message_processor.py
            - websocket/message_processors/hint_processor.py
            - websocket/message_processors/config_processor.py
            - websocket/message_processors/answer_processor.py
            - websocket/message_processors/interrupt_processor.py
            - websocket/message_processors/server_info_processor.py
            """
            # Import the original _process_message from OLD file temporarily
            # This allows us to keep functionality while refactoring incrementally
            from bassi.core_v3 import web_server_v3_old

            # Get original server instance method from OLD implementation
            # NOTE: This is a temporary bridge - we'll replace this with
            # proper message processors in the next refactoring phase
            await web_server_v3_old.WebUIServerV3._process_message(
                self, websocket, data, connection_id
            )

        # Delegate connection handling to ConnectionManager
        await self.connection_manager.handle_connection(
            websocket=websocket,
            requested_session_id=requested_session_id,
            message_processor=process_message,
        )

    async def run(self, reload: bool = False):
        """
        Run the web server.

        Args:
            reload: Enable hot reload for development
        """
        import subprocess
        import sys
        import uvicorn
        from pathlib import Path

        logger.info("Starting Bassi Web UI V3 on http://localhost:8765")

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
                        "localhost",
                        "--port",
                        "8765",
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
                    f"💡 Port 8765 may already be in use. Try:"
                )
                logger.error("   • pkill -9 -f bassi-web")
                logger.error(
                    f"   • lsof -i :8765  (to see what's using the port)"
                )
                logger.error("")
                raise
        else:
            config = uvicorn.Config(
                self.app,
                host="localhost",
                port=8765,
                reload=False,
                log_level="info",
            )
            server = uvicorn.Server(config)
            await server.serve()


# Entry point
def create_server(
    workspace_base_path: str = "_DATA_FROM_USER",
    session_factory: Optional[Callable] = None,
) -> WebUIServerV3:
    """
    Create web server instance.

    Args:
        workspace_base_path: Base directory for session workspaces
        session_factory: Optional custom session factory (for testing)

    Returns:
        Configured WebUIServerV3 instance
    """
    return WebUIServerV3(
        workspace_base_path=workspace_base_path,
        session_factory=session_factory,
    )


def create_default_pool_session_factory() -> Callable:
    """
    Create session factory for agent pool (NO workspace/question_service deps).

    Returns:
        Factory function that creates BassiAgentSession instances for the pool
    """
    from pathlib import Path

    from bassi.shared.mcp_registry import create_mcp_registry
    from bassi.shared.permission_config import get_permission_mode

    def factory() -> BassiAgentSession:
        """
        Factory to create BassiAgentSession for agent pool.

        Pool agents are created WITHOUT workspace or question_service.
        These will be set later when the agent is acquired from the pool.

        Returns:
            Configured agent session (no workspace/question service)
        """
        # Create complete MCP registry (without bassi-interactive)
        # bassi-interactive will be added when agent is acquired
        mcp_config_path = Path(__file__).parent.parent.parent / ".mcp.json"
        mcp_servers = create_mcp_registry(
            include_sdk=True,  # Include bash, web, task_automation
            config_path=mcp_config_path,
        )

        permission_mode = get_permission_mode()
        logger.info(f"🔐 Creating pool agent with permission_mode: {permission_mode}")

        config = SessionConfig(
            allowed_tools=["*"],  # Allow ALL tools
            system_prompt=None,  # Will be set when acquired (workspace context)
            permission_mode=permission_mode,
            mcp_servers=mcp_servers,
            setting_sources=["project", "local"],
        )
        session = BassiAgentSession(config)
        return session

    return factory


def create_default_session_factory() -> Callable:
    """
    Create default session factory with standard configuration.

    Returns:
        Factory function that creates BassiAgentSession instances
    """
    from pathlib import Path

    from bassi.core_v3.agent_session import SessionConfig
    from bassi.core_v3.session_workspace import SessionWorkspace
    from bassi.core_v3.tools import (
        InteractiveQuestionService,
        create_bassi_tools,
    )
    from bassi.shared.mcp_registry import create_mcp_registry
    from bassi.shared.permission_config import get_permission_mode
    from bassi.shared.sdk_loader import create_sdk_mcp_server

    def factory(
        question_service: InteractiveQuestionService,
        workspace: SessionWorkspace,
    ) -> BassiAgentSession:
        """
        Factory to create BassiAgentSession with interactive question handling.

        Args:
            question_service: Service for asking user questions
            workspace: Session workspace for file access

        Returns:
            Configured agent session
        """
        # Create bassi-interactive MCP server for questions
        bassi_tools = create_bassi_tools(question_service)
        bassi_mcp_server = create_sdk_mcp_server(
            name="bassi-interactive", version="1.0.0", tools=bassi_tools
        )

        # Create complete MCP registry
        mcp_config_path = Path(__file__).parent.parent.parent / ".mcp.json"
        mcp_servers = create_mcp_registry(
            include_sdk=True,  # Include bash, web, task_automation
            config_path=mcp_config_path,
            custom_servers={"bassi-interactive": bassi_mcp_server},
        )

        # Generate workspace context for agent awareness
        workspace_context = workspace.get_workspace_context()

        permission_mode = get_permission_mode()
        logger.info(f"🔐 Creating session with permission_mode: {permission_mode}")

        config = SessionConfig(
            allowed_tools=["*"],  # Allow ALL tools
            system_prompt=workspace_context,
            permission_mode=permission_mode,
            mcp_servers=mcp_servers,
            setting_sources=["project", "local"],
        )
        session = BassiAgentSession(config)
        session.workspace = workspace
        return session

    return factory


async def start_web_server_v3(
    session_factory: Optional[Callable] = None,
    host: str = "localhost",
    port: int = 8765,
    reload: bool = False,
    workspace_base_path: str = "chats",
):
    """
    Start the web UI server V3.

    Args:
        session_factory: Factory to create BassiAgentSession instances
        host: Server hostname
        port: Server port
        reload: Enable hot reload for development
        workspace_base_path: Base directory for session workspaces
    """
    if session_factory is None:
        session_factory = create_default_session_factory()

    server = WebUIServerV3(
        workspace_base_path=workspace_base_path,
        session_factory=session_factory,
    )
    await server.run(reload=reload)


def get_app() -> FastAPI:
    """
    Factory function for uvicorn CLI reload mode.
    
    This is called by uvicorn when using --factory flag.
    Creates a new server instance and returns its FastAPI app.
    """
    server = WebUIServerV3(workspace_base_path="chats")
    return server.app
