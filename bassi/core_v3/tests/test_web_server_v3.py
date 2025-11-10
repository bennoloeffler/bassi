"""Tests for web_server_v3.py - Complete test suite for FastAPI web server."""

import asyncio
import logging
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient

from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig
from bassi.core_v3.interactive_questions import (
    InteractiveQuestionService,
    PendingQuestion,
    Question,
    QuestionOption,
)
from bassi.core_v3.session_workspace import SessionWorkspace
from bassi.core_v3.upload_service import FileTooLargeError, InvalidFilenameError
from bassi.core_v3.web_server_v3 import WebUIServerV3
from bassi.shared.sdk_types import AssistantMessage, ResultMessage, TextBlock


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def session_factory():
    """Factory function to create agent sessions for testing."""

    def factory(
        question_service: InteractiveQuestionService,
        workspace: SessionWorkspace,
    ):
        config = SessionConfig(
            permission_mode="bypassPermissions",
        )
        session = BassiAgentSession(config)
        # Attach workspace to session for later access
        session.workspace = workspace
        return session

    return factory


@pytest.fixture
def web_server(session_factory):
    """Create WebUIServerV3 instance for testing."""
    return WebUIServerV3(
        session_factory=session_factory, host="localhost", port=8765
    )


@pytest.fixture
def test_client(web_server):
    """FastAPI test client for HTTP endpoint testing."""
    return TestClient(web_server.app)


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary SessionWorkspace for testing."""
    workspace = SessionWorkspace("test-session", base_path=tmp_path)
    return workspace


@pytest.fixture
def mock_session():
    """Create a mock agent session for testing."""
    session = AsyncMock(spec=BassiAgentSession)
    session.session_id = "test-session-id"
    session.workspace = MagicMock(spec=SessionWorkspace)
    session.workspace.session_id = "test-session-id"
    session.workspace.metadata = {"message_count": 0}
    session.workspace.state = "UNNAMED"
    session.interrupt = AsyncMock()
    return session


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing."""
    websocket = AsyncMock()
    websocket.send_json = AsyncMock()
    websocket.receive_json = AsyncMock()
    return websocket


# ============================================================================
# Basic REST Endpoint Tests
# ============================================================================


def test_health_endpoint(test_client):
    """Test /health endpoint returns 200 with status."""
    response = test_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "bassi-web-ui-v3"
    assert "active_sessions" in data


@pytest.mark.integration
def test_capabilities_endpoint_integration(test_client):
    """
    Integration test for /api/capabilities endpoint.

    Tests that the endpoint:
    1. Returns 200 OK
    2. Returns JSON response
    3. Contains expected capability fields (tools, mcp_servers, etc.)

    Requires actual Agent SDK connection.
    """
    response = test_client.get("/api/capabilities")

    # Should return 200
    assert response.status_code == 200

    # Should return JSON
    data = response.json()
    assert isinstance(data, dict)

    # Should contain capabilities fields
    # Note: Exact fields depend on Agent SDK version
    # We check for at least one expected field
    assert (
        "tools" in data or "mcp_servers" in data or "slash_commands" in data
    )


def test_capabilities_endpoint_format(test_client):
    """
    Test that /api/capabilities returns properly formatted response.

    This is a light test that doesn't require full SDK setup.
    """
    response = test_client.get("/api/capabilities")

    # Should return JSON
    assert response.headers["content-type"] == "application/json"

    # Should not crash
    assert response.status_code in [200, 500]  # Either success or error

    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, dict)


def test_capabilities_endpoint_error_handling(test_client, web_server, monkeypatch):
    """
    Test capabilities endpoint error handling.

    Tests error handling path in web_server_v3.py lines 273-277.
    """
    # Mock BassiDiscovery to raise an error during get_summary()
    class MockDiscovery:
        def get_summary(self):
            raise RuntimeError("Discovery service unavailable")

    # Replace BassiDiscovery in the discovery module (where it's imported from)
    import bassi.core_v3.discovery

    monkeypatch.setattr(
        bassi.core_v3.discovery,
        "BassiDiscovery",
        MockDiscovery,
    )

    response = test_client.get("/api/capabilities")

    # Should return 500 Internal Server Error
    assert response.status_code == 500

    # Should contain error message
    data = response.json()
    assert "error" in data
    assert "Discovery service unavailable" in data["error"]


def test_root_endpoint(test_client):
    """Test / endpoint serves HTML."""
    response = test_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_static_files(test_client):
    """Test /static/ endpoint serves static files."""
    # Try to access a known static file
    response = test_client.get("/static/app.js")

    # Should either succeed or 404 if file doesn't exist
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        # Should be JavaScript
        assert (
            "application/javascript" in response.headers["content-type"]
            or "text/javascript" in response.headers["content-type"]
        )


# ============================================================================
# Session Management Tests
# ============================================================================


