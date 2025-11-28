"""Unit tests for agent_pool.py - Context isolation and agent lifecycle."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bassi.core_v3.services.agent_pool import AgentPool, PooledAgent, reset_agent_pool


@pytest.fixture
def mock_agent():
    """Create a mock BassiAgentSession for testing."""
    agent = MagicMock()
    agent.message_history = ["msg1", "msg2"]
    agent.stats = MagicMock()
    agent.stats.message_count = 5
    agent.stats.tool_calls = 3
    agent.current_workspace_id = "test-workspace-123"
    agent._conversation_context = "Previous chat context about user identity"
    agent.workspace = MagicMock()
    agent.question_service = MagicMock()
    agent.connect = AsyncMock()
    agent.disconnect = AsyncMock()
    return agent


@pytest.fixture
def mock_agent_factory(mock_agent):
    """Create a factory that returns the mock agent."""
    def factory():
        return mock_agent
    return factory


@pytest.fixture(autouse=True)
def reset_pool():
    """Reset global pool before and after each test."""
    reset_agent_pool()
    yield
    reset_agent_pool()


class TestAgentPoolRelease:
    """Tests for agent release and context isolation."""

    @pytest.mark.asyncio
    async def test_release_clears_conversation_context(self, mock_agent, mock_agent_factory):
        """
        CRITICAL: Test that releasing an agent clears _conversation_context.

        This prevents conversation history from leaking between different
        chat sessions when agents are reused from the pool.

        Bug scenario before fix:
        1. User A chats, introduces self as "Benno"
        2. Agent released back to pool (but _conversation_context retained!)
        3. User B gets same agent, introduces self as "Rumpelstilzchen"
        4. Agent resumes User A's chat - confused identities!
        """
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)

        # Manually add the agent to pool (skip actual connection)
        pool._agents.append(PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1"))
        pool._started = True

        # Verify agent has conversation context
        assert mock_agent._conversation_context is not None
        assert "Previous chat" in mock_agent._conversation_context

        # Release agent back to pool
        await pool.release(mock_agent)

        # CRITICAL: Conversation context must be cleared
        assert mock_agent._conversation_context is None, (
            "_conversation_context was not cleared on release! "
            "This causes context leakage between chat sessions."
        )

    @pytest.mark.asyncio
    async def test_release_clears_message_history(self, mock_agent, mock_agent_factory):
        """Test that releasing an agent clears message_history."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pool._agents.append(PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1"))
        pool._started = True

        assert len(mock_agent.message_history) > 0

        await pool.release(mock_agent)

        # message_history should be empty after release
        assert len(mock_agent.message_history) == 0

    @pytest.mark.asyncio
    async def test_release_clears_stats(self, mock_agent, mock_agent_factory):
        """Test that releasing an agent resets stats."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pool._agents.append(PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1"))
        pool._started = True

        await pool.release(mock_agent)

        assert mock_agent.stats.message_count == 0
        assert mock_agent.stats.tool_calls == 0

    @pytest.mark.asyncio
    async def test_release_clears_workspace_id(self, mock_agent, mock_agent_factory):
        """Test that releasing an agent clears current_workspace_id."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pool._agents.append(PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1"))
        pool._started = True

        assert mock_agent.current_workspace_id is not None

        await pool.release(mock_agent)

        assert mock_agent.current_workspace_id is None

    @pytest.mark.asyncio
    async def test_release_clears_workspace_reference(self, mock_agent, mock_agent_factory):
        """Test that releasing an agent clears workspace reference."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pool._agents.append(PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1"))
        pool._started = True

        assert mock_agent.workspace is not None

        await pool.release(mock_agent)

        assert mock_agent.workspace is None

    @pytest.mark.asyncio
    async def test_release_clears_question_service(self, mock_agent, mock_agent_factory):
        """Test that releasing an agent clears question_service reference."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pool._agents.append(PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1"))
        pool._started = True

        assert mock_agent.question_service is not None

        await pool.release(mock_agent)

        assert mock_agent.question_service is None

    @pytest.mark.asyncio
    async def test_release_marks_agent_available(self, mock_agent, mock_agent_factory):
        """Test that releasing an agent marks it as available."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pooled = PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1")
        pool._agents.append(pooled)
        pool._started = True

        await pool.release(mock_agent)

        assert pooled.in_use is False
        assert pooled.browser_id is None


class TestAgentPoolContextIsolation:
    """Integration-style tests for context isolation between chat sessions."""

    @pytest.mark.asyncio
    async def test_agent_reuse_has_clean_state(self, mock_agent_factory):
        """
        Test that an agent reused from pool starts with clean state.

        Simulates:
        1. Browser A acquires agent, uses it
        2. Browser A disconnects, agent released
        3. Browser B acquires same agent
        4. Agent should have NO context from Browser A
        """
        # Create fresh mock for this test
        agent = MagicMock()
        agent.message_history = []
        agent.stats = MagicMock()
        agent.stats.message_count = 0
        agent.stats.tool_calls = 0
        agent.current_workspace_id = None
        agent._conversation_context = None
        agent.workspace = None
        agent.question_service = None
        agent.connect = AsyncMock()

        def factory():
            return agent

        pool = AgentPool(size=1, agent_factory=factory)
        pool._agents.append(PooledAgent(agent=agent, in_use=False))
        pool._started = True

        # Browser A acquires
        acquired_agent = await pool.acquire("browser-A")
        assert acquired_agent is agent

        # Simulate Browser A usage
        agent.message_history = ["user: I am Benno", "assistant: Hello Benno"]
        agent.stats.message_count = 2
        agent._conversation_context = "User introduced as Benno"
        agent.current_workspace_id = "chat-A"
        agent.workspace = MagicMock()

        # Browser A disconnects
        await pool.release(agent)

        # Verify clean state
        assert agent._conversation_context is None
        assert agent.current_workspace_id is None
        assert agent.workspace is None

        # Browser B acquires (same agent from pool)
        acquired_agent_b = await pool.acquire("browser-B")
        assert acquired_agent_b is agent  # Same agent reused

        # Agent should be clean for Browser B
        # (no leftover context from Browser A)
        assert agent._conversation_context is None
