"""
Browser Session Manager - Manages WebSocket connections and agent assignments.

This replaces ConnectionManager with clearer naming:
- Browser session = WebSocket connection (ephemeral)
- Chat context = Conversation history + workspace (persistent)

Architecture:
- Browser connects → acquire agent from pool → create BrowserSession
- Browser switches chat → save current context → load new context
- Browser disconnects → release agent to pool → cleanup BrowserSession
"""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from bassi.core_v3.chat_workspace import ChatWorkspace
from bassi.core_v3.models.browser_session import BrowserSession
from bassi.core_v3.services.agent_pool import AgentPool, PoolExhaustedException
from bassi.core_v3.tools import InteractiveQuestionService

logger = logging.getLogger(__name__)


class BrowserSessionManager:
    """
    Manages browser WebSocket connections and their agent assignments.

    Responsibilities:
    - Accept WebSocket connections
    - Acquire agents from pool for each browser
    - Track browser → agent → chat mappings
    - Handle chat context switching
    - Release agents on disconnect
    """

    def __init__(
        self,
        agent_pool: AgentPool,
        chat_index: Any,  # ChatIndex
        workspace_base_path: str | Path = "chats",
        permission_manager: Optional[Any] = None,
    ):
        """
        Initialize browser session manager.

        Args:
            agent_pool: Pool of pre-connected agents
            chat_index: Index of all chat contexts
            workspace_base_path: Base path for chat workspaces
            permission_manager: Optional permission manager
        """
        self.agent_pool = agent_pool
        self.chat_index = chat_index
        # Ensure workspace_base_path is a Path object
        self.workspace_base_path = (
            Path(workspace_base_path)
            if isinstance(workspace_base_path, str)
            else workspace_base_path
        )
        self.permission_manager = permission_manager

        # Active browser sessions: browser_id -> BrowserSession
        self.browser_sessions: dict[str, BrowserSession] = {}

        # Active WebSocket connections
        self.active_connections: list[WebSocket] = []

        # Legacy compatibility aliases
        self.active_sessions = {}  # Will be populated for backward compat
        self.question_services = {}
        self.workspaces = {}

    async def handle_connection(
        self,
        websocket: WebSocket,
        requested_chat_id: Optional[str] = None,
        message_processor: Optional[Callable] = None,
    ) -> None:
        """
        Handle complete WebSocket connection lifecycle.

        Args:
            websocket: WebSocket connection
            requested_chat_id: Optional chat ID to resume
            message_processor: Callable to process incoming messages

        Flow:
        1. Generate browser_id
        2. Accept WebSocket
        3. Acquire agent from pool
        4. Load or create chat context
        5. Run message loop
        6. Release agent on disconnect
        """
        browser_id = str(uuid.uuid4())
        logger.info(f"🔷 [WS] New browser connection: {browser_id[:8]}...")

        # Accept WebSocket immediately
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"🔷 [WS] WebSocket accepted. Total connections: {len(self.active_connections)}"
        )

        # Send initial status
        await websocket.send_json(
            {
                "type": "status",
                "message": "🔌 Acquiring agent...",
            }
        )

        browser_session: Optional[BrowserSession] = None
        connection_established = False

        try:
            # Acquire agent from pool
            logger.info(
                f"🔶 [WS] Acquiring agent for browser {browser_id[:8]}..."
            )
            agent = await self.agent_pool.acquire(browser_id, timeout=30)
            logger.info(
                f"✅ [WS] Agent acquired for browser {browser_id[:8]}"
            )

            # Determine chat context
            chat_id = await self._resolve_chat_id(requested_chat_id)
            is_resuming = requested_chat_id and ChatWorkspace.exists(
                requested_chat_id, base_path=self.workspace_base_path
            )

            # Load or create chat workspace
            workspace = await self._setup_workspace(chat_id)

            # Create question service
            question_service = InteractiveQuestionService()
            question_service.websocket = websocket

            # Set permission manager websocket
            if self.permission_manager:
                self.permission_manager.websocket = websocket

            # Prepare agent for this session
            await agent.prepare_for_session(
                session_id=chat_id,
                resume=is_resuming,
            )

            # Update permission mode if user changed settings
            from bassi.shared.permission_config import get_permission_mode

            current_permission_mode = get_permission_mode()
            if agent.config.permission_mode != current_permission_mode:
                logger.info(
                    f"🔐 [WS] Updating permission mode: "
                    f"{agent.config.permission_mode} → {current_permission_mode}"
                )
                # Use SDK's set_permission_mode to change during conversation
                await agent.set_permission_mode(current_permission_mode)

            # Attach workspace and services to agent
            agent.workspace = workspace
            agent.question_service = question_service
            agent.current_workspace_id = chat_id

            # Get model settings from config service
            from bassi.core_v3.services.config_service import ConfigService
            from bassi.core_v3.services.model_service import (
                ModelEscalationTracker,
            )

            config_service = ConfigService()
            model_settings = config_service.get_model_settings()
            model_tracker = ModelEscalationTracker(
                current_level=model_settings["default_model_level"],
                auto_escalate=model_settings["auto_escalate"],
            )

            # Create browser session
            browser_session = BrowserSession(
                browser_id=browser_id,
                websocket=websocket,
                agent=agent,
                current_chat_id=chat_id,
                question_service=question_service,
                workspace=workspace,
                model_tracker=model_tracker,
            )
            self.browser_sessions[browser_id] = browser_session

            # Legacy compatibility
            self.active_sessions[chat_id] = agent
            self.question_services[chat_id] = question_service
            self.workspaces[chat_id] = workspace

            # Restore conversation if resuming
            if is_resuming:
                await self._restore_conversation(agent, workspace)

            # Connect agent (should already be connected from pool)
            await self._ensure_agent_connected(websocket, agent)
            connection_established = True

            # Send connected event
            await websocket.send_json(
                {
                    "type": "connected",
                    "chat_id": chat_id,
                    "session_id": chat_id,  # Backward compatibility
                    "browser_id": browser_id,
                }
            )
            logger.info(
                f"✅ [WS] Browser {browser_id[:8]} connected to chat {chat_id[:8]}"
            )

            # Run message loop
            if message_processor:
                await self._message_loop(
                    websocket, browser_id, chat_id, message_processor
                )

        except WebSocketDisconnect:
            logger.info(f"📴 [WS] Browser {browser_id[:8]} disconnected")
        except PoolExhaustedException as e:
            # Pool is at max capacity and all agents are busy - immediate feedback!
            logger.warning(
                f"🚫 [WS] Pool exhausted for browser {browser_id[:8]}: "
                f"{e.in_use}/{e.pool_size} agents in use"
            )
            try:
                await websocket.send_json(
                    {
                        "type": "pool_exhausted",
                        "message": "All AI assistants are busy. Please try again in a few minutes.",
                        "pool_size": e.pool_size,
                        "in_use": e.in_use,
                    }
                )
            except Exception:
                pass  # WebSocket might already be closed
        except Exception as e:
            logger.error(f"❌ [WS] Error: {e}", exc_info=True)
        finally:
            # Cleanup
            await self._cleanup_browser_session(
                browser_id, websocket, connection_established
            )

    async def _resolve_chat_id(self, requested_chat_id: Optional[str]) -> str:
        """Determine chat ID: use requested if valid, else create new."""
        if requested_chat_id and ChatWorkspace.exists(
            requested_chat_id, base_path=self.workspace_base_path
        ):
            logger.info(f"🔷 [WS] Resuming chat: {requested_chat_id[:8]}...")
            return requested_chat_id
        else:
            chat_id = str(uuid.uuid4())
            logger.info(f"🔷 [WS] New chat: {chat_id[:8]}...")
            return chat_id

    async def _setup_workspace(self, chat_id: str) -> ChatWorkspace:
        """Load existing workspace or create new one."""
        if ChatWorkspace.exists(chat_id, base_path=self.workspace_base_path):
            workspace = ChatWorkspace.load(
                chat_id, base_path=self.workspace_base_path
            )
            logger.info(
                f"✅ [WS] Loaded workspace: {chat_id[:8]} "
                f"(files: {workspace.metadata.get('file_count', 0)})"
            )
        else:
            workspace = ChatWorkspace(
                chat_id, base_path=self.workspace_base_path, create=True
            )
            workspace.update_display_name(f"Chat {chat_id[:8]}")
            self.chat_index.add_chat(workspace)
            logger.info(f"✅ [WS] Created workspace: {chat_id[:8]}")

        return workspace

    async def _restore_conversation(
        self, agent: Any, workspace: ChatWorkspace
    ) -> None:
        """Restore conversation history from workspace."""
        logger.info("🔷 [WS] Loading conversation history...")
        history = workspace.load_conversation_history()
        if history:
            agent.restore_conversation_history(history)
            logger.info(f"✅ [WS] Restored {len(history)} messages")
        else:
            logger.info("ℹ️ [WS] No history to restore")

    async def _ensure_agent_connected(
        self, websocket: WebSocket, agent: Any
    ) -> None:
        """Ensure agent is connected (pool agents should already be connected)."""
        if agent._connected:
            await websocket.send_json(
                {
                    "type": "status",
                    "message": "✅ Agent ready",
                }
            )
        else:
            logger.warning("⚠️ [WS] Agent not connected, connecting...")
            await websocket.send_json(
                {
                    "type": "status",
                    "message": "🔌 Connecting to Claude...",
                }
            )
            await agent.connect()
            await websocket.send_json(
                {
                    "type": "status",
                    "message": "✅ Connected to Claude",
                }
            )

        # Log current model on agent activation
        model_id = agent.get_model_id()
        logger.info(f"🤖 [AGENT] Session activated with model: {model_id}")

    async def _message_loop(
        self,
        websocket: WebSocket,
        browser_id: str,
        chat_id: str,
        message_processor: Callable,
    ) -> None:
        """Continuously receive and process messages."""
        try:
            while True:
                data = await websocket.receive_json()
                # Process without blocking
                asyncio.create_task(
                    message_processor(websocket, data, chat_id)
                )
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"❌ [WS] Message loop error: {e}", exc_info=True)

    async def _cleanup_browser_session(
        self,
        browser_id: str,
        websocket: WebSocket,
        connection_established: bool,
    ) -> None:
        """Clean up browser session on disconnect."""
        browser_session = self.browser_sessions.get(browser_id)

        if browser_session:
            chat_id = browser_session.current_chat_id

            # Cancel pending questions
            if browser_session.question_service:
                browser_session.question_service.cancel_all()

            # Clear permission state
            if self.permission_manager:
                self.permission_manager.clear_session_permissions()
                self.permission_manager.cancel_pending_requests()
                self.permission_manager.websocket = None

            # Clean up empty chats if connection failed
            if not connection_established and browser_session.workspace:
                if (
                    browser_session.workspace.metadata.get("message_count", 0)
                    == 0
                ):
                    logger.info(
                        f"🧹 [WS] Deleting empty chat: {chat_id[:8]}..."
                    )
                    try:
                        self.chat_index.remove_chat(chat_id)
                        browser_session.workspace.delete()
                    except Exception as e:
                        logger.error(f"Failed to cleanup empty chat: {e}")

            # Release agent back to pool
            if browser_session.agent:
                await self.agent_pool.release(browser_session.agent)

            # Remove from legacy dicts
            if chat_id in self.active_sessions:
                del self.active_sessions[chat_id]
            if chat_id in self.question_services:
                del self.question_services[chat_id]
            if chat_id in self.workspaces:
                del self.workspaces[chat_id]

            # Remove browser session
            del self.browser_sessions[browser_id]

        # Remove from active connections
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        logger.info(
            f"📴 [WS] Browser {browser_id[:8]} cleaned up. "
            f"Remaining: {len(self.active_connections)}"
        )

    async def switch_chat(
        self,
        browser_id: str,
        new_chat_id: str,
    ) -> bool:
        """
        Switch browser to a different chat context.

        Args:
            browser_id: Browser session ID
            new_chat_id: Chat ID to switch to

        Returns:
            True if switch successful, False otherwise
        """
        browser_session = self.browser_sessions.get(browser_id)
        if not browser_session:
            logger.error(f"❌ [WS] Browser {browser_id[:8]} not found")
            return False

        old_chat_id = browser_session.current_chat_id
        logger.info(
            f"🔄 [WS] Browser {browser_id[:8]} switching: "
            f"{old_chat_id[:8] if old_chat_id else 'new'} → {new_chat_id[:8]}"
        )

        # Save current conversation if exists
        if old_chat_id and browser_session.workspace:
            # Already saved incrementally, but could save final state here
            pass

        # Prepare agent for new chat
        is_resuming = ChatWorkspace.exists(
            new_chat_id, base_path=self.workspace_base_path
        )
        await browser_session.agent.prepare_for_session(
            session_id=new_chat_id,
            resume=is_resuming,
        )

        # Load new workspace
        workspace = await self._setup_workspace(new_chat_id)
        browser_session.workspace = workspace
        browser_session.agent.workspace = workspace
        browser_session.current_chat_id = new_chat_id

        # Restore conversation if resuming
        if is_resuming:
            await self._restore_conversation(browser_session.agent, workspace)

        # Update legacy dicts
        if old_chat_id in self.active_sessions:
            del self.active_sessions[old_chat_id]
        self.active_sessions[new_chat_id] = browser_session.agent
        self.workspaces[new_chat_id] = workspace
        self.question_services[new_chat_id] = browser_session.question_service

        logger.info(f"✅ [WS] Switched to chat {new_chat_id[:8]}")
        return True

    def get_browser_session(
        self, browser_id: str
    ) -> Optional[BrowserSession]:
        """Get browser session by ID."""
        return self.browser_sessions.get(browser_id)

    def get_session_by_chat(self, chat_id: str) -> Optional[Any]:
        """Get agent session for a chat (backward compatibility)."""
        return self.active_sessions.get(chat_id)

    def get_session_by_chat_id(
        self, chat_id: str
    ) -> Optional[BrowserSession]:
        """Get BrowserSession by chat ID."""
        for browser_session in self.browser_sessions.values():
            if browser_session.current_chat_id == chat_id:
                return browser_session
        return None

    def get_workspace(self, chat_id: str) -> Optional[ChatWorkspace]:
        """Get workspace for a chat (backward compatibility)."""
        return self.workspaces.get(chat_id)

    def get_stats(self) -> dict:
        """Get manager statistics."""
        return {
            "active_browsers": len(self.browser_sessions),
            "active_connections": len(self.active_connections),
            "active_chats": len(self.active_sessions),
            "pool_stats": self.agent_pool.get_stats(),
        }

    async def swap_agent_for_thinking_mode(
        self,
        browser_id: str,
        thinking_mode: bool,
    ) -> bool:
        """
        Swap current agent for one with different thinking mode config.

        Since max_thinking_tokens cannot be changed at runtime (SDK limitation),
        we need to:
        1. Save conversation history from current agent
        2. Release current agent back to pool
        3. Create new agent with thinking mode config
        4. Connect new agent
        5. Restore conversation history to new agent

        This preserves the chat context while enabling/disabling thinking mode.

        Args:
            browser_id: Browser session ID
            thinking_mode: Whether to enable extended thinking

        Returns:
            True on success, False on failure
        """
        browser_session = self.browser_sessions.get(browser_id)
        if not browser_session:
            logger.error(f"❌ [WS] Browser {browser_id[:8]} not found")
            return False

        chat_id = browser_session.current_chat_id
        old_agent = browser_session.agent
        workspace = browser_session.workspace

        logger.info(
            f"🔄 [WS] Swapping agent for browser {browser_id[:8]}, "
            f"thinking_mode={thinking_mode}"
        )

        try:
            # Step 1: Save conversation history from workspace
            history = []
            if workspace:
                history = workspace.load_conversation_history()
                logger.info(
                    f"📝 [WS] Saved {len(history)} messages from workspace"
                )

            # Step 2: Release old agent back to pool
            # This resets the agent's state but keeps it connected
            if old_agent:
                await self.agent_pool.release(old_agent)
                logger.info("🔄 [WS] Released old agent to pool")

            # Step 3: Create new agent with thinking mode config
            from bassi.core_v3.web_server_v3 import (
                create_thinking_mode_agent_factory,
            )

            factory = create_thinking_mode_agent_factory(
                permission_manager=self.permission_manager,
                thinking_mode=thinking_mode,
            )
            new_agent = factory()
            logger.info(
                f"🧠 [WS] Created new agent with thinking_mode={thinking_mode}"
            )

            # Step 4: Connect new agent
            await new_agent.connect()
            logger.info("🔌 [WS] New agent connected")

            # Step 5: Prepare agent for session
            is_resuming = ChatWorkspace.exists(
                chat_id, base_path=self.workspace_base_path
            )
            await new_agent.prepare_for_session(
                session_id=chat_id,
                resume=is_resuming,
            )

            # Step 6: Restore conversation history to new agent
            if history:
                new_agent.restore_conversation_history(history)
                logger.info(
                    f"✅ [WS] Restored {len(history)} messages to new agent"
                )

            # Step 7: Attach workspace and services to new agent
            new_agent.workspace = workspace
            new_agent.question_service = browser_session.question_service
            new_agent.current_workspace_id = chat_id

            # Step 8: Update browser session
            browser_session.agent = new_agent

            # Update legacy dicts
            self.active_sessions[chat_id] = new_agent

            logger.info(
                f"✅ [WS] Agent swap complete for browser {browser_id[:8]}, "
                f"thinking_mode={thinking_mode}"
            )
            return True

        except Exception as e:
            logger.error(f"❌ [WS] Failed to swap agent: {e}", exc_info=True)
            return False
