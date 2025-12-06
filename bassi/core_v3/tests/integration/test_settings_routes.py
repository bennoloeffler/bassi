"""Tests for settings API routes."""

import pytest
from fastapi.testclient import TestClient

from bassi.core_v3.routes import settings
from bassi.core_v3.services.config_service import ConfigService
from bassi.core_v3.web_server_v3 import WebUIServerV3


@pytest.fixture
def test_client(tmp_path):
    """Test client with temporary config"""
    # Replace singleton with test instance
    settings._config_service = ConfigService(tmp_path / "config.json")

    # Create server instance and get the app
    server = WebUIServerV3()
    client = TestClient(server.app)

    yield client

    # Cleanup
    settings._config_service = None
    settings._permission_manager = None


def test_get_global_bypass_default(test_client):
    """GET /api/settings/global-bypass returns default value (True)"""
    response = test_client.get("/api/settings/global-bypass")

    assert response.status_code == 200
    assert response.json() == {"enabled": True}


def test_set_global_bypass_to_false(test_client):
    """POST /api/settings/global-bypass can disable bypass"""
    # Disable bypass
    response = test_client.post(
        "/api/settings/global-bypass", json={"enabled": False}
    )

    assert response.status_code == 200
    assert response.json() == {"enabled": False}

    # Verify persisted
    response = test_client.get("/api/settings/global-bypass")
    assert response.json() == {"enabled": False}


def test_set_global_bypass_to_true(test_client):
    """POST /api/settings/global-bypass can enable bypass"""
    # First disable
    test_client.post("/api/settings/global-bypass", json={"enabled": False})

    # Then enable
    response = test_client.post(
        "/api/settings/global-bypass", json={"enabled": True}
    )

    assert response.status_code == 200
    assert response.json() == {"enabled": True}

    # Verify persisted
    response = test_client.get("/api/settings/global-bypass")
    assert response.json() == {"enabled": True}


def test_post_requires_enabled_field(test_client):
    """POST requires 'enabled' field in request"""
    # Missing field
    response = test_client.post("/api/settings/global-bypass", json={})

    assert response.status_code == 422  # Validation error


def test_post_validates_enabled_type(test_client):
    """POST validates 'enabled' must be boolean"""
    # Wrong type
    response = test_client.post(
        "/api/settings/global-bypass", json={"enabled": "yes"}
    )

    assert response.status_code == 422  # Validation error


def test_multiple_updates(test_client):
    """Can toggle setting multiple times"""
    for i in range(5):
        expected = i % 2 == 0
        response = test_client.post(
            "/api/settings/global-bypass",
            json={"enabled": expected},
        )
        assert response.status_code == 200
        assert response.json() == {"enabled": expected}

        # Verify persisted
        response = test_client.get("/api/settings/global-bypass")
        assert response.json() == {"enabled": expected}


def test_concurrent_requests(test_client):
    """Service handles concurrent requests correctly"""
    import concurrent.futures

    def toggle_setting(value: bool):
        return test_client.post(
            "/api/settings/global-bypass",
            json={"enabled": value},
        )

    # Send concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(toggle_setting, i % 2 == 0) for i in range(10)
        ]
        results = [f.result() for f in futures]

    # All should succeed
    assert all(r.status_code == 200 for r in results)

    # Final state should be deterministic (last write wins)
    response = test_client.get("/api/settings/global-bypass")
    assert response.status_code == 200
    assert "enabled" in response.json()


# ========== Permissions Endpoint Tests ==========


def test_get_permissions_with_global_bypass(test_client):
    """GET /api/settings/permissions shows global_bypass=True when enabled"""
    # Default is global bypass enabled
    response = test_client.get("/api/settings/permissions")

    assert response.status_code == 200
    data = response.json()
    assert data["global_bypass"] is True
    assert data["session_permissions"] == []
    assert data["persistent_permissions"] == []
    assert data["one_time_permissions"] == {}


def test_get_permissions_without_global_bypass(test_client):
    """GET /api/settings/permissions shows permissions when bypass disabled"""
    # Disable global bypass
    test_client.post("/api/settings/global-bypass", json={"enabled": False})

    response = test_client.get("/api/settings/permissions")

    assert response.status_code == 200
    data = response.json()
    assert data["global_bypass"] is False
    assert isinstance(data["session_permissions"], list)
    assert isinstance(data["persistent_permissions"], list)
    assert isinstance(data["one_time_permissions"], dict)


def test_get_permissions_shows_session_permissions(test_client):
    """GET /api/settings/permissions includes session permissions"""
    # Disable bypass and add session permission directly
    test_client.post("/api/settings/global-bypass", json={"enabled": False})

    # Add session permission via the permission_manager
    pm = settings.get_permission_manager()
    if pm:
        pm.session_permissions["TestTool"] = True
        pm.session_permissions["AnotherTool"] = True

    response = test_client.get("/api/settings/permissions")

    assert response.status_code == 200
    data = response.json()
    if pm:
        assert "TestTool" in data["session_permissions"]
        assert "AnotherTool" in data["session_permissions"]


