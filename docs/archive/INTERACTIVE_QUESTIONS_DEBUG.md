# Interactive Questions - Debugging Session

## Current Issue

The AskUserQuestion tool sends the question to the UI and displays it correctly, but when the user submits their answer, the tool doesn't receive it and continues spinning indefinitely.

## Root Cause Analysis

Based on the screenshot and user feedback, the issue is that the MCP tool call is not completing. The flow should be:

1. Agent calls AskUserQuestion MCP tool
2. Tool sends question via WebSocket to UI ✅ (works)
3. UI displays question dialog ✅ (works)
4. User clicks Submit ✅ (works - we see "Answer sent successfully")
5. WebSocket receives answer ❌ (FAILS - never reaches backend)
6. Tool receives answer and returns to agent ❌ (never happens)

## Hypothesis: Deadlock in Message Processing

### The Deadlock Scenario

**Before fix**:
```python
# WebSocket handler was synchronous
while True:
    data = await websocket.receive_json()  # BLOCKS HERE
    await self._process_message(...)       # Processes agent query
        └─> await session.query(...)       # Calls agent
            └─> Agent calls AskUserQuestion tool
                └─> await service.ask()     # WAITS for answer
                    └─> event.wait()        # BLOCKS until submit_answer()
```

The problem: The `websocket.receive_json()` can't receive the answer because we're stuck inside `_process_message()` waiting for the tool to complete!

### The Fix: Concurrent Message Processing

**After fix**:
```python
async def message_receiver():
    while True:
        data = await websocket.receive_json()  # Runs independently
        # Create background task - doesn't block
        asyncio.create_task(
            self._process_message(...)
        )

# Main handler
receiver_task = asyncio.create_task(message_receiver())
await receiver_task
```

Now:
- Message receiver runs continuously in background
- Each message is processed as a separate task
- Answer can arrive while agent query is still processing

## Added Debug Logging

### In `tools.py` (the MCP tool):
```
🔔 TOOL: About to call question_service.ask()
🔔 TOOL: Got answers from service: {answers}
🔔 TOOL: Returning response: {response}
```

### In `interactive_questions.py` (the service):
```
🔔 SERVICE: Sending question to UI: {question_id}
🔔 SERVICE: Question sent, now waiting for answer...
🔔 SERVICE: Waiting on event.wait() for up to 300s...
🔔 SERVICE: Event triggered! Answer received!
🔔 SERVICE: Returning answer: {answer}
```

### In `web_server_v3.py` (WebSocket handler):
```
🟢 WS MESSAGE RECEIVED: {msg_type}
🔵 Processing message type={msg_type}
🔔 submit_answer called: question_id={id}
   Pending questions: [...]
   Answers received: {...}
   ✅ Event triggered, answer stored
```

## Expected Log Flow (Success Case)

When testing, you should see this sequence:

```
1. User sends message with question request
   🟢 WS MESSAGE RECEIVED: user_message
   🔵 Processing message type=user_message
   📝 User message: ask question with 4 options...

2. Agent starts processing
   🔄 Starting query...
   📦 Got message: AssistantMessage

3. Agent calls AskUserQuestion tool
   📦 Got message: AssistantMessage
      Content blocks: ['ToolUseBlock']
   🔔 TOOL: About to call question_service.ask()

4. Service sends question to UI
   🔔 SERVICE: Sending question to UI: <uuid>
   🔔 SERVICE: Question sent, now waiting for answer...
   🔔 SERVICE: Waiting on event.wait() for up to 300s...

5. User submits answer in UI
   [Browser console]: ✅ Answer sent successfully

6. Server receives answer
   🟢 WS MESSAGE RECEIVED: answer
   🔵 Processing message type=answer
   🔔 submit_answer called: question_id=<uuid>
      Pending questions: ['<uuid>']
      Answers received: {"What option?": "Option 1"}

7. Event is triggered
      ✅ Event triggered, answer stored

8. Service receives answer
   🔔 SERVICE: Event triggered! Answer received!
   🔔 SERVICE: Returning answer: {"What option?": "Option 1"}

9. Tool receives answer
   🔔 TOOL: Got answers from service: {"What option?": "Option 1"}
   🔔 TOOL: Returning response: User has answered your questions...

10. Agent continues
    📦 Got message: AssistantMessage
       Content blocks: ['TextBlock']
    [Agent provides final response based on user's answer]
```

