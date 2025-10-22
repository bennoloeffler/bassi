# Context Persistence Fix - 2025-10-21

## The Problem

Context was being "loaded" but the assistant had **no memory** of previous conversations. The user would see:

```
✅ Loaded previous context
```

But asking "what did we discuss before?" would get a blank response.

## Root Cause

The Claude Agent SDK stores session history in `~/.claude/projects/{project-dir}/{UUID}.jsonl` files, using **UUID-based session IDs** like:
- `ae7bbada-f363-4f81-9df3-b24f3dea8f97`
- `9a2f2425-abe0-458b-80c3-ff0c1cb8d5f7`

Our code was generating **custom session IDs** like:
- `session_1761076320_abcd1234`
- `session_a057a036`

**Result**: The SDK couldn't find our custom session IDs in its storage, so it always started fresh conversations.

## The Fix

### 1. Let SDK Generate Session IDs (bassi/agent.py)

**Before:**
```python
self.session_id = f"session_{int(time.time())}_{os.urandom(4).hex()}"
```

**After:**
```python
self.session_id: str | None = None  # SDK will generate UUID
```

### 2. Capture SDK's Session ID (bassi/agent.py:390-394)

When `ResultMessage` arrives, capture the SDK's actual session ID:

```python
elif msg_class_name == "ResultMessage":
    # Capture session_id from SDK (this is the actual UUID the SDK uses)
    sdk_session_id = getattr(msg, "session_id", None)
    if sdk_session_id and sdk_session_id != self.session_id:
        logger.info(f"SDK session_id captured: {sdk_session_id}")
        self.session_id = sdk_session_id
```

### 3. Use SDK Session ID for Resume (bassi/agent.py:222-229)

```python
if self.session_id:
    logger.info(f"Resuming session: {self.session_id}")
    await self.client.query(message, session_id=self.session_id)
else:
    logger.info("Starting new session (SDK will generate session_id)")
    await self.client.query(message)
```

### 4. Update Context Loading (bassi/main.py:242-253)

Show the actual session ID being loaded:

```python
agent.session_id = saved_context.get("session_id")
if agent.session_id:
    console.print("[bold green]✅ Loaded previous context[/bold green]")
    console.print(f"[dim]   Session ID: {agent.session_id}[/dim]")
else:
    console.print("[bold yellow]⚠️  No session ID in context, starting fresh[/bold yellow]")
```

## How It Works Now

### First Run:
1. User starts bassi, `session_id = None`
2. User asks a question
3. SDK creates new session with UUID (e.g., `ae7bbada-f363-4f81-9df3-b24f3dea8f97`)
4. SDK returns `ResultMessage` with this UUID
5. Bassi captures and saves the UUID to `.bassi_context.json`

### Second Run (Restart):
1. User starts bassi
2. Bassi loads `.bassi_context.json` → `session_id = "ae7bbada-f363-4f81-9df3-b24f3dea8f97"`
3. User asks "what did we discuss?"
4. Bassi calls `query(message, session_id="ae7bbada-f363-4f81-9df3-b24f3dea8f97")`
5. SDK finds `~/.claude/projects/-Users-benno-projects-ai-bassi/ae7bbada-f363-4f81-9df3-b24f3dea8f97.jsonl`
6. SDK loads full conversation history
7. Claude remembers everything! ✅

## Context File Format

**Before:**
```json
{
  "session_id": "session_a057a036",
  "timestamp": 1761077389.274942,
  "last_updated": "2025-10-21 22:09:49"
}
```

**After (with real SDK UUID):**
```json
{
  "session_id": "ae7bbada-f363-4f81-9df3-b24f3dea8f97",
  "timestamp": 1761077389.274942,
  "last_updated": "2025-10-21 22:09:49"
}
```

## Testing

### Manual Test:
```bash
# Terminal 1: First session
./run-agent.sh
You: remember my name is Benno
# ... conversation happens ...
# Quit

# Terminal 1: Second session (restart)
./run-agent.sh
# Choose "y" to load context
You: what's my name?
# Should answer: "Benno"
```

### Check Session Files:
```bash
# List all sessions for bassi project
ls -la ~/.claude/projects/-Users-benno-projects-ai-bassi/

# View last 5 messages in a session
tail -5 ~/.claude/projects/-Users-benno-projects-ai-bassi/{UUID}.jsonl
```

### Check Logs:
```bash
tail -f bassi_debug.log | grep -i session
```

Look for:
- `"SDK session_id captured: ae7bbada-f363-4f81-9df3-b24f3dea8f97"`
- `"Context saved - session_id: ae7bbada-f363-4f81-9df3-b24f3dea8f97"`
- `"Resuming session: ae7bbada-f363-4f81-9df3-b24f3dea8f97"`

## Files Modified

- `bassi/agent.py` - Session ID handling and capture
- `bassi/main.py` - Context loading UI
- `docs/features_concepts/context_persistence.md` - Updated documentation

## SDK Storage Details

The Claude Agent SDK stores sessions at:
```
~/.claude/projects/{normalized-project-path}/{session-uuid}.jsonl
```

For example:
```
~/.claude/projects/-Users-benno-projects-ai-bassi/ae7bbada-f363-4f81-9df3-b24f3dea8f97.jsonl
```

Each line in the `.jsonl` file is a JSON message with:
- `sessionId`: The UUID
- `type`: "user" | "assistant"
- `message`: The actual message content
- `timestamp`: ISO 8601 timestamp
- `uuid`: Message UUID
- Other metadata

## Result

✅ **Context persistence now works correctly!**
- Conversation history persists across restarts
- SDK's UUID-based sessions are properly saved/restored
- Agent remembers everything from previous sessions