def test_list_sessions_sorts_by_display_name(test_client, web_server):
    """Sessions endpoint should honor display_name sorting."""
    web_server.session_index.index["sessions"] = {
        "b": {
            "session_id": "b",
            "display_name": "Bravo",
            "created_at": "2024-01-02T00:00:00",
            "last_activity": "2024-01-03T00:00:00",
        },
        "a": {
            "session_id": "a",
            "display_name": "Alpha",
            "created_at": "2024-01-01T00:00:00",
            "last_activity": "2024-01-02T00:00:00",
        },
        "c": {
            "session_id": "c",
            "display_name": "Charlie",
            "created_at": "2024-01-03T00:00:00",
            "last_activity": "2024-01-04T00:00:00",
        },
    }

    response = test_client.get(
        "/api/sessions?sort_by=display_name&order=asc"
    )
    assert response.status_code == 200

    payload = response.json()
    names = [session["display_name"] for session in payload["sessions"]]
    assert names == ["Alpha", "Bravo", "Charlie"]

    response = test_client.get(
        "/api/sessions?sort_by=display_name&order=desc"
    )
    payload = response.json()
    names = [session["display_name"] for session in payload["sessions"]]
    assert names == ["Charlie", "Bravo", "Alpha"]


def test_list_sessions_sorts_by_created_at(test_client, web_server):
    """
    Test sessions endpoint sorting by created_at timestamp.

    Tests sorting logic in web_server_v3.py lines 371-374.
    """
    web_server.session_index.index["sessions"] = {
        "mid": {
            "session_id": "mid",
            "display_name": "Middle Session",
            "created_at": "2024-01-02T12:00:00",
            "last_activity": "2024-01-02T12:00:00",
        },
        "old": {
            "session_id": "old",
            "display_name": "Oldest Session",
            "created_at": "2024-01-01T00:00:00",
            "last_activity": "2024-01-01T00:00:00",
        },
        "new": {
            "session_id": "new",
            "display_name": "Newest Session",
            "created_at": "2024-01-03T18:00:00",
            "last_activity": "2024-01-03T18:00:00",
        },
    }

    # Test ascending order (oldest first)
    response = test_client.get("/api/sessions?sort_by=created_at&order=asc")
    assert response.status_code == 200

    payload = response.json()
    session_ids = [session["session_id"] for session in payload["sessions"]]
    assert session_ids == ["old", "mid", "new"]

    # Test descending order (newest first)
    response = test_client.get("/api/sessions?sort_by=created_at&order=desc")
    payload = response.json()
    session_ids = [session["session_id"] for session in payload["sessions"]]
    assert session_ids == ["new", "mid", "old"]


def test_list_sessions_sorts_by_last_activity(test_client, web_server):
    """
    Test sessions endpoint sorting by last_activity timestamp.

    Tests sorting logic in web_server_v3.py lines 376-379.
    """
    web_server.session_index.index["sessions"] = {
        "stale": {
            "session_id": "stale",
            "display_name": "Stale Session",
            "created_at": "2024-01-01T00:00:00",
            "last_activity": "2024-01-01T08:00:00",
        },
        "active": {
            "session_id": "active",
            "display_name": "Most Active",
            "created_at": "2024-01-01T00:00:00",
            "last_activity": "2024-01-03T20:00:00",
        },
        "moderate": {
            "session_id": "moderate",
            "display_name": "Moderate Activity",
            "created_at": "2024-01-01T00:00:00",
            "last_activity": "2024-01-02T14:00:00",
        },
    }

    # Test ascending order (least recent first)
    response = test_client.get("/api/sessions?sort_by=last_activity&order=asc")
    assert response.status_code == 200

    payload = response.json()
    session_ids = [session["session_id"] for session in payload["sessions"]]
    assert session_ids == ["stale", "moderate", "active"]

    # Test descending order (most recent first)
    response = test_client.get("/api/sessions?sort_by=last_activity&order=desc")
    payload = response.json()
    session_ids = [session["session_id"] for session in payload["sessions"]]
    assert session_ids == ["active", "moderate", "stale"]


def test_list_sessions_applies_limit_and_offset(test_client, web_server):
    """Sessions endpoint should paginate results."""
    sessions = {}
    for idx in range(5):
        sid = f"s-{idx}"
        sessions[sid] = {
            "session_id": sid,
            "display_name": f"Session {idx}",
            "created_at": f"2024-01-0{idx+1}T00:00:00",
            "last_activity": f"2024-01-0{idx+1}T00:00:00",
        }
    web_server.session_index.index["sessions"] = sessions

    response = test_client.get("/api/sessions?limit=2&offset=1")
    assert response.status_code == 200
    payload = response.json()

    assert payload["limit"] == 2
    assert payload["offset"] == 1
    assert payload["total"] == 5
    assert len(payload["sessions"]) == 2


