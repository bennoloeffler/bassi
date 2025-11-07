"""
Unit tests for SessionIndex class.
"""

import json

import pytest

from bassi.core_v3.session_index import SessionIndex
from bassi.core_v3.session_workspace import SessionWorkspace


@pytest.fixture
def temp_index(tmp_path):
    """Create temporary session index for testing."""
    index = SessionIndex(base_path=tmp_path)
    return index


@pytest.fixture
def sample_workspaces(tmp_path):
    """Create sample workspaces for testing."""
    workspaces = []

    for i in range(5):
        session_id = f"session-{i:03d}"
        workspace = SessionWorkspace(session_id, base_path=tmp_path)
        workspace.update_display_name(f"Test Session {i}")

        # Add messages and files to vary the stats
        for j in range(i + 1):
            workspace.save_message("user", f"Message {j}")

        workspaces.append(workspace)

    return workspaces


class TestIndexInitialization:
    """Test index initialization and persistence."""

    def test_creates_index_file(self, tmp_path):
        """Should create .index.json on initialization."""
        index = SessionIndex(base_path=tmp_path)

        assert (tmp_path / ".index.json").exists()

    def test_creates_base_directory(self, tmp_path):
        """Should create base directory if it doesn't exist."""
        base_path = tmp_path / "new_dir"
        assert not base_path.exists()

        index = SessionIndex(base_path=base_path)

        assert base_path.exists()

    def test_loads_existing_index(self, tmp_path):
        """Should load index from existing .index.json."""
        # Create first index and add session
        index1 = SessionIndex(base_path=tmp_path)
        workspace = SessionWorkspace("test-123", base_path=tmp_path)
        index1.add_session(workspace)

        # Load second index
        index2 = SessionIndex(base_path=tmp_path)

        assert "test-123" in index2.index["sessions"]

    def test_rebuilds_if_index_missing(self, tmp_path, sample_workspaces):
        """Should rebuild index if .index.json is missing."""
        # Create workspaces first (without index)
        index_file = tmp_path / ".index.json"
        if index_file.exists():
            index_file.unlink()

        # Create index (should trigger rebuild)
        index = SessionIndex(base_path=tmp_path)

        # Should have indexed all workspaces
        assert len(index.index["sessions"]) == 5

    def test_rebuilds_if_version_mismatch(self, tmp_path, sample_workspaces):
        """Should rebuild index if version doesn't match."""
        # Create index with wrong version
        index_file = tmp_path / ".index.json"
        with open(index_file, "w") as f:
            json.dump({"version": "0.9", "sessions": {}}, f)

        # Load index (should trigger rebuild)
        index = SessionIndex(base_path=tmp_path)

        # Should have rebuilt and indexed all workspaces
        assert index.index["version"] == SessionIndex.INDEX_VERSION
        assert len(index.index["sessions"]) == 5


class TestSessionManagement:
    """Test adding, updating, and removing sessions."""

    def test_adds_session_to_index(self, temp_index, tmp_path):
        """Should add session to index."""
        workspace = SessionWorkspace("test-123", base_path=tmp_path)
        temp_index.add_session(workspace)

        assert "test-123" in temp_index.index["sessions"]

        session_info = temp_index.index["sessions"]["test-123"]
        assert session_info["session_id"] == "test-123"
        assert "display_name" in session_info
        assert "created_at" in session_info

    def test_updates_existing_session(self, temp_index, tmp_path):
        """Should update existing session in index."""
        workspace = SessionWorkspace("test-123", base_path=tmp_path)
        temp_index.add_session(workspace)

        # Update display name
        workspace.update_display_name("Updated Name")
        temp_index.update_session(workspace)

        session_info = temp_index.index["sessions"]["test-123"]
        assert session_info["display_name"] == "Updated Name"

    def test_removes_session_from_index(self, temp_index, tmp_path):
        """Should remove session from index."""
        workspace = SessionWorkspace("test-123", base_path=tmp_path)
        temp_index.add_session(workspace)

        assert "test-123" in temp_index.index["sessions"]

        temp_index.remove_session("test-123")

        assert "test-123" not in temp_index.index["sessions"]

    def test_persists_changes_to_file(self, tmp_path):
        """Should persist changes to .index.json."""
        index1 = SessionIndex(base_path=tmp_path)
        workspace = SessionWorkspace("test-123", base_path=tmp_path)
        index1.add_session(workspace)

        # Load new index instance
        index2 = SessionIndex(base_path=tmp_path)

        assert "test-123" in index2.index["sessions"]


