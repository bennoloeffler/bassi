"""
Unit tests for SessionWorkspace class.
"""

import asyncio
import json
import re
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
    async def test_deduplicate_cleans_temp_files(
        self, temp_workspace, mock_upload_file
    ):
        """Should remove temporary upload artifacts after deduplication."""
        content = b"Same content for dedup"

        first = mock_upload_file("first.txt", content)
        await temp_workspace.upload_file(first)

        duplicate = mock_upload_file("duplicate.txt", content)
        await temp_workspace.upload_file(duplicate)

        data_dir = temp_workspace.physical_path / "DATA_FROM_USER"
        temp_files = [
            path
            for path in data_dir.iterdir()
            if path.is_file() and path.name.startswith(".tmp_")
        ]

        assert temp_files == []

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

    @pytest.mark.asyncio
    async def test_concurrent_uploads_are_serialized(
        self, temp_workspace, mock_upload_file
    ):
        """Should handle concurrent uploads without clobbering metadata."""

        async def upload(idx: int):
            upload_file = mock_upload_file(
                f"parallel_{idx}.txt", f"content-{idx}".encode()
            )
            return await temp_workspace.upload_file(upload_file)

        results = await asyncio.gather(
            *(upload(i) for i in range(5)), return_exceptions=False
        )

        assert len(results) == 5
        assert len({path.name for path in results}) == 5
        assert temp_workspace.metadata["file_count"] == 5

        data_dir = temp_workspace.physical_path / "DATA_FROM_USER"
        created_files = [
            path for path in data_dir.iterdir() if path.is_file()
        ]
        assert len(created_files) == 5


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

    def test_list_files_skips_directories(self, temp_workspace):
        """Should not include directories when listing files."""
        data_dir = temp_workspace.physical_path / "DATA_FROM_USER"
        (data_dir / "keep.txt").write_text("ok", encoding="utf-8")
        (data_dir / "nested").mkdir()
        (data_dir / "nested" / "ignored.txt").write_text(
            "ignore", encoding="utf-8"
        )

        files = temp_workspace.list_files()

        assert [entry["name"] for entry in files] == ["keep.txt"]


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

    def test_update_display_name_keeps_symlink_synced(
        self, tmp_path, monkeypatch
    ):
        """Should update symlink path and metadata together across renames."""
        monkeypatch.chdir(tmp_path)
        workspace = SessionWorkspace("sync-session", base_path=tmp_path)

        initial_symlink = workspace.metadata["symlink_name"]
        assert (
            workspace.SYMLINK_DIR / initial_symlink
        ).exists(), "Initial symlink missing"

        workspace.update_display_name("First Rename")
        first_symlink = workspace.metadata["symlink_name"]
        assert (
            workspace.SYMLINK_DIR / first_symlink
        ).exists(), "First rename symlink missing"
        assert not (
            workspace.SYMLINK_DIR / initial_symlink
        ).exists(), "Old symlink should be removed"

        workspace.update_display_name("Second Rename")
        second_symlink = workspace.metadata["symlink_name"]
        assert (
            workspace.SYMLINK_DIR / second_symlink
        ).exists(), "Second rename symlink missing"
        assert not (
            workspace.SYMLINK_DIR / first_symlink
        ).exists(), "First rename symlink should be removed"


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


class TestWorkspaceContext:
    """Test workspace context generation for agent awareness."""

    def test_generates_workspace_context(self, temp_workspace):
        """Should generate markdown workspace context."""
        context = temp_workspace.get_workspace_context()

        assert isinstance(context, str)
        assert "# Your Workspace" in context
        assert temp_workspace.session_id in context
        assert "DATA_FROM_USER" in context
        assert "RESULTS_FROM_AGENT" in context
        assert "SCRIPTS_FROM_AGENT" in context
        assert "DATA_FROM_AGENT" in context

    def test_workspace_context_includes_instructions(self, temp_workspace):
        """Should include file path instructions."""
        context = temp_workspace.get_workspace_context()

        assert "## File Path Instructions" in context
        assert f"chats/{temp_workspace.session_id}/" in context

    @pytest.mark.asyncio
    async def test_workspace_context_lists_uploaded_files(
        self, temp_workspace, mock_upload_file
    ):
        """Should list uploaded files in workspace context."""
        # Upload a file
        file = mock_upload_file("test.txt", b"content")
        await temp_workspace.upload_file(file)

        context = temp_workspace.get_workspace_context()

        assert "## Available Files" in context
        assert "test_" in context  # File will have hash in name

    @pytest.mark.asyncio
    async def test_workspace_context_includes_file_sizes(
        self, temp_workspace, mock_upload_file
    ):
        """Should show file size in KB for uploaded files."""
        file = mock_upload_file("data.csv", b"x" * 2048)  # 2 KB
        await temp_workspace.upload_file(file)

        context = temp_workspace.get_workspace_context()

        assert "(2.0 KB)" in context

    def test_workspace_context_shows_no_files_message(self, temp_workspace):
        """Should show message when no files are uploaded."""
        context = temp_workspace.get_workspace_context()

        assert "No files have been uploaded yet" in context

    def test_get_output_path_results(self, temp_workspace):
        """Should generate correct path for results category."""
        path = temp_workspace.get_output_path("results", "report.pdf")

        assert "RESULTS_FROM_AGENT" in path
        assert "report.pdf" in path
        assert temp_workspace.session_id in path

    def test_get_output_path_scripts(self, temp_workspace):
        """Should generate correct path for scripts category."""
        path = temp_workspace.get_output_path("scripts", "analyze.py")

        assert "SCRIPTS_FROM_AGENT" in path
        assert "analyze.py" in path

    def test_get_output_path_data(self, temp_workspace):
        """Should generate correct path for data category."""
        path = temp_workspace.get_output_path("data", "output.json")

        assert "DATA_FROM_AGENT" in path
        assert "output.json" in path

    def test_get_output_path_rejects_invalid_category(self, temp_workspace):
        """Should raise error for invalid category."""
        with pytest.raises(ValueError, match="Invalid category"):
            temp_workspace.get_output_path("invalid", "file.txt")