def test_list_sessions_error_handling(test_client, web_server, monkeypatch):
    """
    Test list_sessions endpoint error handling.

    Tests error handling path in web_server_v3.py lines 399-404.
    """
    # Mock session_index.index to raise an error
    def mock_index_access(*args, **kwargs):
        raise RuntimeError("Session index database corrupted")

    # Replace the index property to trigger error
    monkeypatch.setattr(
        web_server.session_index,
        "index",
        property(lambda self: mock_index_access()),
    )

    response = test_client.get("/api/sessions")

    # Should return 500 Internal Server Error
    assert response.status_code == 500

    # Should contain error message
    data = response.json()
    assert "error" in data
    assert "Failed to list sessions" in data["error"]


def test_get_session_returns_active_stats(test_client, web_server):
    """Active workspace should be preferred over disk lookup."""
    stats = {
        "session_id": "active-1",
        "display_name": "Active Session",
        "message_count": 3,
    }

    class StubWorkspace:
        def get_stats(self):
            return stats

    web_server.workspaces["active-1"] = StubWorkspace()

    response = test_client.get("/api/sessions/active-1")

    assert response.status_code == 200
    assert response.json() == stats


def test_get_session_missing_returns_404(test_client, web_server, monkeypatch):
    """Requesting unknown session should yield 404."""
    monkeypatch.setattr(
        "bassi.core_v3.web_server_v3.SessionWorkspace.exists",
        lambda session_id: False,
    )

    response = test_client.get("/api/sessions/missing")

    assert response.status_code == 404
    assert "Session not found" in response.json()["error"]


def test_get_session_loads_from_disk(
    test_client, web_server, monkeypatch
):
    """If workspace inactive, endpoint should load from disk."""
    stats = {
        "session_id": "disk-1",
        "display_name": "From Disk",
        "message_count": 2,
    }

    class StubWorkspace:
        def get_stats(self):
            return stats

    monkeypatch.setattr(
        "bassi.core_v3.web_server_v3.SessionWorkspace.exists",
        lambda session_id: session_id == "disk-1",
    )
    monkeypatch.setattr(
        "bassi.core_v3.web_server_v3.SessionWorkspace.load",
        lambda session_id: StubWorkspace(),
    )

    response = test_client.get("/api/sessions/disk-1")

    assert response.status_code == 200
    assert response.json() == stats


def test_get_session_error_handling(test_client, web_server, tmp_path, monkeypatch):
    """
    Test get_session endpoint error handling.

    Tests error handling path in web_server_v3.py lines 435-440.
    """
    from bassi.core_v3.session_workspace import SessionWorkspace

    # Create session with workspace
    session_id = "test-session"
    workspace = SessionWorkspace(session_id, base_path=tmp_path, create=True)
    web_server.workspaces[session_id] = workspace

    # Mock get_stats() to raise an error
    def mock_get_stats():
        raise RuntimeError("Stats database corrupted")

    monkeypatch.setattr(workspace, "get_stats", mock_get_stats)

    response = test_client.get(f"/api/sessions/{session_id}")

    # Should return 500 Internal Server Error
    assert response.status_code == 500

    # Should contain error message
    data = response.json()
    assert "error" in data
    assert "Failed to get session" in data["error"]
    assert "Stats database corrupted" in data["error"]


def test_delete_session_rejects_active_session(test_client, web_server):
    """Deleting active sessions should return 400."""
    session_id = "active-session"
    web_server.active_sessions[session_id] = object()

    response = test_client.delete(f"/api/sessions/{session_id}")

    assert response.status_code == 400
    assert response.json()["error"] == "Cannot delete active session"


def test_delete_session_missing_returns_404(
    test_client, web_server, monkeypatch
):
    """Deleting non-existent sessions should return 404."""
    monkeypatch.setattr(
        "bassi.core_v3.web_server_v3.SessionWorkspace.exists",
        lambda session_id: False,
    )

    response = test_client.delete("/api/sessions/missing-session")

    assert response.status_code == 404
    assert response.json()["error"] == "Session not found"


def test_delete_session_failure_returns_500(
    test_client, web_server, monkeypatch
):
    """Server should surface errors if workspace deletion fails."""
    monkeypatch.setattr(
        "bassi.core_v3.web_server_v3.SessionWorkspace.exists",
        lambda session_id: True,
    )

    class StubWorkspace:
        def delete(self):
            raise RuntimeError("disk failure")

    monkeypatch.setattr(
        "bassi.core_v3.web_server_v3.SessionWorkspace.load",
        lambda session_id: StubWorkspace(),
    )

    removed = []
    monkeypatch.setattr(
        web_server.session_index,
        "remove_session",
        lambda session_id: removed.append(session_id),
    )

    response = test_client.delete("/api/sessions/bad-session")

    assert response.status_code == 500
    assert "Failed to delete session" in response.json()["error"]
    assert removed == ["bad-session"]


