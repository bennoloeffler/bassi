"""
File Registry for Bassi

Tracks files available in a session from all sources (uploads, OneDrive, Dropbox, etc.)
Provides @reference system for mentioning files in messages.

Design principles:
- Upload once, reference anytime with @filename
- Files always visible in context
- Multi-source support (local uploads, cloud storage)
- Clean URI scheme: @source:path or just @filename for uploads
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class FileSource(str, Enum):
    """Source types for files."""

    UPLOAD = "upload"  # Local upload to session
    ONEDRIVE = "onedrive"  # Microsoft OneDrive/SharePoint
    DROPBOX = "dropbox"  # Dropbox
    GDRIVE = "gdrive"  # Google Drive (future)


class FileType(str, Enum):
    """File type categories."""

    IMAGE = "image"
    PDF = "pdf"
    DOCUMENT = "document"  # Word, text, markdown
    SPREADSHEET = "spreadsheet"  # Excel, CSV
    PRESENTATION = "presentation"  # PowerPoint
    CODE = "code"  # Source code files
    OTHER = "other"


@dataclass
class FileEntry:
    """
    Represents a file available in the session.

    Can be a local upload or remote file (OneDrive, Dropbox, etc.)
    """

    ref: str  # Short reference name (e.g., "report.pdf")
    source: FileSource  # Where the file is stored
    path: str  # Full path (local) or URI (remote)
    size: int  # File size in bytes
    file_type: FileType  # Category of file
    mime_type: str  # MIME type
    uploaded_at: str  # ISO timestamp
    file_id: Optional[str] = None  # Anthropic Files API ID (future)
    thumbnail: Optional[str] = None  # Base64 thumbnail for images
    metadata: dict = field(default_factory=dict)  # Additional metadata

    @property
    def size_human(self) -> str:
        """Human-readable file size."""
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        else:
            return f"{self.size / (1024 * 1024):.1f} MB"

    @property
    def icon(self) -> str:
        """Get appropriate icon for file type."""
        icons = {
            FileType.IMAGE: "image",
            FileType.PDF: "pdf",
            FileType.DOCUMENT: "doc",
            FileType.SPREADSHEET: "spreadsheet",
            FileType.PRESENTATION: "presentation",
            FileType.CODE: "code",
            FileType.OTHER: "file",
        }
        return icons.get(self.file_type, "file")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "ref": self.ref,
            "source": self.source.value,
            "path": self.path,
            "size": self.size,
            "size_human": self.size_human,
            "file_type": self.file_type.value,
            "mime_type": self.mime_type,
            "uploaded_at": self.uploaded_at,
            "file_id": self.file_id,
            "thumbnail": self.thumbnail,
            "icon": self.icon,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileEntry":
        """Create from dictionary."""
        return cls(
            ref=data["ref"],
            source=FileSource(data["source"]),
            path=data["path"],
            size=data["size"],
            file_type=FileType(data["file_type"]),
            mime_type=data["mime_type"],
            uploaded_at=data["uploaded_at"],
            file_id=data.get("file_id"),
            thumbnail=data.get("thumbnail"),
            metadata=data.get("metadata", {}),
        )


class FileRegistry:
    """
    Tracks files available in a session from all sources.

    Provides:
    - File registration and lookup
    - @reference resolution
    - Context generation for Claude
    - Persistence to disk

    Usage:
        registry = FileRegistry(chat_id, workspace_path)
        registry.register_upload("report.pdf", path, size, mime_type)
        entry = registry.resolve("@report.pdf")
        context = registry.get_context()
    """

    # Limits
    MAX_FILES_PER_SESSION = 20
    MAX_FILES_PER_MESSAGE = 5
    MAX_FILE_SIZE = 32 * 1024 * 1024  # 32 MB (Anthropic limit)
    MAX_SESSION_STORAGE = 500 * 1024 * 1024  # 500 MB total

    def __init__(self, chat_id: str, workspace_path: Path):
        """
        Initialize file registry for a chat session.

        Args:
            chat_id: Unique chat identifier
            workspace_path: Path to chat workspace directory
        """
        self.chat_id = chat_id
        self.workspace_path = workspace_path
        self.files: dict[str, FileEntry] = {}
        self._registry_file = workspace_path / "file_registry.json"
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        if self._registry_file.exists():
            try:
                with open(self._registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for ref, entry_data in data.get("files", {}).items():
                        self.files[ref] = FileEntry.from_dict(entry_data)
            except (json.JSONDecodeError, KeyError) as e:
                # Corrupted file, start fresh
                print(f"Warning: Could not load file registry: {e}")
                self.files = {}

    def _save(self) -> None:
        """Save registry to disk."""
        data = {
            "files": {
                ref: entry.to_dict() for ref, entry in self.files.items()
            }
        }
        with open(self._registry_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _generate_ref(self, filename: str) -> str:
        """
        Generate unique reference for a file.

        Handles duplicates by appending numbers: report.pdf, report-2.pdf, etc.
        """
        base_ref = Path(filename).name
        ref = base_ref
        counter = 2

        while ref in self.files:
            stem = Path(base_ref).stem
            suffix = Path(base_ref).suffix
            ref = f"{stem}-{counter}{suffix}"
            counter += 1

        return ref

    def _detect_file_type(self, filename: str, mime_type: str) -> FileType:
        """Detect file type from filename and MIME type."""
        ext = Path(filename).suffix.lower()

        # Images
        if mime_type.startswith("image/") or ext in [
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
        ]:
            return FileType.IMAGE

        # PDFs
        if mime_type == "application/pdf" or ext == ".pdf":
            return FileType.PDF

        # Documents
        if ext in [".doc", ".docx", ".txt", ".md", ".rtf", ".odt"]:
            return FileType.DOCUMENT

        # Spreadsheets
        if ext in [".xls", ".xlsx", ".csv", ".ods"]:
            return FileType.SPREADSHEET

        # Presentations
        if ext in [".ppt", ".pptx", ".odp"]:
            return FileType.PRESENTATION

        # Code
        if ext in [
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".cpp",
            ".c",
            ".h",
        ]:
            return FileType.CODE

        return FileType.OTHER

    def register_upload(
        self,
        filename: str,
        path: str,
        size: int,
        mime_type: str,
        thumbnail: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> FileEntry:
        """
        Register an uploaded file.

        Args:
            filename: Original filename
            path: Path where file is stored (relative to workspace)
            size: File size in bytes
            mime_type: MIME type
            thumbnail: Base64 thumbnail (for images)
            metadata: Additional metadata

        Returns:
            FileEntry for the registered file

        Raises:
            ValueError: If file limits exceeded
        """
        # Check limits
        if len(self.files) >= self.MAX_FILES_PER_SESSION:
            raise ValueError(
                f"Maximum files per session ({self.MAX_FILES_PER_SESSION}) exceeded"
            )

        if size > self.MAX_FILE_SIZE:
            raise ValueError(
                f"File too large ({size / 1024 / 1024:.1f} MB). "
                f"Maximum: {self.MAX_FILE_SIZE / 1024 / 1024:.0f} MB"
            )

        total_size = sum(f.size for f in self.files.values()) + size
        if total_size > self.MAX_SESSION_STORAGE:
            raise ValueError(
                f"Session storage limit ({self.MAX_SESSION_STORAGE / 1024 / 1024:.0f} MB) exceeded"
            )

        ref = self._generate_ref(filename)
        file_type = self._detect_file_type(filename, mime_type)

        entry = FileEntry(
            ref=ref,
            source=FileSource.UPLOAD,
            path=path,
            size=size,
            file_type=file_type,
            mime_type=mime_type,
            uploaded_at=datetime.now().isoformat(),
            thumbnail=thumbnail,
            metadata=metadata or {},
        )

        self.files[ref] = entry
        self._save()

        return entry

    def register_remote(
        self,
        source: FileSource,
        remote_path: str,
        filename: str,
        size: int,
        mime_type: str,
        metadata: Optional[dict] = None,
    ) -> FileEntry:
        """
        Register a remote file (OneDrive, Dropbox, etc.)

        Args:
            source: File source (onedrive, dropbox, etc.)
            remote_path: Path in remote storage
            filename: Display filename
            size: File size in bytes
            mime_type: MIME type
            metadata: Additional metadata (e.g., share links)

        Returns:
            FileEntry for the registered file
        """
        if len(self.files) >= self.MAX_FILES_PER_SESSION:
            raise ValueError(
                f"Maximum files per session ({self.MAX_FILES_PER_SESSION}) exceeded"
            )

        ref = self._generate_ref(filename)
        file_type = self._detect_file_type(filename, mime_type)

        entry = FileEntry(
            ref=ref,
            source=source,
            path=remote_path,
            size=size,
            file_type=file_type,
            mime_type=mime_type,
            uploaded_at=datetime.now().isoformat(),
            metadata=metadata or {},
        )

        self.files[ref] = entry
        self._save()

        return entry

    def unregister(self, ref: str) -> bool:
        """
        Remove a file from the registry.

        Args:
            ref: File reference (e.g., "report.pdf")

        Returns:
            True if file was removed, False if not found
        """
        clean_ref = ref.lstrip("@")
        if clean_ref in self.files:
            del self.files[clean_ref]
            self._save()
            return True
        return False

    def resolve(self, ref: str) -> Optional[FileEntry]:
        """
        Resolve a file reference to its entry.

        Handles formats:
        - @report.pdf -> lookup "report.pdf"
        - @upload:report.pdf -> lookup "report.pdf" with source=upload
        - @onedrive:/path/to/file.xlsx -> lookup by path

        Args:
            ref: File reference string

        Returns:
            FileEntry if found, None otherwise
        """
        clean_ref = ref.lstrip("@")

        # Handle source:path format
        if ":" in clean_ref:
            source_str, path = clean_ref.split(":", 1)
            try:
                source = FileSource(source_str)
                # Find by source and path
                for entry in self.files.values():
                    if entry.source == source and (
                        entry.path == path or entry.ref == path.lstrip("/")
                    ):
                        return entry
            except ValueError:
                pass  # Invalid source, fall through to direct lookup

        # Direct lookup by ref
        return self.files.get(clean_ref)

    def extract_refs(self, text: str) -> list[str]:
        """
        Extract all @file references from text.

        Args:
            text: Message text

        Returns:
            List of file references found (without @)
        """
        # Match @word.ext or @source:path patterns
        pattern = r"@([\w\-\.]+(?::[/\w\-\.]+)?)"
        matches = re.findall(pattern, text)
        return matches

    def resolve_all(self, text: str) -> list[FileEntry]:
        """
        Extract and resolve all @file references from text.

        Args:
            text: Message text

        Returns:
            List of resolved FileEntry objects
        """
        refs = self.extract_refs(text)
        entries = []
        for ref in refs:
            entry = self.resolve(ref)
            if entry:
                entries.append(entry)
        return entries

    def get_context(self) -> str:
        """
        Generate markdown context for Claude system prompt.

        Returns:
            Markdown string listing available files
        """
        if not self.files:
            return ""

        lines = [
            "## Available Files",
            "",
            "Reference files with `@filename` in your message.",
            "",
        ]

        for ref, entry in self.files.items():
            source_label = (
                f" ({entry.source.value})"
                if entry.source != FileSource.UPLOAD
                else ""
            )
            lines.append(
                f"- `@{ref}` - {entry.file_type.value}, {entry.size_human}{source_label}"
            )

        lines.append("")
        return "\n".join(lines)

    def get_all(self) -> list[FileEntry]:
        """Get all registered files."""
        return list(self.files.values())

    def get_by_type(self, file_type: FileType) -> list[FileEntry]:
        """Get files of a specific type."""
        return [f for f in self.files.values() if f.file_type == file_type]

    def get_total_size(self) -> int:
        """Get total size of all files in bytes."""
        return sum(f.size for f in self.files.values())

    def clear(self) -> None:
        """Remove all files from registry."""
        self.files = {}
        self._save()

    def to_json(self) -> list[dict]:
        """Export all files as JSON-serializable list."""
        return [entry.to_dict() for entry in self.files.values()]
