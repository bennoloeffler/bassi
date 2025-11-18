# Agent Session Pool

## Overview

The Agent Session Pool dramatically improves web UI performance by maintaining a pool of pre-connected Claude Agent SDK clients. Instead of creating/destroying agent instances for each user session or workspace switch, agents are reused with dynamic history loading.

## Problem Statement

**Before Session Pool**:
- Each WebSocket connection created a new `BassiAgentSession`
- Each `connect()` spawned the Claude Code subprocess (~2-3 seconds)
- Switching workspaces killed and restarted the agent
- User experience: Sluggish, buggy, unresponsive

**Performance Impact**:
```
User action          | Old behavior              | Time
---------------------|---------------------------|-------
Open workspace       | Start new agent process   | 2-3s
Switch workspace     | Kill + restart agent      | 3-5s
Close workspace      | Kill agent                | 1s
```

## Solution: Pre-Warmed Agent Pool

### Architecture

```
WebSocket (User Session)
    ↓
Session Manager (assigns agent from pool)
    ↓
Agent Pool (2-10 pre-connected agents)
    ↓
Dynamic History Loading (from workspace)
    ↓
Claude Agent SDK (single persistent connection)
```

### Key Components

#### 1. `AgentSessionPool` (bassi/core_v3/agent_pool.py)

Manages a pool of pre-connected `BassiAgentSession` instances:

```python
class AgentSessionPool:
    """
    Thread-safe pool of pre-connected Agent SDK clients.

    Features:
    - Pre-warm agents on startup (default: 2)
    - Lazy expansion up to max_size (default: 10)
    - Idle timeout shrinking (default: 5 minutes)
    - Health checks and automatic recovery
    """

    async def acquire(self) -> BassiAgentSession:
        """Get an available agent (instant if pool has idle agents)"""

    async def release(self, agent: BassiAgentSession):
        """Return agent to pool (clears history, stays connected)"""
```

#### 2. Session Assignment (web_server_v3.py)

Maps user sessions to pool agents:

```python
# WebSocket handler
async def websocket_endpoint(websocket: WebSocket):
    # Get agent from pool (instant if available)
    agent = await session_pool.acquire()

    # Load workspace history into agent
    workspace = get_workspace(session_id)
    agent.restore_conversation_history(workspace.load_history())

    try:
        # Handle queries...
        async for msg in agent.query(prompt):
            await websocket.send_json(msg)
    finally:
        # Return agent to pool (keeps it connected)
        await session_pool.release(agent)
```

#### 3. Workspace Context Switching

**OLD (Slow)**:
```python
# Kill and restart agent (2-3 seconds)
await agent.disconnect()
await agent.connect()
```

**NEW (Fast)**:
```python
# Clear and reload history (<100ms)
agent.message_history.clear()
agent.restore_conversation_history(new_workspace.load_history())
```

### Configuration

Pool behavior controlled via `SessionPoolConfig`:

```python
@dataclass
class SessionPoolConfig:
    initial_size: int = 2          # Pre-warm on startup
    max_size: int = 10             # Scale up to this limit
    idle_timeout_seconds: int = 300  # 5 min idle = disconnect
    health_check_interval: int = 60  # Check every 60s
    max_acquire_wait_seconds: int = 30  # Block for 30s max
```

## Performance Characteristics

### Startup Cost
- **First agent**: 2-3 seconds (Claude Code subprocess start)
- **Subsequent agents**: 100-200ms each (reuse SDK connection)
- **Total startup** (2 agents): ~3 seconds one-time cost

### Runtime Performance
```
User action          | New behavior              | Time
---------------------|---------------------------|-------
Open workspace       | Acquire from pool         | <50ms
Switch workspace     | Load new history          | <100ms
Close workspace      | Release to pool           | <10ms
```

**Improvement**: **20-50x faster** for typical operations

### Memory Footprint
- Each agent: ~50-100MB RAM (Claude Code process + SDK overhead)
- Pool of 5 agents: ~250-500MB total
- Acceptable for modern servers/workstations

## Implementation Details

### Agent Lifecycle

1. **Pre-warming** (startup):
   ```python
   for _ in range(initial_size):
       agent = create_agent()
       await agent.connect()  # 2-3s each
       pool.add(agent)
   ```

