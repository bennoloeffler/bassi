"""
Tests for agent integration

Note: These are basic tests. Full integration tests require API key.
"""

import pytest

from bassi.config import ConfigManager
from bassi.shared.sdk_types import AssistantMessage, ResultMessage, TextBlock
from tests.fixtures.mock_agent_client import MockAgentClient


def test_agent_imports():
    """Test that agent module imports correctly"""
    from bassi.agent import BassiAgent

    assert BassiAgent is not None


def test_agent_initialization_requires_api_key(tmp_path, monkeypatch):
    """Test that agent initialization succeeds with SDK (API key checked at runtime)"""
    from bassi.agent import BassiAgent

    # Mock config without API key
    test_config_dir = tmp_path / ".bassi"
    test_config_file = test_config_dir / "config.json"

    monkeypatch.setattr(ConfigManager, "CONFIG_DIR", test_config_dir)
    monkeypatch.setattr(ConfigManager, "CONFIG_FILE", test_config_file)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    # Clear singleton
    import bassi.config

    bassi.config._config_manager = None

    # SDK-based agent initializes successfully (API key checked when chat starts)
    agent = BassiAgent()
    assert agent is not None
    assert agent.sdk_mcp_servers is not None


def test_agent_chat_integration():
    """
    Integration test for agent chat

    This test is skipped by default. To run it:
    1. Set ANTHROPIC_API_KEY in environment
    2. Remove the skip decorator

    Requires actual API key and makes real API calls.
    """
    pytest.skip("Integration test - requires API key")

    from bassi.agent import BassiAgent

    agent = BassiAgent()
    response = agent.chat("What is 2+2?")

    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 0


def test_agent_has_mcp_servers():
    """Test that agent has the expected MCP servers configured"""
    import os

    # Set dummy API key for testing structure
    os.environ["ANTHROPIC_API_KEY"] = "test-key"

    from bassi.agent import BassiAgent

    agent = BassiAgent()

    # Check SDK MCP servers are registered
    assert "bash" in agent.sdk_mcp_servers
    assert "web" in agent.sdk_mcp_servers
    assert "task_automation" in agent.sdk_mcp_servers
    assert len(agent.sdk_mcp_servers) == 3

    # Check options are configured
    assert agent.options is not None
    assert agent.options.mcp_servers is not None
    assert "bash" in agent.options.mcp_servers
    assert "web" in agent.options.mcp_servers

    # Clean up
    del os.environ["ANTHROPIC_API_KEY"]


def test_agent_permission_mode_from_env(monkeypatch):
    """Agent should honor BASSI_PERMISSION_MODE env override."""
    from bassi.agent import BassiAgent

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("BASSI_PERMISSION_MODE", "acceptEdits")
    monkeypatch.setattr("bassi.agent.create_sdk_mcp_servers", lambda: {})
    monkeypatch.setattr("bassi.agent.load_external_mcp_servers", lambda: {})

    agent = BassiAgent(display_tools=False)

    assert agent.session_config.permission_mode == "acceptEdits"


def test_agent_reset():
    """Test conversation reset functionality"""
    import os

    # Set dummy API key
    os.environ["ANTHROPIC_API_KEY"] = "test-key"

    from bassi.agent import BassiAgent

    agent = BassiAgent()

    # SDK manages conversation history internally
    # Reset should clear the client (will be recreated on next chat)
    assert agent.client is None  # No client until first chat

    # Reset should work even without active client
    import anyio

    anyio.run(agent.reset)
    assert agent.client is None

    # Clean up
    del os.environ["ANTHROPIC_API_KEY"]


@pytest.mark.asyncio
async def test_agent_chat_with_mock_client(monkeypatch):
    """BassiAgent supports dependency injection via AgentClientFactory."""
    from bassi.agent import BassiAgent

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_client = MockAgentClient()
    mock_client.queue_response(
        AssistantMessage(
            content=[TextBlock(text="hi there")], model="test-model"
        ),
        ResultMessage(
            subtype="complete",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="test-session",
            usage={"input_tokens": 1, "output_tokens": 2},
        ),
    )

    agent = BassiAgent(client_factory=lambda _config: mock_client)

    messages = []
    async for item in agent.chat("Hello world"):
        messages.append(item)

    assert len(messages) == 2
    assert mock_client.sent_prompts[0]["prompt"] == "Hello world"


@pytest.mark.asyncio
async def test_agent_interrupt_with_mock(monkeypatch):
    """Test that interrupt() delegates to the mock client."""
    from bassi.agent import BassiAgent

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_client = MockAgentClient()
    mock_client.queue_response(
        AssistantMessage(
            content=[TextBlock(text="counting")], model="test-model"
        ),
        ResultMessage(
            subtype="complete",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="test-session",
            usage={"input_tokens": 1, "output_tokens": 2},
        ),
    )

    agent = BassiAgent(client_factory=lambda _config: mock_client)

    # Start a query
    await agent._ensure_client()

    # Interrupt should delegate to client
    await agent.interrupt()

    assert mock_client.interrupted is True


@pytest.mark.asyncio
async def test_agent_verbose_mode_with_mock(monkeypatch):
    """Test that verbose mode can be toggled with mock client."""
    from bassi.agent import BassiAgent

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_client = MockAgentClient()

    agent = BassiAgent(
        client_factory=lambda _config: mock_client, display_tools=False
    )

    # Initially verbose mode is ON (default True)
    assert agent.verbose is True

    # Toggle verbose mode to OFF
    result = agent.toggle_verbose()

    assert agent.verbose is False
    assert result is False

    # Toggle again to ON
    result = agent.toggle_verbose()

    assert agent.verbose is True
    assert result is True


@pytest.mark.asyncio
async def test_agent_accepts_custom_factory(monkeypatch):
    """Test that agent accepts and uses custom client factory."""
    from bassi.agent import BassiAgent

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    factory_called = []

    def custom_factory(config):
        factory_called.append(config)
        mock = MockAgentClient()
        mock.queue_response(
            AssistantMessage(
                content=[TextBlock(text="custom")], model="test-model"
            ),
            ResultMessage(
                subtype="complete",
                duration_ms=100,
                duration_api_ms=80,
                is_error=False,
                num_turns=1,
                usage={"input_tokens": 1, "output_tokens": 2},
            ),
        )
        return mock

    agent = BassiAgent(client_factory=custom_factory, display_tools=False)

    # Factory should not be called until first chat
    assert len(factory_called) == 0

    # Chat should trigger factory
    messages = []
    async for item in agent.chat("Test"):
        messages.append(item)

    # Factory should have been called once
    assert len(factory_called) == 1
    # Should have received messages (either typed events or raw SDK messages)
    assert len(messages) >= 1


@pytest.mark.asyncio
async def test_agent_reset_clears_mock_client(monkeypatch):
    """Test that reset() clears mock client state properly."""
    from bassi.agent import BassiAgent

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock_client = MockAgentClient()
    mock_client.queue_response(
        AssistantMessage(
            content=[TextBlock(text="before reset")], model="test-model"
        ),
        ResultMessage(
            subtype="complete",
            duration_ms=100,
            duration_api_ms=80,
            is_error=False,
            num_turns=1,
            session_id="test-session",
            usage={"input_tokens": 1, "output_tokens": 2},
        ),
    )

    agent = BassiAgent(client_factory=lambda _config: mock_client)

    # Chat to create client
    async for _ in agent.chat("First"):
        pass

    assert agent.client is not None
    assert mock_client.connected is True

    # Reset should clear client
    await agent.reset()

    assert agent.client is None
    assert mock_client.connected is False
