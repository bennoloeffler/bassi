"""
Agent Pool - Manages a dynamic pool of pre-connected agent instances.

Provides:
- Dynamic pool that grows on demand (up to configurable max)
- Pre-connected agents for instant availability
- Async warmup: first agent ready immediately, rest warm up in background
- Automatic state reset between uses
- **SINGLETON**: Survives hot reloads (agents stay connected)

Configuration (via environment variables):
- AGENT_INITIAL_POOL_SIZE: Agents to create at startup (default 5)
- AGENT_KEEP_IDLE_SIZE: Target idle agents - when idle drops below this, start creating more (default 2)
- AGENT_MAX_POOL_SIZE: Maximum agents in pool (default 30)

Architecture:
- Browser session connects → acquire agent from pool
- If pool running low → create new agents in background
- If no agent available → create one synchronously (user waits ~20s)
- Browser session disconnects → release agent back to pool
- Agents stay connected (expensive to start/stop)
- Agent state cleared between uses (history, workspace)
- Hot reload: Pool persists, only app code reloads

Usage:
    from bassi.config import get_pool_config

    # Get or create singleton pool
    pool = get_agent_pool(agent_factory=my_factory)
    await pool.start()  # Only starts if not already started

    # On browser connect:
    agent, is_new = await pool.acquire(browser_id, on_creating=callback)

    # On browser disconnect:
    await pool.release(agent)

    # On REAL server shutdown (not hot reload):
    await pool.shutdown()
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

from bassi.config import PoolConfig, get_pool_config
from bassi.core_v3.agent_session import BassiAgentSession

logger = logging.getLogger(__name__)


class LifecycleCommand(Enum):
    """Commands for the agent lifecycle manager task."""

    CREATE = auto()  # Create and connect a new agent
    DESTROY = auto()  # Disconnect and destroy an agent
    SHUTDOWN = auto()  # Stop the lifecycle manager


class PoolExhaustedException(Exception):
    """
    Raised when the agent pool is at maximum capacity and all agents are busy.

    This is raised IMMEDIATELY (no waiting) to allow fast user feedback.
    The caller should catch this and notify the user that no agents are available.
    """

    def __init__(self, pool_size: int, in_use: int):
        self.pool_size = pool_size
        self.in_use = in_use
        super().__init__(
            f"All {pool_size} agents are busy. Please try again in a moment."
        )


# ============================================================
# SINGLETON POOL - Survives hot reloads
# ============================================================
_global_pool: Optional["AgentPool"] = None


def get_agent_pool(
    agent_factory: Optional[Callable[[], BassiAgentSession]] = None,
    acquire_timeout: float = 30.0,
    pool_config: Optional[PoolConfig] = None,
    # DEPRECATED: size parameter - use pool_config instead
    size: Optional[int] = None,
) -> "AgentPool":
    """
    Get or create the global agent pool singleton.

    The pool persists across hot reloads so agents stay connected.

    Args:
        agent_factory: Factory to create agents (only used on first call)
        acquire_timeout: Timeout for acquiring agents (before creating new one)
        pool_config: Pool configuration (uses env vars if None)
        size: DEPRECATED - use pool_config.initial_size instead

    Returns:
        The global AgentPool instance
    """
    global _global_pool

    # Use provided config or load from environment
    config = pool_config or get_pool_config()

    # Handle deprecated size parameter
    if size is not None:
        logger.warning(
            "⚠️ [POOL] 'size' parameter is deprecated. Use pool_config instead."
        )
        config.initial_size = size

    if _global_pool is None:
        logger.info("🏊 [POOL] Creating new global agent pool singleton")
        _global_pool = AgentPool(
            agent_factory=agent_factory,
            acquire_timeout=acquire_timeout,
            pool_config=config,
        )
        logger.info(f"🏊 [POOL] Created pool_id={id(_global_pool)}")
    else:
        logger.info(
            f"♻️ [POOL] Reusing existing pool_id={id(_global_pool)}, started={_global_pool._started}, shutdown={_global_pool._shutdown}"
        )
        # If pool was shutdown (soft shutdown from hot reload), reset immediately
        # This ensures acquire() won't fail while waiting for startup event
        if _global_pool._shutdown:
            logger.info(
                "⚠️ [POOL] Pool was soft-shutdown, resetting _shutdown flag immediately (agents preserved)"
            )
            _global_pool._shutdown = False
        # Update factory if provided (allows config changes)
        if agent_factory is not None:
            _global_pool.agent_factory = agent_factory

    return _global_pool


def reset_agent_pool() -> None:
    """
    Reset the global pool (for testing or full restart).

    WARNING: This disconnects all agents!
    """
    global _global_pool
    if _global_pool is not None:
        logger.info("🗑️ [POOL] Resetting global pool")
        _global_pool = None


@dataclass
class PooledAgent:
    """Wrapper for agent with pool metadata."""

    agent: BassiAgentSession
    in_use: bool = False
    acquired_at: Optional[float] = None
    released_at: float = field(default_factory=time.time)
    use_count: int = 0
    browser_id: Optional[str] = None  # Track which browser is using this


@dataclass
class AcquireResult:
    """Result of acquiring an agent from the pool."""

    agent: BassiAgentSession
    created_new: bool = False  # True if agent was created for this request
    wait_time_ms: float = 0.0


class AgentPool:
    """
    Manages a dynamic pool of pre-connected Claude Agent SDK clients.

    Key Features:
    - Dynamic sizing: grows on demand, up to max_size
    - Pre-connected agents for instant availability
    - Async warmup (first agent immediate, rest in background)
    - Proactive growth: starts creating when idle drops below threshold
    - Clean acquire/release for browser sessions
    - State reset between uses
    - User notification when creating new agent
    """

    def __init__(
        self,
        agent_factory: Optional[Callable[[], BassiAgentSession]] = None,
        acquire_timeout: float = 30.0,
        pool_config: Optional[PoolConfig] = None,
        # DEPRECATED: size parameter - use pool_config instead
        size: Optional[int] = None,
    ):
        """
        Initialize agent pool.

        Args:
            agent_factory: Factory function to create agents
            acquire_timeout: Max wait time before creating new agent (seconds)
            pool_config: Pool configuration (uses env vars if None)
            size: DEPRECATED - use pool_config.initial_size instead
        """
        self.config = pool_config or get_pool_config()

        # Handle deprecated size parameter
        if size is not None:
            self.config.initial_size = size

        self.agent_factory = agent_factory
        self.acquire_timeout = acquire_timeout

        # For backward compatibility
        self.size = self.config.initial_size

        # Pool state
        self._agents: list[PooledAgent] = []
        self._lock = asyncio.Lock()
        self._available = asyncio.Condition()  # Signal when agent available

        # Lifecycle state
        self._started = False
        self._shutdown = False
        self._warmup_task: Optional[asyncio.Task] = None
        self._growth_task: Optional[asyncio.Task] = None
        self._growth_in_progress = (
            0  # Number of agents currently being created
        )

        # Lifecycle manager: single task that owns all connect/disconnect operations
        # This ensures anyio cancel scopes are entered and exited from the same task
        self._lifecycle_queue: asyncio.Queue = asyncio.Queue()
        self._lifecycle_task: Optional[asyncio.Task] = None

        # Stats
        self._total_acquires = 0
        self._total_releases = 0
        self._acquire_wait_times: list[float] = []
        self._agents_created_on_demand = (
            0  # Agents created because pool was exhausted
        )

    async def start(self) -> None:
        """
        Start the agent pool.

        Creates and connects the first agent synchronously (blocks until ready).
        Starts background task to warm up remaining initial agents.

        After this returns, at least one agent is ready for use.

        NOTE: This is idempotent and handles hot reload recovery.
        """
        # Log config at startup
        logger.info(
            f"🔧 [POOL CONFIG] INITIAL={self.config.initial_size}, "
            f"IDLE={self.config.keep_idle_size}, MAX={self.config.max_size}"
        )

        # Handle hot reload: if pool was shutdown but we're being started again,
        # reset the shutdown flag (uvicorn hot reload calls shutdown then start)
        if self._shutdown:
            logger.info(
                "♻️ [POOL] Resetting shutdown flag (hot reload recovery)"
            )
            self._shutdown = False

        # CRITICAL: Start/restart lifecycle manager BEFORE early return!
        # The lifecycle manager owns all connect/disconnect operations.
        # Without it, agent disconnect fails with "cancel scope" errors.
        if not self._lifecycle_task or self._lifecycle_task.done():
            logger.info("🔄 [POOL] Starting lifecycle manager...")
            self._lifecycle_task = asyncio.create_task(self._lifecycle_manager())

        if self._started and len(self._agents) > 0:
            # Check if all agents are stuck as in_use (possible hot reload issue)
            in_use_count = sum(1 for a in self._agents if a.in_use)
            if in_use_count == len(self._agents):
                logger.warning(
                    f"⚠️ [POOL] All {in_use_count} agents stuck as in_use after hot reload! "
                    f"Force-releasing all agents..."
                )
                for pooled in self._agents:
                    pooled.in_use = False
                    pooled.browser_id = None
                logger.info("✅ [POOL] Force-released all agents")
            else:
                logger.info(
                    f"♻️ [POOL] Already started with {len(self._agents)} agents "
                    f"({in_use_count} in use, {len(self._agents) - in_use_count} available)"
                )
            return

        # Clamp initial_size to max_size (can't start with more than max allows)
        initial_size = min(self.config.initial_size, self.config.max_size)
        print(
            f"🏊🏊🏊 [POOL] Starting with {initial_size} agents (max: {self.config.max_size})..."
        )
        logger.info(
            f"🏊 [POOL] Starting with {initial_size} agents (max: {self.config.max_size})..."
        )
        start_time = time.time()

        # NOTE: Lifecycle manager is started above (before early return check)
        # to ensure it's running even after hot reload recovery.

        # Create and connect first agent (blocking)
        print("🔶🔶🔶 [POOL] Creating first agent (blocking)...")
        logger.info("🔶 [POOL] Creating first agent (blocking)...")
        first_agent = await self._create_and_connect_agent()

        async with self._lock:
            self._agents.append(PooledAgent(agent=first_agent))

        first_ready_time = time.time() - start_time
        logger.info(f"✅ [POOL] First agent ready in {first_ready_time:.2f}s")

        # Mark as started so browser can connect
        self._started = True

        # Warm up remaining initial agents in background
        remaining = initial_size - 1
        if remaining > 0:
            logger.info(
                f"🔥 [POOL] Warming up {remaining} more agents in background..."
            )
            self._warmup_task = asyncio.create_task(
                self._warmup_remaining(remaining)
            )

    async def _create_and_connect_agent(self) -> BassiAgentSession:
        """
        Create a new agent via the lifecycle manager.

        The lifecycle manager task owns all connect/disconnect operations
        to ensure anyio cancel scopes are entered and exited from the same task.
        """
        if not self.agent_factory:
            raise RuntimeError("No agent_factory configured")

        # If lifecycle manager is running, use it
        if self._lifecycle_task and not self._lifecycle_task.done():
            future: asyncio.Future[BassiAgentSession] = asyncio.Future()
            await self._lifecycle_queue.put((LifecycleCommand.CREATE, future))
            return await future

        # Fallback for initial startup (before lifecycle manager starts)
        agent = self.agent_factory()
        await agent.connect()
        return agent

    async def _lifecycle_manager(self) -> None:
        """
        Single task that owns all agent connect/disconnect operations.

        This ensures anyio cancel scopes are entered and exited from the same task,
        avoiding the "Attempted to exit cancel scope in a different task" error.

        The lifecycle manager processes commands from a queue:
        - CREATE: Create a new agent and resolve the future with it
        - DESTROY: Disconnect an agent
        - SHUTDOWN: Stop the lifecycle manager
        """
        logger.info("🔄 [POOL] Lifecycle manager started")

        while True:
            try:
                # Wait for commands with a timeout to check shutdown flag
                try:
                    cmd, data = await asyncio.wait_for(
                        self._lifecycle_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # Check if we should shutdown
                    if self._shutdown:
                        logger.info(
                            "🔄 [POOL] Lifecycle manager stopping (shutdown)"
                        )
                        break
                    continue

                if cmd == LifecycleCommand.CREATE:
                    # data is a Future to resolve with the created agent
                    future: asyncio.Future[BassiAgentSession] = data
                    try:
                        agent = self.agent_factory()
                        await agent.connect()
                        future.set_result(agent)
                        logger.debug("🔄 [POOL] Lifecycle: agent created")
                    except Exception as e:
                        future.set_exception(e)
                        logger.error(f"🔄 [POOL] Lifecycle: create failed: {e}")

                elif cmd == LifecycleCommand.DESTROY:
                    # data is the agent to destroy
                    agent: BassiAgentSession = data
                    try:
                        await agent.disconnect()
                        logger.debug(
                            "🔄 [POOL] Lifecycle: agent disconnected"
                        )
                    except Exception as e:
                        # Log but don't raise - agent cleanup is best-effort
                        logger.warning(
                            f"🔄 [POOL] Lifecycle: disconnect warning: {e}"
                        )

                elif cmd == LifecycleCommand.SHUTDOWN:
                    logger.info(
                        "🔄 [POOL] Lifecycle manager received shutdown command"
                    )
                    break

            except asyncio.CancelledError:
                logger.info("🔄 [POOL] Lifecycle manager cancelled")
                break
            except Exception as e:
                logger.error(f"🔄 [POOL] Lifecycle manager error: {e}")

        logger.info("🔄 [POOL] Lifecycle manager stopped")

    async def _warmup_remaining(self, count: int) -> None:
        """Warm up additional agents in background."""
        warmup_start = time.time()
        created = 0
        logger.info(
            f"🔥 [POOL] _warmup_remaining: creating {count} agents "
            f"(INITIAL={self.config.initial_size}, MAX={self.config.max_size})"
        )

        for _ in range(count):
            if self._shutdown:
                logger.info("⏹️ [POOL] Warmup cancelled (shutdown)")
                break

            # Check we haven't hit max
            current = len(self._agents)
            if current >= self.config.max_size:
                logger.info(
                    f"⏹️ [POOL] Warmup stopped: hit MAX={self.config.max_size} "
                    f"(current={current})"
                )
                break

            try:
                self._growth_in_progress += 1
                logger.debug(
                    f"🔶 [POOL] Warming agent {len(self._agents) + 1}/{self.config.initial_size}..."
                )
                agent = await self._create_and_connect_agent()

                async with self._lock:
                    self._agents.append(PooledAgent(agent=agent))

                created += 1
                logger.debug(
                    f"✅ [POOL] Agent {len(self._agents)}/{self.config.initial_size} ready"
                )

                # Signal that a new agent is available
                async with self._available:
                    self._available.notify_all()

            except Exception as e:
                logger.error(f"❌ [POOL] Failed to create agent: {e}")
            finally:
                self._growth_in_progress -= 1

        warmup_time = time.time() - warmup_start
        logger.info(
            f"✅ [POOL] Warmup complete: {created}/{count} agents in {warmup_time:.2f}s "
            f"(total: {len(self._agents)})"
        )

    def _get_idle_count(self) -> int:
        """Get number of idle (available) agents."""
        return sum(1 for p in self._agents if not p.in_use)

    def _should_grow(self) -> bool:
        """Check if pool should grow based on idle threshold."""
        current = len(self._agents)
        idle = self._get_idle_count()
        total_with_growing = current + self._growth_in_progress

        if self._shutdown:
            logger.debug("📊 [POOL] _should_grow: NO (shutdown)")
            return False
        if total_with_growing >= self.config.max_size:
            logger.debug(
                f"📊 [POOL] _should_grow: NO (at MAX={self.config.max_size}, "
                f"current={current}, growing={self._growth_in_progress})"
            )
            return False

        should = idle < self.config.keep_idle_size
        logger.debug(
            f"📊 [POOL] _should_grow: {'YES' if should else 'NO'} "
            f"(idle={idle}, IDLE_TARGET={self.config.keep_idle_size}, "
            f"current={current}, MAX={self.config.max_size})"
        )
        return should

    async def _maybe_grow_pool(self) -> None:
        """
        Check if we should grow the pool and start background creation if needed.

        Called after each acquire to maintain minimum idle agents.
        """
        if not self._should_grow():
            return

        # Calculate how many to create
        current = len(self._agents)
        idle = self._get_idle_count()
        needed = self.config.keep_idle_size - idle
        max_can_create = (
            self.config.max_size - current - self._growth_in_progress
        )
        to_create = min(needed, max_can_create)

        logger.info(
            f"📈 [POOL] Growth check: current={current}, idle={idle}, "
            f"IDLE_TARGET={self.config.keep_idle_size}, MAX={self.config.max_size}, "
            f"needed={needed}, max_can_create={max_can_create}, to_create={to_create}"
        )

        if to_create <= 0:
            logger.info(f"📈 [POOL] Not growing: to_create={to_create}")
            return

        logger.info(
            f"📈 [POOL] Growing pool: creating {to_create} agents in background"
        )

        # Create agents in background
        asyncio.create_task(self._grow_agents(to_create))

    async def _grow_agents(self, count: int) -> None:
        """Create additional agents in background."""
        created = 0
        logger.info(
            f"🌱 [POOL] _grow_agents: starting to create {count} agents"
        )

        for _ in range(count):
            if self._shutdown:
                logger.info("🌱 [POOL] _grow_agents: stopped (shutdown)")
                break
            current = len(self._agents)
            if current >= self.config.max_size:
                logger.info(
                    f"🌱 [POOL] _grow_agents: stopped at MAX={self.config.max_size} "
                    f"(current={current})"
                )
                break

            try:
                self._growth_in_progress += 1
                logger.debug("🌱 [POOL] Growing: creating agent...")
                agent = await self._create_and_connect_agent()

                async with self._lock:
                    self._agents.append(PooledAgent(agent=agent))

                created += 1
                logger.info(
                    f"✅ [POOL] Grew pool: now {len(self._agents)} agents"
                )

                # Signal that a new agent is available
                async with self._available:
                    self._available.notify_all()

            except Exception as e:
                logger.error(f"❌ [POOL] Failed to grow pool: {e}")
            finally:
                self._growth_in_progress -= 1

    async def acquire(
        self,
        browser_id: str,
        timeout: Optional[float] = None,
        on_creating: Optional[Callable[[], None]] = None,
    ) -> BassiAgentSession:
        """
        Acquire an agent from the pool.

        If no agent available:
        - If under max_size: creates new agent (calls on_creating callback)
        - If at max_size: waits for one to be released (up to timeout)

        Args:
            browser_id: ID of browser session acquiring the agent
            timeout: Max wait time (uses pool default if None)
            on_creating: Callback when we start creating a new agent
                        (for UI notification "Creating AI assistant...")

        Returns:
            Connected BassiAgentSession

        Raises:
            RuntimeError: If pool at max and all busy (after timeout)
            RuntimeError: If pool not started
        """
        # Log state for debugging
        logger.info(
            f"🔍 [POOL] acquire() called: started={self._started}, shutdown={self._shutdown}, "
            f"agents={len(self._agents)}/{self.config.max_size}, pool_id={id(self)}"
        )

        # Handle race condition during hot reload:
        # If shutdown is in progress, wait briefly for new pool to start
        if self._shutdown or not self._started:
            logger.warning(
                f"⏳ [POOL] Pool not ready (started={self._started}, shutdown={self._shutdown}), waiting up to 5s..."
            )
            for i in range(50):  # Wait up to 5 seconds
                await asyncio.sleep(0.1)
                if self._started and not self._shutdown:
                    logger.info("✅ [POOL] Pool is now ready!")
                    break
                if i % 10 == 0:
                    logger.info(
                        f"⏳ [POOL] Still waiting... ({i/10}s) started={self._started}, shutdown={self._shutdown}"
                    )

            # Final check with detailed error
            logger.info(
                f"🔍 [POOL] After wait: started={self._started}, shutdown={self._shutdown}"
            )
            if self._shutdown:
                raise RuntimeError(
                    f"Pool is shutting down - pool_id={id(self)}"
                )
            if not self._started:
                raise RuntimeError(
                    f"Pool not started after 5s wait - pool_id={id(self)}"
                )

        timeout = timeout or self.acquire_timeout
        acquire_start = time.time()

        async with self._available:
            # Try to find available agent
            while True:
                async with self._lock:
                    for pooled in self._agents:
                        if not pooled.in_use:
                            # Found one! Mark as in use
                            pooled.in_use = True
                            pooled.acquired_at = time.time()
                            pooled.browser_id = browser_id
                            pooled.use_count += 1
                            self._total_acquires += 1

                            wait_time = time.time() - acquire_start
                            self._acquire_wait_times.append(wait_time)
                            if len(self._acquire_wait_times) > 100:
                                self._acquire_wait_times.pop(0)

                            logger.info(
                                f"🎯 [POOL] Acquired agent for browser {browser_id[:8]} "
                                f"(wait: {wait_time*1000:.0f}ms, "
                                f"use #{pooled.use_count}, pool: {len(self._agents)})"
                            )

                            # Check if we should grow pool (background)
                            asyncio.create_task(self._maybe_grow_pool())

                            return pooled.agent

                # No agent available
                current = len(self._agents)
                total_agents = current + self._growth_in_progress
                idle = self._get_idle_count()

                logger.info(
                    f"🔍 [POOL] No agent available: current={current}, idle={idle}, "
                    f"growing={self._growth_in_progress}, total={total_agents}, MAX={self.config.max_size}"
                )

                # Can we create a new one?
                if total_agents < self.config.max_size:
                    logger.info(
                        f"🆕 [POOL] Creating new agent on-demand "
                        f"(current={current} + growing={self._growth_in_progress} = {total_agents} < MAX={self.config.max_size})"
                    )

                    # Notify caller that we're creating (for UI feedback)
                    if on_creating:
                        try:
                            on_creating()
                        except Exception as e:
                            logger.warning(
                                f"on_creating callback failed: {e}"
                            )

                    # Create new agent synchronously
                    try:
                        self._growth_in_progress += 1
                        agent = await self._create_and_connect_agent()

                        pooled = PooledAgent(
                            agent=agent,
                            in_use=True,
                            acquired_at=time.time(),
                            browser_id=browser_id,
                            use_count=1,
                        )

                        async with self._lock:
                            self._agents.append(pooled)

                        self._total_acquires += 1
                        self._agents_created_on_demand += 1

                        wait_time = time.time() - acquire_start
                        self._acquire_wait_times.append(wait_time)
                        if len(self._acquire_wait_times) > 100:
                            self._acquire_wait_times.pop(0)

                        logger.info(
                            f"✅ [POOL] Created and acquired new agent for browser {browser_id[:8]} "
                            f"(wait: {wait_time*1000:.0f}ms, pool: {len(self._agents)})"
                        )

                        return agent

                    except Exception as e:
                        logger.error(f"❌ [POOL] Failed to create agent: {e}")
                        raise RuntimeError(f"Failed to create agent: {e}")
                    finally:
                        self._growth_in_progress -= 1

                # At max capacity and all agents busy
                # Wait briefly (2s) for an agent to be released - this handles
                # race conditions when browser refreshes (old connection releasing
                # its agent while new connection is trying to acquire)
                logger.info(
                    f"⏳ [POOL] Pool at MAX={self.config.max_size}, all busy! "
                    f"(current={current}, idle={idle}, growing={self._growth_in_progress}) "
                    f"Waiting 2s for release..."
                )
                try:
                    # Wait for release signal (up to 2 seconds)
                    await asyncio.wait_for(
                        self._available.wait(),
                        timeout=2.0,
                    )
                    # An agent was released! Loop back and try to acquire it
                    logger.info(
                        "✅ [POOL] Agent released during wait, retrying acquire..."
                    )
                    continue
                except asyncio.TimeoutError:
                    # After brief wait, still no agent available - fail
                    logger.warning(
                        f"🚫 [POOL] Pool exhausted after 2s wait: "
                        f"{self.config.max_size}/{self.config.max_size} agents in use."
                    )
                    raise PoolExhaustedException(
                        pool_size=self.config.max_size,
                        in_use=self.config.max_size,
                    )

    async def release(self, agent: BassiAgentSession) -> None:
        """
        Release an agent by DESTROYING it and creating a fresh replacement.

        We do NOT reuse agents because the SDK's conversation context persists
        even across different session_ids. The only reliable way to ensure
        complete isolation between chat sessions is to use fresh agents.

        Args:
            agent: Agent to release (will be destroyed)
        """
        pooled_to_remove = None
        browser_id = "unknown"

        async with self._lock:
            for pooled in self._agents:
                if pooled.agent is agent:
                    browser_id = pooled.browser_id or "unknown"
                    pooled_to_remove = pooled
                    break

            if pooled_to_remove:
                # Remove agent from pool - it will be destroyed
                self._agents.remove(pooled_to_remove)
                self._total_releases += 1

                logger.info(
                    f"🗑️ [POOL] Destroying agent from browser {browser_id[:8]} "
                    f"(was used {pooled_to_remove.use_count} times, "
                    f"remaining pool: {len(self._agents)})"
                )
            else:
                logger.warning(
                    "⚠️ [POOL] Agent not found in pool during release"
                )
                return

        # Disconnect the old agent in background (fire and forget)
        # This avoids blocking and handles cancel scope issues gracefully
        asyncio.create_task(self._destroy_agent(agent, browser_id))

        # Create a fresh replacement agent in background
        asyncio.create_task(self._create_replacement_agent())

        # Signal that pool state changed (new agent will be available soon)
        async with self._available:
            self._available.notify_all()

    async def _destroy_agent(
        self, agent: BassiAgentSession, browser_id: str
    ) -> None:
        """
        Destroy an agent via the lifecycle manager.

        The lifecycle manager task owns all connect/disconnect operations
        to ensure anyio cancel scopes are entered and exited from the same task.

        Runs asynchronously to avoid blocking the release call.
        Handles errors gracefully since the agent is already removed from pool.
        """
        # Send destroy command to lifecycle manager
        if self._lifecycle_task and not self._lifecycle_task.done():
            await self._lifecycle_queue.put((LifecycleCommand.DESTROY, agent))
            logger.info(
                f"✅ [POOL] Agent from {browser_id[:8]} queued for disconnect"
            )
        else:
            # Fallback: try direct disconnect (may fail with cancel scope error)
            try:
                await agent.disconnect()
                logger.info(
                    f"✅ [POOL] Agent from {browser_id[:8]} disconnected (direct)"
                )
            except Exception as e:
                # Log but don't raise - agent is already removed from pool
                logger.warning(
                    f"⚠️ [POOL] Failed to disconnect agent from {browser_id[:8]}: {e}"
                )

    async def _create_replacement_agent(self) -> None:
        """
        Create a fresh agent to replace a destroyed one.

        Respects pool limits and handles errors gracefully.
        """
        # Check if we should create a replacement
        current = len(self._agents)
        total_with_growing = current + self._growth_in_progress

        if self._shutdown:
            logger.debug("📊 [POOL] Skipping replacement (shutdown)")
            return

        if total_with_growing >= self.config.max_size:
            logger.debug(
                f"📊 [POOL] Skipping replacement (at MAX={self.config.max_size})"
            )
            return

        try:
            self._growth_in_progress += 1
            logger.info(
                f"🆕 [POOL] Creating replacement agent "
                f"(current={current}, MAX={self.config.max_size})"
            )

            agent = await self._create_and_connect_agent()

            async with self._lock:
                self._agents.append(PooledAgent(agent=agent))

            logger.info(
                f"✅ [POOL] Replacement agent ready (pool: {len(self._agents)})"
            )

            # Signal that new agent is available
            async with self._available:
                self._available.notify_all()

        except Exception as e:
            logger.error(f"❌ [POOL] Failed to create replacement agent: {e}")
        finally:
            self._growth_in_progress -= 1

    async def shutdown(self, force: bool = False) -> None:
        """
        Shutdown the pool.

        Args:
            force: If True, disconnect all agents. If False (default), just mark
                   as shutdown but keep agents connected (for hot reload).

        With hot reload, shutdown() is called but start() will be called again
        shortly after. We keep agents connected to avoid slow reconnection.
        """
        logger.info(f"🛑 [POOL] Shutting down (force={force})...")
        self._shutdown = True

        # Cancel warmup if still running
        if self._warmup_task and not self._warmup_task.done():
            self._warmup_task.cancel()
            try:
                await self._warmup_task
            except asyncio.CancelledError:
                pass

        if force:
            # Full shutdown: disconnect all agents via lifecycle manager
            async with self._lock:
                # Queue all agents for disconnect
                for pooled in self._agents:
                    if self._lifecycle_task and not self._lifecycle_task.done():
                        await self._lifecycle_queue.put(
                            (LifecycleCommand.DESTROY, pooled.agent)
                        )
                    else:
                        # Fallback to direct disconnect
                        try:
                            await pooled.agent.disconnect()
                        except Exception as e:
                            logger.warning(
                                f"Error during shutdown disconnect: {e}"
                            )

                self._agents.clear()

            # Signal lifecycle manager to stop
            if self._lifecycle_task and not self._lifecycle_task.done():
                await self._lifecycle_queue.put(
                    (LifecycleCommand.SHUTDOWN, None)
                )
                # Wait for lifecycle manager to finish processing
                try:
                    await asyncio.wait_for(self._lifecycle_task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(
                        "⚠️ [POOL] Lifecycle manager didn't stop in time, cancelling"
                    )
                    self._lifecycle_task.cancel()
                    try:
                        await self._lifecycle_task
                    except asyncio.CancelledError:
                        pass

            self._started = False
            logger.info(
                "✅ [POOL] Full shutdown complete (agents disconnected)"
            )
        else:
            # Soft shutdown: keep agents connected for hot reload
            # But stop the lifecycle manager (will restart on next start())
            if self._lifecycle_task and not self._lifecycle_task.done():
                await self._lifecycle_queue.put(
                    (LifecycleCommand.SHUTDOWN, None)
                )
                try:
                    await asyncio.wait_for(self._lifecycle_task, timeout=2.0)
                except asyncio.TimeoutError:
                    self._lifecycle_task.cancel()
                    try:
                        await self._lifecycle_task
                    except asyncio.CancelledError:
                        pass

            logger.info(
                f"✅ [POOL] Soft shutdown complete (keeping {len(self._agents)} agents connected)"
            )

    def get_stats(self) -> dict:
        """
        Get pool statistics.

        Returns:
            Dict with pool metrics
        """
        total = len(self._agents)
        in_use = sum(1 for p in self._agents if p.in_use)
        available = total - in_use

        avg_wait_ms = (
            sum(self._acquire_wait_times)
            / len(self._acquire_wait_times)
            * 1000
            if self._acquire_wait_times
            else 0
        )

        return {
            # Current state
            "total_agents": total,
            "in_use": in_use,
            "available": available,
            "utilization": in_use / total if total > 0 else 0,
            # Configuration
            "initial_size": self.config.initial_size,
            "max_size": self.config.max_size,
            "keep_idle_size": self.config.keep_idle_size,
            # Dynamic sizing
            "growth_in_progress": self._growth_in_progress,
            "agents_created_on_demand": self._agents_created_on_demand,
            # Cumulative stats
            "total_acquires": self._total_acquires,
            "total_releases": self._total_releases,
            "avg_acquire_wait_ms": round(avg_wait_ms, 2),
            # Lifecycle
            "started": self._started,
            "shutdown": self._shutdown,
            # Backward compatibility
            "size": self.config.initial_size,
        }

    @property
    def is_ready(self) -> bool:
        """Check if pool has at least one available agent."""
        return self._started and any(not p.in_use for p in self._agents)

    def get_agent_for_browser(
        self, browser_id: str
    ) -> Optional[BassiAgentSession]:
        """
        Get the agent currently assigned to a browser.

        Args:
            browser_id: Browser session ID

        Returns:
            Agent if found, None otherwise
        """
        for pooled in self._agents:
            if pooled.browser_id == browser_id:
                return pooled.agent
        return None

    async def set_model_all(self, model_id: str) -> int:
        """
        Change the model on all agents in the pool.

        Uses SDK's set_model() which changes model mid-conversation without
        disconnecting. Much faster than recreating agents.

        Args:
            model_id: Model ID string (e.g., 'claude-haiku-4-5-20250929')

        Returns:
            Number of agents updated
        """
        updated = 0

        for i, pooled in enumerate(self._agents):
            try:
                logger.info(
                    f"🤖 [POOL] Setting model on agent {i + 1}/{len(self._agents)}: {model_id}"
                )
                await pooled.agent.set_model(model_id)
                updated += 1
            except Exception as e:
                logger.error(
                    f"❌ [POOL] Failed to set model on agent {i + 1}: {e}"
                )

        logger.info(
            f"✅ [POOL] Updated model on {updated}/{len(self._agents)} agents"
        )
        return updated
