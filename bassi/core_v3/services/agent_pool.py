"""
Agent Pool - Manages a pool of pre-connected agent instances.

Provides:
- Pool of N agents (default 5) that are pre-connected to Claude SDK
- Fast acquire/release for browser sessions
- Async warmup: first agent ready immediately, rest warm up in background
- Automatic state reset between uses
- **SINGLETON**: Survives hot reloads (agents stay connected)

Architecture:
- Browser session connects → acquire agent from pool
- Browser session disconnects → release agent back to pool
- Agents stay connected (expensive to start/stop)
- Agent state cleared between uses (history, workspace)
- Hot reload: Pool persists, only app code reloads

Usage:
    # Get or create singleton pool
    pool = get_agent_pool(size=5, agent_factory=my_factory)
    await pool.start()  # Only starts if not already started

    # On browser connect:
    agent = await pool.acquire(timeout=30)

    # On browser disconnect:
    await pool.release(agent)

    # On REAL server shutdown (not hot reload):
    await pool.shutdown()
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from bassi.core_v3.agent_session import BassiAgentSession

logger = logging.getLogger(__name__)

# ============================================================
# SINGLETON POOL - Survives hot reloads
# ============================================================
_global_pool: Optional["AgentPool"] = None


def get_agent_pool(
    size: int = 5,
    agent_factory: Optional[Callable[[], BassiAgentSession]] = None,
    acquire_timeout: float = 30.0,
) -> "AgentPool":
    """
    Get or create the global agent pool singleton.

    The pool persists across hot reloads so agents stay connected.

    Args:
        size: Number of agents (only used on first call)
        agent_factory: Factory to create agents (only used on first call)
        acquire_timeout: Timeout for acquiring agents

    Returns:
        The global AgentPool instance
    """
    global _global_pool

    if _global_pool is None:
        logger.info("🏊 [POOL] Creating new global agent pool singleton")
        _global_pool = AgentPool(
            size=size,
            agent_factory=agent_factory,
            acquire_timeout=acquire_timeout,
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


class AgentPool:
    """
    Manages a pool of pre-connected Claude Agent SDK clients.

    Key Features:
    - Pre-connected agents for instant availability
    - Async warmup (first agent immediate, rest in background)
    - Clean acquire/release for browser sessions
    - State reset between uses
    - Timeout handling when pool exhausted
    """

    def __init__(
        self,
        size: int = 5,
        agent_factory: Optional[Callable[[], BassiAgentSession]] = None,
        acquire_timeout: float = 30.0,
    ):
        """
        Initialize agent pool.

        Args:
            size: Number of agents in pool (default 5)
            agent_factory: Factory function to create agents
            acquire_timeout: Max wait time when pool exhausted (seconds)
        """
        self.size = size
        self.agent_factory = agent_factory
        self.acquire_timeout = acquire_timeout

        # Pool state
        self._agents: list[PooledAgent] = []
        self._lock = asyncio.Lock()
        self._available = asyncio.Condition()  # Signal when agent available

        # Lifecycle state
        self._started = False
        self._shutdown = False
        self._warmup_task: Optional[asyncio.Task] = None

        # Stats
        self._total_acquires = 0
        self._total_releases = 0
        self._acquire_wait_times: list[float] = []

    async def start(self) -> None:
        """
        Start the agent pool.

        Creates and connects the first agent synchronously (blocks until ready).
        Starts background task to warm up remaining agents.

        After this returns, at least one agent is ready for use.

        NOTE: This is idempotent and handles hot reload recovery.
        """
        # Handle hot reload: if pool was shutdown but we're being started again,
        # reset the shutdown flag (uvicorn hot reload calls shutdown then start)
        if self._shutdown:
            logger.info(
                "♻️ [POOL] Resetting shutdown flag (hot reload recovery)"
            )
            self._shutdown = False

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

        print(f"🏊🏊🏊 [POOL] Starting with {self.size} agents...")
        logger.info(f"🏊 [POOL] Starting with {self.size} agents...")
        start_time = time.time()

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

        # Warm up remaining agents in background
        remaining = self.size - 1
        if remaining > 0:
            logger.info(
                f"🔥 [POOL] Warming up {remaining} more agents in background..."
            )
            self._warmup_task = asyncio.create_task(
                self._warmup_remaining(remaining)
            )

    async def _create_and_connect_agent(self) -> BassiAgentSession:
        """Create a new agent and connect it to the SDK."""
        if not self.agent_factory:
            raise RuntimeError("No agent_factory configured")

        agent = self.agent_factory()
        await agent.connect()
        return agent

    async def _warmup_remaining(self, count: int) -> None:
        """Warm up additional agents in background."""
        warmup_start = time.time()
        created = 0

        for i in range(count):
            if self._shutdown:
                logger.info("⏹️ [POOL] Warmup cancelled (shutdown)")
                break

            try:
                logger.debug(
                    f"🔶 [POOL] Warming agent {i + 2}/{self.size}..."
                )
                agent = await self._create_and_connect_agent()

                async with self._lock:
                    self._agents.append(PooledAgent(agent=agent))

                created += 1
                logger.debug(f"✅ [POOL] Agent {i + 2}/{self.size} ready")

                # Signal that a new agent is available
                async with self._available:
                    self._available.notify_all()

            except Exception as e:
                logger.error(f"❌ [POOL] Failed to create agent {i + 2}: {e}")

        warmup_time = time.time() - warmup_start
        logger.info(
            f"✅ [POOL] Warmup complete: {created}/{count} agents in {warmup_time:.2f}s "
            f"(total: {len(self._agents)}/{self.size})"
        )

    async def acquire(
        self,
        browser_id: str,
        timeout: Optional[float] = None,
    ) -> BassiAgentSession:
        """
        Acquire an agent from the pool.

        Args:
            browser_id: ID of browser session acquiring the agent
            timeout: Max wait time (uses pool default if None)

        Returns:
            Connected BassiAgentSession

        Raises:
            TimeoutError: If no agent available within timeout
            RuntimeError: If pool not started
        """
        # Log state for debugging
        logger.info(
            f"🔍 [POOL] acquire() called: started={self._started}, shutdown={self._shutdown}, agents={len(self._agents)}, pool_id={id(self)}"
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
                                f"use #{pooled.use_count})"
                            )
                            return pooled.agent

                # No agent available - wait for one
                remaining_timeout = timeout - (time.time() - acquire_start)
                if remaining_timeout <= 0:
                    raise TimeoutError(
                        f"No agent available within {timeout}s "
                        f"(pool size: {self.size}, all in use)"
                    )

                logger.warning(
                    f"⏳ [POOL] All {len(self._agents)} agents in use, "
                    f"waiting (timeout: {remaining_timeout:.1f}s)..."
                )

                try:
                    await asyncio.wait_for(
                        self._available.wait(),
                        timeout=remaining_timeout,
                    )
                except asyncio.TimeoutError:
                    raise TimeoutError(
                        f"No agent available within {timeout}s "
                        f"(pool size: {self.size}, all in use)"
                    )

    async def release(self, agent: BassiAgentSession) -> None:
        """
        Release an agent back to the pool.

        Clears agent state (history, workspace) but keeps it connected.

        Args:
            agent: Agent to release
        """
        async with self._lock:
            for pooled in self._agents:
                if pooled.agent is agent:
                    browser_id = pooled.browser_id or "unknown"

                    # Clear agent state
                    agent.message_history.clear()
                    agent.stats.message_count = 0
                    agent.stats.tool_calls = 0
                    agent.current_workspace_id = None

                    # CRITICAL: Clear conversation context to prevent context leakage
                    # between different chat sessions using the same agent
                    agent._conversation_context = None

                    # Clear workspace and question_service references
                    if hasattr(agent, "workspace"):
                        agent.workspace = None
                    if hasattr(agent, "question_service"):
                        agent.question_service = None

                    # Mark as available
                    pooled.in_use = False
                    pooled.released_at = time.time()
                    pooled.browser_id = None
                    self._total_releases += 1

                    logger.info(
                        f"🔄 [POOL] Released agent from browser {browser_id[:8]} "
                        f"(used {pooled.use_count} times)"
                    )
                    break
            else:
                logger.warning(
                    "⚠️ [POOL] Agent not found in pool during release"
                )

        # Signal that an agent is available
        async with self._available:
            self._available.notify_all()

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
            # Full shutdown: disconnect all agents
            async with self._lock:
                disconnect_tasks = []
                for pooled in self._agents:
                    try:
                        disconnect_tasks.append(pooled.agent.disconnect())
                    except Exception as e:
                        logger.error(f"Error preparing disconnect: {e}")

                if disconnect_tasks:
                    await asyncio.gather(
                        *disconnect_tasks, return_exceptions=True
                    )

                self._agents.clear()
            self._started = False
            logger.info(
                "✅ [POOL] Full shutdown complete (agents disconnected)"
            )
        else:
            # Soft shutdown: keep agents connected for hot reload
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
            "size": self.size,
            "total_agents": total,
            "in_use": in_use,
            "available": available,
            "utilization": in_use / total if total > 0 else 0,
            "total_acquires": self._total_acquires,
            "total_releases": self._total_releases,
            "avg_acquire_wait_ms": round(avg_wait_ms, 2),
            "started": self._started,
            "shutdown": self._shutdown,
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
