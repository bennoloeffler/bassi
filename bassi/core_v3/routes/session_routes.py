"""
Session Routes - HTTP endpoints for session management.

BLACK BOX INTERFACE:
- GET /api/sessions - List all sessions
- GET /api/sessions/{session_id} - Get session details
- GET /api/sessions/{session_id}/messages - Get session message history
- DELETE /api/sessions/{session_id} - Delete a session

DEPENDENCIES: SessionService, workspace_base_path (injected)
"""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from bassi.core_v3.services.session_service import SessionService
from bassi.core_v3.session_workspace import SessionWorkspace

logger = logging.getLogger(__name__)


def create_session_router(workspace_base_path: str | Path) -> APIRouter:
    """
    Create session routes with workspace_base_path injected.

    Args:
        workspace_base_path: Base directory for session workspaces

    Returns:
        Configured APIRouter instance
    """
    router = APIRouter(prefix="/api/sessions", tags=["sessions"])

    @router.get("")
    async def list_sessions(
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "last_activity",
        order: str = "desc",
    ) -> dict[str, list[dict[str, Any]]]:
        """
        List all available sessions.

        Query Parameters:
            limit: Maximum number of sessions to return (default: 100)
            offset: Number of sessions to skip (default: 0)
            sort_by: Field to sort by (created_at, last_activity, display_name) (default: last_activity)
            order: Sort order (asc, desc) (default: desc)

        Returns:
            Dictionary with "sessions" key containing list of session metadata
        """
        sessions = await SessionService.list_sessions(
            workspace_base_path=workspace_base_path,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            order=order,
        )
        return {"sessions": sessions}

    @router.get("/{session_id}")
    async def get_session(session_id: str) -> dict[str, Any]:
        """
        Get detailed information about a specific session.

        Path Parameters:
            session_id: The session ID to retrieve

        Returns:
            Session details including messages and workspace files

        Raises:
            HTTPException(404): If session not found
        """
        session = await SessionService.get_session(
            session_id=session_id, workspace_base_path=workspace_base_path
        )

        if session is None:
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found"
            )

        return session

    @router.get("/{session_id}/messages")
    async def get_session_messages(
        session_id: str,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Get message history for a specific session.

        Path Parameters:
            session_id: The session ID to retrieve messages for

        Returns:
            Dictionary with "messages" key containing list of messages
            Each message has: {role, content, timestamp}

        Raises:
            HTTPException(404): If session not found
        """
        session_dir = Path(workspace_base_path) / session_id
        if not session_dir.exists():
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found"
            )

        try:
            # Load workspace to access conversation history
            workspace = SessionWorkspace.load(
                session_id=session_id, base_path=Path(workspace_base_path)
            )

            # Load conversation history from history.md
            messages = workspace.load_conversation_history()

            return {"messages": messages}

        except Exception as e:
            logger.error(
                f"Failed to load messages for session {session_id}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load messages: {str(e)}",
            )

    @router.delete("/{session_id}")
    async def delete_session(session_id: str) -> dict[str, str]:
        """
        Delete a session and its workspace.

        Path Parameters:
            session_id: The session ID to delete

        Returns:
            Success message

        Raises:
            HTTPException(404): If session not found
        """
        success = await SessionService.delete_session(
            session_id=session_id, workspace_base_path=workspace_base_path
        )

        if not success:
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found"
            )

        return {"message": f"Session {session_id} deleted successfully"}

    return router
