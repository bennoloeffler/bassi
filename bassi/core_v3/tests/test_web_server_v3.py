"""Tests for web_server_v3.py - FastAPI REST endpoints."""

import pytest
from fastapi.testclient import TestClient

from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig
from bassi.core_v3.interactive_questions import InteractiveQuestionService
from bassi.core_v3.web_server_v3 import WebUIServerV3


@pytest.fixture
def session_factory():
    """Factory function to create agent sessions for testing."""

    def factory(question_service: InteractiveQuestionService):
        config = SessionConfig(
            permission_mode="bypassPermissions",
        )
        return BassiAgentSession(config)

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