class TestSessionListing:
    """Test session listing with sorting, filtering, pagination."""

    def test_lists_all_sessions(self, temp_index, sample_workspaces):
        """Should list all sessions."""
        # Add all workspaces to index
        for workspace in sample_workspaces:
            temp_index.add_session(workspace)

        sessions = temp_index.list_sessions(limit=100)

        assert len(sessions) == 5

    def test_sorts_by_last_activity_desc(self, temp_index, sample_workspaces):
        """Should sort by last_activity descending by default."""
        for workspace in sample_workspaces:
            temp_index.add_session(workspace)

        sessions = temp_index.list_sessions()

        # Should be sorted by last_activity desc
        for i in range(len(sessions) - 1):
            assert (
                sessions[i]["last_activity"]
                >= sessions[i + 1]["last_activity"]
            )

    def test_sorts_by_created_at(self, temp_index, sample_workspaces):
        """Should sort by created_at when specified."""
        for workspace in sample_workspaces:
            temp_index.add_session(workspace)

        sessions = temp_index.list_sessions(
            sort_by="created_at", sort_desc=False
        )

        # Should be sorted by created_at asc
        for i in range(len(sessions) - 1):
            assert sessions[i]["created_at"] <= sessions[i + 1]["created_at"]

    def test_paginates_results(self, temp_index, sample_workspaces):
        """Should paginate results with limit and offset."""
        for workspace in sample_workspaces:
            temp_index.add_session(workspace)

        # First page (2 items)
        page1 = temp_index.list_sessions(limit=2, offset=0)
        assert len(page1) == 2

        # Second page (2 items)
        page2 = temp_index.list_sessions(limit=2, offset=2)
        assert len(page2) == 2

        # Third page (1 item)
        page3 = temp_index.list_sessions(limit=2, offset=4)
        assert len(page3) == 1

        # No overlap
        page1_ids = [s["session_id"] for s in page1]
        page2_ids = [s["session_id"] for s in page2]
        assert len(set(page1_ids) & set(page2_ids)) == 0

    def test_filters_by_state(self, temp_index, tmp_path):
        """Should filter sessions by state."""
        # Create sessions with different states
        ws1 = SessionWorkspace("session-1", base_path=tmp_path)
        ws1.update_state("CREATED")
        temp_index.add_session(ws1)

        ws2 = SessionWorkspace("session-2", base_path=tmp_path)
        ws2.update_state("AUTO_NAMED")
        temp_index.add_session(ws2)

        ws3 = SessionWorkspace("session-3", base_path=tmp_path)
        ws3.update_state("AUTO_NAMED")
        temp_index.add_session(ws3)

        # Filter for AUTO_NAMED
        auto_named = temp_index.list_sessions(filter_state="AUTO_NAMED")

        assert len(auto_named) == 2
        assert all(s["state"] == "AUTO_NAMED" for s in auto_named)