2. **Acquisition**:
   ```python
   if pool.has_idle():
       return pool.get_idle()  # Instant
   elif pool.size < max_size:
       return await pool.spawn_new()  # 100-200ms
   else:
       return await pool.wait_for_idle()  # Block up to 30s
   ```

3. **Release**:
   ```python
   agent.message_history.clear()
   agent.stats.reset()
   pool.mark_idle(agent)  # Keep connected!
   ```

4. **Shrinking** (background task):
   ```python
   for agent in pool.idle_agents():
       if agent.idle_time > idle_timeout:
           await agent.disconnect()
           pool.remove(agent)
   ```

### Error Recovery

- **Agent crash**: Remove from pool, log error, spawn replacement
- **Connection loss**: Retry with exponential backoff (1s, 2s, 4s, 8s)
- **Pool exhaustion**: Return 503 Service Unavailable (configurable)

### Thread Safety

Uses `asyncio.Lock` to protect shared state:

```python
class AgentSessionPool:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._idle_agents = []
        self._active_agents = {}
```

## Testing Strategy

### Unit Tests (bassi/core_v3/tests/test_agent_pool.py)

```python
@pytest.mark.asyncio
async def test_pool_pre_warms_agents():
    """Pool creates initial_size agents on startup"""

@pytest.mark.asyncio
async def test_pool_scales_on_demand():
    """Pool spawns new agent when all busy"""

@pytest.mark.asyncio
async def test_pool_reuses_released_agents():
    """Released agents go back to idle pool"""

@pytest.mark.asyncio
async def test_pool_shrinks_after_idle_timeout():
    """Idle agents are disconnected after timeout"""
```

### Integration Tests (bassi/core_v3/tests/test_session_pool_integration.py)

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_workspace_switch_performance():
    """Switching workspaces is fast (<200ms)"""

@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_sessions():
    """Multiple users can use pool simultaneously"""
```

### E2E Tests (bassi/core_v3/tests/test_session_pool_e2e.py)

```python
@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
async def test_full_session_lifecycle():
    """User opens workspace → queries → switches → closes"""
```

## Migration Path

### Phase 1: Core Pool Implementation
- ✅ Create `AgentSessionPool` class
- ✅ Add pool configuration
- ✅ Implement acquire/release logic

### Phase 2: Web Server Integration
- Update `WebUIServerV3` to use pool
- Modify WebSocket handlers
- Add pool health endpoint

### Phase 3: Optimization
- Fine-tune pool sizing
- Add metrics/monitoring
- Implement adaptive scaling

### Phase 4: Documentation & Testing
- Complete test suite
- Update user documentation
- Performance benchmarking

## Configuration Examples

### Development (fast startup, small pool)
```python
SessionPoolConfig(
    initial_size=1,
    max_size=3,
    idle_timeout_seconds=120
)
```

### Production (optimized for performance)
```python
SessionPoolConfig(
    initial_size=5,
    max_size=20,
    idle_timeout_seconds=600
)
```

## Monitoring & Observability

Key metrics to track:

- **Pool utilization**: `active_agents / total_agents`
- **Acquisition latency**: Time to acquire agent
- **Idle agent count**: Number of agents available
- **Pool growth events**: How often we scale up
- **Agent health**: Connection failures, crashes

Expose via `/api/pool-stats` endpoint:

```json
{
  "total_agents": 5,
  "idle_agents": 2,
  "active_agents": 3,
  "avg_acquisition_ms": 45,
  "pool_utilization": 0.6,
  "total_acquisitions": 1234,
  "total_releases": 1230
}
```

## Future Enhancements

1. **Agent Specialization**: Different pools for different model types (thinking mode vs standard)
2. **Priority Queuing**: Premium users get priority access
3. **Predictive Scaling**: ML-based pool sizing based on usage patterns
4. **Cross-Server Pooling**: Distribute pool across multiple machines
5. **Graceful Degradation**: Fallback to on-demand agents if pool exhausted

## References

- Claude Agent SDK Docs: https://docs.claude.com/en/docs/agent-sdk/sessions
- BassiAgentSession Implementation: bassi/core_v3/agent_session.py:81
- Web Server V3: bassi/core_v3/web_server_v3.py:53
