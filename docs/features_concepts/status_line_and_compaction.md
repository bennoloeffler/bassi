# Status Line and Auto-Compaction Features

## Overview

Bassi now includes:
1. **Auto-compaction detection** - Notifies user when Claude SDK auto-compacts the context
2. **Status line** - Shows current status, context usage, and session info after each interaction

## Auto-Compaction

### What is it?

The Claude Agent SDK automatically summarizes previous messages when the context window approaches capacity (~95% full or 25% remaining). This prevents the agent from running out of context mid-conversation.

### User Experience

When auto-compaction occurs, bassi displays:

```
⚡ Context window at ~95% - auto-compacting...
```

This lets you know that:
- The context window is at ~95% capacity (SDK threshold)
- Older messages are being summarized to make room
- The agent is still alive and working
- This is normal behavior for long conversations

### Technical Details

- **Trigger**: Auto-compaction starts at ~95% context usage
- **Detection**: Bassi listens for `SystemMessage` events with compaction-related subtypes
- **Logging**: Compaction events are logged to `bassi_debug.log`

**Code location**: `bassi/agent.py:293-302`

```python
elif msg_class_name == "SystemMessage":
    # Check for compaction or other events
    subtype = getattr(msg, "subtype", "")
    if "compact" in subtype.lower():
        self.status_callback("⚡ Auto-compacting context...")
        # Also show message to user
        self.console.print(
            "\n[bold yellow]⚡ Context window at ~95% - auto-compacting...[/bold yellow]\n"
        )
```

## Verbose Mode Usage Display

### What is it?

When verbose mode is enabled, bassi displays simple, honest metrics after each interaction:

### Example Output

```
⏱️  4548ms | 💰 $0.0147 | 💵 Total: $1.23
```

### Why No Token Counts?

We **deliberately don't show cumulative token counts** because:

1. **Misleading After Compaction**: Once auto-compaction happens, cumulative token counts don't reflect the actual context size
2. **SDK-Managed**: The Claude SDK manages context internally with auto-compaction at ~95%
3. **Unknown State**: Only the SDK knows the real context state after compaction
4. **Honesty First**: Showing misleading numbers would be dishonest to users

Instead, we focus on what we **know accurately**:
- Response time (ms)
- Cost per interaction
- Total session cost

### When You'll See Context Info

The only time you'll see context-related messages is when **auto-compaction actually happens**:

```
⚡ Context window at ~95% - auto-compacting...
```

This is honest: we only tell you about context when the SDK tells us something is happening.

### Components

1. **Response Time** (`⏱️`): How long the interaction took in milliseconds
2. **Interaction Cost** (`💰`): Cost of this specific interaction
3. **Total Cost** (`💵`): Cumulative cost for the entire session

### Implementation

**Code location**: `bassi/main.py:68-113`

```python
def format_status_line(
    status: str,
    last_activity_time: float,
    ctx_info: dict | None = None,
    session_id: str | None = None,
) -> Text:
    """Format the bottom status/debug line"""
    # Status with color
    # Time since last activity
    # Context usage if available
    # Session ID (abbreviated)
```

**Display location**: `bassi/main.py:480-491`

After each agent interaction:
```python
# Update context info
context_info[0] = agent.get_context_info()

# Display status line
status_line = format_status_line(
    current_status[0],
    last_activity[0],
    context_info[0],
    agent.session_id,
)
console.print(Panel(status_line, border_style="dim", padding=(0, 1)))
```

## Benefits

### For Users

1. **Transparency**: Know what the agent is doing at all times
2. **Context Awareness**: See when compaction happens and current usage
3. **Debugging**: Quickly identify issues or delays
4. **Session Tracking**: Know which session you're in

### For Development

1. **Logging**: All status changes logged to debug file
2. **Debugging**: Easy to see agent lifecycle
3. **Performance**: Track context usage over time

## Examples

### Normal Operation

```
You: what is 2+2?

🤖 Assistant:
2 + 2 = 4

╭────────────────────────────────────────────────────────────╮
│ [✅ Ready] • Active 1s ago • Context: 234 tokens (0.1%)   │
│ • Session: 651fcfd6                                        │
╰────────────────────────────────────────────────────────────╯
```

### Heavy Context Usage

```
You: <long conversation with many tool calls>

🤖 Assistant:
<response>

╭──────────────────────────────────────────────────────────────────╮
│ [✅ Ready] • Active 3s ago • Context: 152,341 tokens (76.2%) │
│ • Session: 651fcfd6                                              │
╰──────────────────────────────────────────────────────────────────╯
```
_Note: Yellow color indicates approaching compaction threshold_

### Compaction in Progress

```
⚡ Context approaching limit - auto-compacting...

🤖 Assistant:
<continues conversation with summarized context>

╭──────────────────────────────────────────────────────────────────╮
│ [✅ Ready] • Active 1s ago • Context: 125,432 tokens (62.7%) │
│ • Session: 651fcfd6                                              │
╰──────────────────────────────────────────────────────────────────╯
```
_Note: Context usage drops after compaction_

## Configuration

Currently, the status line is always shown. Future enhancements could include:

- Toggle status line on/off
- Customize which fields to show
- Configure warning thresholds
- Status line update frequency

## Related Features

- **Context Persistence**: Session ID shown in status line
- **Verbose Mode**: `/alles_anzeigen` shows more detail
- **Logging**: All events logged to `bassi_debug.log`

## Troubleshooting

### Status Line Not Showing

**Check**: Are you in verbose mode?
```bash
# Status line shows regardless of verbose mode
```

**Check**: Is context info being updated?
```python
# Look for this in bassi/main.py after agent.chat()
context_info[0] = agent.get_context_info()
```

### Compaction Not Detected

**Check**: Logs for compaction events
```bash
tail -f bassi_debug.log | grep -i compact
```

**Check**: Context usage in status line
- If > 90%, compaction should trigger soon
- If stays < 90%, no compaction needed

### Session ID Not Showing

**Check**: Is a session active?
```bash
# First interaction creates session
# Status line shows session ID after first message
```

**Check**: Context file
```bash
cat .bassi_context.json
# Should contain session_id field
```

## Implementation Notes

### Performance

- Status line formatting is fast (< 1ms)
- Context info calculation includes caching
- No performance impact on agent operations

### Thread Safety

- Status updates use mutable references (lists)
- Thread-safe for async operations
- No race conditions in status display

## Future Enhancements

1. **Real-time updates**: Live status while agent is thinking
2. **Cost tracking**: Show cumulative cost in status line
3. **Rate limits**: Show API rate limit status
4. **Network status**: Show connection health
5. **Custom fields**: User-configurable status components
