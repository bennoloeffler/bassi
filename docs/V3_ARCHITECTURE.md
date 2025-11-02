# V3 Architecture - Built on Claude Agent SDK

## Critical Difference from V2

**V2 (WRONG):** Used `anthropic` (low-level API SDK)
**V3 (CORRECT):** Uses `claude-agent-sdk` (Agent SDK with built-in tools, hooks, MCP)

## Architecture Overview

```
User/Web UI
    ↓
BassiAgentSession (our wrapper)
    ↓
ClaudeSDKClient (from claude-agent-sdk)
    ↓
    ├→ Built-in Tools (Bash, Read, Write, etc.)
    ├→ Custom Tools (via MCP servers)
    ├→ Hooks (permissions, logging)
    └→ Message Stream
        ↓
    Event System (for web UI streaming)
```

## Core Components

### 1. BassiAgentSession
Our thin wrapper around `ClaudeSDKClient` that:
- Manages session lifecycle
- Converts Agent SDK messages to web UI format
- Handles reconnection/replay
- Provides statistics

### 2. Tool System
Uses Agent SDK's built-in `@tool` decorator and `create_sdk_mcp_server`:
```python
@tool("custom_search", "Search the web", {"query": str})
async def search_web(args):
    result = await search(args['query'])
    return {"content": [{"type": "text", "text": result}]}

mcp_server = create_sdk_mcp_server(
    name="bassi-tools",
    version="1.0.0",
    tools=[search_web]
)
```

### 3. Hook System
Uses Agent SDK's hook callbacks:
```python
async def permission_hook(input_data, tool_use_id, context):
    if "rm -rf" in input_data.get("command", ""):
        return {
            "decision": "deny",
            "systemMessage": "Dangerous command blocked"
        }
    return {"decision": "allow"}

options = ClaudeAgentOptions(
    hooks={"PreToolUse": permission_hook}
)
```

### 4. Message Handling
Agent SDK provides typed messages:
- `UserMessage` - User input
- `AssistantMessage` - Claude's response (with TextBlock, ToolUseBlock, etc.)
- `SystemMessage` - System events
- `ResultMessage` - Final result with usage stats

### 5. Event Streaming for Web UI
Convert Agent SDK messages to web-compatible format:
```python
async def stream_to_websocket(client, websocket):
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    await websocket.send_json({
                        "type": "text_delta",
                        "text": block.text
                    })
                elif isinstance(block, ToolUseBlock):
                    await websocket.send_json({
                        "type": "tool_start",
                        "id": block.id,
                        "tool_name": block.name,
                        "input": block.input
                    })
```

## Key Features from Agent SDK

### Built-in Tools
Agent SDK already has tools like:
- Bash
- Read/Write files
- Web search (if configured)
- MCP servers

We just configure them:
```python
options = ClaudeAgentOptions(
    allowed_tools=["Bash", "WriteFile", "ReadFile"],
    permission_mode="acceptEdits"  # or "default", "plan", "bypassPermissions"
)
```

### Permission Modes
- `default` - Ask user for each tool use
- `acceptEdits` - Auto-accept file edits
- `plan` - Planning mode (no execution)
- `bypassPermissions` - No permission checks

### Hooks
- `PreToolUse` - Before tool execution
- `PostToolUse` - After tool execution
- `UserPromptSubmit` - When user submits prompt
- `Stop` - When execution stops
- `SubagentStop` - When subagent stops
- `PreCompact` - Before context compaction

## V3 File Structure

```
bassi/core_v3/
├── __init__.py
├── agent_session.py        # BassiAgentSession wrapper
├── tools.py                # Custom tool definitions
├── hooks.py                # Permission and logging hooks
├── message_converter.py    # Convert SDK messages to web format
├── web_server.py           # FastAPI server using Agent SDK
└── tests/
    ├── test_agent_session.py
    ├── test_tools.py
    ├── test_hooks.py
    ├── test_message_converter.py
    ├── test_integration.py
    └── test_e2e_web.py
```

## Implementation Plan

### Phase 1: Core Session Wrapper
1. `BassiAgentSession` class wrapping `ClaudeSDKClient`
2. Unit tests for session lifecycle
3. E2E test with real API call

### Phase 2: Tool System
1. Define custom tools using `@tool` decorator
2. Create MCP server with `create_sdk_mcp_server`
3. Unit tests for each tool
4. Integration test with tools

### Phase 3: Hook System
1. Implement permission hooks
2. Implement logging hooks
3. Test hook denial/modification
4. Test hook composition

### Phase 4: Message Conversion
1. Convert AssistantMessage → web format
2. Convert ToolUseBlock → tool_start
3. Convert ToolResultBlock → tool_end
4. Unit tests for all conversions

### Phase 5: Web Server
1. FastAPI endpoints
2. WebSocket with Agent SDK streaming
3. Multi-session support
4. E2E test with browser

### Phase 6: Complete Testing
1. Unit tests (100% coverage target)
2. Integration tests
3. E2E tests with real web UI
4. Performance tests

## Testing Strategy

### Unit Tests
Every function gets a test:
```python
def test_session_init():
    """Test session initialization"""
    session = BassiAgentSession(options=...)
    assert session.client is not None

async def test_tool_execution():
    """Test custom tool execution"""
    result = await my_tool({"arg": "value"})
    assert result["content"][0]["text"] == expected
```

### Integration Tests
Test components together:
```python
async def test_session_with_tools():
    """Test session with custom tools"""
    session = BassiAgentSession(tools=[my_tool])
    await session.start()
    async for msg in session.query("Use my_tool"):
        # Check tool was called
    await session.close()
```

### E2E Tests
Test full flow:
```python
async def test_web_ui_conversation():
    """Test full web UI conversation flow"""
    # Start server
    # Connect WebSocket
    # Send message
    # Verify tool execution
    # Verify response streaming
    # Check usage stats
```

## Migration from V2

V2 code is **NOT reusable** because it was built on wrong SDK.

We start fresh with V3:
- Use `ClaudeSDKClient` not raw Anthropic API
- Use Agent SDK's tool system not custom executor
- Use Agent SDK's hooks not custom implementation
- Use Agent SDK's message types not custom events

## Benefits of Agent SDK

✅ **Built-in Tools** - No need to implement Bash, Read, Write
✅ **Permission System** - Hooks and modes already work
✅ **MCP Support** - Easy to add MCP servers
✅ **Type Safety** - Proper message types
✅ **Multi-turn** - Session management included
✅ **Interrupts** - Built-in interrupt support
✅ **Statistics** - Usage tracking in ResultMessage

## Next Steps

1. Create `bassi/core_v3/` directory
2. Implement `agent_session.py` with tests
3. Implement `tools.py` with tests
4. Implement `hooks.py` with tests
5. Implement `message_converter.py` with tests
6. Implement `web_server.py` with tests
7. Run E2E tests with real web UI
8. Iterate until everything works

Let's build it right this time! 🚀