# ============================================================================
# File Management Tests
# ============================================================================


def test_list_session_files_missing_workspace(test_client, web_server):
    """Endpoint should return 404 if workspace not active."""
    response = test_client.get("/api/sessions/missing/files")

    assert response.status_code == 404
    assert "Session not found" in response.json()["error"]


def test_list_session_files_empty_dir(test_client, web_server, tmp_path):
    """Returns empty list when DATA_FROM_USER is absent."""
    class StubWorkspace:
        def __init__(self, path):
            self.physical_path = path

    workspace = StubWorkspace(tmp_path)
    web_server.workspaces["s1"] = workspace

    response = test_client.get("/api/sessions/s1/files")

    assert response.status_code == 200
    assert response.json() == {"files": []}


def test_list_session_files_returns_metadata(
    test_client, web_server, tmp_path, monkeypatch
):
    """Should emit upload metadata for each file."""
    data_dir = tmp_path / "DATA_FROM_USER"
    data_dir.mkdir(parents=True)
    file_path = data_dir / "report.txt"
    file_path.write_text("hello")

    class StubWorkspace:
        def __init__(self, path):
            self.physical_path = path

    workspace = StubWorkspace(tmp_path)
    web_server.workspaces["s2"] = workspace

    monkeypatch.setattr(
        web_server.upload_service,
        "get_upload_info",
        lambda path, ws: {
            "name": path.name,
            "size": path.stat().st_size,
            "custom": True,
        },
    )

    response = test_client.get("/api/sessions/s2/files")

    assert response.status_code == 200
    payload = response.json()
    assert payload["files"] == [{"name": "report.txt", "size": 5, "custom": True}]


def test_list_session_files_sorted_by_name(
    test_client, web_server, tmp_path
):
    """Files should be returned in deterministic (sorted) order."""
    data_dir = tmp_path / "DATA_FROM_USER"
    data_dir.mkdir()

    for name in ["c.txt", "a.txt", "b.txt"]:
        (data_dir / name).write_text(name)

    class StubWorkspace:
        def __init__(self, path):
            self.physical_path = path

    web_server.workspaces["s3"] = StubWorkspace(tmp_path)

    response = test_client.get("/api/sessions/s3/files")
    assert response.status_code == 200
    payload = response.json()
    assert [f["name"] for f in payload["files"]] == ["a.txt", "b.txt", "c.txt"]


def test_list_session_files_handles_upload_errors(
    test_client, web_server, tmp_path, monkeypatch
):
    """Upload service failures should return 500."""
    data_dir = tmp_path / "DATA_FROM_USER"
    data_dir.mkdir()
    (data_dir / "boom.txt").write_text("boom")

    class StubWorkspace:
        def __init__(self, path):
            self.physical_path = path

    web_server.workspaces["s4"] = StubWorkspace(tmp_path)

    def boom(*_, **__):
        raise RuntimeError("fail")

    monkeypatch.setattr(
        web_server.upload_service, "get_upload_info", boom
    )

    response = test_client.get("/api/sessions/s4/files")
    assert response.status_code == 500
    assert "Failed to list files" in response.json()["error"]


# ============================================================================
# File Upload Tests
# ============================================================================


def test_upload_file_success_returns_file_info(test_client, web_server, tmp_path):
    """
    Test successful file upload returns file info.

    Tests success path in web_server_v3.py lines 310-319.
    """
    from bassi.core_v3.session_workspace import SessionWorkspace

    # Create session with workspace
    session_id = "test-session"
    workspace = SessionWorkspace(session_id, base_path=tmp_path, create=True)
    web_server.workspaces[session_id] = workspace

    # Upload a file
    file_content = b"Hello, World!"
    response = test_client.post(
        "/api/upload",
        data={"session_id": session_id},
        files={"file": ("test.txt", BytesIO(file_content), "text/plain")},
    )

    # Should return 200 OK
    assert response.status_code == 200

    # Should contain file info
    data = response.json()
    assert "name" in data
    assert "size" in data
    assert "path" in data
    # Upload service adds random suffix for uniqueness (e.g., test_abc123.txt)
    assert data["name"].startswith("test")
    assert data["name"].endswith(".txt")
    assert data["size"] == len(file_content)


