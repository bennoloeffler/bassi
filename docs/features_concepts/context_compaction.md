# Context Compaction and Session Management

**Feature**: Automatic context management and session persistence
**Status**: Implemented
**Files**: `bassi/agent.py`, `bassi/main.py`

## Overview

Bassi uses the Claude Agent SDK's built-in automatic context compaction to manage long conversations without hitting token limits. The system also persists sessions across restarts, allowing you to continue previous conversations.

## How It Works

### Automatic Compaction

The Claude Agent SDK automatically manages the context window:

1. **Monitoring**: SDK tracks the actual context window size internally (~200K tokens for Claude Sonnet 4.5)
2. **Triggering**: Compaction happens automatically at ~95% capacity (~190K tokens)
3. **Summarization**: Older messages are sent to Claude to create a concise summary
4. **Replacement**: Old detailed messages are replaced with the summary
5. **Continuation**: Conversation continues with preserved essential information

**What Gets Preserved:**
- Recent code modifications and decisions
- Current objectives and established patterns
- Project structure and configuration
- Architectural choices made during the session

**What Gets Summarized:**
- Resolved debugging sessions
- Exploratory discussions without code outcomes
- Detailed explanations no longer immediately relevant
- Historical context that's no longer needed for current work

### Visual Feedback

When compaction occurs, bassi displays:

```
┌─────────────── 🔄 Context Management ───────────────┐
│                                                      │
│  ⚡ Auto-Compaction Started                         │
│                                                      │
│  The Claude Agent SDK is automatically summarizing  │
│  older parts of the conversation to make room for   │
│  new interactions. This preserves:                  │
│    • Recent code modifications and decisions        │
│    • Current objectives and patterns                │
│    • Project structure and configuration            │
│                                                      │
│  Compaction happens automatically when the context  │
│  window approaches ~95% capacity.                   │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Session Persistence

Bassi saves session information to `.bassi_context.json` after each interaction:

```json
{
  "session_id": "a92190a4-290e-4182-be1b-56066ccccef4",
  "timestamp": 1761080958.621,
  "last_updated": "2025-10-21 23:09:18"
}
```

When you restart bassi in the same directory, it offers to resume the previous session:

```
┌────────── 🔄 Previous Session Loaded ──────────┐
│                                                 │
│  📋 Session Resumed                             │
│                                                 │
│  Session ID: a92190a4...                        │
│  Last Activity: 2025-10-21 23:09:18 (2 hours ago)│
│                                                 │
│  Claude has full access to previous             │
│  conversation context.                          │
│  The SDK will automatically compact old         │
│  messages if needed.                            │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Token Tracking vs Context Window

**Important Distinction:**

- **Session Total**: Cumulative tokens across the entire session (shown in bassi)
- **Context Window**: The actual ~200K token limit managed by the SDK (internal)

The usage line shows:

```
⏱️  15169ms | 💰 $0.0510 | 📊 Session Total: 323,852 tokens | 💵 Total Cost: $0.23
```

**Why Session Total can exceed 200K:**
- It's a cumulative count of ALL tokens ever sent/received in the session
- The SDK's internal context window only holds ~200K tokens at a time
- After compaction, old messages are removed but session total keeps growing
- This is expected and normal behavior

## Implementation Details

### Files Modified

**bassi/agent.py:476-490** - Updated usage display
```python
# Build usage line with honest labels
# Note: "Session Total" is cumulative across all interactions
# The SDK manages the actual context window internally with auto-compaction
usage_line = (
    f"⏱️  {duration_ms}ms | 💰 ${cost:.4f} | "
    f"📊 Session Total: {session_total:,} tokens | "
    f"💵 Total Cost: ${self.total_cost_usd:.4f}"
)
```

**bassi/agent.py:351-379** - Improved compaction event display
```python
if subtype == "compaction_start" or "compact" in subtype.lower():
    # Show detailed compaction info with Panel
    self.console.print(Panel(...))
```

**bassi/main.py:248-285** - Enhanced session resumption
```python
# Calculate time since last session
# Show session summary in a Panel
console.print(Panel(
    f"Session ID: {resume_session_id[:8]}...\n"
    f"Last Activity: {last_updated} ({time_ago})\n"
    ...
))
```

### SDK Integration

Bassi uses `ClaudeAgentOptions(resume=session_id)` to enable session persistence:

```python
# bassi/agent.py:91-110
options = ClaudeAgentOptions(
    cwd=str(Path.cwd()),
    allowed_tools=ALLOWED_TOOLS,
    sdk_mcp_servers=self.sdk_mcp_servers,
    mcp_servers={
        "bassi-tools": self.bassi_tools_server,
    },
    permission_mode="acceptEdits",
    resume=resume_session_id,  # Resume previous session if provided
    include_partial_messages=True,
)
```

## Best Practices

### For Users

1. **Let it work automatically**: Don't worry about context limits - the SDK handles it
2. **Resume sessions**: Use session persistence for long-running tasks
3. **Clear when needed**: Use `/clear` to start completely fresh if context feels stale
4. **Session Total is informational**: It's for understanding usage and cost, not a limit

### For Developers

1. **Don't try to manage context manually**: The SDK does it better
2. **Track cumulative usage**: For billing and analytics
3. **Listen for compaction events**: To inform users what's happening
4. **Preserve session_id**: Enables resumption across restarts

## Troubleshooting

### Q: Why does Session Total exceed 200K tokens?
**A**: Session Total is cumulative across all interactions. The SDK's internal context window is separate and capped at ~200K tokens.

### Q: How do I know when compaction happens?
**A**: Bassi shows a yellow panel notification when the SDK triggers compaction.

### Q: Can I control when compaction happens?
**A**: No, the SDK manages this automatically at ~95% capacity. This is by design and works well.

### Q: What if I want a fresh start?
**A**:
- Answer "n" when prompted to load previous context, OR
- Delete `.bassi_context.json` in your project directory, OR
- Use the `/clear` command (if implemented)

### Q: Is my conversation history saved to disk?
**A**: No! Only the session ID is saved. The actual conversation lives in the SDK's internal state (in memory during runtime, managed by Claude's servers).

## Related Documentation

- [Session Resumption Analysis](../../SESSION_RESUMPTION_ANALYSIS.md) - Deep dive into session management
- [SDK Message Types](../../SDK_MESSAGE_TYPES.md) - Understanding SDK messages
- [Status Line and Compaction](./status_line_and_compaction.md) - Display features

## References

- Claude Agent SDK: https://github.com/anthropics/claude-agent-sdk-python
- Claude Docs on Auto-Compact: https://claudelog.com/faqs/what-is-claude-code-auto-compact/
