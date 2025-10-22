# Session Context Saving and Loading Analysis

## Overview

This analysis examines how bassi saves and loads conversation context across sessions, what information is stored, and what the SDK provides about previous session state.

---

## 1. Context Saved in .bassi_context.json

### File Location and Format

**File**: `.bassi_context.json` (in the current working directory)

**Current Contents**:
```json
{
  "session_id": "a92190a4-290e-4182-be1b-56066ccccef4",
  "timestamp": 1761080958.621,
  "last_updated": "2025-10-21 23:09:18"
}
```

### Data Structure

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `session_id` | string | Unique identifier for the conversation session | SDK (ClaudeSDKClient) |
| `timestamp` | float | Unix timestamp when context was saved | Python `time.time()` |
| `last_updated` | string | Human-readable datetime when context was saved | Python `time.strftime()` |

### How It's Saved

**Location**: `/Users/benno/projects/ai/bassi/bassi/agent.py` (lines 145-158)

```python
def save_context(self) -> None:
    """Save current context to file"""
    try:
        import time

        context_data = {
            "session_id": self.session_id,
            "timestamp": time.time(),
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.context_file.write_text(json.dumps(context_data, indent=2))
        logger.info(f"Context saved - session_id: {self.session_id}")
    except Exception as e:
        logger.warning(f"Failed to save context: {e}")
```

### When Context is Saved

1. **After each successful chat interaction** (in `agent.py`, line 262)
   - Called in the `finally` block of `chat()` method
   - Only occurs if the chat completes successfully
   
2. **Triggered by**: `async for _ in agent.chat(user_input): pass` in main.py (line 414)

---

## 2. How Context is Loaded

### Load Method

**Location**: `/Users/benno/projects/ai/bassi/bassi/agent.py` (lines 160-175)

```python
def load_context(self) -> dict | None:
    """Load context from file"""
    try:
        if self.context_file.exists():
            data: dict = json.loads(self.context_file.read_text())
            session_id = data.get("session_id", "unknown")
            last_updated = data.get("last_updated", "unknown")
            logger.info(
                f"Context loaded - session_id: {session_id}, last_updated: {last_updated}"
            )
            return data
        logger.info("No previous context found")
        return None
    except Exception as e:
        logger.warning(f"Failed to load context: {e}")
        return None
```

### Loading Flow

**Location**: `/Users/benno/projects/ai/bassi/bassi/main.py` (lines 230-274)

1. **Step 1: Check for saved context file**
   ```python
   context_file = Path.cwd() / ".bassi_context.json"
   if context_file.exists():
   ```

2. **Step 2: Parse the JSON and display prompt**
   ```python
   saved_context = json.loads(context_file.read_text())
   console.print("\n[bold yellow]📋 Found saved context from previous session[/bold yellow]")
   ```

3. **Step 3: Ask user whether to resume**
   ```python
   load_choice = Prompt.ask(
       "Load previous context?",
       choices=["y", "n"],
       default="y",
   )
   ```

4. **Step 4: Extract session_id if user chooses to resume**
   ```python
   if load_choice.lower() == "y":
       resume_session_id = saved_context.get("session_id")
       if resume_session_id:
           console.print("[bold green]✅ Will resume previous session[/bold green]")
           console.print(f"[dim]   Session ID: {resume_session_id}[/dim]")
   ```

5. **Step 5: Pass to agent initialization**
   ```python
   agent = BassiAgent(
       status_callback=update_status,
       resume_session_id=resume_session_id,
   )
   ```

### Session Resumption in BassiAgent

**Location**: `/Users/benno/projects/ai/bassi/bassi/agent.py` (lines 81-119)

```python
def __init__(
    self, status_callback=None, resume_session_id: str | None = None
) -> None:
    # ...
    self.options = ClaudeAgentOptions(
        mcp_servers=self.sdk_mcp_servers,
        system_prompt=self.SYSTEM_PROMPT,
        allowed_tools=[
            "mcp__bash__execute",
            "mcp__web__search",
        ],
        permission_mode="acceptEdits",
        resume=resume_session_id,  # <-- This is the key parameter
        include_partial_messages=True,
    )
    
    self.session_id: str | None = resume_session_id
```

---

## 3. Information Available When Resuming a Session

### From Saved Context File

When resuming, the `.bassi_context.json` provides:
- **Session ID**: Required to reconnect to the previous conversation
- **Timestamp**: When the context was last saved (useful for UI display)
- **Last Updated**: Human-readable timestamp for user display