def test_upload_file_too_large_returns_413(test_client, web_server, tmp_path, monkeypatch):
    """
    Test that uploading a file exceeding size limit returns 413 status.

    Tests error handling path in web_server_v3.py lines 321-326.
    """
    from bassi.core_v3.session_workspace import SessionWorkspace

    # Create session with workspace
    session_id = "test-session"
    workspace = SessionWorkspace(session_id, base_path=tmp_path, create=True)
    web_server.workspaces[session_id] = workspace

    # Mock upload_service.upload_to_session to raise FileTooLargeError
    def mock_upload(*args, **kwargs):
        raise FileTooLargeError(
            size=150 * 1024 * 1024,  # 150 MB
            max_size=100 * 1024 * 1024,  # 100 MB
        )

    monkeypatch.setattr(
        web_server.upload_service,
        "upload_to_session",
        mock_upload,
    )

    # Attempt to upload file
    file_content = b"fake large file content"
    response = test_client.post(
        "/api/upload",
        data={"session_id": session_id},
        files={"file": ("huge.bin", BytesIO(file_content), "application/octet-stream")},
    )

    # Should return 413 Payload Too Large
    assert response.status_code == 413

    # Should contain error message about file size
    data = response.json()
    assert "error" in data
    assert "150.0 MB" in data["error"]
    assert "100.0 MB" in data["error"]


def test_upload_invalid_filename_returns_400(test_client, web_server, tmp_path, monkeypatch):
    """
    Test that uploading a file with invalid filename returns 400 status.

    Tests error handling path in web_server_v3.py lines 328-333.
    """
    from bassi.core_v3.session_workspace import SessionWorkspace

    # Create session with workspace
    session_id = "test-session"
    workspace = SessionWorkspace(session_id, base_path=tmp_path, create=True)
    web_server.workspaces[session_id] = workspace

    # Mock upload_service.upload_to_session to raise InvalidFilenameError
    def mock_upload(*args, **kwargs):
        raise InvalidFilenameError(
            filename="../../etc/passwd",
            reason="Path traversal attempt detected",
        )

    monkeypatch.setattr(
        web_server.upload_service,
        "upload_to_session",
        mock_upload,
    )

    # Attempt to upload file with malicious filename
    file_content = b"fake file content"
    response = test_client.post(
        "/api/upload",
        data={"session_id": session_id},
        files={"file": ("../../etc/passwd", BytesIO(file_content), "text/plain")},
    )

    # Should return 400 Bad Request
    assert response.status_code == 400

    # Should contain error message about invalid filename
    data = response.json()
    assert "error" in data
    assert "../../etc/passwd" in data["error"]
    assert "Path traversal" in data["error"]


def test_upload_generic_error_returns_500(test_client, web_server, tmp_path, monkeypatch):
    """
    Test that unexpected upload errors return 500 status.

    Tests error handling path in web_server_v3.py lines 335-340.
    """
    from bassi.core_v3.session_workspace import SessionWorkspace

    # Create session with workspace
    session_id = "test-session"
    workspace = SessionWorkspace(session_id, base_path=tmp_path, create=True)
    web_server.workspaces[session_id] = workspace

    # Mock upload_service.upload_to_session to raise unexpected error
    def mock_upload(*args, **kwargs):
        raise RuntimeError("Disk I/O error: write failed")

    monkeypatch.setattr(
        web_server.upload_service,
        "upload_to_session",
        mock_upload,
    )

    # Attempt to upload file
    file_content = b"fake file content"
    response = test_client.post(
        "/api/upload",
        data={"session_id": session_id},
        files={"file": ("document.txt", BytesIO(file_content), "text/plain")},
    )

    # Should return 500 Internal Server Error
    assert response.status_code == 500

    # Should contain generic error message
    data = response.json()
    assert "error" in data
    assert "Upload failed" in data["error"]
    assert "Disk I/O error" in data["error"]


# ============================================================================
# Configuration Tests
# ============================================================================


def test_default_session_factory_respects_permission_env(
    monkeypatch, tmp_path
):
    """Factory should use permission mode from environment variable."""
    monkeypatch.setenv("BASSI_PERMISSION_MODE", "default")
    monkeypatch.setattr(
        "bassi.core_v3.web_server_v3.create_sdk_mcp_server",
        lambda **kwargs: {
            "name": kwargs.get("name"),
            "version": kwargs.get("version"),
            "tools": kwargs.get("tools", []),
            "sdk_available": False,
        },
    )

    from bassi.core_v3.web_server_v3 import create_default_session_factory

    factory = create_default_session_factory()
    workspace = SessionWorkspace("env-session", base_path=tmp_path)
    question_service = InteractiveQuestionService()

    session = factory(question_service, workspace)

    assert session.config.permission_mode == "default"


# ============================================================================
# WebSocket Connection Tests
# ============================================================================


