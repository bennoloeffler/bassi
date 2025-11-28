"""
Web Server V3 - FastAPI app with Agent Pool architecture.

Architecture:
- Agent Pool: 5 pre-connected agents (first ready immediately, rest warm async)
- Browser Sessions: WebSocket connections, each acquires an agent from pool
- Chat Contexts: Persistent conversation history + workspace

Terminology:
- browser_id: Ephemeral WebSocket connection ID
- chat_id: Persistent conversation context ID
- agent: Claude SDK client from the pool

See docs/features_concepts/chat_context_architecture.md for details.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig
from bassi.core_v3.chat_index import ChatIndex
from bassi.core_v3.chat_workspace import ChatWorkspace
from bassi.core_v3.routes import (
    capability_routes,
    create_session_router,
    file_routes,
    settings,
)
from bassi.core_v3.services.agent_pool import AgentPool, get_agent_pool
from bassi.core_v3.services.capability_service import CapabilityService
from bassi.core_v3.services.config_service import ConfigService
from bassi.core_v3.services.permission_manager import PermissionManager
from bassi.core_v3.upload_service import UploadService
from bassi.core_v3.websocket.browser_session_manager import BrowserSessionManager

# Backward compatibility imports
from bassi.core_v3.session_index import SessionIndex  # noqa: F401
from bassi.core_v3.session_workspace import SessionWorkspace  # noqa: F401

logger = logging.getLogger(__name__)

# Constants
AGENT_POOL_SIZE = 5


class WebUIServerV3:
    """
    FastAPI server for bassi web UI with Agent Pool architecture.

    Features:
    - Pool of 5 pre-connected agents
    - Fast browser connection (agent already ready)
    - Support for multiple concurrent browsers
    - Clean chat context switching
    """

    def __init__(
        self,
        workspace_base_path: str = "chats",
        session_factory: Optional[Callable] = None,
        pool_size: int = AGENT_POOL_SIZE,
    ):
        """
        Initialize web server.

        Args:
            workspace_base_path: Base directory for chat workspaces
            session_factory: Factory function to create agent sessions
                           (injected for testing)
            pool_size: Number of agents in pool (default 5)
        """
        self.workspace_base_path = Path(workspace_base_path)
        self._is_custom_session_factory = session_factory is not None
        self.pool_size = pool_size

        # Initialize services FIRST (permission_manager needed for agent factory)
        self.chat_index = ChatIndex(self.workspace_base_path)
        self.upload_service = UploadService()
        self.config_service = ConfigService()
        self.permission_manager = PermissionManager(self.config_service)

        # Use custom factory or create default pool factory
        # NOTE: permission_manager must be created BEFORE agent factory
        if session_factory:
            self.agent_factory = self._wrap_legacy_factory(session_factory)
        else:
            self.agent_factory = create_pool_agent_factory(self.permission_manager)
        self.capability_service = CapabilityService(
            self._create_capability_factory()
        )

        # Get or create agent pool singleton (survives hot reloads)
        self.agent_pool = get_agent_pool(
            size=pool_size,
            agent_factory=self.agent_factory,
            acquire_timeout=30.0,
        )

        # Create browser session manager
        self.browser_session_manager = BrowserSessionManager(
            agent_pool=self.agent_pool,
            chat_index=self.chat_index,
            workspace_base_path=str(self.workspace_base_path),
            permission_manager=self.permission_manager,
        )

        # Backward compatibility aliases
        self.session_index = self.chat_index  # Legacy name
        self.connection_manager = self.browser_session_manager  # Legacy name
        self.active_sessions = self.browser_session_manager.active_sessions
        self.question_services = self.browser_session_manager.question_services
        self.workspaces = self.browser_session_manager.workspaces

        # Naming service for auto-naming chats
        from bassi.core_v3.session_naming import SessionNamingService
        self.naming_service = SessionNamingService()

        # Create FastAPI app
        self.app = self._create_app()
        self._register_routes()

    def _wrap_legacy_factory(
        self,
        legacy_factory: Callable,
    ) -> Callable[[], BassiAgentSession]:
        """Wrap legacy factory (with workspace/question args) for pool use."""

        def pool_factory() -> BassiAgentSession:
            # Create minimal deps for legacy factory
            from bassi.core_v3.interactive_questions import InteractiveQuestionService
            import uuid

            question_service = InteractiveQuestionService()
            chat_id = str(uuid.uuid4())
            workspace = ChatWorkspace(chat_id, self.workspace_base_path)
            return legacy_factory(question_service, workspace)

        return pool_factory

    def _create_capability_factory(self) -> Callable:
        """Create factory for capability discovery."""
        from bassi.core_v3.interactive_questions import InteractiveQuestionService
        import uuid

        def factory(
            question_service: InteractiveQuestionService,
            workspace: ChatWorkspace,
        ) -> BassiAgentSession:
            # Same as pool agent but with workspace
            return self.agent_factory()

        return factory

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

        # Static files
        static_dir = Path(__file__).parent.parent / "static"
        app.mount(
            "/static",
            StaticFiles(directory=str(static_dir)),
            name="static",
        )

        # Startup: Initialize agent pool (idempotent - safe to call multiple times)
        @app.on_event("startup")
        async def startup():
            logger.info(f"🚀 [SERVER] STARTUP EVENT - pool_id={id(self.agent_pool)}, started={self.agent_pool._started}, shutdown={self.agent_pool._shutdown}")
            if self.agent_pool._started:
                logger.info("♻️ [SERVER] Agent pool already started (hot reload)")
                stats = self.agent_pool.get_stats()
                logger.info(f"♻️ [SERVER] Pool status: {stats['total_agents']} agents, {stats['available']} available")
            else:
                logger.info(f"🏊 [SERVER] Starting agent pool with {self.pool_size} agents...")
                await self.agent_pool.start()
                stats = self.agent_pool.get_stats()
                logger.info(
                    f"✅ [SERVER] Agent pool ready: {stats['total_agents']}/{self.pool_size} agents, pool_id={id(self.agent_pool)}"
                )

        # Shutdown: Only shutdown on real server stop, not hot reload
        @app.on_event("shutdown")
        async def shutdown():
            logger.info(f"🛑 [SERVER] SHUTDOWN EVENT - pool_id={id(self.agent_pool)}")
            await self.agent_pool.shutdown()
            logger.info("✅ [SERVER] Agent pool shutdown complete")

        # Health check
        @app.get("/health")
        async def health():
            pool_stats = self.agent_pool.get_stats()
            manager_stats = self.browser_session_manager.get_stats()
            return JSONResponse({
                "status": "healthy",
                # Backward compatibility: flatten key stats to root level
                "active_connections": manager_stats.get("active_connections", 0),
                "active_sessions": manager_stats.get("active_chats", 0),
                # Detailed stats under nested keys
                "pool": pool_stats,
                "sessions": manager_stats,
            })

        # Root: Serve index.html
        @app.get("/")
        async def serve_index():
            index_file = static_dir / "index.html"
            return FileResponse(index_file)

        return app

    def _register_routes(self):
        """Register all route modules."""
        # Session/Chat routes (backward compatible)
        session_router = create_session_router(
            workspace_base_path=self.workspace_base_path
        )
        self.app.include_router(session_router)

        # File routes
        file_router = file_routes.create_file_router(
            workspaces=self.workspaces,
            upload_service=self.upload_service,
        )
        self.app.include_router(file_router)

        # Capability routes
        capability_router = capability_routes.create_capability_router(
            capability_service=self.capability_service
        )
        self.app.include_router(capability_router)

        # Settings routes
        self.app.include_router(settings.router)

        # WebSocket endpoint (supports both old and new param names)
        @self.app.websocket("/ws")
        async def websocket_endpoint(
            websocket: WebSocket,
            session_id: Optional[str] = None,
            chat_id: Optional[str] = None,
        ):
            # Use chat_id if provided, fall back to session_id for compatibility
            requested_chat_id = chat_id or session_id
            await self._handle_websocket(websocket, requested_chat_id)

    async def _handle_websocket(
        self,
        websocket: WebSocket,
        requested_chat_id: Optional[str] = None,
    ):
        """Handle WebSocket connection via BrowserSessionManager."""

        async def process_message(
            websocket: WebSocket,
            data: dict,
            chat_id: str,
        ):
            """Message processor - delegates to old implementation for now."""
            from bassi.core_v3 import web_server_v3_old
            await web_server_v3_old.WebUIServerV3._process_message(
                self, websocket, data, chat_id
            )

        await self.browser_session_manager.handle_connection(
            websocket=websocket,
            requested_chat_id=requested_chat_id,
            message_processor=process_message,
        )

    async def _process_images(self, content_blocks: list[dict[str, Any]]):
        """Process and save images from content blocks."""
        import base64
        import time

        for block in content_blocks:
            if block.get("type") != "image":
                continue

            source = block.get("source", {})
            if source.get("type") != "base64":
                continue

            base64_data = source.get("data", "")
            media_type = source.get("media_type", "image/png")
            filename = block.get("filename", f"image_{int(time.time())}.png")

            if not base64_data:
                continue

            try:
                image_bytes = base64.b64decode(base64_data)
                data_dir = Path.cwd() / "_DATA_FROM_USER"
                data_dir.mkdir(exist_ok=True)
                save_path = data_dir / filename
                save_path.write_bytes(image_bytes)
                block["saved_path"] = str(save_path)
                logger.info(f"📷 Saved image: {save_path}")
            except Exception as e:
                logger.error(f"Failed to save image: {e}")

    async def run(self, reload: bool = False):
        """Run the web server."""
        import subprocess
        import sys
        import uvicorn

        logger.info("Starting Bassi Web UI V3 on http://localhost:8765")

        if reload:
            logger.info("🔥 Hot reload enabled")
            reload_dir = str(Path(__file__).parent.parent)
            try:
                subprocess.run(
                    [
                        sys.executable, "-m", "uvicorn",
                        "bassi.core_v3.web_server_v3:get_app",
                        "--factory", "--host", "localhost",
                        "--port", "8765", "--reload",
                        "--reload-dir", reload_dir,
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"❌ Failed to start: {e}")
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


def create_pool_agent_factory(
    permission_manager: Optional[PermissionManager] = None,
) -> Callable[[], BassiAgentSession]:
    """
    Create agent factory for the pool.

    Pool agents are created WITHOUT workspace/question_service.
    These are attached when the agent is acquired by a browser session.

    Args:
        permission_manager: Optional PermissionManager for can_use_tool callback.
                          If provided, enables interactive permission handling.
    """
    from bassi.shared.mcp_registry import create_mcp_registry
    from bassi.shared.permission_config import get_permission_mode

    def factory() -> BassiAgentSession:
        mcp_config_path = Path(__file__).parent.parent.parent / ".mcp.json"
        mcp_servers = create_mcp_registry(
            include_sdk=True,
            config_path=mcp_config_path,
        )

        permission_mode = get_permission_mode()
        logger.debug(f"🔐 Creating pool agent with permission_mode: {permission_mode}")

        config = SessionConfig(
            allowed_tools=["*"],
            permission_mode=permission_mode,
            mcp_servers=mcp_servers,
            setting_sources=["project", "local"],
            can_use_tool=permission_manager.can_use_tool_callback if permission_manager else None,
        )
        return BassiAgentSession(config)

    return factory


def create_default_session_factory() -> Callable:
    """
    Create default session factory (backward compatibility).

    This creates agents with workspace context, used by tests and
    legacy code paths.
    """
    from bassi.core_v3.tools import InteractiveQuestionService, create_bassi_tools
    from bassi.shared.mcp_registry import create_mcp_registry
    from bassi.shared.permission_config import get_permission_mode
    from bassi.shared.sdk_loader import create_sdk_mcp_server

    def factory(
        question_service: InteractiveQuestionService,
        workspace: ChatWorkspace,
    ) -> BassiAgentSession:
        bassi_tools = create_bassi_tools(question_service)
        bassi_mcp_server = create_sdk_mcp_server(
            name="bassi-interactive", version="1.0.0", tools=bassi_tools
        )

        mcp_config_path = Path(__file__).parent.parent.parent / ".mcp.json"
        mcp_servers = create_mcp_registry(
            include_sdk=True,
            config_path=mcp_config_path,
            custom_servers={"bassi-interactive": bassi_mcp_server},
        )

        workspace_context = workspace.get_workspace_context()
        permission_mode = get_permission_mode()

        config = SessionConfig(
            allowed_tools=["*"],
            system_prompt=workspace_context,
            permission_mode=permission_mode,
            mcp_servers=mcp_servers,
            setting_sources=["project", "local"],
        )
        session = BassiAgentSession(config)
        session.workspace = workspace
        return session

    return factory


# Backward compatibility aliases
create_default_pool_session_factory = create_pool_agent_factory


async def start_web_server_v3(
    session_factory: Optional[Callable] = None,
    host: str = "localhost",
    port: int = 8765,
    reload: bool = False,
    workspace_base_path: str = "chats",
):
    """Start the web UI server V3."""
    server = WebUIServerV3(
        workspace_base_path=workspace_base_path,
        session_factory=session_factory,
    )
    await server.run(reload=reload)


def create_server(
    workspace_base_path: str = "chats",
    session_factory: Optional[Callable] = None,
) -> WebUIServerV3:
    """Create web server instance."""
    return WebUIServerV3(
        workspace_base_path=workspace_base_path,
        session_factory=session_factory,
    )


def get_app() -> FastAPI:
    """Factory function for uvicorn CLI reload mode."""
    server = WebUIServerV3(workspace_base_path="chats")
    return server.app
