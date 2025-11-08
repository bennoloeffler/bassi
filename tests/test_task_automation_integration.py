"""
Integration tests for task automation feature

These tests verify the full integration with the agent.
"""

import pytest

from bassi.shared.sdk_loader import SDK_AVAILABLE

pytestmark = pytest.mark.skipif(
    not SDK_AVAILABLE, reason="claude_agent_sdk not installed"
)


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

    agent = BassiAgent()

    # Get the task automation server
    task_server = agent.sdk_mcp_servers["task_automation"]

    # List tools
    tools = await task_server.list_tools()

    # Verify execute_python tool exists
    tool_names = [tool.name for tool in tools]
    assert "execute_python" in tool_names


# Note: Full end-to-end integration tests with Claude API
# would require an API key and would make actual API calls.
# Those are better tested manually or in a separate CI environment.
#
# Example manual test:
# 1. Run bassi
# 2. Say: "create a Python script that prints hello world and run it"
# 3. Verify: Claude calls mcp__task_automation__execute_python
# 4. Verify: Output shows "hello world"