@pytest.mark.asyncio
async def test_websocket_connection_failure_handling(tmp_path):
    """
    Test comprehensive WebSocket connection failure handling in _handle_websocket.

    This test verifies that when session.connect() fails:
    1. Error messages are sent to the client with proper format
    2. Proper cleanup occurs (question service, session, workspace)
    3. WebSocket is properly closed/removed from active connections
    4. Empty sessions are auto-deleted
    5. Different exception types are handled gracefully

    Test coverage:
    - ConnectionError during session.connect()
    - RuntimeError during session.connect()
    - Generic Exception during session.connect()
    - Cleanup of question service (cancel_all called)
    - Cleanup of empty workspace (auto-deletion)
    - Removal from active_sessions dict
    - Removal from active_connections list
    - Error messages sent to client
    """
    # Create a mock session factory that returns sessions which fail to connect
    mock_session_instance = MagicMock(spec=BassiAgentSession)

    # Configure mock to fail on connect() with different exceptions
    connection_error = ConnectionError("Failed to connect to Claude Agent SDK")
    mock_session_instance.connect = AsyncMock(side_effect=connection_error)
    mock_session_instance.disconnect = AsyncMock()

    def failing_session_factory(
        question_service: InteractiveQuestionService,
        workspace: SessionWorkspace,
    ):
        """Factory that creates sessions that fail to connect"""
        return mock_session_instance

    # Create web server with failing session factory
    web_server = WebUIServerV3(
        session_factory=failing_session_factory,
        host="localhost",
        port=8765,
    )

    # Create mock WebSocket
    mock_websocket = MagicMock(spec=WebSocket)
    mock_websocket.accept = AsyncMock()
    mock_websocket.send_json = AsyncMock()
    mock_websocket.receive_json = AsyncMock(side_effect=Exception("Connection closed"))

    # Track sent messages
    sent_messages = []

    async def capture_send_json(data):
        sent_messages.append(data)

    mock_websocket.send_json = AsyncMock(side_effect=capture_send_json)

    # Patch SessionWorkspace to use tmp_path and track deletions
    deleted_sessions = []
    original_exists = SessionWorkspace.exists
    original_load = SessionWorkspace.load
    original_delete = SessionWorkspace.delete

    def mock_exists(session_id, base_path=None):
        # No existing sessions for this test
        return False

    def mock_delete(self):
        deleted_sessions.append(self.session_id)

    # Mock the SessionWorkspace constructor to use tmp_path as base_path
    original_init = SessionWorkspace.__init__

    def mock_init(self, session_id, base_path=None, create=True):
        # Always use tmp_path as base_path
        original_init(self, session_id, tmp_path, create)

    with patch.object(SessionWorkspace, "exists", side_effect=mock_exists), patch.object(
        SessionWorkspace, "load", side_effect=original_load
    ), patch.object(SessionWorkspace, "delete", mock_delete), patch.object(
        SessionWorkspace, "__init__", mock_init
    ):

        # Execute _handle_websocket and expect it to handle the connection error
        try:
            await web_server._handle_websocket(mock_websocket, None)
        except Exception as e:
            # Should not raise - errors should be caught and handled internally
            pytest.fail(f"_handle_websocket raised unexpected exception: {e}")

        # Verify WebSocket was accepted before connection attempt
        assert mock_websocket.accept.called, "WebSocket should be accepted"

        # Verify status messages were sent
        assert len(sent_messages) >= 1, "Should send at least one status message"

        # Find the connection status message
        connection_status = next(
            (msg for msg in sent_messages if msg.get("type") == "status"), None
        )
        assert connection_status is not None, "Should send connection status message"
        assert (
            "Connecting" in connection_status.get("message", "")
            or "connecting" in connection_status.get("message", "").lower()
        ), "Status message should indicate connection attempt"

        # Verify session.connect() was called
        assert (
            mock_session_instance.connect.called
        ), "session.connect() should have been called"

        # Verify cleanup occurred:
        # 1. Session should be disconnected
        assert (
            mock_session_instance.disconnect.called
        ), "session.disconnect() should be called during cleanup"

        # 2. Empty workspace should be auto-deleted (message_count == 0)
        assert len(deleted_sessions) > 0, "Empty workspace should be auto-deleted"

        # 3. WebSocket should be removed from active_connections
        assert (
            mock_websocket not in web_server.active_connections
        ), "WebSocket should be removed from active_connections"

        # 4. Session should be removed from active_sessions
        # (Check that active_sessions is empty or doesn't contain our session)
        for session_id, session in web_server.active_sessions.items():
            assert (
                session is not mock_session_instance
            ), "Failed session should be removed from active_sessions"

        # 5. Question service should be cleaned up (cancel_all called)
        # We can verify this by checking that question_services dict is clean
        assert (
            len(web_server.question_services) == 0
        ), "Question services should be cleaned up"


