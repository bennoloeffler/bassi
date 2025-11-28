"""
Session Service - Manages session CRUD operations.

BLACK BOX INTERFACE:
- list_sessions(workspace_base_path) -> List of session metadata
- get_session(session_id, workspace_base_path) -> Session details
- delete_session(session_id, workspace_base_path) -> Success/failure

DEPENDENCIES: None (stateless service)
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SessionService:
    """Service for session management operations."""

    @staticmethod
    async def list_sessions(
        workspace_base_path: str | Path,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "last_activity",
        order: str = "desc",
    ) -> list[dict[str, Any]]:
        """
        List all available sessions with metadata.

        Args:
            workspace_base_path: Base directory for session workspaces
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip
            sort_by: Field to sort by (created_at, last_activity, display_name)
            order: Sort order (asc, desc)

        Returns:
            List of session dictionaries with session_id, display_name, created_at, etc.
        """
        sessions = []
        workspace_dir = Path(workspace_base_path)

        if not workspace_dir.exists():
            return sessions

        # Collect all session directories
        # Note: ChatWorkspace uses "chat.json", old SessionWorkspace used "session.json"
        session_dirs = [
            d
            for d in workspace_dir.iterdir()
            if d.is_dir() and ((d / "chat.json").exists() or (d / "session.json").exists())
        ]

        # Load metadata for each session
        for session_dir in session_dirs:
            # Support both new (chat.json) and old (session.json) names
            state_file = session_dir / "chat.json"
            if not state_file.exists():
                state_file = session_dir / "session.json"
            try:
                with open(state_file, "r") as f:
                    state = json.load(f)

                # Use format compatible with SessionIndex
                sessions.append(
                    {
                        "session_id": session_dir.name,
                        "display_name": state.get("display_name", session_dir.name),
                        "state": state.get("state", "active"),
                        "created_at": state.get(
                            "created_at",
                            datetime.fromtimestamp(
                                state_file.stat().st_ctime
                            ).isoformat(),
                        ),
                        "last_activity": state.get(
                            "last_activity",
                            datetime.fromtimestamp(
                                state_file.stat().st_mtime
                            ).isoformat(),
                        ),
                        "message_count": state.get("message_count", 0),
                        "file_count": state.get("file_count", 0),
                    }
                )
            except Exception as e:
                logger.warning(
                    f"Failed to load session {session_dir.name}: {e}"
                )
                continue

        # Filter out empty sessions (message_count == 0)
        # User requirement: "JUST REMOVE THEM"
        sessions = [s for s in sessions if s.get("message_count", 0) > 0]

        # Sort sessions
        reverse = order == "desc"
        if sort_by == "created_at":
            sessions.sort(
                key=lambda s: s.get("created_at", ""), reverse=reverse
            )
        elif sort_by == "last_activity":
            sessions.sort(
                key=lambda s: s.get("last_activity", ""), reverse=reverse
            )
        elif sort_by == "display_name":
            sessions.sort(
                key=lambda s: s.get("display_name", "").lower(),
                reverse=reverse,
            )

        # Apply offset and limit after sorting
        return sessions[offset : offset + limit]

    @staticmethod
    async def get_session(
        session_id: str, workspace_base_path: str | Path
    ) -> dict[str, Any] | None:
        """
        Get detailed information about a specific session.

        Args:
            session_id: The session ID to retrieve
            workspace_base_path: Base directory for session workspaces

        Returns:
            Session details dict or None if not found
        """
        session_dir = Path(workspace_base_path) / session_id
        # Support both new (chat.json) and old (session.json) names
        state_file = session_dir / "chat.json"
        if not state_file.exists():
            state_file = session_dir / "session.json"

        if not state_file.exists():
            return None

        try:
            with open(state_file, "r") as f:
                state = json.load(f)

            # Count files in workspace
            workspace_files = []
            if session_dir.exists():
                workspace_files = [
                    str(f.relative_to(session_dir))
                    for f in session_dir.rglob("*")
                    if f.is_file() and f.name != "session.json"
                ]

            return {
                "id": session_id,
                "name": state.get("name", session_id),
                "messages": state.get("messages", []),
                "workspace_files": workspace_files,
                "created": session_dir.stat().st_ctime,
                "last_modified": state_file.stat().st_mtime,
            }
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None

    @staticmethod
    async def delete_session(
        session_id: str, workspace_base_path: str | Path
    ) -> bool:
        """
        Delete a session and its workspace.

        Args:
            session_id: The session ID to delete
            workspace_base_path: Base directory for session workspaces

        Returns:
            True if deleted successfully, False otherwise
        """
        session_dir = Path(workspace_base_path) / session_id

        if not session_dir.exists():
            return False

        try:
            import shutil

            shutil.rmtree(session_dir)
            logger.info(f"Deleted session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
