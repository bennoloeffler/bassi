"""
Integration test for agent pool lifecycle manager - REAL agents, NO mocks.

This test verifies the lifecycle manager handles connect/disconnect properly
by using REAL Claude SDK agents. This catches issues like "Attempted to exit
cancel scope in a different task" that only occur with real async code.

Run with:
    uv run pytest bassi/core_v3/tests/integration/test_agent_pool_lifecycle_real.py -v -s

NOTE: These tests are slow (~20-40 seconds each) because they create real agents.
They require ANTHROPIC_API_KEY to be set.
"""

import asyncio
import os

import pytest

from bassi.config import PoolConfig
from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig
from bassi.core_v3.services.agent_pool import (
    AgentPool,
    get_agent_pool,
    reset_agent_pool,
)

# Skip if no API key available
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set - skipping real agent tests",
)


def create_real_agent_factory() -> callable:
    """
    Create factory that returns REAL BassiAgentSession instances.

    These connect to the actual Claude SDK - no mocks!
    """

    def factory() -> BassiAgentSession:
        config = SessionConfig(
            allowed_tools=["*"],
            model_id="claude-haiku-4-5-20251001",  # Cheapest model
            permission_mode="default",
            mcp_servers={},  # No MCP servers for faster startup
            setting_sources=[],  # No settings discovery for faster startup
        )
        return BassiAgentSession(config)

    return factory


@pytest.fixture(autouse=True)
def reset_global_pool():
    """Reset global pool before and after each test."""
    reset_agent_pool()
    yield
    reset_agent_pool()


class TestLifecycleManagerWithRealAgents:
    """
    Test the lifecycle manager with REAL Claude SDK agents.

    These tests catch cancel scope issues that only manifest with real async code.
    """

    @pytest.mark.asyncio
    async def test_lifecycle_manager_handles_disconnect(self):
        """
        Test that lifecycle manager properly handles agent disconnect.

        This catches the "Attempted to exit cancel scope in a different task"
        error that occurs when disconnect is called from a different task than
        the one that called connect.
        """
        factory = create_real_agent_factory()
        config = PoolConfig(initial_size=1, keep_idle_size=0, max_size=2)

        pool = AgentPool(agent_factory=factory, pool_config=config)

        # Start pool - this creates the lifecycle manager
        print("\n📦 Starting agent pool...")
        await pool.start()

        assert pool._started, "Pool should be started"
        assert (
            pool._lifecycle_task is not None
        ), "Lifecycle task should exist"
        assert (
            not pool._lifecycle_task.done()
        ), "Lifecycle task should be running"

        # Acquire an agent
        print("🎯 Acquiring agent...")
        agent = await pool.acquire("test-browser-1")
        assert agent is not None
        assert agent._connected, "Agent should be connected"

        # Release the agent - this should trigger disconnect via lifecycle manager
        print("🔄 Releasing agent (triggers disconnect via lifecycle manager)...")
        await pool.release(agent)

        # Give background tasks time to run
        await asyncio.sleep(1.0)

        # The test passes if no "cancel scope" error was raised
        # Check that lifecycle manager is still running
        assert (
            not pool._lifecycle_task.done()
        ), "Lifecycle manager should still be running after release"

        # Cleanup
        print("🛑 Shutting down pool...")
        await pool.shutdown(force=True)

        print("✅ Test passed - lifecycle manager handled disconnect properly")

    @pytest.mark.asyncio
    async def test_lifecycle_manager_survives_hot_reload(self):
        """
        Test that lifecycle manager is restarted after hot reload (soft shutdown).

        Scenario:
        1. Start pool with agents
        2. Acquire an agent
        3. Soft shutdown (simulates hot reload)
        4. Restart pool
        5. Release agent - should NOT fail with cancel scope error
        6. Acquire new agent - should work
        """
        factory = create_real_agent_factory()
        config = PoolConfig(initial_size=1, keep_idle_size=0, max_size=2)

        pool = AgentPool(agent_factory=factory, pool_config=config)

        # Step 1: Start pool
        print("\n📦 [Step 1] Starting agent pool...")
        await pool.start()
        assert pool._started
        assert not pool._lifecycle_task.done()

        # Step 2: Acquire an agent
        print("🎯 [Step 2] Acquiring agent...")
        agent = await pool.acquire("test-browser-1")
        assert agent._connected

        # Step 3: Soft shutdown (simulates hot reload)
        print("🔄 [Step 3] Soft shutdown (hot reload simulation)...")
        await pool.shutdown(force=False)

        # After soft shutdown:
        # - _shutdown is True
        # - lifecycle manager is stopped
        # - agents are still there (not disconnected)
        assert pool._shutdown, "Pool should be marked as shutdown"

        # Step 4: Restart pool (simulates uvicorn restart after hot reload)
        print("🔄 [Step 4] Restarting pool after hot reload...")
        await pool.start()

        # After restart:
        # - _shutdown should be False
        # - lifecycle manager should be running again
        # - agents should still be available
        assert not pool._shutdown, "Shutdown flag should be reset"
        assert pool._lifecycle_task is not None, "Lifecycle task should exist"
        assert (
            not pool._lifecycle_task.done()
        ), "Lifecycle manager should be running after restart"

        # Step 5: Release the old agent
        # This is the critical test - without the fix, this would fail with
        # "Attempted to exit cancel scope in a different task"
        print(
            "🔄 [Step 5] Releasing agent (should use restarted lifecycle manager)..."
        )
        await pool.release(agent)

        # Give background tasks time to run
        await asyncio.sleep(1.0)

        # Check lifecycle manager is still running
        assert (
            not pool._lifecycle_task.done()
        ), "Lifecycle manager should survive release after hot reload"

        # Step 6: Acquire new agent - should work
        print("🎯 [Step 6] Acquiring new agent after hot reload...")
        new_agent = await pool.acquire("test-browser-2")
        assert new_agent is not None
        assert new_agent._connected

        # Cleanup
        print("🛑 Shutting down pool...")
        await pool.shutdown(force=True)

        print("✅ Test passed - lifecycle manager survives hot reload")

    @pytest.mark.asyncio
    async def test_multiple_acquire_release_cycles(self):
        """
        Test multiple acquire/release cycles don't cause cancel scope errors.

        This catches issues where the lifecycle manager queue gets corrupted
        or tasks get mixed up.
        """
        factory = create_real_agent_factory()
        config = PoolConfig(initial_size=1, keep_idle_size=0, max_size=3)

        pool = AgentPool(agent_factory=factory, pool_config=config)

        print("\n📦 Starting pool...")
        await pool.start()

        # Run 3 cycles of acquire/release
        for i in range(3):
            print(f"\n🔄 Cycle {i + 1}/3")

            # Acquire
            print(f"  🎯 Acquiring agent...")
            agent = await pool.acquire(f"browser-{i}")
            assert agent._connected

            # Small delay
            await asyncio.sleep(0.5)

            # Release
            print(f"  🔓 Releasing agent...")
            await pool.release(agent)

            # Wait for replacement
            await asyncio.sleep(1.0)

            # Check lifecycle manager still running
            assert (
                not pool._lifecycle_task.done()
            ), f"Lifecycle manager died in cycle {i + 1}"

        print("\n🛑 Shutting down...")
        await pool.shutdown(force=True)

        print("✅ Test passed - multiple cycles work correctly")