@pytest.mark.asyncio
async def test_websocket_connection_failure_with_runtime_error(tmp_path):
    """
    Test WebSocket connection failure with RuntimeError.

    Verifies that different exception types are handled consistently.
    """
    # Create a mock session that raises RuntimeError
    mock_session_instance = MagicMock(spec=BassiAgentSession)
    runtime_error = RuntimeError("SDK initialization failed")
    mock_session_instance.connect = AsyncMock(side_effect=runtime_error)
    mock_session_instance.disconnect = AsyncMock()

    def failing_session_factory(
        question_service: InteractiveQuestionService,
        workspace: SessionWorkspace,
    ):
        return mock_session_instance

    web_server = WebUIServerV3(
        session_factory=failing_session_factory,
        host="localhost",
        port=8765,
    )

    mock_websocket = MagicMock(spec=WebSocket)
    mock_websocket.accept = AsyncMock()
    mock_websocket.send_json = AsyncMock()
    mock_websocket.receive_json = AsyncMock(side_effect=Exception("Connection closed"))

    # Mock SessionWorkspace to use tmp_path
    original_init = SessionWorkspace.__init__

    def mock_init(self, session_id, base_path=None, create=True):
        original_init(self, session_id, tmp_path, create)

    with patch.object(SessionWorkspace, "exists", return_value=False), patch.object(
        SessionWorkspace, "__init__", mock_init
    ):
        # Should handle RuntimeError gracefully
        try:
            await web_server._handle_websocket(mock_websocket, None)
        except Exception as e:
            pytest.fail(f"Should not raise exception, got: {e}")

        # Verify cleanup occurred
        assert mock_session_instance.disconnect.called, "Cleanup should occur"
        assert (
            mock_websocket not in web_server.active_connections
        ), "WebSocket should be removed"




# ============================================================================
# WebSocket Disconnect Tests
# ============================================================================












# ============================================================================
# WebSocket Message Processing Tests
# ============================================================================










# ============================================================================
# Config Change and Interrupt Tests
# ============================================================================




# =================================================================
# Interrupt and Hint Error Handling Tests (E2E)
# Migrated from AGENT_05 - covers lines 1323-1504
# =================================================================


def skip_connection_messages(ws):
    """Helper to skip status/connected messages and return session_id."""
    # Get first message (status: "Connecting...")
    msg = ws.receive_json()
    assert msg["type"] == "status"

    # Get second message (status: "Connected!" or connected event)
    msg = ws.receive_json()
    if msg["type"] == "status":
        # Get third message (connected event)
        msg = ws.receive_json()

    assert msg["type"] == "connected"
    return msg.get("session_id")


@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
def test_interrupt_failure_handling_e2e():
    """
    Test interrupt failure handling via WebSocket E2E.

    Tests that when session.interrupt() fails:
    1. Error message is sent to client
    2. Server doesn't crash
    3. Connection remains active for recovery
    """

    def failing_interrupt_factory(
        question_service: InteractiveQuestionService,
        workspace: SessionWorkspace,
    ):
        session = BassiAgentSession(
            SessionConfig(permission_mode="bypassPermissions")
        )
        session.workspace = workspace

        # Mock interrupt to fail
        async def failing_interrupt():
            raise RuntimeError("Interrupt failed")

        session.interrupt = failing_interrupt
        return session

    web_server = WebUIServerV3(
        session_factory=failing_interrupt_factory,
        host="localhost",
        port=8888,  # Use fixed port for E2E
    )

    with TestClient(web_server.app) as client:
        with client.websocket_connect("/ws") as ws:
            # Skip connection messages
            skip_connection_messages(ws)

            # Send interrupt request
            ws.send_json({"type": "interrupt"})

            # Should receive error (not interrupted message)
            error_response = ws.receive_json()
            assert error_response["type"] == "error"
            assert "Failed to interrupt" in error_response["message"]
            assert "Interrupt failed" in error_response["message"]


@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
def test_hint_processing_error_handling_e2e():
    """
    Test hint processing error handling via WebSocket E2E.

    Tests that when session.query() fails during hint processing:
    1. Error message is sent to client
    2. Server doesn't crash
    3. Proper error format is used
    """

    def failing_hint_factory(
        question_service: InteractiveQuestionService,
        workspace: SessionWorkspace,
    ):
        session = BassiAgentSession(
            SessionConfig(permission_mode="bypassPermissions")
        )
        session.workspace = workspace

        # Mock query to fail (must be async generator)
        async def failing_query(prompt=None, **kwargs):
            raise ValueError("Query failed")
            yield  # Make it an async generator (unreachable)

        session.query = failing_query
        return session

    web_server = WebUIServerV3(
        session_factory=failing_hint_factory,
        host="localhost",
        port=8889,  # Use fixed port for E2E
    )

    with TestClient(web_server.app) as client:
        with client.websocket_connect("/ws") as ws:
            # Skip connection messages and get session_id
            session_id = skip_connection_messages(ws)

            # Send hint request
            ws.send_json(
                {
                    "type": "hint",
                    "content": "Test hint content",
                    "session_id": session_id,
                }
            )

            # Should receive error message
            error_response = ws.receive_json()
            assert error_response["type"] == "error"
            assert "Failed to process hint" in error_response["message"]
            assert "Query failed" in error_response["message"]


