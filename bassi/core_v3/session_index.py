"""
Session Index Manager

Maintains an in-memory index of all sessions for fast listing and searching.
Backed by chats/.index.json for persistence.
"""

import json
import logging
from pathlib import Path
from typing import Literal, Optional

from bassi.core_v3.session_workspace import SessionWorkspace

logger = logging.getLogger(__name__)

SessionState = Literal["CREATED", "AUTO_NAMED", "FINALIZED", "ARCHIVED"]
SortField = Literal[
    "last_activity", "created_at", "message_count", "file_count"
]


class SessionIndex:
    """
    In-memory index for fast session listing.

    Responsibilities:
    - Index all sessions in chats/ directory
    - Provide fast listing without filesystem traversal
    - Support sorting, filtering, pagination
    - Auto-rebuild index if stale or missing
    - Persist index to .index.json
    """

    INDEX_VERSION = "1.0"

    def __init__(self, base_path: Path = Path("chats")):
        """
        Initialize session index.

        Args:
            base_path: Base directory for all sessions
        """
        self.base_path = base_path
        self.index_file = base_path / ".index.json"
        self.index: dict = {"version": self.INDEX_VERSION, "sessions": {}}

        # Create base directory if it doesn't exist
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Load or rebuild index
        if self.index_file.exists():
            self._load_index()
        else:
            self._rebuild_index()

    def _load_index(self) -> None:
        """Load index from .index.json."""
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            # Verify version
            if loaded.get("version") != self.INDEX_VERSION:
                logger.warning(
                    f"Index version mismatch. Rebuilding. "
                    f"Expected {self.INDEX_VERSION}, got {loaded.get('version')}"
                )
                self._rebuild_index()
                return

            self.index = loaded
            logger.info(
                f"Loaded index with {len(self.index['sessions'])} sessions"
            )

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load index: {e}. Rebuilding.")
            self._rebuild_index()

    def _save_index(self) -> None:
        """Save index to .index.json."""
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(self.index, f, indent=2, ensure_ascii=False)

        except OSError as e:
            logger.error(f"Failed to save index: {e}")

    def _rebuild_index(self) -> None:
        """Rebuild index by scanning all session directories."""
        logger.info("Rebuilding session index...")

        self.index = {"version": self.INDEX_VERSION, "sessions": {}}

        if not self.base_path.exists():
            logger.info("Base path doesn't exist. Empty index created.")
            self._save_index()
            return

        # Scan all directories
        scanned = 0
        indexed = 0

        for session_dir in self.base_path.iterdir():
            if not session_dir.is_dir():
                continue

            # Skip .index.json and other dot files
            if session_dir.name.startswith("."):
                continue

            scanned += 1
            session_id = session_dir.name

            # Check if this is a valid session (has session.json)
            if not SessionWorkspace.exists(session_id, self.base_path):
                continue

            try:
                # Load session and add to index
                workspace = SessionWorkspace.load(session_id, self.base_path)
                self.add_session(workspace)
                indexed += 1

            except Exception as e:
                logger.warning(f"Failed to index session {session_id}: {e}")

        logger.info(
            f"Index rebuild complete. Scanned {scanned} directories, "
            f"indexed {indexed} sessions"
        )

        self._save_index()

    def add_session(self, workspace: SessionWorkspace) -> None:
        """
        Add or update session in index.

        Args:
            workspace: SessionWorkspace to add
        """
        stats = workspace.get_stats()

        self.index["sessions"][workspace.session_id] = {
            "session_id": workspace.session_id,
            "display_name": workspace.display_name,
            "state": workspace.state,
            "created_at": stats["created_at"],
            "last_activity": stats["last_activity"],
            "message_count": stats["message_count"],
            "file_count": stats["file_count"],
        }

        self._save_index()

    def update_session(self, workspace: SessionWorkspace) -> None:
        """
        Update existing session in index.

        Args:
            workspace: SessionWorkspace to update
        """
        # Same as add_session (upsert behavior)
        self.add_session(workspace)

    def remove_session(self, session_id: str) -> None:
        """
        Remove session from index.

        Args:
            session_id: Session ID to remove
        """
        if session_id in self.index["sessions"]:
            del self.index["sessions"][session_id]
            self._save_index()

    def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: SortField = "last_activity",
        sort_desc: bool = True,
        filter_state: Optional[SessionState] = None,
    ) -> list[dict]:
        """
        List sessions with sorting, filtering, and pagination.

        Args:
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip
            sort_by: Field to sort by
            sort_desc: Sort in descending order if True
            filter_state: Filter by session state (optional)

        Returns:
            List of session info dicts
        """
        sessions = list(self.index["sessions"].values())

        # Filter by state
        if filter_state:
            sessions = [s for s in sessions if s["state"] == filter_state]

        # Sort
        sessions.sort(key=lambda s: s.get(sort_by, ""), reverse=sort_desc)

        # Paginate
        return sessions[offset : offset + limit]

    def search_sessions(self, query: str) -> list[dict]:
        """
        Search sessions by display name.

        Args:
            query: Search query (case-insensitive substring match)

        Returns:
            List of matching session info dicts
        """
        query_lower = query.lower()
        sessions = list(self.index["sessions"].values())

        matches = [
            s for s in sessions if query_lower in s["display_name"].lower()
        ]

        # Sort by last_activity desc
        matches.sort(key=lambda s: s["last_activity"], reverse=True)

        return matches

    def get_session_info(self, session_id: str) -> Optional[dict]:
        """
        Get session info from index.

        Args:
            session_id: Session ID to get

        Returns:
            Session info dict or None if not found
        """
        return self.index["sessions"].get(session_id)

    def get_stats(self) -> dict:
        """
        Get overall index statistics.

        Returns:
            Dict with total_sessions, states breakdown, etc.
        """
        sessions = list(self.index["sessions"].values())

        # Count by state
        state_counts = {
            "CREATED": 0,
            "AUTO_NAMED": 0,
            "FINALIZED": 0,
            "ARCHIVED": 0,
        }

        for session in sessions:
            state = session.get("state", "CREATED")
            if state in state_counts:
                state_counts[state] += 1

        return {
            "total_sessions": len(sessions),
            "states": state_counts,
            "index_version": self.INDEX_VERSION,
        }

    def verify_consistency(self) -> dict:
        """
        Verify index consistency with filesystem.

        Returns:
            Dict with verification results
        """
        if not self.base_path.exists():
            return {
                "consistent": True,
                "missing_from_index": [],
                "missing_from_fs": [],
            }

        # Find sessions in filesystem
        fs_sessions = set()
        for session_dir in self.base_path.iterdir():
            if session_dir.is_dir() and not session_dir.name.startswith("."):
                if SessionWorkspace.exists(session_dir.name, self.base_path):
                    fs_sessions.add(session_dir.name)

        # Find sessions in index
        index_sessions = set(self.index["sessions"].keys())

        # Compare
        missing_from_index = fs_sessions - index_sessions
        missing_from_fs = index_sessions - fs_sessions

        consistent = (
            len(missing_from_index) == 0 and len(missing_from_fs) == 0
        )

        return {
            "consistent": consistent,
            "missing_from_index": list(missing_from_index),
            "missing_from_fs": list(missing_from_fs),
        }

    def repair(self) -> dict:
        """
        Repair index by syncing with filesystem.

        Adds missing sessions, removes deleted sessions.

        Returns:
            Dict with repair results
        """
        verification = self.verify_consistency()

        added = 0
        removed = 0

        # Add missing sessions
        for session_id in verification["missing_from_index"]:
            try:
                workspace = SessionWorkspace.load(session_id, self.base_path)
                self.add_session(workspace)
                added += 1
            except Exception as e:
                logger.warning(f"Failed to add session {session_id}: {e}")

        # Remove deleted sessions
        for session_id in verification["missing_from_fs"]:
            self.remove_session(session_id)
            removed += 1

        return {
            "added": added,
            "removed": removed,
            "consistent": verification["consistent"],
        }