### From the SDK When Resuming

The Claude Agent SDK provides several message types during and after session resumption:

#### 3.1 **ResultMessage** (Per Interaction)

**Type**: `ResultMessage` dataclass in SDK types

**Available fields**:
```python
@dataclass
class ResultMessage:
    """Result message with cost and usage information."""
    
    subtype: str                           # Event type (e.g., "result")
    duration_ms: int                       # Time taken for this turn
    duration_api_ms: int                   # API call duration
    is_error: bool                         # Whether an error occurred
    num_turns: int                         # Total number of turns in session
    session_id: str                        # Session identifier (UUID format)
    total_cost_usd: float | None = None   # USD cost for this interaction
    usage: dict[str, Any] | None = None   # Token usage breakdown
    result: str | None = None              # Result summary
```

**Where it's captured**: Lines 244-250 in agent.py
```python
if msg_class_name == "ResultMessage":
    sdk_session_id = getattr(msg, "session_id", None)
    if sdk_session_id and sdk_session_id != self.session_id:
        logger.info(f"SDK session_id captured: {sdk_session_id}")
        self.session_id = sdk_session_id
```

**Usage tracking** (lines 466-474):
```python
# Update cumulative token tracking
self.total_input_tokens += usage.get("input_tokens", 0)
self.total_output_tokens += usage.get("output_tokens", 0)
self.total_cache_creation_tokens += usage.get(
    "cache_creation_input_tokens", 0
)
self.total_cache_read_tokens += usage.get(
    "cache_read_input_tokens", 0
)
self.total_cost_usd += cost
```

#### 3.2 **SystemMessage** (Session Events)

**Type**: `SystemMessage` dataclass

**Available fields**:
```python
@dataclass
class SystemMessage:
    """System message with metadata."""
    
    subtype: str               # Event type (e.g., "compaction_start")
    data: dict[str, Any]       # Event-specific data
```

**Examples**:
- `subtype="compaction_start"`: Context compaction starting
- Other subtypes for session initialization

**Where it's handled**: Lines 351-368 in agent.py

#### 3.3 **AssistantMessage** (Responses)

**Type**: `AssistantMessage` dataclass

**Available fields**:
```python
@dataclass
class AssistantMessage:
    """Assistant message with content blocks."""
    
    content: list[ContentBlock]     # List of content blocks
    model: str                      # Model used (e.g., "claude-sonnet-4-5")
    parent_tool_use_id: str | None  # Parent tool use ID if nested
```

**Note**: When resuming, previous conversation history is NOT streamed to the client, but Claude has access to it internally.

#### 3.4 **StreamEvent** (Real-time Streaming)

**Type**: `StreamEvent` dataclass

**Available fields**:
```python
@dataclass
class StreamEvent:
    """Stream event for partial message updates during streaming."""
    
    uuid: str                      # Event UUID
    session_id: str                # Session identifier
    event: dict[str, Any]          # Raw Anthropic API stream event
    parent_tool_use_id: str | None # Parent tool ID if nested
```

**Contains**: Streaming text chunks with `content_block_delta` events

---

## 4. Session Resumption Flow in Code

### Flow Diagram

```
main_async()
    ↓
[Check .bassi_context.json exists]
    ↓ (if yes)
[Load JSON and parse]
    ↓
[Prompt user: "Load previous context?"]
    ↓ (if yes)
[Extract session_id from saved_context]
    ↓
BassiAgent(resume_session_id=session_id)
    ↓
ClaudeAgentOptions(resume=session_id)
    ↓
ClaudeSDKClient(options)
    ↓
[Agent.chat() → SDK handles session resumption]
    ↓
[ResultMessage includes num_turns, usage, cost]
    ↓
[save_context() updates .bassi_context.json]
```

### Key Code Locations

| Step | File | Lines | Function |
|------|------|-------|----------|
| Check context | main.py | 234-235 | `main_async()` |
| Parse JSON | main.py | 237 | `main_async()` |
| Ask user | main.py | 242-264 | `main_async()` |
| Extract session | main.py | 249 | `main_async()` |
| Create agent | main.py | 279-282 | `main_async()` |
| SDK resumption | agent.py | 108 | `__init__()` |
| Capture session | agent.py | 244-250 | `chat()` |
| Save context | agent.py | 262 | `chat()` |

---

## 5. What SDK Provides About Previous Session State

### Information Available

The SDK provides the following information about the **current/resumed session**:

