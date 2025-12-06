# Runtime Configuration Changes

This document describes how to change agent configuration at runtime, including model switching, permission mode changes, and thinking mode toggling.

## Overview

The Bassi application uses the Claude Agent SDK which provides different mechanisms for runtime configuration changes:

| Configuration | Can Change at Runtime? | Mechanism | Impact |
|---------------|----------------------|-----------|--------|
| Model | **Yes** | `set_model()` | No reconnection needed |
| Permission Mode | **Yes** | `set_permission_mode()` | No reconnection needed |
| Thinking Mode | **No** | Agent swap | Requires new agent |

## SDK Runtime Methods

The Claude Agent SDK (`ClaudeSDKClient`) provides methods that can be called during an active conversation without disconnecting:

### Model Switching

```python
# Change model during conversation (no disconnect!)
await client.set_model("claude-sonnet-4-5")
await client.set_model("claude-opus-4-1-20250805")
await client.set_model(None)  # Reset to default
```

This sends a control protocol request to Claude Code, which switches models seamlessly without interrupting the connection.

### Permission Mode

```python
# Change permission mode during conversation (no disconnect!)
await client.set_permission_mode("default")        # CLI prompts for dangerous tools
await client.set_permission_mode("acceptEdits")    # Auto-accept file edits
await client.set_permission_mode("bypassPermissions")  # Allow all tools
```

### Thinking Mode (Extended Thinking)

Thinking mode (`max_thinking_tokens`) is set at connection time via `ClaudeAgentOptions` and **cannot be changed at runtime**. This is a limitation of the Claude Agent SDK.

```python
# Set at connection time only
options = ClaudeAgentOptions(max_thinking_tokens=10000)
client = ClaudeSDKClient(options=options)
await client.connect()

# CANNOT change later - SDK limitation!
```

## Bassi Implementation

### Model and Permission Changes

In `BassiAgentSession`, these are simple wrappers around the SDK methods:

```python
# bassi/core_v3/agent_session.py

async def set_model(self, model: str | None) -> None:
    """Change model at runtime (no reconnection needed)."""
    await self._client.set_model(model)

async def set_permission_mode(self, mode: str) -> None:
    """Change permission mode at runtime (no reconnection needed)."""
    await self._client.set_permission_mode(mode)
```

### Thinking Mode Changes

Since thinking mode cannot be changed at runtime, Bassi uses an **agent swap pattern**:

1. Save current conversation history
2. Request a new agent from the pool with different config
3. Release old agent back to pool
4. Restore conversation history to new agent

This is handled by `BrowserSessionManager.swap_agent_for_thinking_mode()`:

```python
# In browser_session_manager.py
async def swap_agent_for_thinking_mode(
    self,
    browser_id: str,
    thinking_mode: bool,
) -> bool:
    """
    Swap current agent for one with different thinking mode config.

    This preserves chat context by:
    1. Saving conversation history from current agent
    2. Releasing current agent to pool
    3. Acquiring new agent with thinking mode config
    4. Restoring conversation history to new agent

    Returns True on success, False on failure.
    """
```

## Architecture: Why Agent Swap?

### The Problem

The SDK maintains an internal anyio task group that must be exited from the same async task that entered it. When thinking mode is toggled:

1. WebSocket message comes in on task A (message processor)
2. Task A calls `update_thinking_mode()`
3. This calls `disconnect()` which tries to close the SDK's task group
4. **ERROR**: "Attempted to exit cancel scope in a different task than it was entered in"

The SDK's task group was created during pool startup (task B), not in the message processor (task A).

### The Solution: Agent Pool Pattern

Instead of disconnecting/reconnecting the same agent:

1. **Release** the current agent back to the pool (returns to its original state)
2. **Acquire** a new agent with the desired thinking mode config
3. **Restore** conversation history to maintain context

This avoids the task mismatch issue because:
- Release just returns the agent to the pool (no SDK disconnect)
- Acquire gets an already-connected agent from the pool
- The SDK connection/disconnection happens within the pool's own task management

## Message Flow

```
Browser: config_change { thinking_mode: true }
    ↓
web_server_v3_old.py: msg_type == "config_change"
    ↓
BrowserSessionManager.swap_agent_for_thinking_mode()
    ↓
1. Save history from current agent
2. agent_pool.release(current_agent)
3. agent_pool.acquire(browser_id, thinking_mode=true)
4. Restore history to new agent
    ↓
Browser: config_updated { thinking_mode: true }
```

## Usage from Frontend

```javascript
// Send config change to toggle thinking mode
websocket.send(JSON.stringify({
    type: "config_change",
    thinking_mode: true
}));

// Listen for confirmation
websocket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "config_updated") {
        console.log("Thinking mode:", data.thinking_mode);
    }
};
```

## Key Files

- `bassi/core_v3/agent_session.py` - `BassiAgentSession` with `set_model()`, `set_permission_mode()`
- `bassi/core_v3/websocket/browser_session_manager.py` - `swap_agent_for_thinking_mode()`
- `bassi/core_v3/services/agent_pool.py` - Agent pool with thinking mode support
- `bassi/core_v3/web_server_v3_old.py` - Message handler for `config_change`

## Related Documentation

- [Chat Context Architecture](chat_context_architecture.md) - How conversation history is managed
- [Permissions](permissions.md) - Permission model details
