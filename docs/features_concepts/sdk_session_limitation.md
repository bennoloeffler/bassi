# Claude Agent SDK Session Switching Limitation

## Summary

The Claude Agent SDK (as of v0.0.20) **cannot switch between chat histories** within a single connected client. This is a fundamental architectural limitation that affects how Bassi handles chat context switching.

## The SDK Limitation

From the SDK source code (`claude_agent_sdk/client.py`, lines 46-52):

```
Caveat: As of v0.0.20, you cannot use a ClaudeSDKClient instance across
different async runtime contexts (e.g., different trio nurseries or asyncio
task groups). The client internally maintains a persistent anyio task group
for reading messages that remains active from connect() until disconnect().
This means you must complete all operations with the client within the same
async context where it was connected.
```

## What This Means

### SDK Session Management

The SDK provides two session-related features:

1. **`options.resume = session_id`** - Set at **connection time**
   - Loads conversation history from SDK's internal storage
   - Only works when creating the client connection
   - Cannot be changed after connecting

2. **`session_id` parameter in `query()`** - Set per query
   - Tags messages with a session identifier
   - Does NOT load historical conversation
   - Just for tracking/organizing, not context restoration

### Why We Can't Switch Sessions

```
┌─────────────────────────────────────────────────────────┐
│                    Server Startup                        │
│                                                         │
│  Agent.connect() ─────────────────► Task A              │
│  (options.resume = "chat_123")      (async context 1)   │
│                                                         │
└─────────────────────────────────────────────────────────┘
                         │
                         │ Time passes...
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  WebSocket Request                       │
│                                                         │
│  "Switch to chat_456"  ─────────────► Task B            │
│                                       (async context 2) │
│                                                         │
│  ❌ Agent.disconnect() → FAILS!                         │
│     RuntimeError: Attempted to exit cancel scope        │
│     in a different task than it was entered in          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

Even with a SINGLE agent (no pool), the problem persists because:
- Agent connects in the server startup context
- WebSocket handlers run in different async contexts
- SDK prohibits disconnect/reconnect across contexts

## Bassi's Workaround: Context Injection

Since we can't use SDK's native session resumption for chat switching, we inject the conversation history directly into the prompt:

```python
# When switching to a chat with existing history:
if self._conversation_context:
    # Prepend full conversation to the prompt
    prompt = self._conversation_context + "\n\n" + prompt
    self._conversation_context = None  # Clear after first use
```

### How It Works

1. **Chat history is saved** in workspace files (`chats/{id}/history.md`)
2. **On chat switch**, full history is loaded from workspace
3. **First query** includes conversation context as prefix
4. **Agent "remembers"** via the injected context

### Limitations of This Workaround

| Aspect | SDK Native Resume | Context Injection |
|--------|-------------------|-------------------|
| Token usage | Efficient (SDK manages) | Higher (history in prompt) |
| Context limit | SDK handles compaction | Limited to ~50k chars |
| Tool call history | Full fidelity | Text summary only |
| Speed | Instant | Slight overhead |

## Alternative Architectures Considered

### 1. Per-Chat Agents (Rejected)
- Create new agent for each chat with `resume=chat_id`
- ❌ Expensive: ~2-3 seconds per agent startup
- ❌ Defeats pooling benefits
- ❌ Resource intensive with multiple browsers

### 2. Single Dedicated Task (Complex)
- Run agent in its own task with message queue
- All operations happen in same context
- ✅ Would allow proper session switching
- ❌ Complex to implement
- ❌ Serializes all requests

### 3. Context Injection (Current)
- Pool of connected agents
- Inject history into prompts when switching
- ✅ Fast agent acquisition
- ✅ Works with current SDK
- ⚠️ Higher token usage on first message after switch

## Future Considerations

If the Claude Agent SDK adds:
- A `switch_session(session_id)` method
- Or removes the async context restriction

We could eliminate context injection and use native session management.

## Related Files

- `bassi/core_v3/agent_session.py` - Context injection in `restore_conversation_history()` and `query()`
- `bassi/core_v3/chat_workspace.py` - History storage in `load_conversation_history()`
- `bassi/core_v3/services/agent_pool.py` - Agent pooling (works around reconnect issue)

## References

- Claude Agent SDK source: `.venv/lib/python3.11/site-packages/claude_agent_sdk/client.py`
- Original error: `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in`