1. **Session Continuity**
   - Same `session_id` returned in ResultMessage
   - Proves conversation is properly resumed
   - Claude has full access to previous messages internally

2. **Turn Counter**
   - `ResultMessage.num_turns`: Total turns in this session
   - Indicates how many interactions have occurred
   - Useful for detecting when session was resumed

3. **Usage Statistics** (Per Interaction)
   - `input_tokens`: Tokens in the prompt
   - `output_tokens`: Tokens generated
   - `cache_creation_input_tokens`: Cache creation cost
   - `cache_read_input_tokens`: Cache hits
   - `total_cost_usd`: USD cost for this turn

4. **Performance Metrics**
   - `duration_ms`: Total time for interaction
   - `duration_api_ms`: API call time
   - `is_error`: Whether an error occurred

### Information NOT Available

⚠️ **Limitation**: The SDK does not provide an API to retrieve historical messages programmatically.

- ❌ Cannot get list of previous messages/turns
- ❌ Cannot access previous tool calls
- ❌ Cannot retrieve conversation history on startup
- ✅ BUT: Claude has full internal access to history for context

**Related GitHub Issue**: [anthropics/claude-agent-sdk-python#109](https://github.com/anthropics/claude-agent-sdk-python/issues/109)

---

## 6. Context Information Available for UI Display on Resume

### What Can Be Shown

Based on available data, when resuming a session, the UI could show:

1. **From .bassi_context.json**:
   - Session ID (current format only shows first part)
   - Last session activity timestamp
   - How long ago session was created

2. **From First ResultMessage After Resumption**:
   - Confirmation that session resumed (same session_id)
   - Total turns in this session (indicates activity level)
   - Cumulative token usage
   - Cumulative cost
   - Context window status

### Example Summary Display

```
📋 Session Resumed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Session ID: a92190a4-290e-4182-be1b-56066ccccef4
Last Activity: 2025-10-21 23:09:18 (2 hours ago)
Total Interactions: 12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Tokens Used: 45,234
Total Cost: $0.23
Context Usage: 22,451 / 200,000 tokens (11%)
```

---

## 7. Implementation Details

### Session ID Format

Session IDs from the SDK follow UUID4 format:
- Example: `a92190a4-290e-4182-be1b-56066ccccef4`
- Generated by Claude Agent SDK
- Stored in `.bassi_context.json` after first interaction

### Token Usage Tracking

BassiAgent tracks cumulative usage across session:

**Stored in agent instance**:
- `self.total_input_tokens`
- `self.total_output_tokens`
- `self.total_cache_creation_tokens`
- `self.total_cache_read_tokens`
- `self.total_cost_usd`

**Method**: `get_context_info()` (lines 177-204)
```python
def get_context_info(self) -> dict:
    """Get context size and info"""
    current_context_size = (
        self.total_input_tokens
        + self.total_cache_creation_tokens
        + self.total_cache_read_tokens
    )
    
    context_percentage = (
        current_context_size / self.context_window_size
    ) * 100
```

### Context Window Management

- Window size: 200,000 tokens (Claude Sonnet 4.5)
- Compaction threshold: 150,000 tokens (75% of window)
- Auto-compaction triggered when approaching threshold
- SystemMessage with `subtype="compaction_start"` indicates event

---

## 8. Non-Interactive Mode Behavior

**Location**: main.py, lines 265-271

In non-interactive environments (EOF on input):
```python
except (EOFError, KeyboardInterrupt):
    # Non-interactive mode - load context by default
    resume_session_id = saved_context.get("session_id")
    if resume_session_id:
        console.print(
            "[bold green]✅ Will resume previous session (non-interactive mode)[/bold green]"
        )
```

- Automatically resumes saved session without prompting
- Useful for scripted/piped usage

---

## Summary

| Aspect | Details |
|--------|---------|
| **Storage** | `.bassi_context.json` in current directory |
| **Saved Data** | session_id, timestamp, last_updated |
| **Loading** | User prompted; auto-resume in non-interactive mode |
| **Session Resumption** | Via `ClaudeAgentOptions.resume` parameter |
| **Per-Turn Info** | ResultMessage provides num_turns, usage, cost |
| **Historical Access** | Not exposed via SDK API (internal only) |
| **Summary Possible** | Yes, from session_id, timestamps, and turn counts |
| **Token Tracking** | Cumulative per agent instance |
| **Context Window** | 200K tokens, auto-compact at 75% |

