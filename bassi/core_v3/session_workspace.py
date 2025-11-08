"""
Session Workspace Manager

Manages session-specific file storage and organization following the
session workspace architecture.

Physical path: chats/{session_id}/
Display name: Stored in metadata (mutable)
"""

import asyncio
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import UploadFile


class SessionWorkspace:
    """
    Manages a single session's workspace.

    Responsibilities:
    - Create directory structure (DATA_FROM_USER, RESULTS_FROM_AGENT, etc.)
    - Store uploaded files with hash-based deduplication
    - Track file metadata
    - Save conversation history
    - Manage session metadata (display_name, state, etc.)
    """

    # File upload settings
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    CHUNK_SIZE = 64 * 1024  # 64 KB chunks for streaming

    # Directory structure
    SUBDIRS = [
        "DATA_FROM_USER",
        "RESULTS_FROM_AGENT",
        "SCRIPTS_FROM_AGENT",
        "DATA_FROM_AGENT",
    ]

    def __init__(
        self,
        session_id: str,
        base_path: Path = Path("chats"),
        create: bool = True,
    ):
        """
        Initialize session workspace.

        Args:
            session_id: Unique session identifier (UUID format)
            base_path: Base directory for all sessions
            create: If True, create directory structure
        """
        self.session_id = session_id
        self.base_path = base_path
        self.physical_path = base_path / session_id
        self._upload_lock = asyncio.Lock()

        if create:
            self._create_directory_structure()

        self.metadata = self._load_or_create_metadata()

    def _create_directory_structure(self) -> None:
        """Create workspace directory structure."""
        self.physical_path.mkdir(parents=True, exist_ok=True)

        for subdir in self.SUBDIRS:
            (self.physical_path / subdir).mkdir(exist_ok=True)

    def _load_or_create_metadata(self) -> dict:
        """Load existing metadata or create new metadata file."""
        metadata_path = self.physical_path / "session.json"

        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)

        # Create new metadata
        metadata = {
            "session_id": self.session_id,
            "display_name": f"Session {self.session_id[:8]}",
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "state": "CREATED",  # CREATED, AUTO_NAMED, FINALIZED, ARCHIVED
            "message_count": 0,
            "file_count": 0,
        }

        self._save_metadata(metadata)
        return metadata

    def _save_metadata(self, metadata: Optional[dict] = None) -> None:
        """Save metadata to session.json."""
        if metadata is None:
            metadata = self.metadata

        metadata_path = self.physical_path / "session.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    async def upload_file(self, file: UploadFile) -> Path:
        """
        Upload file to DATA_FROM_USER/ with hash-based deduplication.

        Args:
            file: FastAPI UploadFile object

        Returns:
            Path to saved file

        Raises:
            ValueError: If file exceeds size limit
        """
        async with self._upload_lock:
            # Validate file size
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset to beginning

            if file_size > self.MAX_FILE_SIZE:
                raise ValueError(
                    f"File too large: {file_size / 1024 / 1024:.1f} MB "
                    f"(max {self.MAX_FILE_SIZE / 1024 / 1024:.1f} MB)"
                )

            # Stream to temporary file while hashing (bounded memory)
            hasher = hashlib.sha256()
            temp_dir = self.physical_path / "DATA_FROM_USER"
            temp_file_path = temp_dir / f".tmp_{file.filename}"

            # Ensure directory exists
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Write and hash in one pass
            with open(temp_file_path, "wb") as f:
                while True:
                    chunk = await file.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    f.write(chunk)

            file_hash = hasher.hexdigest()[:16]  # Use first 16 chars

            # Check for duplicate by hash
            existing_file = self._find_file_by_hash(file_hash)
            if existing_file:
                # Remove temp file and return existing
                temp_file_path.unlink()
                return existing_file

            # Generate unique filename
            filename = self._generate_unique_filename(
                file.filename, file_hash
            )
            file_path = self.physical_path / "DATA_FROM_USER" / filename

            # Rename temp file to final location
            temp_file_path.rename(file_path)

            # Update metadata
            self.metadata["file_count"] = (
                self.metadata.get("file_count", 0) + 1
            )
            self.metadata["last_activity"] = datetime.now().isoformat()
            self._save_metadata()

            return file_path

    def _find_file_by_hash(self, file_hash: str) -> Optional[Path]:
        """Check if file with same hash already exists."""
        data_dir = self.physical_path / "DATA_FROM_USER"

        for file_path in data_dir.glob("*"):
            if file_hash in file_path.name:
                return file_path

        return None

    def _generate_unique_filename(
        self, original_name: str, file_hash: str
    ) -> str:
        """
        Generate unique filename with hash.

        Format: {stem}_{hash}{extension}
        Example: report_a1b2c3d4.pdf
        """
        path = Path(original_name)
        stem = path.stem
        suffix = path.suffix

        return f"{stem}_{file_hash}{suffix}"

    def list_files(self) -> list[dict]:
        """
        List all files in DATA_FROM_USER/.

        Returns:
            List of file info dicts with name, size, uploaded_at
        """
        data_dir = self.physical_path / "DATA_FROM_USER"

        if not data_dir.exists():
            return []

        files = []
        for file_path in sorted(data_dir.iterdir()):
            if file_path.is_file():
                stat = file_path.stat()
                files.append(
                    {
                        "name": file_path.name,
                        "size": stat.st_size,
                        "uploaded_at": datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(),
                        "path": str(
                            file_path.relative_to(self.physical_path)
                        ),
                    }
                )

        return files

    def save_message(
        self, role: str, content: str, timestamp: Optional[datetime] = None
    ) -> None:
        """
        Append message to history.md.

        Args:
            role: 'user' or 'assistant'
            content: Message content
            timestamp: Message timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        history_path = self.physical_path / "history.md"

        # Create file if it doesn't exist
        if not history_path.exists():
            with open(history_path, "w", encoding="utf-8") as f:
                f.write(f"# Chat History: {self.display_name}\n\n")

        # Append message
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(f"\n## {role.capitalize()} - {timestamp.isoformat()}\n\n")
            f.write(f"{content}\n")

        # Update metadata
        self.metadata["message_count"] = (
            self.metadata.get("message_count", 0) + 1
        )
        self.metadata["last_activity"] = timestamp.isoformat()
        self._save_metadata()

    @property
    def display_name(self) -> str:
        """Get human-readable session name from metadata."""
        return self.metadata.get(
            "display_name", f"Session {self.session_id[:8]}"
        )

    def update_display_name(self, new_name: str) -> None:
        """
        Update session display name.

        Args:
            new_name: New display name (mutable, doesn't affect physical path)
        """
        self.metadata["display_name"] = new_name
        self._save_metadata()

    def update_state(self, new_state: str) -> None:
        """
        Update session state.

        Args:
            new_state: One of CREATED, AUTO_NAMED, FINALIZED, ARCHIVED
        """
        valid_states = ["CREATED", "AUTO_NAMED", "FINALIZED", "ARCHIVED"]
        if new_state not in valid_states:
            raise ValueError(
                f"Invalid state: {new_state}. Must be one of {valid_states}"
            )

        self.metadata["state"] = new_state
        self._save_metadata()

    @property
    def state(self) -> str:
        """Get current session state."""
        return self.metadata.get("state", "CREATED")

    def get_stats(self) -> dict:
        """
        Get session statistics.

        Returns:
            Dict with message_count, file_count, created_at, last_activity, state
        """
        return {
            "session_id": self.session_id,
            "display_name": self.display_name,
            "state": self.state,
            "message_count": self.metadata.get("message_count", 0),
            "file_count": self.metadata.get("file_count", 0),
            "created_at": self.metadata.get("created_at"),
            "last_activity": self.metadata.get("last_activity"),
        }

    @classmethod
    def load(
        cls, session_id: str, base_path: Path = Path("chats")
    ) -> "SessionWorkspace":
        """
        Load existing session workspace.

        Args:
            session_id: Session ID to load
            base_path: Base directory for sessions

        Returns:
            SessionWorkspace instance

        Raises:
            FileNotFoundError: If session doesn't exist
        """
        workspace_path = base_path / session_id

        if not workspace_path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        return cls(session_id, base_path, create=False)

    @classmethod
    def exists(cls, session_id: str, base_path: Path = Path("chats")) -> bool:
        """Check if session workspace exists."""
        workspace_path = base_path / session_id
        return (
            workspace_path.exists()
            and (workspace_path / "session.json").exists()
        )
