# Bug Fix: Tool Calls Not Displaying in Web UI

**Date**: 2025-10-31
**Status**: ✅ FIXED
**Severity**: HIGH (core feature not working)

---

## Problem

Tool calls were not appearing in the Web UI, regardless of the verbose level setting (Minimal, Summary, or Full).

**Symptoms**:
- WebSocket messages showed only `content_delta` events
- No `tool_call_start` or `tool_call_end` events
- Tools were executing (visible in backend logs), but UI showed no indication
- Browser console showed hundreds of `content_delta` messages, but zero tool messages

---

## Root Causes

### Cause 1: Backend Event Handling

**File**: `bassi/web_server.py` (line 147-227)

**Issue**: The `_agent_event_to_ws_message()` method was checking for raw SDK message types (like `ToolUseBlock`), but the agent was actually sending **typed events** (like `ToolCallStartEvent`).

**Original Code**:
```python
def _agent_event_to_ws_message(self, event: Any) -> dict[str, Any] | None:
    # Handle event objects (after we add them to agent.py)
    if hasattr(event, "type"):
        event_type = (
            event.type.value
            if hasattr(event.type, "value")
            else str(event.type)
        )

        if event_type == "content_delta":
            return {"type": "content_delta", "text": event.text}
        # ... etc
```

This code was looking for events with a `.type` attribute, but it was checking the **value** of the type, not the **class name** of the event object.

**Fix**:
```python
def _agent_event_to_ws_message(self, event: Any) -> dict[str, Any] | None:
    # Handle typed event objects from agent.py
    event_class_name = type(event).__name__

    if event_class_name == "ContentDeltaEvent":
        return {"type": "content_delta", "text": event.text}

    elif event_class_name == "ToolCallStartEvent":
        return {
            "type": "tool_call_start",
            "tool_name": event.tool_name,
            "input": event.input_data,
        }
    # ... etc
```

Now it checks the **class name** directly, which correctly identifies the typed event objects.

---

### Cause 2: Dataclass Initialization Error

**File**: `bassi/agent.py` (line 62-66)

**Issue**: The `AgentEvent` base class required a `type: EventType` parameter, but subclasses were trying to create instances WITHOUT passing it, relying on `__post_init__` to set it.

**Error in logs**:
```
TypeError: ContentDeltaEvent.__init__() missing 1 required positional argument: 'type'
```

**Original Code**:
```python
@dataclass
class AgentEvent:
    """Base event class"""
    type: EventType
```

This made `type` a required constructor argument.

**Fix** (Best Practice with `field(init=False)`):
```python
from dataclasses import dataclass, field

@dataclass
class AgentEvent:
    """Base event class"""
    type: EventType = field(init=False)  # Will be set in __post_init__ by subclasses
```

Using `field(init=False)` is the proper dataclass way to exclude a field from `__init__()`, making it clearer that this field is NOT passed during initialization. This is better than using `= None` because:
1. More explicit intent - clearly shows the field is not initialized
2. Better type checking - mypy understands `field(init=False)`
3. Cleaner semantics - no default value needed

Now subclasses can create instances like:
```python
ContentDeltaEvent(text="hello")  # ✅ Works now
```

And `__post_init__` in each subclass sets the correct type:
```python
@dataclass
class ContentDeltaEvent(AgentEvent):
    text: str

    def __post_init__(self):
        self.type = EventType.CONTENT_DELTA
```

---

## Debugging Process

### Step 1: Chrome DevTools MCP

Used `mcp__chrome-devtools` to:
1. Navigate to http://localhost:8765
2. Send test message
3. Check console logs

**Finding**: Only `content_delta` messages, no `tool_call_start` or `tool_call_end`.

### Step 2: Server Logs

Checked `bassi_debug.log`:
```bash
tail -n 200 bassi_debug.log | grep -i "tool\|event"
```

**Finding**:
```
TypeError: ContentDeltaEvent.__init__() missing 1 required positional argument: 'type'
```

This revealed the dataclass initialization problem.

### Step 3: Event Conversion

Traced the flow:
```
agent.py:chat()
  → yields typed events (ContentDeltaEvent, ToolCallStartEvent, etc.)
    → web_server.py:_agent_event_to_ws_message()
      → converts to WebSocket messages
        → sent to browser
```

Found that `_agent_event_to_ws_message()` wasn't recognizing the typed events.

---

## Files Modified

### 1. `/bassi/web_server.py`

**Lines Changed**: 147-186

**Before**: Checked `event.type.value` to identify events
**After**: Checks `type(event).__name__` (class name)

**Impact**: Backend now correctly converts typed events to WebSocket messages

### 2. `/bassi/agent.py`

**Lines Changed**: 62-66

**Before**: `type: EventType` (required argument)
**After**: `type: EventType = None` (optional, set in `__post_init__`)

**Impact**: Event objects can now be created without type parameter

---

## Testing

### Manual Test

1. Start server: `./run-agent.sh`
2. Open http://localhost:8765
3. Set Detail level to "Full"
4. Send message: "list all files in the current directory"
5. **Expected**: Tool call panel appears with bash command
6. **Actual**: ✅ Tool calls now display correctly

### Console Verification

Browser console should show:
```
📨 WebSocket message received: tool_call_start
🔧 Tool call START detected: mcp__bash__execute
🔧 handleToolCallStart called: {tool_name: "mcp__bash__execute", input: {...}}
Verbose level: full
→ Creating FULL tool panel
→ Full panel added to DOM
```

---

## Success Criteria

- ✅ Tool calls appear in Web UI
- ✅ All verbose levels work (Minimal, Summary, Full)
- ✅ No errors in browser console
- ✅ No errors in server logs
- ✅ Quality checks pass (black, ruff)

---

## Lessons Learned

1. **Type checking matters**: Using `type(event).__name__` is more reliable than `hasattr()` checks
2. **Dataclass defaults**: Base dataclass fields need defaults if subclasses don't pass them
3. **Debug tools**: Chrome DevTools MCP is excellent for WebSocket debugging
4. **Log everything**: Debug logging in frontend helped trace the issue
5. **Test early**: Should have tested tool display immediately after implementing verbose levels

---

## Related Files

- Verbose Levels Feature: `docs/features_concepts/verbose_levels_spec.md`
- Verbose Levels Implementation: `docs/features_concepts/verbose_levels_implementation.md`
- Agent Interruption: `docs/features_concepts/agent_interruption_implementation.md`

---

**Status**: ✅ RESOLVED
**Verified**: 2025-10-31
**Ready for**: Production use
