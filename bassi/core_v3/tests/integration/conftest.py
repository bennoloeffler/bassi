"""
Integration test fixtures - FastAPI server with httpx.AsyncClient.

INFRASTRUCTURE:
- Uses pytest-asyncio (NOT Playwright)
- One server per test (isolated, ephemeral ports)
- Bulletproof teardown with health checks
"""

import socket
import threading
import time
from typing import Any

import httpx
import pytest
import uvicorn

from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig
from bassi.core_v3.interactive_questions import InteractiveQuestionService
from bassi.core_v3.session_workspace import SessionWorkspace
from bassi.core_v3.tests.fixtures.mock_agent_client import MockAgentClient
from bassi.core_v3.tools import create_bassi_tools
from bassi.core_v3.web_server_v3 import WebUIServerV3
from bassi.shared.sdk_loader import create_sdk_mcp_server


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
            from bassi.shared.sdk_types import (
                AssistantMessage,
                SystemMessage,
                TextBlock,
            )

            # First, send SystemMessage with 'init' subtype containing tools
            # This is what the real SDK sends at the start of a conversation
            init_msg = SystemMessage(
                subtype="init",
                data={
                    "tools": [
                        {"name": "bash"},
                        {"name": "read"},
                        {"name": "write"},
                        {"name": "mcp__bassi-interactive__ask_user_question"},
                    ],
                    "agents": ["mock-agent"],
                    "slash_commands": ["/help", "/clear"],
                    "skills": ["mock-skill"],
                },
            )
            self._active_stream.append(init_msg)

            # Then send the actual response
            response_text = "Mock agent response"
            text_block = TextBlock(text=response_text)
            assistant_msg = AssistantMessage(
                content=[text_block], model="mock-model"
            )
            self._active_stream.append(assistant_msg)


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


def free_port() -> int:
    """Get an ephemeral port from the OS."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    _, port = s.getsockname()
    s.close()
    return port


@pytest.fixture(scope="function")
def running_server(tmp_path):
    """
    Start isolated FastAPI server for integration tests.

    FEATURES:
    - Ephemeral port (no conflicts)
    - Health check before yielding
    - Bulletproof teardown
    - Mock agent client (no API calls)

    Returns:
        dict: {"base_url": "http://127.0.0.1:<port>"}
    """
    port = free_port()

    # Create isolated workspace for this test
    tmp_workspace = tmp_path / "chats"
    tmp_workspace.mkdir()

    # Create server with mock session factory
    session_factory = create_mock_session_factory()
    server_instance = WebUIServerV3(
        workspace_base_path=str(tmp_workspace),
        session_factory=session_factory,
    )
    app = server_instance.app

    # Configure uvicorn
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    # Run in background thread
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"

    # Health probe - wait for server to be ready
    for _ in range(100):
        try:
            with httpx.Client(timeout=0.1) as client:
                response = client.get(f"{base_url}/health")
                if response.status_code == 200:
                    break
        except Exception:
            time.sleep(0.05)
    else:
        pytest.fail("Server did not become healthy in 5 seconds")

    # Yield server info to test
    yield {"base_url": base_url, "workspace": str(tmp_workspace)}

    # Bulletproof teardown
    if hasattr(server, "started") and server.started:
        server.should_exit = True
    thread.join(timeout=3)


@pytest.fixture
def mock_agent_client() -> MockAgentClient:
    """Provide a mock AgentClient instance scoped per test."""
    return MockAgentClient()
