"""
Upload Service - Black Box Component

Handles file uploads to session workspaces with validation and error handling.

Responsibilities:
- Validate file uploads (size, type, name)
- Save files to session workspaces
- Handle upload errors gracefully
- Provide clean interface to web server

This is a Black Box component: implementation details are hidden,
only the public interface matters.
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from bassi.core_v3.session_workspace import SessionWorkspace

logger = logging.getLogger(__name__)


class FileTooLargeError(ValueError):
    """Raised when uploaded file exceeds size limit."""

    def __init__(self, size: int, max_size: int):
        self.size = size
        self.max_size = max_size
        super().__init__(
            f"File too large: {size / 1024 / 1024:.1f} MB "
            f"(max {max_size / 1024 / 1024:.1f} MB)"
        )


class InvalidFilenameError(ValueError):
    """Raised when filename contains invalid characters."""

    def __init__(self, filename: str, reason: str):
        self.filename = filename
        self.reason = reason
        super().__init__(f"Invalid filename '{filename}': {reason}")


class UploadService:
    """
    Black Box: File Upload Service

    Public Interface:
    - upload_to_session(file, workspace) -> Path
    - validate_file(file) -> None (raises on invalid)

    Hidden Implementation:
    - File validation logic
    - Error handling details
    - Upload mechanics
    """

    # Configuration
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    ALLOWED_EXTENSIONS = None  # None = allow all

    # Blocked extensions for security
    BLOCKED_EXTENSIONS = [
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bat",
        ".cmd",
        ".sh",
    ]

    def __init__(
        self,
        max_file_size: Optional[int] = None,
        allowed_extensions: Optional[list[str]] = None,
    ):
        """
        Initialize upload service.

        Args:
            max_file_size: Maximum file size in bytes (default: 100 MB)
            allowed_extensions: List of allowed extensions (default: all except blocked)
        """
        self.max_file_size = (
            max_file_size if max_file_size is not None else self.MAX_FILE_SIZE
        )
        self.allowed_extensions = allowed_extensions

    async def upload_to_session(
        self, file: UploadFile, workspace: SessionWorkspace
    ) -> Path:
        """
        Upload file to session workspace.

        This is the main public interface method.

        Args:
            file: FastAPI UploadFile object
            workspace: SessionWorkspace to upload to

        Returns:
            Path to uploaded file

        Raises:
            FileTooLargeError: File exceeds size limit
            InvalidFilenameError: Filename is invalid
            Exception: Other upload errors
        """
        try:
            # Validate before upload
            self.validate_file(file)

            # Upload to workspace (handles deduplication, etc.)
            file_path = await workspace.upload_file(file)

            logger.info(
                f"File uploaded successfully: {file.filename} -> {file_path}"
            )

            return file_path

        except FileTooLargeError:
            raise  # Re-raise validation errors as-is

        except InvalidFilenameError:
            raise

        except Exception as e:
            logger.error(f"Upload failed for {file.filename}: {e}")
            raise

    def validate_file(self, file: UploadFile) -> None:
        """
        Validate file before upload.

        Args:
            file: UploadFile to validate

        Raises:
            FileTooLargeError: File exceeds size limit
            InvalidFilenameError: Filename is invalid
        """
        # Validate filename exists
        if not file.filename:
            raise InvalidFilenameError("", "Filename is empty")

        # Validate filename characters
        if any(char in file.filename for char in ["/", "\\", "\0"]):
            raise InvalidFilenameError(
                file.filename, "Contains path separators or null bytes"
            )

        # Validate file extension
        extension = Path(file.filename).suffix.lower()

        if extension in self.BLOCKED_EXTENSIONS:
            raise InvalidFilenameError(
                file.filename,
                f"Extension '{extension}' is blocked for security",
            )

        if self.allowed_extensions is not None:
            if extension not in self.allowed_extensions:
                raise InvalidFilenameError(
                    file.filename,
                    f"Extension '{extension}' not in allowed list: "
                    f"{self.allowed_extensions}",
                )

        # Validate file size (we'll check again during upload, but early check is good)
        if hasattr(file, "size") and file.size:
            if file.size > self.max_file_size:
                raise FileTooLargeError(file.size, self.max_file_size)

    def get_upload_info(
        self, file_path: Path, workspace: SessionWorkspace
    ) -> dict:
        """
        Get information about uploaded file.

        Args:
            file_path: Path to uploaded file
            workspace: SessionWorkspace containing file

        Returns:
            Dict with file info (name, size, path, etc.)
        """
        stat = file_path.stat()

        return {
            "name": file_path.name,
            "size": stat.st_size,
            "path": str(file_path.relative_to(workspace.physical_path)),
            "absolute_path": str(file_path),
        }