class TestSessionSearch:
    """Test session search functionality."""

    def test_searches_by_display_name(self, temp_index, sample_workspaces):
        """Should search sessions by display name."""
        for workspace in sample_workspaces:
            temp_index.add_session(workspace)

        # Search for "Session 2"
        results = temp_index.search_sessions("Session 2")

        assert len(results) == 1
        assert "Session 2" in results[0]["display_name"]

    def test_search_is_case_insensitive(self, temp_index, sample_workspaces):
        """Should perform case-insensitive search."""
        for workspace in sample_workspaces:
            temp_index.add_session(workspace)

        results = temp_index.search_sessions("session 3")

        assert len(results) == 1
        assert "Session 3" in results[0]["display_name"]

    def test_search_with_partial_match(self, temp_index, sample_workspaces):
        """Should match partial strings."""
        for workspace in sample_workspaces:
            temp_index.add_session(workspace)

        # Search for "Test" (should match all)
        results = temp_index.search_sessions("Test")

        assert len(results) == 5


class TestSessionInfo:
    """Test getting session info."""

    def test_gets_session_info(self, temp_index, tmp_path):
        """Should get session info by ID."""
        workspace = SessionWorkspace("test-123", base_path=tmp_path)
        temp_index.add_session(workspace)

        info = temp_index.get_session_info("test-123")

        assert info is not None
        assert info["session_id"] == "test-123"

    def test_returns_none_for_nonexistent_session(self, temp_index):
        """Should return None for non-existent session."""
        info = temp_index.get_session_info("nonexistent")

        assert info is None


class TestIndexStats:
    """Test index statistics."""

    def test_gets_overall_stats(self, temp_index, tmp_path):
        """Should return overall index statistics."""
        # Create sessions with different states
        ws1 = SessionWorkspace("session-1", base_path=tmp_path)
        ws1.update_state("CREATED")
        temp_index.add_session(ws1)

        ws2 = SessionWorkspace("session-2", base_path=tmp_path)
        ws2.update_state("AUTO_NAMED")
        temp_index.add_session(ws2)

        ws3 = SessionWorkspace("session-3", base_path=tmp_path)
        ws3.update_state("FINALIZED")
        temp_index.add_session(ws3)

        stats = temp_index.get_stats()

        assert stats["total_sessions"] == 3
        assert stats["states"]["CREATED"] == 1
        assert stats["states"]["AUTO_NAMED"] == 1
        assert stats["states"]["FINALIZED"] == 1


class TestIndexConsistency:
    """Test index consistency verification and repair."""

    def test_verifies_consistent_index(self, temp_index, sample_workspaces):
        """Should verify index is consistent with filesystem."""
        for workspace in sample_workspaces:
            temp_index.add_session(workspace)

        verification = temp_index.verify_consistency()

        assert verification["consistent"] is True
        assert len(verification["missing_from_index"]) == 0
        assert len(verification["missing_from_fs"]) == 0

    def test_detects_missing_from_index(self, temp_index, tmp_path):
        """Should detect sessions missing from index."""
        # Create workspace but don't add to index
        workspace = SessionWorkspace("orphan-session", base_path=tmp_path)

        verification = temp_index.verify_consistency()

        assert verification["consistent"] is False
        assert "orphan-session" in verification["missing_from_index"]

    def test_detects_missing_from_filesystem(self, temp_index, tmp_path):
        """Should detect sessions missing from filesystem."""
        # Add to index
        workspace = SessionWorkspace("temp-session", base_path=tmp_path)
        temp_index.add_session(workspace)

        # Delete from filesystem
        import shutil

        shutil.rmtree(workspace.physical_path)

        verification = temp_index.verify_consistency()

        assert verification["consistent"] is False
        assert "temp-session" in verification["missing_from_fs"]

    def test_repairs_index(self, temp_index, tmp_path):
        """Should repair index by syncing with filesystem."""
        # Create orphan session (not in index)
        orphan = SessionWorkspace("orphan", base_path=tmp_path)

        # Create ghost session (in index but not on fs)
        ghost = SessionWorkspace("ghost", base_path=tmp_path)
        temp_index.add_session(ghost)

        import shutil

        shutil.rmtree(ghost.physical_path)

        # Repair
        result = temp_index.repair()

        assert result["added"] == 1
        assert result["removed"] == 1

        # Verify consistency
        verification = temp_index.verify_consistency()
        assert verification["consistent"] is True
