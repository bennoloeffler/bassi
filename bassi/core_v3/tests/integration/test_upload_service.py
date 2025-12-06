"""
Unit tests for UploadService class.
"""

from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi import UploadFile

from bassi.core_v3.session_workspace import SessionWorkspace
from bassi.core_v3.upload_service import (
    FileTooLargeError,
    InvalidFilenameError,
    UploadService,
)


@pytest.fixture
def upload_service():
    """Create UploadService instance for testing."""
    return UploadService()


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace for testing."""
    session_id = "test-upload-session"
    workspace = SessionWorkspace(session_id, base_path=tmp_path, create=True)
    return workspace


@pytest.fixture
def mock_upload_file():
    """Create mock UploadFile for testing."""

    def _create_file(filename: str, content: bytes, size: int = None):
        file_obj = BytesIO(content)
        upload_file = UploadFile(filename=filename, file=file_obj)
        if size is not None:
            upload_file.size = size
        return upload_file

    return _create_file


class TestFileValidation:
    """Test file validation logic."""

    def test_validates_empty_filename(self, upload_service, mock_upload_file):
        """Should reject files with empty filename."""
        file = mock_upload_file("", b"content")

        with pytest.raises(InvalidFilenameError, match="Filename is empty"):
            upload_service.validate_file(file)

    def test_validates_path_separators(
        self, upload_service, mock_upload_file
    ):
        """Should reject filenames with path separators."""
        # Test forward slash
        file1 = mock_upload_file("../etc/passwd", b"content")
        with pytest.raises(InvalidFilenameError, match="path separators"):
            upload_service.validate_file(file1)

        # Test backslash
        file2 = mock_upload_file("..\\windows\\system32", b"content")
        with pytest.raises(InvalidFilenameError, match="path separators"):
            upload_service.validate_file(file2)

    def test_validates_null_bytes(self, upload_service, mock_upload_file):
        """Should reject filenames with null bytes."""
        file = mock_upload_file("test\0file.txt", b"content")

        with pytest.raises(InvalidFilenameError, match="null bytes"):
            upload_service.validate_file(file)

    def test_blocks_dangerous_extensions(
        self, upload_service, mock_upload_file
    ):
        """Should block security-sensitive file extensions."""
        dangerous_files = [
            "malware.exe",
            "virus.dll",
            "trojan.so",
            "library.dylib",
            "script.bat",
            "command.cmd",
            "exploit.sh",
        ]

        for filename in dangerous_files:
            file = mock_upload_file(filename, b"content")
            with pytest.raises(
                InvalidFilenameError, match="blocked for security"
            ):
                upload_service.validate_file(file)

    def test_allows_safe_extensions(self, upload_service, mock_upload_file):
        """Should allow safe file extensions."""
        safe_files = [
            "document.pdf",
            "report.docx",
            "data.csv",
            "image.png",
            "video.mp4",
            "archive.zip",
            "code.py",
            "notebook.ipynb",
        ]

        for filename in safe_files:
            file = mock_upload_file(filename, b"content")
            # Should not raise
            upload_service.validate_file(file)

    def test_validates_file_size_when_available(
        self, upload_service, mock_upload_file
    ):
        """Should validate file size if size attribute is set."""
        # File exactly at limit (should pass)
        file1 = mock_upload_file(
            "large.bin", b"x" * 1000, size=100 * 1024 * 1024  # 100 MB
        )
        upload_service.validate_file(file1)  # Should not raise

        # File over limit (should fail)
        file2 = mock_upload_file(
            "huge.bin", b"x" * 1000, size=101 * 1024 * 1024  # 101 MB
        )
        with pytest.raises(FileTooLargeError):
            upload_service.validate_file(file2)

    def test_custom_max_file_size(self, mock_upload_file):
        """Should respect custom max file size."""
        # 10 MB limit
        service = UploadService(max_file_size=10 * 1024 * 1024)

        file = mock_upload_file(
            "file.bin", b"x" * 1000, size=11 * 1024 * 1024
        )

        with pytest.raises(FileTooLargeError) as exc_info:
            service.validate_file(file)

        assert exc_info.value.size == 11 * 1024 * 1024
        assert exc_info.value.max_size == 10 * 1024 * 1024

    def test_custom_allowed_extensions(self, mock_upload_file):
        """Should respect custom allowed extensions list."""
        service = UploadService(allowed_extensions=[".pdf", ".docx"])

        # Allowed extension (should pass)
        file1 = mock_upload_file("report.pdf", b"content")
        service.validate_file(file1)  # Should not raise

        # Not in allowed list (should fail)
        file2 = mock_upload_file("data.csv", b"content")
        with pytest.raises(InvalidFilenameError, match="not in allowed list"):
            service.validate_file(file2)


class TestFileUpload:
    """Test file upload functionality."""

    @pytest.mark.asyncio
    async def test_uploads_valid_file(
        self, upload_service, temp_workspace, mock_upload_file
    ):
        """Should successfully upload valid file."""
        content = b"Test file content"
        file = mock_upload_file("test.txt", content)

        file_path, _file_entry = await upload_service.upload_to_session(
            file, temp_workspace
        )

        assert file_path.exists()
        assert file_path.parent.name == "DATA_FROM_USER"
        assert file_path.read_bytes() == content

    @pytest.mark.asyncio
    async def test_rejects_invalid_file(
        self, upload_service, temp_workspace, mock_upload_file
    ):
        """Should reject invalid files during upload."""
        file = mock_upload_file("malware.exe", b"virus content")

        with pytest.raises(InvalidFilenameError):
            await upload_service.upload_to_session(file, temp_workspace)

    @pytest.mark.asyncio
    async def test_handles_workspace_errors(
        self, upload_service, temp_workspace, mock_upload_file
    ):
        """Should propagate workspace errors properly."""
        file = mock_upload_file("test.txt", b"content")

        # Mock workspace.upload_file to raise error
        with patch.object(
            temp_workspace, "upload_file", side_effect=OSError("Disk full")
        ):
            with pytest.raises(OSError, match="Disk full"):
                await upload_service.upload_to_session(file, temp_workspace)

    @pytest.mark.asyncio
    async def test_logs_successful_upload(
        self, upload_service, temp_workspace, mock_upload_file
    ):
        """Should log successful uploads."""
        file = mock_upload_file("report.pdf", b"pdf content")

        with patch("bassi.core_v3.upload_service.logger") as mock_logger:
            file_path, _file_entry = await upload_service.upload_to_session(
                file, temp_workspace
            )

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "report.pdf" in call_args
            assert str(file_path) in call_args

    @pytest.mark.asyncio
    async def test_logs_failed_upload(
        self, upload_service, temp_workspace, mock_upload_file
    ):
        """Should log failed uploads."""
        file = mock_upload_file("test.txt", b"content")

        with patch.object(
            temp_workspace, "upload_file", side_effect=OSError("Disk error")
        ):
            with patch("bassi.core_v3.upload_service.logger") as mock_logger:
                with pytest.raises(OSError):
                    await upload_service.upload_to_session(
                        file, temp_workspace
                    )

                mock_logger.error.assert_called_once()
                call_args = mock_logger.error.call_args[0][0]
                assert "test.txt" in call_args


class TestUploadInfo:
    """Test upload info retrieval."""

    @pytest.mark.asyncio
    async def test_gets_upload_info(
        self, upload_service, temp_workspace, mock_upload_file
    ):
        """Should return file info for uploaded file."""
        content = b"Test content"
        file = mock_upload_file("document.pdf", content)

        file_path, _file_entry = await upload_service.upload_to_session(
            file, temp_workspace
        )

        info = upload_service.get_upload_info(file_path, temp_workspace)

        assert "name" in info
        assert "size" in info
        assert "path" in info
        assert "absolute_path" in info

        assert info["size"] == len(content)
        assert info["name"] == file_path.name
        assert info["absolute_path"] == str(file_path)

    @pytest.mark.asyncio
    async def test_upload_info_relative_path(
        self, upload_service, temp_workspace, mock_upload_file
    ):
        """Should return path relative to workspace."""
        file = mock_upload_file("test.txt", b"content")

        file_path, _file_entry = await upload_service.upload_to_session(
            file, temp_workspace
        )
        info = upload_service.get_upload_info(file_path, temp_workspace)

        # Path should be relative to workspace root
        assert info["path"].startswith("DATA_FROM_USER/")
        assert not info["path"].startswith("/")


class TestExceptionDetails:
    """Test custom exception classes."""

    def test_file_too_large_error_message(self):
        """Should format size error message correctly."""
        error = FileTooLargeError(
            size=150 * 1024 * 1024,  # 150 MB
            max_size=100 * 1024 * 1024,  # 100 MB
        )

        message = str(error)
        assert "150.0 MB" in message
        assert "100.0 MB" in message
        assert error.size == 150 * 1024 * 1024
        assert error.max_size == 100 * 1024 * 1024

    def test_invalid_filename_error_message(self):
        """Should format filename error message correctly."""
        error = InvalidFilenameError(
            "../etc/passwd", "Contains path separators"
        )

        message = str(error)
        assert "../etc/passwd" in message
        assert "Contains path separators" in message
        assert error.filename == "../etc/passwd"
        assert error.reason == "Contains path separators"
