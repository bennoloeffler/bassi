# Claude Agent SDK Message Types Reference

## Overview

When the SDK sends messages during session operations (including resumption), these are the available message types and their properties. This helps understand what information can be extracted for UI display.

---

## 1. ResultMessage

**Purpose**: Sent after each interaction completes with result and usage information.

**Python Type Definition**:
```python
@dataclass
class ResultMessage:
    """Result message with cost and usage information."""
    
    subtype: str                           # Event type (e.g., "result")
    duration_ms: int                       # Time taken for this interaction
    duration_api_ms: int                   # API call duration
    is_error: bool                         # Whether an error occurred
    num_turns: int                         # Total turns in this session
    session_id: str                        # Session identifier (UUID)
    total_cost_usd: float | None = None   # USD cost for this interaction
    usage: dict[str, Any] | None = None   # Token usage breakdown
    result: str | None = None              # Result summary
```

**Usage Dict Contents**:
```python
{
    "input_tokens": 1234,                      # Tokens in prompt
    "output_tokens": 567,                      # Tokens generated
    "cache_creation_input_tokens": 0,          # Cache creation cost
    "cache_read_input_tokens": 0,              # Cache hits
}
```

**Example Usage in Code**:
```python
# From agent.py lines 466-474
self.total_input_tokens += usage.get("input_tokens", 0)
self.total_output_tokens += usage.get("output_tokens", 0)
self.total_cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
self.total_cache_read_tokens += usage.get("cache_read_input_tokens", 0)
self.total_cost_usd += cost
```

**When Available**: After each interaction completes

**For UI Display**:
- `session_id`: Confirm session resumed
- `num_turns`: Show conversation length
- `duration_ms`: Show responsiveness
- `total_cost_usd`: Show cost impact
- `usage`: Show token consumption
- `is_error`: Show error status

---

## 2. SystemMessage

**Purpose**: Sent for system events like compaction, initialization, etc.

**Python Type Definition**:
```python
@dataclass
class SystemMessage:
    """System message with metadata."""
    
    subtype: str               # Event type (e.g., "compaction_start")
    data: dict[str, Any]       # Event-specific data
```

**Known Subtypes**:
- `"compaction_start"`: Context compaction is starting
- `"initialization"`: Session initialization events
- Other system events

**Example Usage in Code**:
```python
# From agent.py lines 356-365
if (
    subtype == "compaction_start"
    or "compact" in subtype.lower()
):
    self.console.print(
        "\n[bold yellow]⚡ Context approaching limit - auto-compacting...[/bold yellow]\n"
    )
```

**When Available**: During session lifecycle events

**For UI Display**:
- Warn when context compaction starts
- Show initialization progress

---

## 3. StreamEvent

**Purpose**: Real-time streaming of response text as it's generated.

**Python Type Definition**:
```python
@dataclass
class StreamEvent:
    """Stream event for partial message updates during streaming."""
    
    uuid: str                      # Event UUID
    session_id: str                # Session identifier
    event: dict[str, Any]          # Raw Anthropic API stream event
    parent_tool_use_id: str | None # Parent tool ID if nested
```

**Event Dict Structure** (for text):
```python
{
    "type": "content_block_delta",
    "delta": {
        "type": "text_delta",
        "text": "Partial text..."
    }
}
```

**Example Usage in Code**:
```python
# From agent.py lines 327-347
if event_type == "content_block_delta":
    delta = event.get("delta", {})
    if delta.get("type") == "text_delta":
        text = delta.get("text", "")
        # Stream text directly to console
        self.console.print(text, end="")
```

**When Available**: During response generation

**For UI Display**:
- Used for real-time text streaming
- Not typically shown as summary info

---

## 4. AssistantMessage

**Purpose**: Claude's response after processing request.

**Python Type Definition**:
```python
@dataclass
class AssistantMessage:
    """Assistant message with content blocks."""
    
    content: list[ContentBlock]     # List of content blocks
    model: str                      # Model used (e.g., "claude-sonnet-4-5")
    parent_tool_use_id: str | None  # Parent tool ID if nested
```

