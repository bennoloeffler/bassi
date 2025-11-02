# Quick Start Guide - Bassi V2 Architecture

## 🚀 What's New in V2?

The V2 architecture is a complete rewrite using **event sourcing** and modern async patterns:

- ✅ **Event-Sourced**: All actions emit events → single source of truth
- ✅ **Type-Safe**: No dict soup! Strongly typed events throughout
- ✅ **Observable**: Every action is traceable via event log
- ✅ **Testable**: 57/57 tests passing (100% on core components)
- ✅ **Multi-Model**: Easy to add DeepSeek, Moonshot, GPT-4, etc.
- ✅ **Tool Permissions**: Pre/post hooks for security
- ✅ **Backpressure**: Handles slow clients without blocking model
- ✅ **Reconnection**: Event replay for client reconnection

## 📦 Installation

```bash
# Clone repo
git clone <repo-url>
cd bassi

# Install dependencies
uv sync

# Set API key
export ANTHROPIC_API_KEY=your-key-here
```

## 🎯 Three Ways to Use V2

### 1. Web UI (Easiest)

```bash
# Start V2 web server
./run-web-v2.sh

# Open browser
open http://localhost:8765
```

The web UI provides:
- Chat interface
- Tool execution display
- Token usage stats
- Hot reload for development

### 2. Python API (Most Flexible)

```python
from bassi.core_v2.agent_session import AgentConfig, AgentSession
from bassi.core_v2.tool_executor import create_bash_tool
import asyncio
import os

# Configure
config = AgentConfig(
    model_provider="anthropic",
    model_name="claude-3-5-sonnet-latest",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    system_prompt="You are helpful",
    max_tokens=2048
)

# Create session with tools
session = AgentSession(config, tools=[create_bash_tool()])

async def main():
    # Start
    await session.start()

    # Subscribe to events
    subscriber = session.subscribe("my-app")

    # Send prompt
    async for event in session.send_prompt("What's 2+2?"):
        # Events automatically in event_store
        pass

    # Query events
    events = await session.get_events()
    print(f"Total events: {len(events)}")

    # Complete
    await session.complete()

asyncio.run(main())
```

### 3. Demo Script (For Testing)

```bash
# Run comprehensive demo
uv run python demo_agent_v2.py

# Shows:
# - Basic streaming
# - Tool execution
# - Event replay
# - Multi-turn conversations
```

## 🔧 Core Components

### 1. Events (`bassi/core_v2/events.py`)

All actions emit strongly-typed events:

```python
from bassi.core_v2.events import TokenDeltaEvent, ToolCallEvent

# Every event is immutable and has:
# - type: EventType
# - timestamp: datetime (UTC)
# - event_id: UUID
# - session_id: str
# - run_id: str

event = TokenDeltaEvent(
    delta="Hello",
    block_id="block-0",
    session_id="session-123",
    run_id="run-1"
)

# Serialize for transport
json_data = event.to_dict()
```

**Event Types:**
- `SESSION_STARTED`, `SESSION_ENDED`
- `PROMPT_RECEIVED`, `PLAN_GENERATED`
- `TOKEN_DELTA` (streaming text)
- `CONTENT_BLOCK_START`, `CONTENT_BLOCK_END`
- `TOOL_CALL_STARTED`, `TOOL_CALL_COMPLETED`, `TOOL_CALL_FAILED`
- `HOOK_EXECUTED`, `HOOK_DENIED`
- `MESSAGE_COMPLETED` (with usage stats)
- `ERROR`

### 2. Event Store (`bassi/core_v2/event_store.py`)

Append-only log with pub/sub:

```python
from bassi.core_v2.event_store import EventStore

store = EventStore()

# Subscribe with filters
subscriber = store.subscribe(
    "websocket",
    drop_on_full=True,  # Don't block model
    filter_fn=lambda e: e.type == EventType.TOKEN_DELTA
)

# Append events
await store.append(event)

# Stream events
async for event in store.stream(subscriber):
    await websocket.send_json(event.to_dict())

# Replay for reconnection
await store.replay(subscriber, from_event_id="last-seen-id")

# Query
events = await store.get_events(
    session_id="session-123",
    event_types=[EventType.TOOL_CALL_COMPLETED]
)
```

### 3. Tool Executor (`bassi/core_v2/tool_executor.py`)

Execute tools with permission hooks:

```python
from bassi.core_v2.tool_executor import (
    ToolExecutor,
    ToolDefinition,
    HookDecision,
    HookResult,
    create_bash_tool
)

executor = ToolExecutor(event_store, session_id, run_id)

# Add permission hook
def permission_hook(tool_name, tool_id, tool_input):
    if tool_name == "bash" and "rm -rf" in tool_input["command"]:
        return HookResult(
            decision=HookDecision.DENY,
            reason="Dangerous command blocked"
        )
    return HookResult(decision=HookDecision.ALLOW)

executor.add_pre_hook(permission_hook)

# Register tools
executor.register_tool(create_bash_tool())

# Execute
result = await executor.execute(
    tool_name="bash",
    tool_id="tool-1",
    tool_input={"command": "ls"}
)
```