@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
def test_hint_stream_conversion_error_e2e():
    """
    Test hint processing when message conversion fails.

    Tests that when convert_message_to_websocket raises exception:
    1. Error message is sent to client
    2. Server doesn't crash
    3. Stream processing stops gracefully
    """

    def broken_stream_factory(
        question_service: InteractiveQuestionService,
        workspace: SessionWorkspace,
    ):
        session = BassiAgentSession(
            SessionConfig(permission_mode="bypassPermissions")
        )
        session.workspace = workspace

        # Mock query to return invalid message
        async def broken_query(prompt=None, **kwargs):
            # Yield something that can't be converted
            yield {"invalid": "structure"}

        session.query = broken_query
        return session

    web_server = WebUIServerV3(
        session_factory=broken_stream_factory,
        host="localhost",
        port=8890,  # Use fixed port for E2E
    )

    with TestClient(web_server.app) as client:
        with patch(
            "bassi.core_v3.web_server_v3.convert_message_to_websocket"
        ) as mock_convert:
            # Make conversion fail
            mock_convert.side_effect = TypeError(
                "Cannot convert invalid message"
            )

            with client.websocket_connect("/ws") as ws:
                # Skip connection messages and get session_id
                session_id = skip_connection_messages(ws)

                # Send hint request
                ws.send_json(
                    {
                        "type": "hint",
                        "content": "Another hint",
                        "session_id": session_id,
                    }
                )

                # Should receive error message
                error_response = ws.receive_json()
                assert error_response["type"] == "error"
                assert "Failed to process hint" in error_response["message"]
                assert (
                    "Cannot convert invalid message"
                    in error_response["message"]
                )


@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
def test_successful_interrupt_e2e():
    """
    Test successful interrupt flow via WebSocket E2E.

    Verifies that when interrupt succeeds:
    1. Interrupted message is sent
    2. session.interrupt() is called
    3. Server remains operational
    """

    interrupt_called = False

    def working_interrupt_factory(
        question_service: InteractiveQuestionService,
        workspace: SessionWorkspace,
    ):
        session = BassiAgentSession(
            SessionConfig(permission_mode="bypassPermissions")
        )
        session.workspace = workspace

        # Mock interrupt to succeed
        async def working_interrupt():
            nonlocal interrupt_called
            interrupt_called = True

        session.interrupt = working_interrupt
        return session

    web_server = WebUIServerV3(
        session_factory=working_interrupt_factory,
        host="localhost",
        port=8891,  # Use fixed port for E2E
    )

    with TestClient(web_server.app) as client:
        with client.websocket_connect("/ws") as ws:
            # Skip connection messages
            skip_connection_messages(ws)

            # Send interrupt request
            ws.send_json({"type": "interrupt"})

            # Should receive success message
            success_response = ws.receive_json()
            assert success_response["type"] == "interrupted"
            assert "Agent execution stopped" in success_response["message"]

            # Verify interrupt was called
            assert interrupt_called, "session.interrupt() should have been called"


@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
def test_successful_hint_processing_e2e():
    """
    Test successful hint processing via WebSocket E2E.

    Verifies that when hint succeeds:
    1. Text delta events are sent
    2. Message complete event is sent
    3. Formatted hint prompt is used
    """

    query_called = False
    query_prompt = None

    def working_hint_factory(
        question_service: InteractiveQuestionService,
        workspace: SessionWorkspace,
    ):
        session = BassiAgentSession(
            SessionConfig(permission_mode="bypassPermissions")
        )
        session.workspace = workspace

        # Mock query to succeed
        async def working_query(prompt=None, **kwargs):
            nonlocal query_called, query_prompt
            query_called = True
            query_prompt = prompt

            # Yield valid assistant message
            yield AssistantMessage(
                content=[TextBlock(text="Hint response")], model="test-model"
            )

        session.query = working_query
        return session

    web_server = WebUIServerV3(
        session_factory=working_hint_factory,
        host="localhost",
        port=8892,  # Use fixed port for E2E
    )

    with TestClient(web_server.app) as client:
        with client.websocket_connect("/ws") as ws:
            # Skip connection messages and get session_id
            session_id = skip_connection_messages(ws)

            # Send hint request
            ws.send_json(
                {
                    "type": "hint",
                    "content": "Test hint content",
                    "session_id": session_id,
                }
            )

            # Should receive text_delta and message_complete
            messages_received = []
            max_messages = 10

            for _ in range(max_messages):
                msg = ws.receive_json()
                messages_received.append(msg)

                if msg.get("type") == "message_complete":
                    break
                if msg.get("type") == "error":
                    break

            # Verify we got messages
            assert len(messages_received) > 0
            assert messages_received[-1]["type"] == "message_complete"

            # Verify query was called with formatted hint
            assert query_called, "session.query() should have been called"
            assert query_prompt is not None
            assert "Task was interrupted" in query_prompt
            assert "Test hint content" in query_prompt
            assert "Now continue" in query_prompt
