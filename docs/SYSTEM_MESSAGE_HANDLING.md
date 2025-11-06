# System Message Handling in Bassi V3

## Overview

The Claude Agent SDK sends `SystemMessage` objects for various purposes. Not all of them should be displayed to users.

## SDK SystemMessage Structure

```python
SystemMessage(
    subtype: str,  # Message category/type
    data: dict     # Arbitrary fields depending on subtype
)
```

## Known Subtypes

| Subtype | Purpose | Show to User? | When Sent |
|---------|---------|---------------|-----------|
| `init` | Capability announcement (tools, MCP servers, agents, slash commands, skills) | ❌ **NO** | Startup, after tool changes |
| `compaction_start` | Context window auto-summarization | ✅ **YES** | When context hits ~95% capacity |
| Others with `content` | Warnings, errors, status updates | ✅ **YES** | As needed |

## Original SDK Data Fields

### `init` Subtype
```python
data = {
    "tools": [{"name": "tool1"}, {"name": "tool2"}, ...],
    "mcp_servers": [...],
    "slash_commands": [...],
    "skills": [...],
    "agents": [...]
}
```

### `compaction_start` Subtype
```python
data = {
    # May contain compaction stats (not well documented)
}
```

### Other Subtypes
```python
data = {
    "content": "Human-readable message text",
    # or "message" or "text"
}
```

## Implementation

### Backend Filter (`web_server_v3.py`)

**Strategy: Subtype-based filtering**

1. **Skip `init` entirely** - metadata not for display
2. **Transform compaction** - add user-friendly message
3. **Check content** for other subtypes - only show if displayable

```python
elif event_type == "system":
    subtype = event.get("subtype", "")

    # Skip metadata
    if subtype == "init":
        continue

    # Add friendly message for compaction
    if "compact" in subtype.lower():
        event["content"] = "⚡ **Auto-Compaction Started**\n\n..."

    # Other: only show if has content
    else:
        if not any(key in event for key in ["content", "message", "text"]):
            continue
```

### Frontend Filter (`app.js`)

**Strategy: Belt-and-suspenders approach**

1. **Skip `init` by subtype**
2. **Skip if no content**
3. **Special styling for compaction**

```javascript
handleSystemMessage(msg) {
    const subtype = msg.subtype || ''
    const content = msg.content || msg.message || msg.text || null

    // Skip 'init'
    if (subtype === 'init') return

    // Skip empty
    if (!content || content.trim() === '') return

    // Special styling for compaction
    const isCompaction = subtype.includes('compact')
    // ... render with appropriate styling
}
```

### CSS Styling

- **Regular system messages**: Blue-tinted background, info icon (ℹ️)
- **Compaction messages**: Yellow-tinted background, lightning icon (⚡)

## Why This Design?

### Problem
Before this fix:
- SDK sent `init` SystemMessages with tool lists, MCP servers, etc.
- Backend unpacked all fields: `{"type": "system", "subtype": "init", "tools": [...], ...}`
- Frontend looked for `content`/`message`/`text` → found nothing → showed empty box

### Solution
**Filter by subtype + content presence:**
- Recognize that `init` is metadata → always skip
- Recognize that `compaction_start` is important → always show (with friendly message)
- For others → only show if they have displayable content

### Why Two Layers?
1. **Backend filter** - prevents sending unnecessary data over WebSocket
2. **Frontend filter** - safety net in case SDK adds new metadata subtypes

## Testing

To trigger compaction message (for testing):
1. Have a very long conversation (>190K tokens)
2. SDK will auto-compact at ~95% capacity
3. You should see: "⚡ Auto-Compaction Started" message in yellow box

To verify `init` is filtered:
1. Start fresh conversation
2. Check browser console logs
3. Should see: `⏩ Skipping "init" system message (metadata only)`
4. Should NOT see empty system message box in UI

## References

- V1 CLI implementation: `bassi/agent.py:684-716`
- Message converter: `bassi/core_v3/message_converter.py:121-148`
- Web server filter: `bassi/core_v3/web_server_v3.py:798-831`
- Frontend handler: `bassi/static/app.js:1125-1165`