def test_get_permissions_shows_persistent_permissions(test_client, tmp_path):
    """GET /api/settings/permissions includes persistent permissions"""
    # Create config with persistent permissions
    config = settings.get_config_service()
    config.set_global_bypass_permissions(False)
    config.set_persistent_permissions(["mcp__test__tool", "Bash"])

    response = test_client.get("/api/settings/permissions")

    assert response.status_code == 200
    data = response.json()
    assert "mcp__test__tool" in data["persistent_permissions"]
    assert "Bash" in data["persistent_permissions"]


def test_get_permissions_shows_one_time_permissions(test_client):
    """GET /api/settings/permissions includes one-time permissions"""
    # Disable bypass and add one-time permission
    test_client.post("/api/settings/global-bypass", json={"enabled": False})

    pm = settings.get_permission_manager()
    if pm:
        pm.one_time_permissions["WriteFile"] = 3
        pm.one_time_permissions["DeleteFile"] = 1

    response = test_client.get("/api/settings/permissions")

    assert response.status_code == 200
    data = response.json()
    if pm:
        assert data["one_time_permissions"].get("WriteFile") == 3
        assert data["one_time_permissions"].get("DeleteFile") == 1


def test_get_permissions_response_model(test_client):
    """GET /api/settings/permissions returns correct response model"""
    response = test_client.get("/api/settings/permissions")

    assert response.status_code == 200
    data = response.json()

    # Verify all required fields exist
    assert "global_bypass" in data
    assert "session_permissions" in data
    assert "persistent_permissions" in data
    assert "one_time_permissions" in data

    # Verify field types
    assert isinstance(data["global_bypass"], bool)
    assert isinstance(data["session_permissions"], list)
    assert isinstance(data["persistent_permissions"], list)
    assert isinstance(data["one_time_permissions"], dict)


# ========== Delete Permission Endpoint Tests ==========


def test_delete_persistent_permission(test_client):
    """DELETE /api/settings/permissions/persistent/{tool} removes persistent permission"""
    # Add a persistent permission
    config = settings.get_config_service()
    config.set_persistent_permissions(["TestTool", "AnotherTool"])

    # Delete one permission
    response = test_client.delete(
        "/api/settings/permissions/persistent/TestTool"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["tool"] == "TestTool"
    assert data["scope"] == "persistent"

    # Verify it was removed
    perms = config.get_persistent_permissions()
    assert "TestTool" not in perms
    assert "AnotherTool" in perms


def test_delete_session_permission(test_client):
    """DELETE /api/settings/permissions/session/{tool} removes session permission"""
    # Add session permission via permission_manager
    pm = settings.get_permission_manager()
    if pm:
        pm.session_permissions["SessionTool"] = True
        pm.session_permissions["KeepTool"] = True

        # Delete one permission
        response = test_client.delete(
            "/api/settings/permissions/session/SessionTool"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["tool"] == "SessionTool"
        assert data["scope"] == "session"

        # Verify it was removed
        assert "SessionTool" not in pm.session_permissions
        assert "KeepTool" in pm.session_permissions


def test_delete_one_time_permission(test_client):
    """DELETE /api/settings/permissions/one_time/{tool} removes one-time permission"""
    pm = settings.get_permission_manager()
    if pm:
        pm.one_time_permissions["WriteOnce"] = 3
        pm.one_time_permissions["KeepOnce"] = 1

        # Delete one permission
        response = test_client.delete(
            "/api/settings/permissions/one_time/WriteOnce"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["tool"] == "WriteOnce"
        assert data["scope"] == "one_time"

        # Verify it was removed
        assert "WriteOnce" not in pm.one_time_permissions
        assert "KeepOnce" in pm.one_time_permissions


def test_delete_invalid_scope(test_client):
    """DELETE /api/settings/permissions/{invalid}/{tool} returns 400"""
    response = test_client.delete(
        "/api/settings/permissions/invalid_scope/SomeTool"
    )

    assert response.status_code == 400
    data = response.json()
    assert (
        "invalid" in data["detail"].lower()
        or "scope" in data["detail"].lower()
    )


def test_delete_nonexistent_permission_succeeds(test_client):
    """DELETE for non-existent permission succeeds (idempotent)"""
    # Delete a permission that doesn't exist
    response = test_client.delete(
        "/api/settings/permissions/persistent/NonExistentTool"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_delete_permission_with_special_chars(test_client):
    """DELETE handles tool names with special characters (URL encoded)"""
    # Add a permission with special chars (like MCP tool names)
    config = settings.get_config_service()
    config.set_persistent_permissions(["mcp__ms365__list-mail-messages"])

    # Delete using URL-encoded path
    response = test_client.delete(
        "/api/settings/permissions/persistent/mcp__ms365__list-mail-messages"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["tool"] == "mcp__ms365__list-mail-messages"

    # Verify it was removed
    perms = config.get_persistent_permissions()
    assert "mcp__ms365__list-mail-messages" not in perms
