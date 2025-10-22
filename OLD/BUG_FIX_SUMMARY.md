# Bug Fix Summary: SystemMessage AttributeError

## Issue
When running bassi with a simple query like "2 + 2", the application crashed with:
```
Error: 'SystemMessage' object has no attribute 'get'
```

## Root Cause
The Claude Agent SDK returns **dataclass objects**, not dictionaries:
- `SystemMessage` - initialization info
- `AssistantMessage` - actual response with content blocks
- `ResultMessage` - summary with usage stats

The code was incorrectly treating these as dictionaries using `.get()` method, which doesn't exist on dataclass objects.

## Solution
Updated `bassi/agent.py` to properly handle SDK message types:

### 1. Message Type Detection
Changed from:
```python
msg_type = msg.get("type", "")  # ❌ Fails on dataclass
```

To:
```python
msg_class_name = type(msg).__name__  # ✅ Works for all types
```

### 2. Display Logic (`_display_message`)
Now handles three SDK message types:

**SystemMessage**: Initialization (silently skip)
```python
if msg_class_name == "SystemMessage":
    return  # Don't display init messages
```

**AssistantMessage**: Extract text from content blocks
```python
elif msg_class_name == "AssistantMessage":
    content = getattr(msg, "content", [])
    for block in content:
        if hasattr(block, "text"):
            self.console.print(f"🤖 Assistant: {block.text}")
```

**ResultMessage**: Show summary stats
```python
elif msg_class_name == "ResultMessage":
    duration_ms = getattr(msg, "duration_ms", 0)
    cost = getattr(msg, "total_cost_usd", 0)
    self.console.print(f"⏱️  {duration_ms}ms | 💰 ${cost:.4f}")
```

### 3. Status Updates (`_update_status_from_message`)
Simplified status updates based on message class:
```python
if msg_class_name == "AssistantMessage":
    self.status_callback("💭 Responding...")
```

### 4. Debug Logging
Added comprehensive logging system:
- Logs to `bassi_debug.log` file
- INFO level by default
- DEBUG level with `BASSI_DEBUG=1` environment variable
- Helped identify exact message types and attributes

## Testing
Created `test_chat_simple.py` integration test that:
1. Creates BassiAgent
2. Sends "2 + 2" query
3. Iterates through all message types
4. Verifies successful completion

Test output:
```
📨 You: 2 + 2
🤖 Assistant: 2 + 2 = 4
⏱️  4516ms | 💰 $0.0053
✅ Test completed successfully!
```

## Files Changed
- `bassi/agent.py` - Fixed message handling in `_display_message` and `_update_status_from_message`
- `test_chat_simple.py` - New integration test for chat functionality

## Verification
- ✅ All unit tests pass (13 passed, 1 skipped)
- ✅ Integration test passes
- ✅ Code quality checks pass (black, ruff, mypy)
- ✅ Application runs successfully

## Lessons Learned
1. Always check SDK documentation for actual return types
2. Don't assume dictionary interfaces - use `isinstance()` or `type()` checks
3. Add logging early when debugging complex integrations
4. Create simple integration tests to reproduce bugs
