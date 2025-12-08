"""
Integration tests for help routes.

Tests the HTTP /api/help endpoint that provides formatted help
for the local ecosystem.
"""

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from bassi.core_v3.routes.help_routes import create_help_router


@pytest.fixture
def test_app():
    """Create a test FastAPI app with help routes."""
    app = FastAPI()
    help_router = create_help_router()
    app.include_router(help_router)
    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


class TestHelpRoutes:
    """Tests for the help routes."""

    def test_help_overview_endpoint(self, client):
        """Test GET /api/help returns overview."""
        response = client.get("/api/help")
        assert response.status_code == 200

        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "help" in data
        assert "query" in data
        assert data["query"] == "overview"
        assert "items" in data
        assert "items_by_type" in data
        assert "counts" in data
        assert isinstance(data["items"], list)
        if data["items"]:
            first_item = data["items"][0]
            assert "name" in first_item
            assert "type" in first_item

        # Check that help text contains expected content
        help_text = data["help"]
        assert isinstance(help_text, str)
        assert len(help_text) > 0
        # Should mention the ecosystem
        assert (
            "ecosystem" in help_text.lower() or "agent" in help_text.lower()
        )

    def test_help_agents_query(self, client):
        """Test GET /api/help?query=agents returns agent list."""
        response = client.get("/api/help?query=agents")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["query"] == "agents"
        assert "help" in data

        help_text = data["help"]
        # Should mention agents
        assert "agent" in help_text.lower()

    def test_help_skills_query(self, client):
        """Test GET /api/help?query=skills returns skill list."""
        response = client.get("/api/help?query=skills")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["query"] == "skills"
        assert "help" in data

        help_text = data["help"]
        # Should mention skills
        assert "skill" in help_text.lower()

    def test_help_commands_query(self, client):
        """Test GET /api/help?query=commands returns command list."""
        response = client.get("/api/help?query=commands")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["query"] == "commands"
        assert "help" in data

    def test_help_ecosystem_query(self, client):
        """Test GET /api/help?query=ecosystem returns ecosystem map."""
        response = client.get("/api/help?query=ecosystem")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["query"] == "ecosystem"
        assert "help" in data

        help_text = data["help"]
        # Should mention workflows
        assert (
            "workflow" in help_text.lower() or "pattern" in help_text.lower()
        )

    def test_help_specific_skill_query(self, client):
        """Test GET /api/help?query=<skill_name> returns skill details."""
        # Query for a known skill
        response = client.get("/api/help?query=pdf")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["query"] == "pdf"
        assert "help" in data

    def test_help_query_response_format(self, client):
        """Test response format is consistent."""
        response = client.get("/api/help?query=test")
        assert response.status_code == 200

        data = response.json()
        # Check required fields
        assert "success" in data
        assert "query" in data
        assert "help" in data

        # help should be a non-empty string
        assert isinstance(data["help"], str)
        assert len(data["help"]) > 0

        # query should echo back the input
        assert data["query"] == "test"

    def test_help_no_query_parameter(self, client):
        """Test that no query parameter defaults to overview."""
        response = client.get("/api/help")
        assert response.status_code == 200

        data = response.json()
        assert data["query"] == "overview"

    def test_help_empty_query_parameter(self, client):
        """Test that empty query parameter is handled."""
        response = client.get("/api/help?query=")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        # Empty string should be treated as None or overview
        assert "help" in data