class TestGetAgentPoolSingleton:
    """Test the get_agent_pool singleton function with real agents."""

    @pytest.mark.asyncio
    async def test_singleton_lifecycle_after_hot_reload(self):
        """
        Test the global singleton properly restarts lifecycle manager.

        This is closer to real-world usage where get_agent_pool() is called.
        """
        factory = create_real_agent_factory()
        config = PoolConfig(initial_size=1, keep_idle_size=0, max_size=2)

        # Get singleton pool
        print("\n📦 Getting singleton pool...")
        pool1 = get_agent_pool(agent_factory=factory, pool_config=config)
        await pool1.start()

        assert pool1._started
        assert not pool1._lifecycle_task.done()

        # Acquire agent
        print("🎯 Acquiring agent...")
        agent = await pool1.acquire("browser-1")

        # Soft shutdown
        print("🔄 Soft shutdown...")
        await pool1.shutdown(force=False)

        # Get pool again (simulates new request after hot reload)
        print("🔄 Getting pool again after shutdown...")
        pool2 = get_agent_pool(agent_factory=factory)

        # Should be same pool object (singleton)
        assert pool2 is pool1, "Should get same singleton pool"

        # Start again
        print("🔄 Restarting pool...")
        await pool2.start()

        # Lifecycle manager should be running
        assert not pool2._lifecycle_task.done()

        # Release should work
        print("🔓 Releasing agent...")
        await pool2.release(agent)
        await asyncio.sleep(1.0)

        # Lifecycle manager should still be running
        assert not pool2._lifecycle_task.done()

        # Cleanup
        print("🛑 Full shutdown...")
        await pool2.shutdown(force=True)

        print("✅ Test passed - singleton survives hot reload")
