"""
WebSocket Connection Manager - Handles WebSocket lifecycle and connection state.

BLACK BOX INTERFACE:
- handle_connection(websocket, session_id?) -> Manages full WebSocket lifecycle
- cleanup_connection(connection_id) -> Clean up resources

DEPENDENCIES: SessionWorkspace, InteractiveQuestionService, AgentPoolService
"""

import asyncio
import logging
import uuid
from typing import Any, Callable, Optional

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from bassi.core_v3.session_workspace import SessionWorkspace
from bassi.core_v3.tools import InteractiveQuestionService

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connection lifecycle and session state."""

    def __init__(
        self,
        session_factory: Callable,
        session_index,
        workspace_base_path: str,
        agent_pool: Optional[Any] = None,
        single_agent_provider: Optional[Callable] = None,
        permission_manager: Optional[Any] = None,
    ):
        """
        Initialize connection manager.

        Args:
            session_factory: DEPRECATED - not used
            session_index: Session index for tracking sessions
            workspace_base_path: Base path for session workspaces
            agent_pool: DEPRECATED - always None
            single_agent_provider: Callable that returns the single shared agent
            permission_manager: PermissionManager for handling tool permissions
        """
        self.session_factory = session_factory
        self.session_index = session_index
        self.workspace_base_path = workspace_base_path
        self.agent_pool = None  # Always None - pooling disabled
        self.single_agent_provider = single_agent_provider
        self.permission_manager = permission_manager

        # Connection state
        self.active_connections: list[WebSocket] = []
        self.active_sessions: dict[str, Any] = (
            {}
        )  # connection_id -> AgentSession
        self.workspaces: dict[str, SessionWorkspace] = (
            {}
        )  # connection_id -> workspace
        self.question_services: dict[str, InteractiveQuestionService] = (
            {}
        )  # connection_id -> service

    async def handle_connection(
        self,
        websocket: WebSocket,
        requested_session_id: Optional[str] = None,
        message_processor: Optional[Callable] = None,
    ):
        """
        Handle complete WebSocket connection lifecycle.

        Args:
            websocket: WebSocket connection
            requested_session_id: Optional session ID to resume
            message_processor: Callable to process incoming messages
                               Should accept (websocket, data, connection_id)

        Flow:
            1. Determine session ID (resume or create new)
            2. Load or create workspace
            3. Create question service and agent session
            4. Restore conversation history if resuming
            5. Accept WebSocket connection
            6. Connect to agent SDK
            7. Listen for messages (via message_processor)
            8. Handle disconnection and cleanup
        """
        # 1. Determine session ID
        connection_id = await self._get_or_create_session_id(
            requested_session_id
        )

        # 2. Accept WebSocket IMMEDIATELY to prevent client timeout
        # NOTE: Multiple connections are now allowed to coexist
        logger.info("🔷 [WS] Accepting WebSocket connection...")
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"🔷 [WS] WebSocket accepted. Total connections: {len(self.active_connections)}")

        # Set websocket on permission_manager for sending permission requests
        if self.permission_manager:
            self.permission_manager.websocket = websocket
            logger.info("🔷 [WS] Permission manager websocket set")

        # Determine whether we're resuming an existing session
        is_resuming = bool(
            requested_session_id
            and SessionWorkspace.exists(
                requested_session_id, base_path=self.workspace_base_path
            )
        )

        # Send initial status
        await websocket.send_json(
            {
                "type": "status",
                "message": "🔌 Setting up session...",
            }
        )

        # 3. Setup workspace
        workspace = await self._setup_workspace(connection_id)
        self.workspaces[connection_id] = workspace

        # 4. Create services
        question_service = await self._create_question_service(
            websocket, connection_id
        )
        self.question_services[connection_id] = question_service

        # 5. Get the single shared agent
        logger.info("🤖 [WS] Using single shared agent...")
        session = self.single_agent_provider()

        if not session:
            raise RuntimeError("Single agent not initialized!")

        # Always reset and reconnect SDK client with the correct resume flag
        await session.prepare_for_session(
            session_id=connection_id, resume=is_resuming
        )

        # Update permission mode if changed
        from bassi.shared.permission_config import get_permission_mode
        current_permission_mode = get_permission_mode()

        if session.config.permission_mode != current_permission_mode:
            logger.info(
                f"🔐 [WS] Updating permission mode: "
                f"{session.config.permission_mode} → {current_permission_mode}"
            )
            session.config.permission_mode = current_permission_mode

            # Reconnect agent with new permission mode
            await session.disconnect()
            await session.connect()
            logger.info("✅ [WS] Agent reconnected with updated permission mode")

        # Set workspace and question_service on agent
        session.workspace = workspace
        session.question_service = question_service

        self.active_sessions[connection_id] = session
        logger.info(f"🔷 [WS] Agent session ready: {type(session)}")

        # 6. Restore conversation history if resuming
        if is_resuming:
            await self._restore_conversation(session, workspace)

        logger.info(
            f"New session: {connection_id[:8]}... | Total connections: {len(self.active_connections)}"
        )

        connection_established = False
        try:
            # 7. Connect to agent SDK
            await self._connect_agent(websocket, session)
            connection_established = True  # Connection succeeded

            # 8. Send connected event
            logger.info("🔷 [WS] Sending 'connected' event to client...")
            await websocket.send_json(
                {
                    "type": "connected",
                    "session_id": connection_id,
                }
            )
            logger.info("🔷 [WS] 'connected' event sent successfully")

            # 9. Listen for messages
            if message_processor:
                await self._message_receiver_loop(
                    websocket, connection_id, message_processor
                )

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {connection_id[:8]}...")
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
        finally:
            # 10. Cleanup (pass flag to indicate if connection was established)
            await self.cleanup_connection(
                connection_id, websocket, connection_established
            )

    async def _get_or_create_session_id(
        self, requested_session_id: Optional[str]
    ) -> str:
        """Determine session ID: resume existing or create new."""
        if requested_session_id and SessionWorkspace.exists(
            requested_session_id, base_path=self.workspace_base_path
        ):
            logger.info(
                f"🔷 [WS] Resuming session: {requested_session_id[:8]}..."
            )
            return requested_session_id
        else:
            connection_id = str(uuid.uuid4())
            logger.info(
                f"🔷 [WS] Generated new connection ID: {connection_id[:8]}..."
            )
            return connection_id

    async def _setup_workspace(self, connection_id: str) -> SessionWorkspace:
        """Load existing workspace or create new one."""
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

        return workspace

    async def _create_question_service(
        self, websocket: WebSocket, connection_id: str
    ) -> InteractiveQuestionService:
        """Create interactive question service for this connection."""
        logger.info("🔷 [WS] Creating InteractiveQuestionService...")
        question_service = InteractiveQuestionService()
        question_service.websocket = websocket
        logger.info("🔷 [WS] InteractiveQuestionService created")
        return question_service

    async def _restore_conversation(
        self, session: Any, workspace: SessionWorkspace
    ):
        """Restore conversation history from workspace."""
        logger.info("🔷 [WS] Loading conversation history from workspace...")
        history = workspace.load_conversation_history()
        if history:
            session.restore_conversation_history(history)
            logger.info(
                f"✅ [WS] Restored {len(history)} messages to SDK context"
            )
        else:
            logger.info("ℹ️ [WS] No conversation history to restore")

    async def _connect_agent(self, websocket: WebSocket, session: Any):
        """Connect agent session to SDK (single agent is already connected at startup)."""
        # Single agent is already connected at server startup
        if session._connected:
            logger.info(
                "✅ [WS] Agent already connected, skipping connect()"
            )
            await websocket.send_json(
                {
                    "type": "status",
                    "message": "✅ Agent ready",
                }
            )
            return

        # Fallback: Connect if somehow not connected (shouldn't happen)
        logger.warning("⚠️ [WS] Agent not connected, connecting now...")
        await websocket.send_json(
            {
                "type": "status",
                "message": "🔌 Connecting to Claude Agent SDK...",
            }
        )

        logger.info("🔷 [WS] Calling session.connect()...")
        await session.connect()
        logger.info("🔷 [WS] session.connect() completed")

        await websocket.send_json(
            {
                "type": "status",
                "message": "✅ Claude Agent SDK connected successfully",
            }
        )

    async def _message_receiver_loop(
        self,
        websocket: WebSocket,
        connection_id: str,
        message_processor: Callable,
    ):
        """Continuously receive and process WebSocket messages."""

        async def message_receiver():
            """Inner receiver function"""
            try:
                while True:
                    data = await websocket.receive_json()
                    # Process message without awaiting to avoid blocking
                    asyncio.create_task(
                        message_processor(websocket, data, connection_id)
                    )
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error(f"Message receiver error: {e}", exc_info=True)

        # Start receiver and wait for completion
        receiver_task = asyncio.create_task(message_receiver())
        await receiver_task

    async def cleanup_connection(
        self,
        connection_id: str,
        websocket: WebSocket,
        connection_established: bool = True,
    ):
        """
        Clean up connection resources.

        Args:
            connection_id: Session/connection ID
            websocket: WebSocket to close
            connection_established: Whether the connection was fully established
                                   (False if failed during initial connect)

        Cleanup steps:
            1. Cancel pending questions
            2. Delete empty sessions if connection failed
            3. Remove from active sessions (agent stays connected, keeps workspace/question_service)
            4. Remove from active connections
        """
        # 1. Cancel any pending questions and clear permission state
        if connection_id in self.question_services:
            question_service = self.question_services[connection_id]
            question_service.cancel_all()
            del self.question_services[connection_id]

        # Clear permission state
        if self.permission_manager:
            self.permission_manager.clear_session_permissions()
            self.permission_manager.cancel_pending_requests()
            self.permission_manager.websocket = None
            logger.info("🧹 [WS] Cleared permission state")

        # 2. Auto-cleanup empty sessions ONLY if connection failed
        # If connection never established and session is empty, clean it up
        # This handles the case where agent SDK connection fails on startup
        if not connection_established:
            workspace = self.workspaces.get(connection_id)
            if workspace and workspace.metadata.get("message_count", 0) == 0:
                logger.info(
                    f"🧹 Deleting empty session after connection failure: {connection_id[:8]}..."
                )
                try:
                    self.session_index.remove_session(connection_id)
                    workspace.delete()
                except Exception as e:
                    logger.error(f"Failed to cleanup empty session: {e}")

        # 3. Remove agent from active sessions (single agent stays connected)
        if connection_id in self.active_sessions:
            try:
                # Single agent mode: Agent stays connected with current workspace/question_service
                # These will be updated when next client connects
                # We don't clear them to avoid race conditions with in-flight messages
                logger.info("🧹 [WS] Removing connection from active sessions...")
                logger.info("✅ [WS] Agent staying connected (will be reused)")
            except Exception as e:
                logger.error(f"Error removing session: {e}")
            del self.active_sessions[connection_id]

        # 4. Remove from active connections
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        logger.info(
            f"Session ended: {connection_id[:8]}... | Remaining: {len(self.active_connections)}"
        )

    def get_session(self, connection_id: str) -> Optional[Any]:
        """Get active agent session by connection ID."""
        return self.active_sessions.get(connection_id)

    def get_workspace(self, connection_id: str) -> Optional[SessionWorkspace]:
        """Get workspace by connection ID."""
        return self.workspaces.get(connection_id)
