"""
Concurrency and Race Condition Tests

Tests to verify thread safety and concurrent access handling:
- Concurrent message saving
- Concurrent file uploads
- Concurrent WebSocket connections
- Session index race conditions
- Workspace metadata race conditions

Based on documented requirements in:
- TEST_QUALITY_REPORT.md (line 40-42)
- session_management_test_specification.md (Test 1.6)
"""

import asyncio

import pytest

from bassi.core_v3.session_index import SessionIndex
from bassi.core_v3.session_workspace import SessionWorkspace


class TestConcurrentMessageSaving:
    """Test thread safety of message persistence."""

    @pytest.mark.asyncio
    async def test_concurrent_message_saving(self, tmp_path):
        """
        Verify message saving is thread-safe under concurrent load.

        Documented requirement: session_management_test_specification.md Test 1.6

        Corner cases tested:
        - High concurrency (10 messages)
        - Verify no lost messages
        - Verify no duplicate messages
        - Verify correct message count
        - Verify message order preserved (or at least all present)
        """
        workspace = SessionWorkspace(
            "test-concurrent", base_path=tmp_path, create=True
        )

        # Simulate 10 concurrent message saves
        async def save_message(i: int):
            await asyncio.sleep(0.01 * i)  # Stagger slightly
            workspace.save_message("user", f"Message {i}")

        # Run all saves concurrently
        tasks = [save_message(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify all messages saved
        assert (
            workspace.metadata["message_count"] == 10
        ), "Message count should be exactly 10"

        # Verify all messages in history
        history_content = (workspace.physical_path / "history.md").read_text()
        for i in range(10):
            assert (
                f"Message {i}" in history_content
            ), f"Message {i} should be in history"

        # Verify no duplicate counts
        message_lines = [
            line
            for line in history_content.split("\n")
            if "Message" in line and "Message" in line.split()[0]
        ]
        # Count actual message content lines
        message_count_in_file = history_content.count("Message ")
        assert (
            message_count_in_file == 10
        ), f"Should have exactly 10 messages, found {message_count_in_file}"

        # Verify metadata file is consistent
        import json

        metadata_file = workspace.physical_path / "chat.json"
        metadata_data = json.loads(metadata_file.read_text())
        assert (
            metadata_data["message_count"] == 10
        ), "Metadata file should match workspace metadata"

    @pytest.mark.asyncio
    async def test_concurrent_assistant_messages(self, tmp_path):
        """Test concurrent assistant message saving."""
        workspace = SessionWorkspace(
            "test-concurrent-assistant", base_path=tmp_path, create=True
        )

        # Save user message first
        workspace.save_message("user", "Hello")

        # Simulate concurrent assistant responses (shouldn't happen in practice, but test safety)
        async def save_assistant(i: int):
            workspace.save_message("assistant", f"Response {i}")

        tasks = [save_assistant(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # Verify all messages saved
        assert (
            workspace.metadata["message_count"] == 6
        )  # 1 user + 5 assistant

        history_content = (workspace.physical_path / "history.md").read_text()
        assert "Hello" in history_content
        for i in range(5):
            assert f"Response {i}" in history_content


class TestConcurrentFileUploads:
    """Test concurrent file upload handling."""

    @pytest.mark.asyncio
    async def test_concurrent_file_uploads(self, tmp_path):
        """
        Test multiple files uploaded concurrently to same session.

        Documented requirement: Concurrency testing
        """
        workspace = SessionWorkspace(
            "test-concurrent-upload", base_path=tmp_path, create=True
        )

        from io import BytesIO

        from fastapi import UploadFile

        async def upload_file(i: int):
            content = f"File {i} content".encode()
            file_obj = BytesIO(content)
            # Need to reset file pointer for each upload
            file_obj.seek(0)
            upload_file = UploadFile(filename=f"file_{i}.txt", file=file_obj)
            # Set size attribute
            upload_file.size = len(content)
            await workspace.upload_file(upload_file)

        # Upload 5 files concurrently
        tasks = [upload_file(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # Verify all files uploaded
        files = workspace.list_files()
        assert len(files) == 5, f"Expected 5 files, got {len(files)}"

        # Verify file count in metadata
        assert workspace.metadata["file_count"] == 5

        # Verify all files exist (check by listing, not by exact filename)
        # Files may have hash-based names
        uploaded_files = [f for f in files if f["name"].startswith("file_")]
        assert len(uploaded_files) == 5


class TestSessionIndexRaceConditions:
    """Test session index updates under concurrent load."""

    @pytest.mark.asyncio
    async def test_concurrent_session_index_updates(self, tmp_path):
        """
        Test session index updates are safe under concurrent access.

        Documented requirement: Race condition testing
        """
        index = SessionIndex(base_path=tmp_path)

        # Create multiple sessions concurrently
        async def create_and_update_session(i: int):
            session_id = f"session-{i}"
            workspace = SessionWorkspace(
                session_id, base_path=tmp_path, create=True
            )
            workspace.save_message("user", f"Message from session {i}")
            index.update_session(workspace)

        # Create 10 sessions concurrently
        tasks = [create_and_update_session(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify all sessions in index
        sessions = index.list_sessions()
        assert len(sessions) == 10

        # Verify index file is valid JSON
        index_file = tmp_path / ".index.json"
        assert index_file.exists()

        import json

        index_data = json.loads(index_file.read_text())
        assert len(index_data["sessions"]) == 10

        # Verify no duplicate sessions
        session_ids = [s["session_id"] for s in sessions]
        assert len(session_ids) == len(
            set(session_ids)
        ), "No duplicate sessions"


class TestWorkspaceMetadataRaceConditions:
    """Test workspace metadata updates are thread-safe."""

    @pytest.mark.asyncio
    async def test_concurrent_metadata_updates(self, tmp_path):
        """
        Test workspace metadata updates don't corrupt under concurrent access.

        Documented requirement: Thread safety verification

        Corner cases tested:
        - Concurrent updates to same key
        - Concurrent updates to different keys
        - Verify no data loss
        """
        workspace = SessionWorkspace(
            "test-metadata-race", base_path=tmp_path, create=True
        )

        # Test concurrent updates to same key
        async def update_message_count(i: int):
            workspace.metadata["message_count"] = i
            workspace._save_metadata()

        tasks = [update_message_count(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify metadata exists and is valid
        assert "message_count" in workspace.metadata
        assert isinstance(workspace.metadata["message_count"], int)

        # Test concurrent updates to different keys
        async def update_different_key(i: int):
            workspace.metadata[f"key_{i}"] = f"value_{i}"
            workspace._save_metadata()

        tasks = [update_different_key(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify all keys were saved
        for i in range(10):
            assert f"key_{i}" in workspace.metadata
            assert workspace.metadata[f"key_{i}"] == f"value_{i}"

        # Verify metadata file is valid JSON
        import json

        metadata_file = workspace.physical_path / "chat.json"
        assert metadata_file.exists()
        metadata_data = json.loads(metadata_file.read_text())
        assert isinstance(metadata_data, dict)
        assert len(metadata_data) >= 10  # At least our test keys


class TestConcurrentWebSocketConnections:
    """Test concurrent WebSocket connection handling."""

    @pytest.mark.asyncio
    async def test_multiple_websocket_connections(self):
        """
        Test server handles multiple WebSocket connections concurrently.

        Documented requirement: TEST_COVERAGE_STRATEGY.md line 63
        """
        # This would require integration test with actual server
        # For now, document the requirement
        pytest.skip("Requires live server fixture - integration test needed")


class TestConcurrentSessionOperations:
    """Test concurrent session operations."""

    @pytest.mark.asyncio
    async def test_concurrent_session_creation(self, tmp_path):
        """Test creating multiple sessions concurrently."""
        index = SessionIndex(base_path=tmp_path)

        async def create_session(i: int):
            session_id = f"concurrent-session-{i}"
            workspace = SessionWorkspace(
                session_id, base_path=tmp_path, create=True
            )
            index.add_session(workspace)

        # Create 5 sessions concurrently
        tasks = [create_session(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # Verify all sessions created
        sessions = index.list_sessions()
        assert len(sessions) == 5

        # Verify all workspace directories exist
        for i in range(5):
            session_dir = tmp_path / f"concurrent-session-{i}"
            assert session_dir.exists()
            assert (session_dir / "chat.json").exists()
