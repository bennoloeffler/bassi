"""
Integration tests for task automation feature

These tests verify the full integration with the agent.
"""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_task_automation_server_registered():
    """Test that task automation server is registered in agent"""
    from bassi.agent import BassiAgent

    # Initialize agent
    agent = BassiAgent()

    # Verify task_automation server is registered
    assert "task_automation" in agent.sdk_mcp_servers
    assert agent.sdk_mcp_servers["task_automation"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_task_automation_tools_available():
    """Test that task automation tools are available"""
    from bassi.agent import BassiAgent
    from bassi.shared.sdk_loader import SDK_AVAILABLE

    agent = BassiAgent()

    # Get the task automation server entry
    task_server_entry = agent.sdk_mcp_servers["task_automation"]

    # The agent wraps MCP servers in a dict with metadata
    assert isinstance(task_server_entry, dict)
    assert "type" in task_server_entry
    assert "name" in task_server_entry

    if SDK_AVAILABLE:
        # When SDK is available, verify the server is properly configured
        assert task_server_entry["type"] == "sdk"
        assert task_server_entry["name"] == "task_automation"
        assert "instance" in task_server_entry

        # Verify we have an MCP Server instance
        server = task_server_entry["instance"]
        from mcp.server.lowlevel.server import Server

        assert isinstance(server, Server)
        assert server.name == "task_automation"
        assert server.version == "1.0.0"

        # Note: list_tools() is a decorator factory in MCP Server API,
        # not a method to list tools. Tools are registered via decorators.
        # To truly verify tools, we'd need to make an actual request to the server.
    else:
        # When SDK is not available, tools are directly in the dict as functions
        assert "tools" in task_server_entry
        tool_funcs = task_server_entry["tools"]
        assert len(tool_funcs) > 0
        # Verify task_automation_execute_python function is present
        tool_names = [func.__name__ for func in tool_funcs]
        assert "task_automation_execute_python" in tool_names


# Note: Full end-to-end integration tests with Claude API
# would require an API key and would make actual API calls.
# Those are better tested manually or in a separate CI environment.
#
# Example manual test:
# 1. Run bassi
# 2. Say: "create a Python script that prints hello world and run it"
# 3. Verify: Claude calls mcp__task_automation__execute_python
# 4. Verify: Output shows "hello world"