**Content Block Types**:
- `TextBlock`: Text response
- `ToolUseBlock`: Tool call
- `ThinkingBlock`: Internal reasoning
- `ToolResultBlock`: Result from tool

**Example Usage in Code**:
```python
# From agent.py lines 371-395
content = getattr(msg, "content", [])
for block in content:
    block_type = type(block).__name__
    
    if block_type == "TextBlock":
        # Text was already streamed
        pass
    elif block_type == "ToolUseBlock":
        # Tool call - show what tool is being used
        tool_name = getattr(block, "name", "unknown")
        tool_input = getattr(block, "input", {})
```

**When Available**: After Claude processes request

**For UI Display**:
- Not typically shown in summary (content displayed inline)

---

## 5. UserMessage

**Purpose**: User's input messages (rarely received by SDK client).

**Python Type Definition**:
```python
@dataclass
class UserMessage:
    """User message."""
    
    content: str | list[ContentBlock]
    parent_tool_use_id: str | None = None
```

**For UI Display**:
- Not typically displayed (user knows their own input)

---

## Message Flow During Session Resume

```
Application Start
    ↓
[User chooses to resume]
    ↓
BassiAgent initialized with resume_session_id
    ↓
agent.chat("user input")
    ↓
[SDK connects to existing session]
    ↓
StreamEvent (text streaming) ← for real-time display
    ↓
AssistantMessage (response content) ← for processing
    ↓
ResultMessage (usage/stats) ← for summary display
    ↓
[Optional] SystemMessage (compaction events) ← for warnings
```

---

## Recommended UI Display on Session Resume

### Option 1: Minimal Summary
```
✅ Session Resumed (Session ID: a92190a4-290e-4182-be1b-56066ccccef4)
Last Activity: 2025-10-21 23:09:18 | Total Interactions: 12
```

### Option 2: Detailed Summary
```
📋 Session Resumed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Session ID:        a92190a4-290e-4182-be1b-56066ccccef4
Last Activity:     2025-10-21 23:09:18 (2 hours ago)
Total Turns:       12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Context Usage:     45,234 / 200,000 tokens (22.6%)
Cumulative Cost:   $0.23
Cache Efficiency:  234 tokens read, 0 created
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Data Sources for Summary

| Item | Source | How to Access |
|------|--------|---------------|
| Session ID | .bassi_context.json | `saved_context.get("session_id")` |
| Last Activity | .bassi_context.json | `saved_context.get("last_updated")` |
| Total Turns | First ResultMessage | `result_msg.num_turns` |
| Context Usage | agent.get_context_info() | `agent.total_input_tokens + cache_creation + cache_read` |
| Total Cost | agent object | `agent.total_cost_usd` |
| Cache Stats | agent object | `agent.total_cache_read_tokens` |

---

## Known Limitations

1. **No Historical Message API**
   - Cannot retrieve list of previous messages from SDK
   - Cannot replay conversation history on startup
   - Claude has internal access to history (for context awareness)

2. **No Session Metadata**
   - SDK does not provide session creation time
   - Must store manually in .bassi_context.json
   - No API to list all sessions

3. **Turn Count**
   - `num_turns` is available but only after resuming and interacting
   - Not available before first interaction in resumed session

---

## Code Integration Checklist

For displaying session resume summary, ensure access to:

- [ ] `.bassi_context.json` file contents (timestamp, session_id)
- [ ] ResultMessage from first interaction (num_turns, usage, cost)
- [ ] agent.get_context_info() for cumulative stats
- [ ] agent.total_cost_usd for cost display
- [ ] Check ResultMessage.session_id matches original to confirm proper resumption

---

## References

- **ClaudeAgentOptions**: Where `resume` parameter is set
- **ResultMessage**: Token usage and session info
- **SystemMessage**: Compaction events
- **StreamEvent**: Real-time text streaming
- **agent.py**: Lines 244-250 (session capture), 466-474 (usage tracking)

