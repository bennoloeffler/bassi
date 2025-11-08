"""
Tests for agent integration

Note: These are basic tests. Full integration tests require API key.
"""

import pytest

from bassi.config import ConfigManager


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
