# Conversation Context Fix

## Issue
The agent was not retaining conversation context between messages. Each message was treated as a brand new conversation.

**Test:**
```
User: remember that my favorite color is blue
Agent: I've noted that your favorite color is blue!

User: what is my favorite color?
Agent: I don't have access to information about your favorite color.
```

## Root Cause

The `chat()` method was creating a **new SDK client for each message** using `async with`:

```python
async def chat(self, message: str) -> AsyncIterator[Any]:
    async with ClaudeSDKClient(options=self.options) as client:
        # New client = new conversation!
        await client.query(message)
        async for msg in client.receive_response():
            yield msg
```

The `async with` context manager creates a fresh client and destroys it when the `with` block exits, **losing all conversation history**.

## Solution

Changed to **persistent client pattern** - create the client once and reuse it across multiple messages:

### Before:
```python
async def chat(self, message: str) -> AsyncIterator[Any]:
    # Creates NEW client every time (loses history)
    async with ClaudeSDKClient(options=self.options) as client:
        self.client = client
        await client.query(message)
        # ... client destroyed when exiting 'with' block
```

### After:
```python
async def chat(self, message: str) -> AsyncIterator[Any]:
    # Create client once, reuse for subsequent messages
    if self.client is None:
        logger.debug("Creating new ClaudeSDKClient")
        self.client = ClaudeSDKClient(options=self.options)
        await self.client.__aenter__()  # Manually enter context

    # Reuse existing client (preserves history)
    await self.client.query(message)
    async for msg in self.client.receive_response():
        yield msg
```

Also updated `reset()` to properly cleanup the client:

```python
async def reset(self) -> None:
    """Reset conversation - will create new client on next chat"""
    if self.client:
        # Properly exit the client context
        try:
            await self.client.__aexit__(None, None, None)
        except Exception as e:
            logger.warning(f"Error closing client: {e}")
        self.client = None
```

## How It Works

**Client Lifecycle:**

1. **First message**: `self.client` is `None`
   - Create new `ClaudeSDKClient`
   - Call `__aenter__()` to initialize context
   - Send message and stream response
   - **Keep client alive** (don't exit context)

2. **Second message**: `self.client` exists
   - Reuse existing client (has conversation history)
   - Send message and stream response
   - **Keep client alive**

3. **Reset**: User calls `agent.reset()`
   - Call `__aexit__()` to cleanup client
   - Set `self.client = None`
   - Next message creates fresh client

## Test Results

**After Fix:**
```
TURN 1:
User: remember that my favorite color is blue
Agent: I've noted that your favorite color is blue! I'll remember this

TURN 2:
User: what is my favorite color?
Agent: Your favorite color is blue! I remembered it from what you just told me.
```

✅ **Conversation context is now preserved across multiple messages!**

## Benefits

1. **Multi-turn conversations** - Agent remembers previous messages
2. **Follow-up questions** - Can reference earlier context
3. **Efficient** - Reuses same client instead of creating new ones
4. **Explicit reset** - User controls when to start fresh conversation

## Testing
- ✅ Created `test_context.py` to verify context retention
- ✅ Tested multi-turn conversation successfully
- ✅ All quality checks pass
- ✅ Reset functionality works correctly

## Files Changed
- `bassi/agent.py`:
  - `chat()` - Changed from `async with` to persistent client
  - `reset()` - Properly cleanup client with `__aexit__()`
- `test_context.py` - New test for conversation context
