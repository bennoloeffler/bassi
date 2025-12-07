# Dynamic Agent Pool

## Overview

The agent pool dynamically scales based on demand rather than having a fixed size.
When agents run low, new ones are created asynchronously. Users are notified when
a new agent is being created (takes ~20 seconds).

## Configuration (.env)

```bash
# Initial pool size at startup (first agent blocks, rest async)
AGENT_INITIAL_POOL_SIZE=5

# Target idle agents to maintain - when idle drops below this, start creating more
AGENT_KEEP_IDLE_SIZE=2

# Maximum pool size - hard limit to prevent runaway resource usage
AGENT_MAX_POOL_SIZE=30
```

## Behavior

### Startup
1. Create first agent (blocking) - server waits for this
2. Create `AGENT_INITIAL_POOL_SIZE - 1` agents asynchronously in background
3. Pool is ready after first agent connects

### On Acquire
1. Find available agent → return immediately
2. If available agents drop below `AGENT_KEEP_IDLE_SIZE`:
   - Start creating new agent(s) in background (if under max)
3. If NO agent available AND under max:
   - Create new agent synchronously
   - Send WebSocket event: `{"type": "pool_creating_agent", "estimated_seconds": 20}`
   - User sees: "Creating new AI assistant... (~20 seconds)"
4. If NO agent available AND at max:
   - **Fail IMMEDIATELY** (no waiting!)
   - Raise `PoolExhaustedException` with pool stats
   - Send WebSocket event: `{"type": "pool_exhausted", ...}`
   - User sees: "All AI assistants are busy. Please try again in a few minutes."

### On Release
1. Clear agent state (existing behavior)
2. Mark as available
3. Check if we have excess idle agents (optional future: could shrink pool)

## WebSocket Events

### New Event: `pool_creating_agent`
Sent when user must wait for agent creation:
```json
{
  "type": "pool_creating_agent",
  "message": "Creating new AI assistant...",
  "estimated_seconds": 20
}
```

### New Event: `pool_exhausted`
Sent **IMMEDIATELY** when pool is at max and all busy (no waiting!):
```json
{
  "type": "pool_exhausted",
  "message": "All AI assistants are busy. Please try again in a few minutes.",
  "pool_size": 30,
  "in_use": 30
}
```

## Implementation Status

All core functionality is implemented:

1. **Config vars** - `bassi/config.py` has `PoolConfig` dataclass, `.env.example` updated
2. **Dynamic AgentPool** - `bassi/core_v3/services/agent_pool.py` fully refactored
3. **Background growth** - `_maybe_grow_pool()` triggers when idle < keep_idle_size
4. **User notifications** - `on_creating` callback in `acquire()` for UI feedback
5. **Immediate exhaustion feedback** - `PoolExhaustedException` for instant user notification
6. **Tests** - 15 tests in `bassi/core_v3/tests/unit/test_agent_pool.py`

### Key Methods

- `acquire(browser_id, on_creating=callback)` - Get agent, create if needed
- `release(agent)` - Return agent, clear state
- `get_stats()` - Pool metrics including dynamic sizing info
- `_should_grow()` / `_maybe_grow_pool()` - Proactive growth logic

### Key Classes

- `PoolExhaustedException` - Raised immediately when pool is at max and all busy

## Edge Cases

- Hot reload: Pool persists, sizing config may change → handle gracefully
- Rapid connections: Multiple clients connect simultaneously → don't over-create
- Agent creation failure: Don't count failed attempts, retry logic
- Pool shrinking: Future consideration - not implementing initially

## Metrics (get_stats)

Extended stats to include:
- `initial_size`: Configured initial size
- `max_size`: Configured maximum
- `keep_idle_size`: Target idle agents to maintain
- `growth_in_progress`: Number of agents currently being created
- `agents_created_on_demand`: Count of agents created because pool was exhausted
