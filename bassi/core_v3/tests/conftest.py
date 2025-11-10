"""
Pytest fixtures for bassi.core_v3 tests.
"""

import asyncio
import threading
import time
from typing import Any

import httpx
import pytest
import uvicorn

from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig
from bassi.core_v3.interactive_questions import InteractiveQuestionService
from bassi.core_v3.session_workspace import SessionWorkspace
from bassi.core_v3.tools import create_bassi_tools
from bassi.core_v3.web_server_v3 import WebUIServerV3
from bassi.shared.sdk_loader import create_sdk_mcp_server
from tests.fixtures.mock_agent_client import MockAgentClient


@pytest.fixture
def mock_agent_client() -> MockAgentClient:
    """Provide a mock AgentClient instance scoped per test."""
    return MockAgentClient()


class AutoRespondingMockAgentClient(MockAgentClient):
    """
    MockAgentClient that automatically generates simple text responses.

    This enables E2E tests to work without manually queuing responses.
    """

    async def query(
        self, prompt: Any, /, *, session_id: str = "default"
    ) -> None:
        # Call parent to track the query
        await super().query(prompt, session_id=session_id)

        # Auto-generate a simple response if none was queued
        if not self._active_stream:
            from anthropic.types import TextBlock, ContentBlock
            # Simple mock response
            response_text = "Mock agent response"
            text_block = TextBlock(type="text", text=response_text)
            self._active_stream.append(text_block)


def create_mock_session_factory():
    """
    Create session factory using AutoRespondingMockAgentClient for E2E tests.

    This factory creates BassiAgentSession instances that use the mock client
    instead of the real Claude API, allowing tests to run without API keys
    and without making real API calls.
    """

    def mock_client_factory(config: SessionConfig):
        """Factory that creates AutoRespondingMockAgentClient instances"""
        return AutoRespondingMockAgentClient()

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
        session = BassiAgentSession(
            config, client_factory=mock_client_factory
        )
        # Attach workspace to session for later access
        session.workspace = workspace
        return session

    return factory


@pytest.fixture(scope="session")
def live_server():
    """
    Start web server on localhost:8765 for E2E tests.

    Uses mock agent client to avoid real API calls.
    Server runs for entire test session and is shared by all E2E tests.

    NOTE: Tests using this fixture MUST have @pytest.mark.xdist_group(name="e2e_server")
    to ensure they run in the same worker. Markers on fixtures have no effect.
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
    try:
        server.should_exit = True
        # Force shutdown to ensure clean exit
        if hasattr(server, "force_exit"):
            server.force_exit = True
        thread.join(timeout=5)

        # Verify server is actually stopped
        if thread.is_alive():
            print("⚠️ Warning: Server thread still alive after 5s timeout")
    except Exception as e:
        print(f"⚠️ Warning: Error during server shutdown: {e}")
