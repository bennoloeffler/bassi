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
    test_client.post(
        "/api/settings/global-bypass", json={"enabled": False}
    )

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
    response = test_client.post(
        "/api/settings/global-bypass", json={}
    )

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
            executor.submit(toggle_setting, i % 2 == 0)
            for i in range(10)
        ]
        results = [f.result() for f in futures]

    # All should succeed
    assert all(r.status_code == 200 for r in results)

    # Final state should be deterministic (last write wins)
    response = test_client.get("/api/settings/global-bypass")
    assert response.status_code == 200
    assert "enabled" in response.json()