class TestSymlinkEdgeCases:
    """Test edge cases in symlink management."""

    def test_empty_sanitized_name_fallback(self, tmp_path):
        """Should use 'unnamed-session' when sanitized name is empty."""
        session_id = "test-session-456"
        workspace = SessionWorkspace(session_id, base_path=tmp_path)

        # Update symlink with name that sanitizes to empty (special chars only)
        workspace.update_symlink("!!!")

        # Check that "unnamed-session" was used
        symlink_name = workspace.metadata["symlink_name"]
        assert "unnamed-session" in symlink_name

    def test_symlink_safety_limit_exceeded(self, tmp_path, monkeypatch):
        """Should raise error when symlink collision exceeds 100 attempts."""
        import os

        session_id = "test-session-789"
        workspace = SessionWorkspace(session_id, base_path=tmp_path)

        # Mock os.symlink to always raise FileExistsError
        original_symlink = os.symlink

        def mock_symlink(src, dst):
            # Simulate persistent collision
            raise FileExistsError(f"Symlink exists: {dst}")

        monkeypatch.setattr(os, "symlink", mock_symlink)

        # Should raise ValueError after 100+ attempts
        with pytest.raises(
            ValueError, match="Could not create unique symlink"
        ):
            workspace.update_symlink("test-name")

    def test_symlink_name_truncates_long_titles(self, tmp_path):
        """Should truncate sanitized portion of symlink to 50 characters."""
        session_id = "test-session-long-name"
        workspace = SessionWorkspace(session_id, base_path=tmp_path)

        long_name = "VeryLongSessionNameWithManyCharacters_" * 3
        workspace.update_symlink(long_name)

        symlink_name = workspace.metadata["symlink_name"]
        parts = symlink_name.split("__")

        assert len(parts) >= 3  # timestamp, clean name, short id
        clean_name = parts[1]
        expected = long_name.lower().replace(" ", "-").replace("_", "-")
        expected = re.sub(r"[^a-z0-9-]", "", expected)
        expected = re.sub(r"-+", "-", expected).strip("-")[:50]

        assert len(clean_name) == 50
        assert clean_name == expected


class TestFileListingEdgeCases:
    """Test edge cases in file listing."""

    def test_list_files_when_directory_deleted(self, tmp_path):
        """Should return empty list when DATA_FROM_USER directory is deleted."""
        import shutil

        session_id = "test-session-999"
        workspace = SessionWorkspace(session_id, base_path=tmp_path)

        # Delete DATA_FROM_USER directory
        data_dir = workspace.physical_path / "DATA_FROM_USER"
        shutil.rmtree(data_dir)

        # Should return empty list without raising error
        files = workspace.list_files()
        assert files == []


class TestSymlinkRetryPath:
    """Test symlink collision retry success path."""

    def test_symlink_collision_retry_succeeds(self, tmp_path, monkeypatch):
        """Should succeed on retry when first attempt collides."""
        import os

        session_id = "test-session-retry"
        workspace = SessionWorkspace(session_id, base_path=tmp_path)

        original_symlink = os.symlink
        call_count = [0]

        def mock_symlink_fail_once(src, dst):
            """Fail on first call, succeed on second."""
            call_count[0] += 1
            if call_count[0] == 1:
                # First call fails (simulate collision)
                raise FileExistsError(f"Symlink exists: {dst}")
            else:
                # Second call succeeds
                return original_symlink(src, dst)

        monkeypatch.setattr(os, "symlink", mock_symlink_fail_once)

        # Should succeed on retry
        workspace.update_symlink("collision-test")
        assert "collision-test" in workspace.metadata["symlink_name"]


class TestSymlinkRemoval:
    """Test symlink removal edge cases."""

    def test_remove_nonexistent_symlink(self, tmp_path):
        """Should handle FileNotFoundError gracefully when symlink doesn't exist."""
        session_id = "test-session-nolink"
        workspace = SessionWorkspace(session_id, base_path=tmp_path)

        # Get the initial symlink name that was created
        initial_symlink = workspace.metadata["symlink_name"]

        # Delete the symlink file manually to simulate missing symlink
        symlink_path = workspace.SYMLINK_DIR / initial_symlink
        if symlink_path.exists():
            symlink_path.unlink()

        # Should not raise error when removing already-deleted symlink
        workspace._remove_symlink()

        # Test passes if no exception was raised
        assert True


class TestSessionDeletion:
    """Test session deletion functionality."""

    def test_delete_removes_session(self, tmp_path, monkeypatch):
        """Should delete entire session directory and symlink."""
        # Change to tmp_path so symlinks are created there
        monkeypatch.chdir(tmp_path)

        session_id = "test-session-delete"
        workspace = SessionWorkspace(session_id, base_path=tmp_path)

        # Create a symlink
        workspace.update_symlink("to-be-deleted")

        # Verify workspace exists
        assert workspace.physical_path.exists()
        symlink_path = (
            workspace.SYMLINK_DIR / workspace.metadata["symlink_name"]
        )
        assert symlink_path.exists()

        # Delete workspace
        workspace.delete()

        # Verify physical directory is deleted
        assert not workspace.physical_path.exists()

        # Verify symlink is removed
        assert not symlink_path.exists()
