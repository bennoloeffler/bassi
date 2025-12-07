"""Unit tests for agent_pool.py - Context isolation and agent lifecycle."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bassi.core_v3.services.agent_pool import (
    AgentPool,
    PooledAgent,
    PoolExhaustedException,
    reset_agent_pool,
)


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
    agent.clear_server_context = AsyncMock()  # Required for release()
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
    async def test_release_clears_conversation_context(
        self, mock_agent, mock_agent_factory
    ):
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
        pool._agents.append(
            PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1")
        )
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
    async def test_release_clears_message_history(
        self, mock_agent, mock_agent_factory
    ):
        """Test that releasing an agent clears message_history."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pool._agents.append(
            PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1")
        )
        pool._started = True

        assert len(mock_agent.message_history) > 0

        await pool.release(mock_agent)

        # message_history should be empty after release
        assert len(mock_agent.message_history) == 0

    @pytest.mark.asyncio
    async def test_release_clears_stats(self, mock_agent, mock_agent_factory):
        """Test that releasing an agent resets stats."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pool._agents.append(
            PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1")
        )
        pool._started = True

        await pool.release(mock_agent)

        assert mock_agent.stats.message_count == 0
        assert mock_agent.stats.tool_calls == 0

    @pytest.mark.asyncio
    async def test_release_clears_workspace_id(
        self, mock_agent, mock_agent_factory
    ):
        """Test that releasing an agent clears current_workspace_id."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pool._agents.append(
            PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1")
        )
        pool._started = True

        assert mock_agent.current_workspace_id is not None

        await pool.release(mock_agent)

        assert mock_agent.current_workspace_id is None

    @pytest.mark.asyncio
    async def test_release_clears_workspace_reference(
        self, mock_agent, mock_agent_factory
    ):
        """Test that releasing an agent clears workspace reference."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pool._agents.append(
            PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1")
        )
        pool._started = True

        assert mock_agent.workspace is not None

        await pool.release(mock_agent)

        assert mock_agent.workspace is None

    @pytest.mark.asyncio
    async def test_release_clears_question_service(
        self, mock_agent, mock_agent_factory
    ):
        """Test that releasing an agent clears question_service reference."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pool._agents.append(
            PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1")
        )
        pool._started = True

        assert mock_agent.question_service is not None

        await pool.release(mock_agent)

        assert mock_agent.question_service is None

    @pytest.mark.asyncio
    async def test_release_marks_agent_available(
        self, mock_agent, mock_agent_factory
    ):
        """Test that releasing an agent marks it as available."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pooled = PooledAgent(
            agent=mock_agent, in_use=True, browser_id="browser-1"
        )
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
        agent.clear_server_context = AsyncMock()  # Required for release()

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


class TestAgentPoolDynamicSizing:
    """Tests for dynamic pool sizing behavior."""

    def _create_mock_agent(self):
        """Create a fresh mock agent for testing."""
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
        agent.disconnect = AsyncMock()
        agent.clear_server_context = AsyncMock()
        return agent

    @pytest.mark.asyncio
    async def test_on_creating_callback_called_when_pool_exhausted(self):
        """
        Test that on_creating callback is called when a new agent must be created.

        This allows UI to notify user: "Creating new AI assistant (~20 seconds)..."
        """
        from bassi.config import PoolConfig

        agents_created = []

        def factory():
            agent = self._create_mock_agent()
            agents_created.append(agent)
            return agent

        # Pool with max_size=2, starts empty
        config = PoolConfig(initial_size=1, keep_idle_size=0, max_size=2)
        pool = AgentPool(agent_factory=factory, pool_config=config)

        # Manually set up pool with one agent in use
        first_agent = self._create_mock_agent()
        pool._agents.append(PooledAgent(agent=first_agent, in_use=True, browser_id="browser-1"))
        pool._started = True

        # Track if callback was called
        callback_called = False

        def on_creating():
            nonlocal callback_called
            callback_called = True

        # Acquire should trigger on_creating since no agent available
        agent = await pool.acquire("browser-2", on_creating=on_creating)

        assert callback_called, "on_creating callback should be called when creating new agent"
        assert agent is not None
        assert len(pool._agents) == 2

    @pytest.mark.asyncio
    async def test_max_size_limit_respected(self):
        """Test that pool respects max_size limit after brief wait."""
        from bassi.config import PoolConfig

        def factory():
            return self._create_mock_agent()

        # Pool with max_size=2
        config = PoolConfig(initial_size=1, keep_idle_size=0, max_size=2)
        pool = AgentPool(agent_factory=factory, pool_config=config)

        # Pre-populate with 2 agents (at max), both in use
        pool._agents.append(PooledAgent(agent=self._create_mock_agent(), in_use=True, browser_id="b1"))
        pool._agents.append(PooledAgent(agent=self._create_mock_agent(), in_use=True, browser_id="b2"))
        pool._started = True

        # Try to acquire third - should wait briefly (2s) then raise PoolExhaustedException
        # This handles race conditions when browser refreshes (old connection releasing)
        import time
        start = time.time()
        with pytest.raises(PoolExhaustedException) as exc_info:
            await pool.acquire("browser-3", timeout=0.1)
        elapsed = time.time() - start

        # Should have waited ~2 seconds before failing
        assert elapsed >= 1.5, f"Expected ~2s wait, got {elapsed:.2f}s"
        assert elapsed < 4.0, f"Waited too long: {elapsed:.2f}s"

        # Verify exception has correct pool stats
        assert exc_info.value.pool_size == 2
        assert exc_info.value.in_use == 2

    @pytest.mark.asyncio
    async def test_acquire_succeeds_when_agent_released_during_wait(self):
        """Test that acquire succeeds if an agent is released during the brief wait.

        This tests the fix for the race condition when browser refreshes:
        1. Browser disconnects (old connection)
        2. Browser reconnects immediately (new connection)
        3. New connection waits briefly for old agent to be released
        4. Old connection finishes cleanup, releases agent
        5. New connection acquires the released agent
        """
        from bassi.config import PoolConfig
        import asyncio

        def factory():
            return self._create_mock_agent()

        # Pool with max_size=2
        config = PoolConfig(initial_size=1, keep_idle_size=0, max_size=2)
        pool = AgentPool(agent_factory=factory, pool_config=config)

        # Pre-populate with 2 agents (at max), both in use
        agent1 = self._create_mock_agent()
        agent2 = self._create_mock_agent()
        pool._agents.append(PooledAgent(agent=agent1, in_use=True, browser_id="b1"))
        pool._agents.append(PooledAgent(agent=agent2, in_use=True, browser_id="b2"))
        pool._started = True

        # Schedule agent release after 0.5 seconds (simulates old connection cleanup)
        async def delayed_release():
            await asyncio.sleep(0.5)
            await pool.release(agent1)

        release_task = asyncio.create_task(delayed_release())

        # Try to acquire - should wait and then succeed when agent is released
        import time
        start = time.time()
        acquired_agent = await pool.acquire("browser-3")
        elapsed = time.time() - start

        # Should have acquired the released agent
        assert acquired_agent is agent1
        assert elapsed >= 0.4, f"Should have waited for release, got {elapsed:.2f}s"
        assert elapsed < 2.0, f"Waited too long: {elapsed:.2f}s"

        await release_task  # Ensure task completes

    @pytest.mark.asyncio
    async def test_agents_created_on_demand_stat(self):
        """Test that agents_created_on_demand stat is tracked correctly."""
        from bassi.config import PoolConfig

        def factory():
            return self._create_mock_agent()

        config = PoolConfig(initial_size=1, keep_idle_size=0, max_size=5)
        pool = AgentPool(agent_factory=factory, pool_config=config)

        # Start with one agent in use
        pool._agents.append(PooledAgent(agent=self._create_mock_agent(), in_use=True, browser_id="b1"))
        pool._started = True

        assert pool.get_stats()["agents_created_on_demand"] == 0

        # Acquire should create a new one on demand
        await pool.acquire("browser-2")

        assert pool.get_stats()["agents_created_on_demand"] == 1

    @pytest.mark.asyncio
    async def test_get_stats_returns_config_values(self):
        """Test that get_stats includes configuration values."""
        from bassi.config import PoolConfig

        config = PoolConfig(initial_size=5, keep_idle_size=2, max_size=30)
        pool = AgentPool(agent_factory=lambda: self._create_mock_agent(), pool_config=config)
        pool._started = True

        stats = pool.get_stats()

        assert stats["initial_size"] == 5
        assert stats["max_size"] == 30
        assert stats["keep_idle_size"] == 2
        assert stats["growth_in_progress"] == 0

    @pytest.mark.asyncio
    async def test_should_grow_returns_true_when_below_idle_threshold(self):
        """Test that _should_grow correctly detects when pool needs to grow."""
        from bassi.config import PoolConfig

        config = PoolConfig(initial_size=3, keep_idle_size=2, max_size=10)
        pool = AgentPool(agent_factory=lambda: self._create_mock_agent(), pool_config=config)

        # Pool with 3 agents, 2 in use, 1 idle (below keep_idle_size=2)
        pool._agents.append(PooledAgent(agent=self._create_mock_agent(), in_use=True))
        pool._agents.append(PooledAgent(agent=self._create_mock_agent(), in_use=True))
        pool._agents.append(PooledAgent(agent=self._create_mock_agent(), in_use=False))
        pool._started = True

        assert pool._get_idle_count() == 1
        assert pool._should_grow() is True

    @pytest.mark.asyncio
    async def test_should_grow_returns_false_at_max_size(self):
        """Test that _should_grow returns False when at max size."""
        from bassi.config import PoolConfig

        config = PoolConfig(initial_size=2, keep_idle_size=1, max_size=2)
        pool = AgentPool(agent_factory=lambda: self._create_mock_agent(), pool_config=config)

        # Pool at max size (2), with 0 idle
        pool._agents.append(PooledAgent(agent=self._create_mock_agent(), in_use=True))
        pool._agents.append(PooledAgent(agent=self._create_mock_agent(), in_use=True))
        pool._started = True

        assert pool._get_idle_count() == 0
        assert pool._should_grow() is False  # Can't grow, at max

    @pytest.mark.asyncio
    async def test_deprecated_size_parameter_still_works(self):
        """Test backward compatibility with deprecated size parameter."""
        pool = AgentPool(size=3, agent_factory=lambda: self._create_mock_agent())

        assert pool.config.initial_size == 3
        assert pool.size == 3  # Backward compat property