## Test Plan

### Step 1: Restart Server
```bash
./run-agent.sh
```

### Step 2: Open Browser
Navigate to http://localhost:8000

### Step 3: Ask Test Question
Type in chat:
```
ask question with 4 options and wait for my answer before continuing
```

### Step 4: Observe Logs

**CRITICAL CHECKPOINTS**:

✅ **Checkpoint 1**: Question appears in UI
- Should see the question dialog
- Should have Submit button

✅ **Checkpoint 2**: Logs show question sent
```
🔔 SERVICE: Sending question to UI: <uuid>
🔔 SERVICE: Waiting on event.wait() for up to 300s...
```

✅ **Checkpoint 3**: Click Submit in UI
- Browser console should show: `✅ Answer sent successfully`

✅ **Checkpoint 4**: Server receives answer
```
🟢 WS MESSAGE RECEIVED: answer    ← THIS IS THE KEY!
```

If you DON'T see this, the concurrent message processing fix didn't work.

✅ **Checkpoint 5**: Answer is processed
```
🔔 submit_answer called: question_id=<uuid>
   ✅ Event triggered, answer stored
```

✅ **Checkpoint 6**: Tool receives answer
```
🔔 SERVICE: Event triggered! Answer received!
🔔 TOOL: Got answers from service: {...}
🔔 TOOL: Returning response: ...
```

✅ **Checkpoint 7**: Agent continues
- Agent should provide a follow-up response
- Spinner in UI should stop

## Possible Outcomes

### Outcome A: Complete Success ✅
All checkpoints pass. The tool completes and agent continues.

**Action**: Remove debug logging and mark feature as complete.

### Outcome B: Answer Still Not Received ❌
Checkpoint 4 fails - server never sees `🟢 WS MESSAGE RECEIVED: answer`

**Diagnosis**: Concurrent message processing didn't fix the deadlock. Need to investigate further:
- Is the WebSocket actually in OPEN state when answer is sent?
- Is there an exception in message_receiver() that's silently failing?
- Is the answer being sent to the wrong WebSocket connection?

**Action**: Add even more detailed logging around WebSocket send/receive.

### Outcome C: Answer Received But Event Not Triggered ❌
Checkpoints 4-5 pass but checkpoint 6 fails.

**Diagnosis**: The submit_answer() method isn't triggering the event properly.
- Is the question_id matching?
- Is the event object the same instance?
- Is there an exception in submit_answer()?

**Action**: Debug the submit_answer() method.

### Outcome D: Event Triggered But Tool Doesn't Return ❌
Checkpoints 4-7 pass but agent doesn't continue.

**Diagnosis**: The tool response format is incorrect for MCP.
- Check the return value matches MCP tool schema
- Verify the SDK is processing the response

**Action**: Investigate MCP tool response format.

## Next Steps

1. **User**: Restart server with new debug logging
2. **User**: Test asking a question
3. **User**: Share complete server logs from the test
4. **Dev**: Analyze logs based on checkpoints above
5. **Dev**: Apply appropriate fix based on outcome

## Files Modified for Debug Logging

- `bassi/core_v3/tools.py` - Added 3 debug print statements
- `bassi/core_v3/interactive_questions.py` - Added 7 debug print statements
- `bassi/core_v3/web_server_v3.py` - Already had debug logging

All debug prints use `flush=True` to ensure they appear immediately in logs.
