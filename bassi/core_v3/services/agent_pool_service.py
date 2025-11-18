"""
Agent Pool Service - Manages a pool of pre-connected agent sessions.

BLACK BOX INTERFACE:
- acquire() -> BassiAgentSession (get agent from pool, instant if available)
- release(agent) -> None (return agent to pool, stays connected)
- get_stats() -> dict (pool metrics: utilization, health, performance)
- shutdown() -> None (disconnect all agents, cleanup)

PRIMITIVE:
- BassiAgentSession (pre-connected, reusable agent instances)

IMPLEMENTATION:
- Pre-warms N agents on startup
- Lazy expansion up to max_size
- Idle timeout shrinking
- Thread-safe async operations

DEPENDENCIES: BassiAgentSession, SessionConfig
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from bassi.core_v3.agent_session import BassiAgentSession, SessionConfig

logger = logging.getLogger(__name__)


@dataclass
class PoolConfig:
    """Configuration for agent session pool."""

    initial_size: int = 2  # Pre-warm on startup
    max_size: int = 10  # Maximum pool size
    idle_timeout_seconds: int = 300  # 5 minutes
    health_check_interval: int = 60  # Check every 60s
    max_acquire_wait_seconds: int = 30  # Block for 30s max


@dataclass
class PoolAgent:
    """Wrapper for agent with pool metadata."""

    agent: BassiAgentSession
    acquired: bool = False
    last_released: float = field(default_factory=time.time)
    acquire_count: int = 0
    error_count: int = 0


class AgentPoolService:
    """
    Service for managing a pool of pre-connected agent sessions.

    Black Box Implementation:
    - Hides connection management complexity
    - Provides instant agent acquisition
    - Automatic scaling and health management
    - Clean async interface

    Example:
        ```python
        pool = AgentPoolService(pool_config, session_config)
        await pool.initialize()

        # Get agent (instant if available)
        agent = await pool.acquire()
        try:
            async for msg in agent.query("Hello"):
                print(msg)
        finally:
            await pool.release(agent)
        ```
    """

    def __init__(
        self,
        pool_config: Optional[PoolConfig] = None,
        session_config: Optional[SessionConfig] = None,
        session_factory: Optional[Callable[[], BassiAgentSession]] = None,
    ):
        """
        Initialize agent pool service.

        Args:
            pool_config: Pool configuration (size, timeouts)
            session_config: Agent session configuration (model, tools, etc)
            session_factory: Optional factory for creating agent sessions
        """
        self.pool_config = pool_config or PoolConfig()
        self.session_config = session_config or SessionConfig()
        self.session_factory = session_factory

        # Pool state
        self._lock = asyncio.Lock()
        self._agents: list[PoolAgent] = []
        self._wait_condition = asyncio.Condition(self._lock)

        # Statistics
        self._total_acquisitions = 0
        self._total_releases = 0
        self._total_spawn_count = 0
        self._acquisition_times: list[float] = []

        # Background tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._shrink_task: Optional[asyncio.Task] = None
        self._shutdown = False

    async def initialize(self):
        """
        Initialize pool by pre-warming agents.

        This spawns initial_size agents in parallel, reducing startup time.
        """
        logger.info(
            f"🏊 [POOL] Initializing with {self.pool_config.initial_size} agents..."
        )
        start_time = time.time()

        # Spawn initial agents in parallel
        spawn_tasks = [
            self._spawn_agent() for _ in range(self.pool_config.initial_size)
        ]
        agents = await asyncio.gather(*spawn_tasks, return_exceptions=True)

        # Count successful spawns
        success_count = sum(1 for a in agents if isinstance(a, PoolAgent))

        elapsed = time.time() - start_time
        logger.info(
            f"✅ [POOL] Initialized {success_count}/{self.pool_config.initial_size} "
            f"agents in {elapsed:.2f}s"
        )

        # Start background tasks
        self._health_check_task = asyncio.create_task(
            self._health_check_loop()
        )
        self._shrink_task = asyncio.create_task(self._shrink_loop())

    async def acquire(self) -> BassiAgentSession:
        """
        Acquire an agent from the pool.

        Returns instantly if idle agent available, otherwise:
        1. Spawns new agent if pool not at max_size
        2. Waits for agent to be released (up to max_acquire_wait_seconds)

        Returns:
            Pre-connected BassiAgentSession

        Raises:
            TimeoutError: If no agent available within timeout
        """
        acquire_start = time.time()

        async with self._lock:
            # Try to get idle agent
            for pool_agent in self._agents:
                if not pool_agent.acquired:
                    pool_agent.acquired = True
                    pool_agent.acquire_count += 1
                    self._total_acquisitions += 1

                    # Track acquisition time
                    elapsed = time.time() - acquire_start
                    self._acquisition_times.append(elapsed)
                    if len(self._acquisition_times) > 100:
                        self._acquisition_times.pop(0)

                    logger.debug(
                        f"🎯 [POOL] Acquired idle agent (took {elapsed*1000:.0f}ms)"
                    )
                    return pool_agent.agent

            # No idle agents - try to spawn if under max_size
            if len(self._agents) < self.pool_config.max_size:
                logger.info(
                    f"📈 [POOL] Spawning new agent ({len(self._agents) + 1}/{self.pool_config.max_size})"
                )
                pool_agent = await self._spawn_agent()
                pool_agent.acquired = True
                pool_agent.acquire_count += 1
                self._total_acquisitions += 1

                elapsed = time.time() - acquire_start
                self._acquisition_times.append(elapsed)
                logger.info(
                    f"✅ [POOL] Spawned and acquired agent in {elapsed:.2f}s"
                )
                return pool_agent.agent

            # Pool exhausted - wait for release
            logger.warning(
                f"⏳ [POOL] Pool exhausted, waiting for release (max {self.pool_config.max_acquire_wait_seconds}s)..."
            )

        # Wait outside of lock to allow releases
        async with self._wait_condition:
            try:
                await asyncio.wait_for(
                    self._wait_condition.wait(),
                    timeout=self.pool_config.max_acquire_wait_seconds,
                )
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"No agent available within {self.pool_config.max_acquire_wait_seconds}s"
                )

        # Recursively try to acquire again
        return await self.acquire()

    async def release(self, agent: BassiAgentSession):
        """
        Release agent back to pool.

        Clears agent state (history, stats) but keeps it connected.

        Args:
            agent: Agent to release
        """
        async with self._lock:
            # Find agent in pool
            for pool_agent in self._agents:
                if pool_agent.agent is agent:
                    # Clear agent state (keep connection alive!)
                    agent.message_history.clear()
                    agent.stats.message_count = 0
                    agent.stats.tool_calls = 0

                    # Mark as idle
                    pool_agent.acquired = False
                    pool_agent.last_released = time.time()
                    self._total_releases += 1

                    logger.debug(
                        f"🔄 [POOL] Released agent (acquired {pool_agent.acquire_count} times)"
                    )
                    break
            else:
                logger.warning(
                    "⚠️ [POOL] Agent not found in pool during release"
                )

        # Notify waiters
        async with self._wait_condition:
            self._wait_condition.notify_all()

    async def get_stats(self) -> dict:
        """
        Get pool statistics.

        Returns:
            Dictionary with pool metrics:
            - total_agents: Total agents in pool
            - idle_agents: Number of available agents
            - active_agents: Number of acquired agents
            - pool_utilization: Fraction of agents in use (0.0 to 1.0)
            - total_acquisitions: Lifetime acquisition count
            - total_releases: Lifetime release count
            - avg_acquisition_ms: Average time to acquire (milliseconds)
        """
        async with self._lock:
            idle_count = sum(1 for a in self._agents if not a.acquired)
            active_count = sum(1 for a in self._agents if a.acquired)
            total_count = len(self._agents)

            avg_acquisition_ms = (
                sum(self._acquisition_times)
                / len(self._acquisition_times)
                * 1000
                if self._acquisition_times
                else 0
            )

            return {
                "total_agents": total_count,
                "idle_agents": idle_count,
                "active_agents": active_count,
                "pool_utilization": (
                    active_count / total_count if total_count > 0 else 0.0
                ),
                "total_acquisitions": self._total_acquisitions,
                "total_releases": self._total_releases,
                "total_spawns": self._total_spawn_count,
                "avg_acquisition_ms": round(avg_acquisition_ms, 2),
            }

    async def shutdown(self):
        """
        Shutdown pool and disconnect all agents.

        Cancels background tasks and cleanly disconnects all agents.
        """
        logger.info("🛑 [POOL] Shutting down...")
        self._shutdown = True

        # Cancel background tasks
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._shrink_task:
            self._shrink_task.cancel()
            try:
                await self._shrink_task
            except asyncio.CancelledError:
                pass

        # Disconnect all agents
        async with self._lock:
            disconnect_tasks = [
                pool_agent.agent.disconnect() for pool_agent in self._agents
            ]
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)
            self._agents.clear()

        logger.info("✅ [POOL] Shutdown complete")

    # --- Internal Methods ---

    async def _spawn_agent(self) -> PoolAgent:
        """
        Spawn and connect a new agent.

        Returns:
            PoolAgent wrapper with connected agent

        Raises:
            Exception: If agent creation or connection fails
        """
        try:
            # Create agent (use factory if provided)
            if self.session_factory:
                agent = self.session_factory()
            else:
                agent = BassiAgentSession(config=self.session_config)

            # Connect agent
            await agent.connect()

            # Wrap in PoolAgent
            pool_agent = PoolAgent(agent=agent)

            # Add to pool
            async with self._lock:
                self._agents.append(pool_agent)
                self._total_spawn_count += 1

            logger.debug(
                f"✅ [POOL] Spawned agent (pool size: {len(self._agents)})"
            )
            return pool_agent

        except Exception as e:
            logger.error(f"❌ [POOL] Failed to spawn agent: {e}")
            raise

    async def _health_check_loop(self):
        """Background task: Check agent health periodically."""
        logger.debug(
            f"🏥 [POOL] Starting health check loop (every {self.pool_config.health_check_interval}s)"
        )

        while not self._shutdown:
            try:
                await asyncio.sleep(self.pool_config.health_check_interval)

                async with self._lock:
                    # Check each agent
                    unhealthy = []
                    for pool_agent in self._agents:
                        if not pool_agent.agent._connected:
                            logger.warning(
                                "⚠️ [POOL] Agent disconnected, marking for removal"
                            )
                            unhealthy.append(pool_agent)

                    # Remove unhealthy agents
                    for pool_agent in unhealthy:
                        self._agents.remove(pool_agent)
                        logger.info(
                            f"🗑️ [POOL] Removed unhealthy agent (pool size: {len(self._agents)})"
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ [POOL] Health check error: {e}")

    async def _shrink_loop(self):
        """Background task: Shrink pool by disconnecting idle agents."""
        logger.debug(
            f"🔻 [POOL] Starting shrink loop (idle timeout: {self.pool_config.idle_timeout_seconds}s)"
        )

        while not self._shutdown:
            try:
                await asyncio.sleep(self.pool_config.idle_timeout_seconds)

                async with self._lock:
                    now = time.time()
                    idle_threshold = (
                        now - self.pool_config.idle_timeout_seconds
                    )
                    min_size = self.pool_config.initial_size

                    # Find agents idle beyond threshold
                    to_remove = []
                    for pool_agent in self._agents:
                        # Keep minimum pool size
                        if len(self._agents) - len(to_remove) <= min_size:
                            break

                        # Only remove truly idle agents
                        if (
                            not pool_agent.acquired
                            and pool_agent.last_released < idle_threshold
                        ):
                            to_remove.append(pool_agent)

                    # Remove idle agents
                    for pool_agent in to_remove:
                        await pool_agent.agent.disconnect()
                        self._agents.remove(pool_agent)
                        logger.info(
                            f"🔻 [POOL] Removed idle agent (pool size: {len(self._agents)})"
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ [POOL] Shrink loop error: {e}")
