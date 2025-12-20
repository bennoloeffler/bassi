"""
Chat Index Manager

Maintains an in-memory index of all chats for fast listing and searching.
Backed by chats/.index.json for persistence.

NOTE: This is the renamed version of SessionIndex.
      "Session" was confusing with browser sessions.
      "Chat" clearly refers to a conversation context.
"""

import json
import logging
from pathlib import Path
from typing import Literal, Optional

from bassi.core_v3.chat_workspace import ChatWorkspace

logger = logging.getLogger(__name__)

ChatState = Literal["CREATED", "AUTO_NAMED", "FINALIZED", "ARCHIVED"]
SortField = Literal[
    "last_activity", "created_at", "message_count", "file_count"
]


class ChatIndex:
    """
    In-memory index for fast chat listing.

    Responsibilities:
    - Index all chats in chats/ directory
    - Provide fast listing without filesystem traversal
    - Support sorting, filtering, pagination
    - Auto-rebuild index if stale or missing
    - Persist index to .index.json

    NOTE: Renamed from SessionIndex. "Chat" is clearer than "Session"
          which was confused with browser sessions.
    """

    INDEX_VERSION = "1.0"

    def __init__(self, base_path: Path = Path("chats")):
        """
        Initialize chat index.

        Args:
            base_path: Base directory for all chats
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
                f"Loaded index with {len(self.index['sessions'])} chats"
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
        """Rebuild index by scanning all chat directories."""
        logger.info("Rebuilding chat index...")

        self.index = {"version": self.INDEX_VERSION, "sessions": {}}

        if not self.base_path.exists():
            logger.info("Base path doesn't exist. Empty index created.")
            self._save_index()
            return

        # Scan all directories
        scanned = 0
        indexed = 0

        for chat_dir in self.base_path.iterdir():
            if not chat_dir.is_dir():
                continue

            # Skip .index.json and other dot files
            if chat_dir.name.startswith("."):
                continue

            scanned += 1
            chat_id = chat_dir.name

            # Check if this is a valid chat (has chat.json or session.json)
            if not ChatWorkspace.exists(chat_id, self.base_path):
                continue

            try:
                # Load chat and add to index
                workspace = ChatWorkspace.load(chat_id, self.base_path)
                self.add_chat(workspace)
                indexed += 1

            except Exception as e:
                logger.warning(f"Failed to index chat {chat_id}: {e}")

        logger.info(
            f"Index rebuild complete. Scanned {scanned} directories, "
            f"indexed {indexed} chats"
        )

        self._save_index()

    def add_chat(self, workspace: ChatWorkspace) -> None:
        """
        Add or update chat in index.

        Args:
            workspace: ChatWorkspace to add
        """
        stats = workspace.get_stats()

        logger.debug(
            f"📝 add_chat: workspace.display_name={workspace.display_name}, "
            f"stats={stats}"
        )

        self.index["sessions"][workspace.chat_id] = {
            "session_id": workspace.chat_id,  # Backward compatibility
            "chat_id": workspace.chat_id,
            "display_name": workspace.display_name,
            "state": workspace.state,
            "created_at": stats["created_at"],
            "last_activity": stats["last_activity"],
            "message_count": stats["message_count"],
            "file_count": stats["file_count"],
        }

        self._save_index()

    # Backward compatibility aliases
    def add_session(self, workspace: ChatWorkspace) -> None:
        """Backward compatibility: add_session -> add_chat."""
        self.add_chat(workspace)

    def update_chat(self, workspace: ChatWorkspace) -> None:
        """
        Update existing chat in index.

        Args:
            workspace: ChatWorkspace to update
        """
        # Same as add_chat (upsert behavior)
        self.add_chat(workspace)

    def update_session(self, workspace: ChatWorkspace) -> None:
        """Backward compatibility: update_session -> update_chat."""
        self.update_chat(workspace)

    def remove_chat(self, chat_id: str) -> None:
        """
        Remove chat from index.

        Args:
            chat_id: Chat ID to remove
        """
        if chat_id in self.index["sessions"]:
            del self.index["sessions"][chat_id]
            self._save_index()

    def remove_session(self, session_id: str) -> None:
        """Backward compatibility: remove_session -> remove_chat."""
        self.remove_chat(session_id)

    def list_chats(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: SortField = "last_activity",
        sort_desc: bool = True,
        filter_state: Optional[ChatState] = None,
    ) -> list[dict]:
        """
        List chats with sorting, filtering, and pagination.

        Args:
            limit: Maximum number of chats to return
            offset: Number of chats to skip
            sort_by: Field to sort by
            sort_desc: Sort in descending order if True
            filter_state: Filter by chat state (optional)

        Returns:
            List of chat info dicts
        """
        chats = list(self.index["sessions"].values())

        # Filter by state
        if filter_state:
            chats = [s for s in chats if s["state"] == filter_state]

        # Sort
        chats.sort(key=lambda s: s.get(sort_by, ""), reverse=sort_desc)

        # Paginate
        return chats[offset : offset + limit]

    def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: SortField = "last_activity",
        sort_desc: bool = True,
        filter_state: Optional[ChatState] = None,
    ) -> list[dict]:
        """Backward compatibility: list_sessions -> list_chats."""
        return self.list_chats(
            limit, offset, sort_by, sort_desc, filter_state
        )

    def search_chats(self, query: str) -> list[dict]:
        """
        Search chats by display name.

        Args:
            query: Search query (case-insensitive substring match)

        Returns:
            List of matching chat info dicts
        """
        query_lower = query.lower()
        chats = list(self.index["sessions"].values())

        matches = [
            s for s in chats if query_lower in s["display_name"].lower()
        ]

        # Sort by last_activity desc
        matches.sort(key=lambda s: s["last_activity"], reverse=True)

        return matches

    def search_sessions(self, query: str) -> list[dict]:
        """Backward compatibility: search_sessions -> search_chats."""
        return self.search_chats(query)

    def get_chat_info(self, chat_id: str) -> Optional[dict]:
        """
        Get chat info from index.

        Args:
            chat_id: Chat ID to get

        Returns:
            Chat info dict or None if not found
        """
        return self.index["sessions"].get(chat_id)

    def get_session_info(self, session_id: str) -> Optional[dict]:
        """Backward compatibility: get_session_info -> get_chat_info."""
        return self.get_chat_info(session_id)

    def get_stats(self) -> dict:
        """
        Get overall index statistics.

        Returns:
            Dict with total_chats, states breakdown, etc.
        """
        chats = list(self.index["sessions"].values())

        # Count by state
        state_counts = {
            "CREATED": 0,
            "AUTO_NAMED": 0,
            "FINALIZED": 0,
            "ARCHIVED": 0,
        }

        for chat in chats:
            state = chat.get("state", "CREATED")
            if state in state_counts:
                state_counts[state] += 1

        return {
            "total_chats": len(chats),
            "total_sessions": len(chats),  # Backward compatibility
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

        # Find chats in filesystem
        fs_chats = set()
        for chat_dir in self.base_path.iterdir():
            if chat_dir.is_dir() and not chat_dir.name.startswith("."):
                if ChatWorkspace.exists(chat_dir.name, self.base_path):
                    fs_chats.add(chat_dir.name)

        # Find chats in index
        index_chats = set(self.index["sessions"].keys())

        # Compare
        missing_from_index = fs_chats - index_chats
        missing_from_fs = index_chats - fs_chats

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

        Adds missing chats, removes deleted chats.

        Returns:
            Dict with repair results
        """
        verification = self.verify_consistency()

        added = 0
        removed = 0

        # Add missing chats
        for chat_id in verification["missing_from_index"]:
            try:
                workspace = ChatWorkspace.load(chat_id, self.base_path)
                self.add_chat(workspace)
                added += 1
            except Exception as e:
                logger.warning(f"Failed to add chat {chat_id}: {e}")

        # Remove deleted chats
        for chat_id in verification["missing_from_fs"]:
            self.remove_chat(chat_id)
            removed += 1

        return {
            "added": added,
            "removed": removed,
            "consistent": verification["consistent"],
        }


# Backward compatibility alias
SessionIndex = ChatIndex

