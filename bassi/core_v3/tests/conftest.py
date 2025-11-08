"""
Pytest fixtures for bassi.core_v3 tests.
"""

import asyncio
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
import uvicorn

from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig
from bassi.core_v3.interactive_questions import InteractiveQuestionService
from bassi.core_v3.session_workspace import SessionWorkspace
from bassi.core_v3.tools import create_bassi_tools
from bassi.core_v3.web_server_v3 import WebUIServerV3
from bassi.shared.agent_protocol import AgentClientFactory
from bassi.shared.mcp_registry import create_mcp_registry
from bassi.shared.sdk_loader import create_sdk_mcp_server
from tests.fixtures.mock_agent_client import MockAgentClient


@pytest.fixture
def mock_agent_client() -> MockAgentClient:
    """Provide a mock AgentClient instance scoped per test."""
    return MockAgentClient()


def create_mock_session_factory():
    """
    Create session factory using MockAgentClient for E2E tests.

    This factory creates BassiAgentSession instances that use the mock client
    instead of the real Claude API, allowing tests to run without API keys
    and without making real API calls.
    """

    def mock_client_factory(config: SessionConfig):
        """Factory that creates MockAgentClient instances"""
        return MockAgentClient()

    def factory(
        question_service: InteractiveQuestionService,
        workspace: SessionWorkspace,
    ):
        # Create Bassi interactive tools (including AskUserQuestion)
        bassi_tools = create_bassi_tools(question_service)
        bassi_mcp_server = create_sdk_mcp_server(
            name="bassi-interactive", version="1.0.0", tools=bassi_tools
        )

        # Create MCP registry (minimal for tests)
        mcp_servers = {
            "bassi-interactive": bassi_mcp_server,
        }

        # Generate workspace context
        workspace_context = workspace.get_workspace_context()

        config = SessionConfig(
            allowed_tools=["*"],
            system_prompt=workspace_context,
            permission_mode="bypassPermissions",
            mcp_servers=mcp_servers,
            setting_sources=["project", "local"],
        )

        # Create session with mock client factory
        return BassiAgentSession(config, client_factory=mock_client_factory)

    return factory


@pytest.fixture(scope="session")
@pytest.mark.xdist_group(name="e2e_server")
def live_server():
    """
    Start web server on localhost:8765 for E2E tests.

    Uses mock agent client to avoid real API calls.
    Uses xdist_group to ensure all E2E tests run in same worker (avoids multiple servers).
    Server runs for entire test session and is shared by all E2E tests.
    """
    # Create server with mock session factory
    session_factory = create_mock_session_factory()
    server_instance = WebUIServerV3(session_factory, "localhost", 8765)
    app = server_instance.app

    # Configure uvicorn to run in background thread
    config = uvicorn.Config(
        app=app,
        host="localhost",
        port=8765,
        log_level="error",  # Suppress logs during tests
    )
    server = uvicorn.Server(config)

    # Run server in background thread
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to be ready (check health endpoint)
    base_url = "http://localhost:8765"
    max_retries = 50  # 5 seconds total
    for i in range(max_retries):
        try:
            response = httpx.get(f"{base_url}/health", timeout=0.5)
            if response.status_code == 200:
                print(f"\n✅ Test server ready at {base_url}")
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            if i == max_retries - 1:
                raise RuntimeError(
                    f"Test server failed to start after {max_retries * 0.1}s"
                )
            time.sleep(0.1)

    yield base_url

    # Shutdown server after tests
    server.should_exit = True
    thread.join(timeout=5)