**Built-in Tools:**
- `create_bash_tool()` - Execute bash commands
- `create_read_file_tool()` - Read files
- `create_write_file_tool()` - Write files (requires permission)

### 4. Model Adapters (`bassi/core_v2/model_adapter.py`)

Unified interface for any LLM:

```python
from bassi.core_v2.model_adapter import create_adapter

# Anthropic (Claude)
adapter = create_adapter(
    provider="anthropic",
    model_name="claude-3-5-sonnet-latest",
    api_key=api_key,
    event_store=event_store,
    session_id=session_id,
    run_id=run_id
)

# DeepSeek
adapter = create_adapter(
    provider="deepseek",
    model_name="deepseek-chat",
    api_key=deepseek_key,
    base_url="https://api.deepseek.com/v1",
    event_store=event_store,
    session_id=session_id,
    run_id=run_id
)

# Stream response (events automatically emitted)
async for event in adapter.send_message(
    messages=messages,
    tools=tool_defs,
    system="You are helpful"
):
    # Events in event_store
    pass
```

### 5. Agent Session (`bassi/core_v2/agent_session.py`)

Complete lifecycle management:

```python
from bassi.core_v2.agent_session import AgentConfig, AgentSession

config = AgentConfig(
    model_provider="anthropic",
    model_name="claude-3-5-sonnet-latest",
    api_key=api_key,
    system_prompt="You are helpful"
)

session = AgentSession(config, tools=[bash_tool])

# Start
await session.start()

# Stream response
async for event in session.send_prompt("What's 2+2?"):
    print(f"Event: {event.type}")

# Multi-turn
async for event in session.send_prompt("And 5*6?"):
    pass

# Get stats
stats = session.get_stats()
print(f"Messages: {stats['message_count']}")

# Complete
await session.complete()
```

## 🧪 Testing

```bash
# Run all tests (57 tests, 100% passing)
uv run pytest bassi/core_v2/tests/ -v

# Run specific test suite
uv run pytest bassi/core_v2/tests/test_events.py -v
uv run pytest bassi/core_v2/tests/test_event_store.py -v
uv run pytest bassi/core_v2/tests/test_tool_executor.py -v

# Run quality checks
./check.sh  # Runs black, ruff, mypy, pytest
```

## 📊 Architecture Diagram

```
User Input
    ↓
AgentSession (Orchestrator)
    ↓
    ├→ ModelAdapter (Anthropic/DeepSeek/etc)
    │   └→ Events → EventStore
    ├→ ToolExecutor (with hooks)
    │   └→ Events → EventStore
    └→ EventStore (Pub/Sub)
        └→ Subscribers
            ├→ WebSocket
            ├→ CLI
            └→ Persistence
```

## 🔍 Debugging

All events are logged, making debugging easy:

```python
# Subscribe to all events
debug_sub = session.subscribe("debug")

# Stream events
async for event in store.stream(debug_sub):
    print(f"{event.timestamp} | {event.type} | {event.to_dict()}")

# Or query after the fact
events = await session.get_events()
for event in events:
    if event.type == EventType.ERROR:
        print(f"Error: {event.error_message}")
        print(f"Traceback: {event.traceback}")
```

## 🚦 Next Steps

1. **Try the Demo**
   ```bash
   uv run python demo_agent_v2.py
   ```

2. **Start Web UI**
   ```bash
   ./run-web-v2.sh
   ```

3. **Read the Docs**
   - `docs/V2_IMPLEMENTATION_STATUS.md` - Full status
   - `docs/IMPLEMENTATION_SUMMARY.md` - Technical details
   - `docs/agent_rethink/ARCHITECTURE.md` - Design decisions

4. **Run Tests**
   ```bash
   ./check.sh
   ```

5. **Build Something!**
   - Add custom tools
   - Integrate with your app
   - Try different models
   - Implement custom hooks

## 💡 Tips

- **Event Replay**: Clients can reconnect and replay missed events
- **Backpressure**: Use `drop_on_full=True` for WebSocket, `False` for persistence
- **Tool Permissions**: Always add hooks for security-sensitive operations
- **Multiple Models**: Easy to switch providers via `create_adapter()`
- **Testing**: Replay events in tests for deterministic behavior

## 📞 Support

- Issues: GitHub Issues
- Docs: `docs/` directory
- Examples: `demo_agent_v2.py`, `test_event_system.py`

## 🎉 What's Working

- ✅ Event system (22 tests)
- ✅ Event store (17 tests)
- ✅ Tool executor (18 tests)
- ✅ Model adapters (Anthropic + OpenAI-compatible)
- ✅ Agent session (lifecycle management)
- ✅ Web server V2 (event streaming)

**Total: 57/57 tests passing (100%)**

Start building! 🚀
