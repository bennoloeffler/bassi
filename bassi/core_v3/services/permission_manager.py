"""
Permission Manager Service - Handles tool permission requests and state.

Supports 4 permission scopes:
1. "one_time" - Allow just this single tool invocation
2. "session" - Allow for the current WebSocket session
3. "persistent" - Allow for all sessions (persistent across sessions)
4. "global" - Bypass all permissions forever (same as global toggle)

BLACK BOX INTERFACE:
- can_use_tool_callback(tool_name, tool_input, context) -> PermissionResult: Agent SDK callback
- request_permission(tool_name, websocket) -> str: Request permission from user
- handle_permission_response(scope, tool_name) -> None: Process user's choice

DEPENDENCIES: ConfigService (for persistent permissions)
"""

import asyncio
import logging
from typing import Any, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class PermissionManager:
    """Manages tool permissions with multiple scopes."""

    def __init__(self, config_service):
        """
        Initialize permission manager.

        Args:
            config_service: ConfigService instance for persistent storage
        """
        self.config_service = config_service

        # Session-level permissions: {tool_name: True}
        self.session_permissions: dict[str, bool] = {}

        # One-time permissions: {tool_name: count}
        # Decremented on each use, removed when 0
        self.one_time_permissions: dict[str, int] = {}

        # Pending permission requests: {tool_name: asyncio.Future}
        self.pending_requests: dict[str, asyncio.Future] = {}

        # Current WebSocket connection for sending permission requests
        self.websocket: Optional[WebSocket] = None

    async def can_use_tool_callback(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: Any,  # ToolPermissionContext from SDK
    ):
        """
        Agent SDK callback to check if tool can be used.

        This is called by the Agent SDK before using each tool.

        Args:
            tool_name: Name of the tool to check
            tool_input: The input parameters being passed to the tool
            context: ToolPermissionContext from the SDK

        Returns:
            PermissionResultAllow or PermissionResultDeny

        Permission check priority:
        1. Global bypass (ConfigService) - allows all tools
        2. One-time permission - allows once then removed
        3. Session permission - allows for current session
        4. Persistent permission (ConfigService) - allows across all sessions
        5. If none match, request permission from user
        """
        from claude_agent_sdk.types import (
            PermissionResultAllow,
            PermissionResultDeny,
        )

        # DEBUG: Log that callback is being invoked
        logger.info(
            f"🔐🔐🔐 [PERMISSION] can_use_tool_callback INVOKED for tool: {tool_name}"
        )

        # 1. Check global bypass
        global_bypass = self.config_service.get_global_bypass_permissions()
        logger.info(
            f"🔐 [PERMISSION] global_bypass_permissions = {global_bypass}"
        )
        if global_bypass:
            logger.info(f"🔓 Tool '{tool_name}' allowed (global bypass)")
            return PermissionResultAllow()

        # 2. Check one-time permission
        if tool_name in self.one_time_permissions:
            self.one_time_permissions[tool_name] -= 1
            if self.one_time_permissions[tool_name] <= 0:
                del self.one_time_permissions[tool_name]
            logger.debug(f"🔓 Tool '{tool_name}' allowed (one-time)")
            return PermissionResultAllow()

        # 3. Check session permission
        if self.session_permissions.get(tool_name):
            logger.debug(f"🔓 Tool '{tool_name}' allowed (session)")
            return PermissionResultAllow()

        # 4. Check persistent permission
        persistent_permissions = (
            self.config_service.get_persistent_permissions()
        )
        if tool_name in persistent_permissions:
            logger.debug(f"🔓 Tool '{tool_name}' allowed (persistent)")
            return PermissionResultAllow()

        # 5. Permission not found - request from user
        logger.info(
            f"🔐 Tool '{tool_name}' requires permission - requesting from user..."
        )
        try:
            scope = await self.request_permission(tool_name)
            logger.info(
                f"✅ Permission granted for '{tool_name}' with scope: {scope}"
            )
            return PermissionResultAllow()
        except Exception as e:
            logger.error(
                f"❌ Permission request failed for '{tool_name}': {e}"
            )
            return PermissionResultDeny(
                message=f"Permission denied: {str(e)}", interrupt=False
            )

    async def request_permission(self, tool_name: str) -> str:
        """
        Request permission from user via WebSocket.

        Args:
            tool_name: Name of the tool requesting permission

        Returns:
            Permission scope chosen by user: "one_time", "session", "persistent", "global"

        Raises:
            RuntimeError: If no WebSocket connection available
            asyncio.TimeoutError: If user doesn't respond within 60 seconds
        """
        if not self.websocket:
            raise RuntimeError(
                "No WebSocket connection available for permission request"
            )

        # Create future for this request
        future: asyncio.Future[str] = asyncio.Future()
        self.pending_requests[tool_name] = future

        # Send permission request to frontend
        await self.websocket.send_json(
            {
                "type": "permission_request",
                "tool_name": tool_name,
                "message": f"The agent wants to use the '{tool_name}' tool. How would you like to proceed?",
            }
        )

        logger.info(
            f"📤 Sent permission request for '{tool_name}' to frontend"
        )

        # Wait for user response (with 60 second timeout)
        try:
            scope: str = await asyncio.wait_for(future, timeout=60.0)
            logger.info(
                f"✅ Received permission response for '{tool_name}': {scope}"
            )
            return scope
        except asyncio.TimeoutError:
            logger.warning(
                f"⏱️ Permission request for '{tool_name}' timed out"
            )
            del self.pending_requests[tool_name]
            raise
        finally:
            # Clean up future if still pending
            if tool_name in self.pending_requests:
                del self.pending_requests[tool_name]

    def handle_permission_response(self, tool_name: str, scope: str):
        """
        Process user's permission choice.

        Args:
            tool_name: Name of the tool
            scope: Permission scope chosen: "one_time", "session", "persistent", "global"
        """
        logger.info(
            f"🔐 Processing permission response: {tool_name} → {scope}"
        )

        if scope == "one_time":
            # Allow just this one invocation
            self.one_time_permissions[tool_name] = 1
            logger.info(f"✅ Granted one-time permission for '{tool_name}'")

        elif scope == "session":
            # Allow for current session
            self.session_permissions[tool_name] = True
            logger.info(f"✅ Granted session permission for '{tool_name}'")

        elif scope == "persistent":
            # Allow across all sessions (save to ConfigService)
            persistent_perms = (
                self.config_service.get_persistent_permissions()
            )
            if tool_name not in persistent_perms:
                persistent_perms.append(tool_name)
                self.config_service.set_persistent_permissions(
                    persistent_perms
                )
            logger.info(f"✅ Granted persistent permission for '{tool_name}'")

        elif scope == "global":
            # Bypass all permissions forever
            self.config_service.set_global_bypass_permissions(True)
            logger.info("✅ Enabled global bypass (all tools allowed)")

        # Resolve the pending future
        if tool_name in self.pending_requests:
            future = self.pending_requests[tool_name]
            if not future.done():
                future.set_result(scope)

    def clear_session_permissions(self):
        """Clear session-level and one-time permissions (called on disconnect)."""
        self.session_permissions.clear()
        self.one_time_permissions.clear()
        logger.info("🧹 Cleared session and one-time permissions")

    def cancel_pending_requests(self):
        """Cancel all pending permission requests."""
        for tool_name, future in self.pending_requests.items():
            if not future.done():
                future.cancel()
                logger.info(
                    f"❌ Cancelled pending permission request for '{tool_name}'"
                )
        self.pending_requests.clear()
