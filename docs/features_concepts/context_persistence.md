# Context Persistence Feature

## Overview

Bassi now properly saves and restores conversation context across sessions using the Claude Agent SDK's built-in session management.

## How It Works

### Session Management

The Claude Agent SDK automatically handles conversation history persistence when you provide a `session_id` parameter. Bassi leverages this by:

1. **Session Creation**: On first run, generates a unique session ID like `session_1761076320_abcd1234`
2. **Session Persistence**: Saves the session ID to `.bassi_context.json` after each interaction
3. **Session Restoration**: On restart, loads the session ID and passes it to the SDK, which automatically restores the full conversation history

### Context File Format

The `.bassi_context.json` file stores:

```json
{
  "session_id": "session_1761076320_abcd1234",
  "timestamp": 1761076320.2059512,
  "last_updated": "2025-10-21 14:32:00"
}
```

### User Experience

When starting bassi:

1. If a previous session exists, user is prompted:
   ```
   📋 Found saved context from previous session
   Load previous context? [y/n] (y):
   ```

2. If user selects **yes** (or just presses Enter):
   - The previous `session_id` is restored
   - Claude automatically loads the full conversation history
   - Agent continues exactly where it left off

3. If user selects **no**:
   - A new session ID is generated
   - Conversation starts fresh

## Implementation Details

### Key Code Changes (2025-10-21)

**Problem**: Context was being saved but not loaded properly. The `session_id` was read from file but never actually used to restore the session.

**Fix**: Modified `bassi/main.py` to restore the `session_id` when user chooses to load context:

```python
# Before (BROKEN):
if load_choice.lower() == "y":
    console.print("[bold green]✅ Loaded previous context[/bold green]")
    # BUG: session_id was never restored!

# After (FIXED):
if load_choice.lower() == "y":
    # Restore the session_id from saved context
    agent.session_id = saved_context.get("session_id", "default")
    console.print("[bold green]✅ Loaded previous context[/bold green]")
```

### Session ID Format

Session IDs follow the format: `session_{timestamp}_{random_hex}`

- `timestamp`: Unix timestamp when session was created
- `random_hex`: 4-byte random hex string for uniqueness

Example: `session_1761076320_abcd1234`

## Technical Notes

### Claude Agent SDK Session Behavior

The SDK's session management:
- **Automatic**: SDK handles all conversation history storage internally
- **Transparent**: No need to manually save/load messages
- **Persistent**: Survives process restarts as long as session ID is preserved
- **Isolated**: Different session IDs = completely separate conversations

### Context Window Management

Bassi tracks context usage:
- Context window: 200K tokens (Claude Sonnet 4.5)
- Compaction threshold: 150K tokens (75% of window)
- Warning shown when approaching threshold

### Limitations

**Current limitation**: The SDK does not provide an API to retrieve historical messages programmatically. When resuming a session, the SDK streams only new messages, not the historical conversation. However, Claude itself has access to the full history internally.

This means:
- ✅ Claude remembers everything from previous sessions
- ✅ Conversation continuity is maintained
- ❌ UI cannot display previous conversation on startup

**Web UI Limitation**: In the web interface with agent pooling, the SDK's `options.resume` cannot be changed after connection due to async context restrictions. Chat switching uses context injection instead. See [SDK Session Limitation](./sdk_session_limitation.md) for details.

## Testing

Run the test script to verify context persistence:

```bash
uv run python test_context_loading.py
```

## Related Files

- `bassi/agent.py`: Session management, save/load context
- `bassi/main.py`: User prompts, session restoration
- `.bassi_context.json`: Stored session data (git-ignored)
- `test_context_loading.py`: Test script

## Future Enhancements

Potential improvements:
1. Display summary of previous session on load
2. Show token usage stats from previous session
3. Implement session forking (explore alternatives without modifying original)
4. Add command to list all saved sessions
5. Implement conversation export/import

## References

- [Claude Agent SDK Sessions](https://docs.claude.com/en/api/agent-sdk/sessions)
- [GitHub Issue #109 - Historical Messages](https://github.com/anthropics/claude-agent-sdk-python/issues/109)
