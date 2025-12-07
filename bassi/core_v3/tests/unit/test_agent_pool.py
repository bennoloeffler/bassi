"""Unit tests for agent_pool.py - Context isolation and agent lifecycle."""

import asyncio
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
    agent.clear_server_context = AsyncMock()
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
    """Tests for agent release (destroy and replace model)."""

    @pytest.mark.asyncio
    async def test_release_removes_agent_from_pool(
        self, mock_agent
    ):
        """
        Test that releasing an agent REMOVES it from the pool.

        With destroy-and-replace model, agents are not reused.
        """
        # Use a factory that creates DISTINCT agents (not the released one)
        def factory():
            agent = MagicMock()
            agent.connect = AsyncMock()
            agent.disconnect = AsyncMock()
            return agent

        pool = AgentPool(size=1, agent_factory=factory)

        # Manually add the agent to pool
        pool._agents.append(
            PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1")
        )
        pool._started = True

        # Verify agent is in pool
        assert len(pool._agents) == 1
        assert pool._agents[0].agent is mock_agent

        # Release agent
        await pool.release(mock_agent)

        # Allow background tasks to run
        await asyncio.sleep(0.1)

        # Agent should be removed from pool (replacement is a different agent)
        assert all(p.agent is not mock_agent for p in pool._agents), (
            "Released agent should be removed from pool"
        )

    @pytest.mark.asyncio
    async def test_release_calls_disconnect(
        self, mock_agent, mock_agent_factory
    ):
        """Test that releasing an agent calls disconnect."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pool._agents.append(
            PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1")
        )
        pool._started = True

        await pool.release(mock_agent)

        # Allow background tasks to run
        await asyncio.sleep(0.1)

        # Disconnect should be called in background
        mock_agent.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_creates_replacement_agent(
        self, mock_agent
    ):
        """Test that releasing an agent triggers creation of a replacement."""
        from bassi.config import PoolConfig

        agents_created = []

        def factory():
            agent = MagicMock()
            agent.connect = AsyncMock()
            agent.disconnect = AsyncMock()
            agents_created.append(agent)
            return agent

        config = PoolConfig(initial_size=2, keep_idle_size=1, max_size=5)
        pool = AgentPool(agent_factory=factory, pool_config=config)
        pool._agents.append(
            PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1")
        )
        pool._started = True

        initial_count = len(agents_created)

        await pool.release(mock_agent)

        # Allow background tasks to run (replacement creation)
        await asyncio.sleep(0.2)

        # A replacement agent should have been created
        assert len(agents_created) > initial_count, (
            "Replacement agent should be created after release"
        )

    @pytest.mark.asyncio
    async def test_release_increments_total_releases(
        self, mock_agent, mock_agent_factory
    ):
        """Test that releasing an agent increments release counter."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pool._agents.append(
            PooledAgent(agent=mock_agent, in_use=True, browser_id="browser-1")
        )
        pool._started = True

        assert pool._total_releases == 0

        await pool.release(mock_agent)

        assert pool._total_releases == 1

    @pytest.mark.asyncio
    async def test_release_unknown_agent_logs_warning(
        self, mock_agent, mock_agent_factory
    ):
        """Test that releasing an unknown agent logs warning and returns."""
        pool = AgentPool(size=1, agent_factory=mock_agent_factory)
        pool._started = True
        # Don't add agent to pool

        # Should not raise, just log warning
        await pool.release(mock_agent)

        # disconnect should NOT be called since agent wasn't in pool
        mock_agent.disconnect.assert_not_called()


class TestAgentPoolContextIsolation:
    """Integration-style tests for context isolation between chat sessions."""

    @pytest.mark.asyncio
    async def test_new_chat_gets_fresh_agent(self):
        """
        Test that after release, the next acquire gets a FRESH agent.

        With destroy-and-replace model:
        1. Browser A acquires agent1
        2. Browser A releases agent1 (destroyed)
        3. Browser B acquires agent2 (fresh, from factory)
        4. agent2 has NO context from agent1
        """
        agents_created = []

        def factory():
            agent = MagicMock()
            agent.message_history = []
            agent.stats = MagicMock()
            agent.stats.message_count = 0
            agent._conversation_context = None
            agent.connect = AsyncMock()
            agent.disconnect = AsyncMock()
            agents_created.append(agent)
            return agent

        from bassi.config import PoolConfig
        config = PoolConfig(initial_size=1, keep_idle_size=1, max_size=3)
        pool = AgentPool(agent_factory=factory, pool_config=config)
        pool._started = True

        # Pre-populate with one agent
        first_agent = factory()
        pool._agents.append(PooledAgent(agent=first_agent, in_use=False))

        # Browser A acquires
        agent_a = await pool.acquire("browser-A")
        assert agent_a is first_agent

        # Simulate Browser A usage - pollute the agent
        agent_a._conversation_context = "User introduced as Benno"
        agent_a.message_history = ["I am Benno"]

        # Browser A disconnects - agent destroyed
        await pool.release(agent_a)

        # Allow background tasks to run (replacement creation)
        await asyncio.sleep(0.2)

        # Browser B acquires - should get a DIFFERENT agent
        agent_b = await pool.acquire("browser-B")

        # Agent B should be fresh (from factory)
        assert agent_b._conversation_context is None, (
            "New agent should have no conversation context"
        )
        assert agent_b.message_history == [], (
            "New agent should have empty message history"
        )


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
        import time

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
    async def test_acquire_succeeds_when_replacement_created_during_wait(self):
        """Test that acquire succeeds when a replacement agent becomes available.

        With destroy-and-replace model:
        1. Pool at max, all in use
        2. New browser waits for agent
        3. Old browser releases agent (triggers replacement creation)
        4. Waiting browser gets the replacement agent
        """
        from bassi.config import PoolConfig
        import time

        agents_created = []

        def factory():
            agent = self._create_mock_agent()
            agents_created.append(agent)
            return agent

        # Pool with max_size=2
        config = PoolConfig(initial_size=1, keep_idle_size=0, max_size=2)
        pool = AgentPool(agent_factory=factory, pool_config=config)

        # Pre-populate with 2 agents (at max), both in use
        agent1 = self._create_mock_agent()
        agent2 = self._create_mock_agent()
        pool._agents.append(PooledAgent(agent=agent1, in_use=True, browser_id="b1"))
        pool._agents.append(PooledAgent(agent=agent2, in_use=True, browser_id="b2"))
        pool._started = True

        # Schedule agent release after 0.5 seconds
        async def delayed_release():
            await asyncio.sleep(0.5)
            await pool.release(agent1)

        release_task = asyncio.create_task(delayed_release())

        # Try to acquire - should wait and then succeed when replacement is created
        start = time.time()
        acquired_agent = await pool.acquire("browser-3")
        elapsed = time.time() - start

        # Should have acquired the REPLACEMENT agent (not agent1)
        assert acquired_agent is not agent1, "Should get replacement, not the destroyed agent"
        assert elapsed >= 0.4, f"Should have waited for release, got {elapsed:.2f}s"
        assert elapsed < 3.0, f"Waited too long: {elapsed:.2f}s"

        await release_task

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
