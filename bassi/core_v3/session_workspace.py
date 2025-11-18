"""
Session Workspace Manager

Manages session-specific file storage and organization following the
session workspace architecture.

Physical path: chats/{session_id}/
Display name: Stored in metadata (mutable)
Symlink: chats-human-readable/{timestamp}__{name}__{short-id} -> ../chats/{session_id}
"""

import asyncio
import hashlib
import json
import os
import re
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

        # Symlink directory for human-readable session names
        # Place it as sibling to base_path (e.g., if base_path="chats", symlink_dir="chats-human-readable")
        # Use with_name to handle both relative (Path("chats")) and absolute (tmp_path) paths
        self.SYMLINK_DIR = base_path.with_name("chats-human-readable")

        if create:
            self._create_directory_structure()

        self.metadata = self._load_or_create_metadata()

        # Create initial symlink for new sessions
        if create and not self.metadata.get("symlink_name"):
            self._create_initial_symlink()

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

    def _sanitize_name(self, name: str) -> str:
        """
        Clean name for filesystem use (kebab-case).

        Converts to lowercase, replaces spaces/underscores with hyphens,
        removes non-alphanumeric chars (except hyphens), collapses multiple
        hyphens, and truncates to 50 chars.

        Args:
            name: Original name

        Returns:
            Sanitized kebab-case name
        """
        # Lowercase and replace spaces/underscores with hyphens
        name = name.lower().replace(" ", "-").replace("_", "-")

        # Remove non-alphanumeric except hyphens
        name = re.sub(r"[^a-z0-9-]", "", name)

        # Collapse multiple hyphens
        name = re.sub(r"-+", "-", name)

        # Strip leading/trailing hyphens
        name = name.strip("-")

        # Truncate to 50 chars
        return name[:50]

    def _create_initial_symlink(self) -> None:
        """
        Create initial symlink with timestamp and placeholder name.

        Format: {iso-datetime}__new-session__{short-id}
        Example: 2025-11-08T14-30-45-123456__new-session__a1b2c3d4
        """
        # Ensure symlink directory exists
        self.SYMLINK_DIR.mkdir(parents=True, exist_ok=True)

        # Generate symlink name with milliseconds for test robustness
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")
        short_id = self.session_id[:8]
        symlink_name = f"{timestamp}__new-session__{short_id}"

        # Create symlink with correct relative target
        symlink_path = self.SYMLINK_DIR / symlink_name
        target = Path("..") / self.base_path.name / self.session_id

        try:
            os.symlink(target, symlink_path)
            self.metadata["symlink_name"] = symlink_name
            self._save_metadata()
        except FileExistsError:
            # Symlink already exists (race condition), just update metadata
            self.metadata["symlink_name"] = symlink_name
            self._save_metadata()

    def update_symlink(self, new_name: str) -> None:
        """
        Update symlink with new LLM-generated or user-provided name.

        Removes old symlink and creates new one with updated name.

        Format: {iso-datetime}__{sanitized-name}__{short-id}
        Example: 2025-11-08T14-30-45__implement-login-feature__a1b2c3d4

        Args:
            new_name: New human-readable name (will be sanitized)
        """
        # Remove old symlink if it exists
        self._remove_symlink()

        # Ensure symlink directory exists
        self.SYMLINK_DIR.mkdir(parents=True, exist_ok=True)

        # Generate new symlink name with milliseconds for test robustness
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")
        short_id = self.session_id[:8]
        clean_name = self._sanitize_name(new_name)

        if not clean_name:
            clean_name = "unnamed-session"

        symlink_name = f"{timestamp}__{clean_name}__{short_id}"

        # Create new symlink with correct relative target
        symlink_path = self.SYMLINK_DIR / symlink_name
        target = Path("..") / self.base_path.name / self.session_id

        try:
            os.symlink(target, symlink_path)
            self.metadata["symlink_name"] = symlink_name
            self._save_metadata()
        except FileExistsError:
            # Symlink already exists, append counter
            counter = 1
            while True:
                new_symlink_name = f"{symlink_name}-{counter}"
                new_symlink_path = self.SYMLINK_DIR / new_symlink_name

                try:
                    # Try to create symlink with counter suffix
                    os.symlink(target, new_symlink_path)
                    self.metadata["symlink_name"] = new_symlink_name
                    self._save_metadata()
                    break
                except FileExistsError:
                    # Race condition: symlink created between iterations
                    # Continue to next counter
                    pass

                counter += 1
                if counter > 100:
                    # Safety limit
                    raise ValueError(
                        f"Could not create unique symlink for {symlink_name}"
                    )

    def _remove_symlink(self) -> None:
        """Remove existing symlink if it exists and clear metadata."""
        symlink_name = self.metadata.get("symlink_name")

        if symlink_name:
            symlink_path = self.SYMLINK_DIR / symlink_name

            try:
                # Try to remove symlink (will raise if not exists)
                symlink_path.unlink()
            except FileNotFoundError:
                # Race condition: symlink already removed by another process
                # or never existed - both cases are fine
                pass

            # Clear symlink metadata
            self.metadata["symlink_name"] = None
            self._save_metadata()

    def delete(self) -> None:
        """
        Delete workspace directory and symlink.

        WARNING: This permanently deletes all session data.
        """
        import shutil

        # Remove symlink first
        self._remove_symlink()

        # Remove physical directory
        if self.physical_path.exists():
            shutil.rmtree(self.physical_path)

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

    def load_conversation_history(self) -> list[dict]:
        """
        Load conversation history from history.md.

        Returns:
            List of message dicts with role, content, timestamp

        Format in history.md:
            ## User - 2025-11-09T10:30:00.123456

            message content here

            ## Assistant - 2025-11-09T10:30:05.654321

            assistant response here
        """
        history_path = self.physical_path / "history.md"

        if not history_path.exists():
            return []

        messages = []
        current_message = None

        with open(history_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")

                # Check for message header: ## User - timestamp or ## Assistant - timestamp
                # CRITICAL: Only match if line contains " - " (timestamp separator)
                # This prevents treating markdown headings (## Background) as message boundaries
                if line.startswith("## ") and " - " in line:
                    # Save previous message if exists
                    if current_message is not None:
                        messages.append(current_message)

                    # Parse new message header
                    # Format: ## User - 2025-11-09T10:30:00.123456
                    parts = line[3:].split(" - ", 1)
                    if len(parts) == 2:
                        role = parts[0].strip().lower()
                        timestamp_str = parts[1].strip()

                        current_message = {
                            "role": role,
                            "content": "",
                            "timestamp": timestamp_str,
                        }
                elif current_message is not None:
                    # Accumulate content lines (skip empty lines between sections)
                    if line or current_message["content"]:
                        if current_message["content"]:
                            current_message["content"] += "\n" + line
                        else:
                            current_message["content"] = line

        # Don't forget the last message
        if current_message is not None:
            messages.append(current_message)

        # Clean up content (strip trailing newlines)
        for msg in messages:
            msg["content"] = msg["content"].strip()

        return messages

    @property
    def display_name(self) -> str:
        """Get human-readable session name from metadata."""
        return self.metadata.get(
            "display_name", f"Session {self.session_id[:8]}"
        )

    def update_display_name(self, new_name: str) -> None:
        """
        Update session display name and symlink.

        Args:
            new_name: New display name (mutable, doesn't affect physical path)
        """
        self.metadata["display_name"] = new_name
        self._save_metadata()

        # Update symlink with new name
        self.update_symlink(new_name)

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

    def get_workspace_context(self) -> str:
        """
        Generate workspace context string for agent awareness.

        Returns a formatted string describing:
        - Available workspace folders and their purposes
        - Files currently in DATA_FROM_USER/
        - Instructions for saving outputs to appropriate folders

        Returns:
            Formatted workspace context string
        """
        # Build context string
        context_lines = [
            "# Your Workspace",
            "",
            f"**Session:** {self.display_name}",
            f"**Session ID:** {self.session_id}",
            "",
            "## Folder Structure",
            "",
            "Your workspace has the following folders:",
            "",
            "- **DATA_FROM_USER/** - Files uploaded by the user. Read-only.",
            "- **RESULTS_FROM_AGENT/** - Save analysis results, reports, processed data here.",
            "- **SCRIPTS_FROM_AGENT/** - Save reusable scripts, tools, utilities here.",
            "- **DATA_FROM_AGENT/** - Save other data files (downloads, generated data) here.",
            "",
        ]

        # List available files in DATA_FROM_USER
        uploaded_files = self.list_files()

        if uploaded_files:
            context_lines.extend(
                [
                    "## Available Files",
                    "",
                    "The user has uploaded these files:",
                    "",
                ]
            )

            for file_info in uploaded_files:
                file_size_kb = file_info["size"] / 1024
                context_lines.append(
                    f"- `{file_info['path']}` ({file_size_kb:.1f} KB)"
                )

            context_lines.extend(["", ""])
        else:
            context_lines.extend(
                [
                    "## Available Files",
                    "",
                    "No files have been uploaded yet.",
                    "",
                ]
            )

        # Add usage instructions
        context_lines.extend(
            [
                "## File Path Instructions",
                "",
                "When working with files:",
                "",
                f"1. **Reading user files:** Use `chats/{self.session_id}/DATA_FROM_USER/filename`",
                f"2. **Saving results:** Use `chats/{self.session_id}/RESULTS_FROM_AGENT/filename`",
                f"3. **Saving scripts:** Use `chats/{self.session_id}/SCRIPTS_FROM_AGENT/filename`",
                f"4. **Saving data:** Use `chats/{self.session_id}/DATA_FROM_AGENT/filename`",
                "",
                "**Always use these full paths when calling tools like file read/write.**",
                "",
            ]
        )

        return "\n".join(context_lines)

    def get_output_path(self, category: str, filename: str) -> str:
        """
        Get full output path for a given category and filename.

        Args:
            category: One of 'results', 'scripts', 'data'
            filename: Name of the file to save

        Returns:
            Full path string suitable for agent tool use

        Raises:
            ValueError: If category is invalid
        """
        category_map = {
            "results": "RESULTS_FROM_AGENT",
            "scripts": "SCRIPTS_FROM_AGENT",
            "data": "DATA_FROM_AGENT",
        }

        if category not in category_map:
            raise ValueError(
                f"Invalid category: {category}. Must be one of: {list(category_map.keys())}"
            )

        subdir = category_map[category]
        return str(self.physical_path / subdir / filename)
