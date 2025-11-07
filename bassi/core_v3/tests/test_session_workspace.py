"""
Unit tests for SessionWorkspace class.
"""

import json
from io import BytesIO

import pytest
from fastapi import UploadFile

from bassi.core_v3.session_workspace import SessionWorkspace


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace for testing."""
    session_id = "test-session-123"
    workspace = SessionWorkspace(session_id, base_path=tmp_path, create=True)
    return workspace


@pytest.fixture
def mock_upload_file():
    """Create mock UploadFile for testing."""

    def _create_file(filename: str, content: bytes):
        file_obj = BytesIO(content)
        upload_file = UploadFile(filename=filename, file=file_obj)
        return upload_file

    return _create_file


class TestSessionWorkspaceInitialization:
    """Test workspace initialization and directory structure."""

    def test_creates_directory_structure(self, tmp_path):
        """Should create all required subdirectories."""
        session_id = "test-123"
        workspace = SessionWorkspace(session_id, base_path=tmp_path)

        assert workspace.physical_path.exists()
        assert (workspace.physical_path / "DATA_FROM_USER").exists()
        assert (workspace.physical_path / "RESULTS_FROM_AGENT").exists()
        assert (workspace.physical_path / "SCRIPTS_FROM_AGENT").exists()
        assert (workspace.physical_path / "DATA_FROM_AGENT").exists()

    def test_creates_metadata_file(self, tmp_path):
        """Should create session.json with metadata."""
        session_id = "test-123"
        workspace = SessionWorkspace(session_id, base_path=tmp_path)

        metadata_path = workspace.physical_path / "session.json"
        assert metadata_path.exists()

        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        assert metadata["session_id"] == session_id
        assert "display_name" in metadata
        assert "created_at" in metadata
        assert metadata["state"] == "CREATED"

    def test_loads_existing_metadata(self, tmp_path):
        """Should load metadata from existing session.json."""
        session_id = "test-123"

        # Create workspace and modify metadata
        workspace1 = SessionWorkspace(session_id, base_path=tmp_path)
        workspace1.update_display_name("Custom Name")

        # Load same workspace
        workspace2 = SessionWorkspace(
            session_id, base_path=tmp_path, create=False
        )

        assert workspace2.display_name == "Custom Name"


class TestFileUpload:
    """Test file upload functionality."""

    @pytest.mark.asyncio
    async def test_uploads_file(self, temp_workspace, mock_upload_file):
        """Should upload file to DATA_FROM_USER/."""
        content = b"Test file content"
        upload_file = mock_upload_file("test.txt", content)

        file_path = await temp_workspace.upload_file(upload_file)

        assert file_path.exists()
        assert file_path.parent.name == "DATA_FROM_USER"
        assert file_path.read_bytes() == content

    @pytest.mark.asyncio
    async def test_generates_unique_filename_with_hash(
        self, temp_workspace, mock_upload_file
    ):
        """Should generate filename with hash suffix."""
        content = b"Test content"
        upload_file = mock_upload_file("report.pdf", content)

        file_path = await temp_workspace.upload_file(upload_file)

        # Filename should be: report_{hash}.pdf
        assert file_path.stem.startswith("report_")
        assert file_path.suffix == ".pdf"
        assert len(file_path.stem) > len("report_")  # Has hash

    @pytest.mark.asyncio
    async def test_deduplicates_identical_files(
        self, temp_workspace, mock_upload_file
    ):
        """Should return existing file if hash matches."""
        content = b"Identical content"

        # Upload first file
        file1 = mock_upload_file("file1.txt", content)
        path1 = await temp_workspace.upload_file(file1)

        # Upload identical file with different name
        file2 = mock_upload_file("file2.txt", content)
        path2 = await temp_workspace.upload_file(file2)

        # Should return same path (deduplication)
        assert path1 == path2
        assert temp_workspace.metadata["file_count"] == 1

    @pytest.mark.asyncio
    async def test_handles_large_files_with_streaming(
        self, temp_workspace, mock_upload_file
    ):
        """Should stream large files in chunks."""
        # Create 1MB file
        large_content = b"x" * (1024 * 1024)
        upload_file = mock_upload_file("large.bin", large_content)

        file_path = await temp_workspace.upload_file(upload_file)

        assert file_path.exists()
        assert file_path.stat().st_size == len(large_content)

    @pytest.mark.asyncio
    async def test_rejects_files_exceeding_size_limit(
        self, temp_workspace, mock_upload_file
    ):
        """Should raise error for files > MAX_FILE_SIZE."""
        # Create file larger than 100MB limit
        too_large = b"x" * (101 * 1024 * 1024)
        upload_file = mock_upload_file("huge.bin", too_large)

        with pytest.raises(ValueError, match="File too large"):
            await temp_workspace.upload_file(upload_file)

    @pytest.mark.asyncio
    async def test_updates_file_count_metadata(
        self, temp_workspace, mock_upload_file
    ):
        """Should increment file_count in metadata."""
        initial_count = temp_workspace.metadata["file_count"]

        file1 = mock_upload_file("file1.txt", b"content1")
        await temp_workspace.upload_file(file1)

        assert temp_workspace.metadata["file_count"] == initial_count + 1


class TestFileManagement:
    """Test file listing and management."""

    @pytest.mark.asyncio
    async def test_lists_uploaded_files(
        self, temp_workspace, mock_upload_file
    ):
        """Should list all files in DATA_FROM_USER/."""
        # Upload multiple files
        file1 = mock_upload_file("report.pdf", b"pdf content")
        file2 = mock_upload_file("data.csv", b"csv content")

        await temp_workspace.upload_file(file1)
        await temp_workspace.upload_file(file2)

        files = temp_workspace.list_files()

        assert len(files) == 2
        assert all("name" in f for f in files)
        assert all("size" in f for f in files)
        assert all("uploaded_at" in f for f in files)

    def test_returns_empty_list_when_no_files(self, temp_workspace):
        """Should return empty list if no files uploaded."""
        files = temp_workspace.list_files()
        assert files == []


class TestMessageHistory:
    """Test conversation history management."""

    def test_saves_message_to_history(self, temp_workspace):
        """Should append message to history.md."""
        temp_workspace.save_message("user", "Hello, assistant!")

        history_path = temp_workspace.physical_path / "history.md"
        assert history_path.exists()

        content = history_path.read_text()
        assert "Hello, assistant!" in content
        assert "## User" in content

    def test_creates_history_file_on_first_message(self, temp_workspace):
        """Should create history.md with header on first message."""
        temp_workspace.save_message("user", "First message")

        history_path = temp_workspace.physical_path / "history.md"
        content = history_path.read_text()

        assert content.startswith("# Chat History:")
        assert "First message" in content

    def test_increments_message_count(self, temp_workspace):
        """Should increment message_count in metadata."""
        initial_count = temp_workspace.metadata["message_count"]

        temp_workspace.save_message("user", "Message 1")
        temp_workspace.save_message("assistant", "Message 2")

        assert temp_workspace.metadata["message_count"] == initial_count + 2


class TestDisplayName:
    """Test display name management."""

    def test_default_display_name(self, tmp_path):
        """Should use session_id prefix as default display name."""
        session_id = "abc123def456"
        workspace = SessionWorkspace(session_id, base_path=tmp_path)

        assert "abc123de" in workspace.display_name.lower()

    def test_updates_display_name(self, temp_workspace):
        """Should update display name in metadata."""
        new_name = "My Custom Session Name"
        temp_workspace.update_display_name(new_name)

        assert temp_workspace.display_name == new_name

        # Verify persisted to file
        metadata_path = temp_workspace.physical_path / "session.json"
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        assert metadata["display_name"] == new_name


class TestSessionState:
    """Test session state management."""

    def test_initial_state_is_created(self, temp_workspace):
        """Should initialize with CREATED state."""
        assert temp_workspace.state == "CREATED"

    def test_updates_state(self, temp_workspace):
        """Should update state to valid values."""
        temp_workspace.update_state("AUTO_NAMED")
        assert temp_workspace.state == "AUTO_NAMED"

        temp_workspace.update_state("FINALIZED")
        assert temp_workspace.state == "FINALIZED"

    def test_rejects_invalid_state(self, temp_workspace):
        """Should raise error for invalid state values."""
        with pytest.raises(ValueError, match="Invalid state"):
            temp_workspace.update_state("INVALID_STATE")


class TestSessionStats:
    """Test session statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self, temp_workspace, mock_upload_file):
        """Should return comprehensive session statistics."""
        # Upload file and save message
        file = mock_upload_file("test.txt", b"content")
        await temp_workspace.upload_file(file)
        temp_workspace.save_message("user", "Hello")

        stats = temp_workspace.get_stats()

        assert stats["session_id"] == temp_workspace.session_id
        assert stats["display_name"] == temp_workspace.display_name
        assert stats["state"] == "CREATED"
        assert stats["file_count"] == 1
        assert stats["message_count"] == 1
        assert "created_at" in stats
        assert "last_activity" in stats


class TestSessionLoading:
    """Test loading existing sessions."""

    def test_loads_existing_session(self, tmp_path):
        """Should load existing workspace without recreating."""
        session_id = "existing-session"

        # Create workspace
        workspace1 = SessionWorkspace(session_id, base_path=tmp_path)
        workspace1.update_display_name("Original Name")

        # Load same workspace
        workspace2 = SessionWorkspace.load(session_id, base_path=tmp_path)

        assert workspace2.session_id == session_id
        assert workspace2.display_name == "Original Name"

    def test_raises_error_if_session_not_found(self, tmp_path):
        """Should raise FileNotFoundError for non-existent session."""
        with pytest.raises(FileNotFoundError, match="Session not found"):
            SessionWorkspace.load("nonexistent-session", base_path=tmp_path)

    def test_checks_session_existence(self, tmp_path):
        """Should correctly check if session exists."""
        session_id = "test-session"

        # Should not exist initially
        assert not SessionWorkspace.exists(session_id, base_path=tmp_path)

        # Create workspace
        SessionWorkspace(session_id, base_path=tmp_path)

        # Should exist now
        assert SessionWorkspace.exists(session_id, base_path=tmp_path)
