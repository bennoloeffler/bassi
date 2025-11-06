# Agent Hints Feature

## Overview

Allow users to provide hints/guidance to Claude while it's actively working on a task, without fully interrupting and restarting the conversation. The agent should incorporate the hint and continue with the original task.

## Problem Statement

Currently, when Claude is working on a task:
- **Current Behavior**: Input field is disabled, user can only click "Stop" to interrupt
- **Issue**: If user thinks of helpful guidance mid-execution, they must:
  1. Stop the agent (losing current progress)
  2. Start a completely new task
  3. Re-explain context + add the hint

**Desired Behavior**: User can send a hint while agent is working, and agent incorporates the hint while continuing the current task/plan.

## User Experience Design

### Visual Changes

**When Agent is Idle**:
```
Input: [Ask me anything...                          ] [Send]
```

**When Agent is Working** (NEW):
```
Input: [HINT: Guide the current task...             ] [Send Hint]
```

### Interaction Flow

1. **User sends initial task**: "Create a web scraper for product prices"
2. **Agent starts working**: Input placeholder changes to "HINT: Guide the current task..."
3. **User types hint**: "Make sure to handle pagination"
4. **User presses Enter/clicks "Send Hint"**:
   - Hint is sent to agent with special formatting
   - Agent receives context: "Task was interrupted. Received this hint: {USER_HINT}. Continue with the original task incorporating this guidance."
   - Agent continues working with the hint
5. **Agent completes task** with hint incorporated

## Technical Design

### Message Protocol

#### New Message Type: `hint`

```json
{
  "type": "hint",
  "content": "Make sure to handle pagination"
}
```

#### Backend Processing

When backend receives a `hint` message:
1. **DO NOT** call `session.interrupt()`
2. **Format the hint** as a user message with special prefix
3. **Send to agent** via `session.query()` with same session_id
4. **Continue streaming** responses as normal

**Formatted Message**:
```
Task was interrupted. Received this hint:

{USER_HINT}

Now continue with the interrupted task/plan/intention. Go on...
```

### State Machine

```
┌─────────────────────────────────────────────────┐
│  IDLE STATE                                     │
│  - Input enabled                                │
│  - Placeholder: "Ask me anything..."            │
│  - Button: "Send"                               │
└──────────────────┬──────────────────────────────┘
                   │
                   │ User sends message
                   ▼
┌─────────────────────────────────────────────────┐
│  WORKING STATE                                  │
│  - Input enabled (NEW!)                         │
│  - Placeholder: "HINT: Guide the current task..." │
│  - Button: "Send Hint"                          │
│                                                 │
│  Options:                                       │
│  1. User sends hint → HINT_SENT                 │
│  2. Agent finishes → IDLE                       │
└──────────────────┬──────────────────────────────┘
                   │
                   │ User sends hint
                   ▼
┌─────────────────────────────────────────────────┐
│  HINT_SENT STATE (brief transition)            │
│  - Show hint message in chat                    │
│  - Send formatted hint to agent                 │
│  - Return to WORKING state                      │
└──────────────────┬──────────────────────────────┘
                   │
                   │ Hint processed
                   ▼
          Back to WORKING STATE
```

### Frontend Changes

**File**: `bassi/static/app.js`

1. **Remove input disable** in `setAgentWorking()`:
   ```javascript
   // BEFORE:
   this.messageInput.disabled = true

   // AFTER:
   this.messageInput.disabled = false  // Keep enabled for hints
   ```

2. **Update placeholder** based on agent state:
   ```javascript
   setAgentWorking(working) {
       this.isAgentWorking = working

       if (working) {
           // Keep input enabled for hints
           this.messageInput.disabled = false
           this.messageInput.placeholder = 'HINT: Guide the current task...'
           this.sendButton.textContent = 'Send Hint'
           this.sendButton.classList.add('hint-mode')
           this.showServerStatus('🤖 Claude is thinking...')
       } else {
           this.messageInput.placeholder = 'Ask me anything...'
           this.sendButton.textContent = 'Send'
           this.sendButton.classList.remove('hint-mode')
           this.hideServerStatus()
       }
   }
   ```

3. **Modify sendMessage()** to detect hint vs normal message:
   ```javascript
   sendMessage() {
       const content = this.messageInput.value.trim()
       if (!content || !this.isConnected) return

       // Determine message type based on agent state
       const messageType = this.isAgentWorking ? 'hint' : 'user_message'

       // Add to UI with appropriate styling
       if (messageType === 'hint') {
           this.addHintMessage(content)
       } else {
           this.addUserMessage(content)
           // Reset currentMessage for new conversation
           this.currentMessage = null
           this.blocks.clear()
           this.textBuffers.clear()
       }

       // Send to server
       this.ws.send(JSON.stringify({
           type: messageType,
           content: content
       }))

       // Clear input
       this.messageInput.value = ''
       this.messageInput.style.height = 'auto'

       // If this was a regular message, set agent working
       if (messageType === 'user_message') {
           this.setAgentWorking(true)
       }
   }
   ```

4. **Add new UI method** for hint messages:
   ```javascript
   addHintMessage(content) {
       const hintMsg = document.createElement('div')
       hintMsg.className = 'message hint-message'
       hintMsg.innerHTML = `
           <div class="message-header">
               <span class="hint-icon">💡</span>
               <span class="hint-label">Hint</span>
           </div>
           <div class="message-content">${this.escapeHtml(content)}</div>
       `
       this.conversationEl.appendChild(hintMsg)
       this.scrollToBottom()
   }
   ```

### Backend Changes

**File**: `bassi/core_v3/web_server_v3.py`

Add handler for `hint` message type:

```python
elif msg_type == "hint":
    # User sent a hint while agent is working
    hint_content = data.get("content", "")
    logger.info(f"Hint received: {hint_content}")

    try:
        # Format the hint with special context
        formatted_hint = f"""Task was interrupted. Received this hint:

{hint_content}

Now continue with the interrupted task/plan/intention. Go on..."""

        # Send hint as a user message (same session)
        # The agent will receive it and incorporate it
        async for message in session.query(
            formatted_hint,
            session_id=data.get("session_id", "default")
        ):
            # Convert and send to frontend
            event = convert_message_to_websocket(message)
            if event:
                await websocket.send_json(event)

    except Exception as e:
        logger.error(f"Error processing hint: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "message": str(e),
        })
```

### CSS Changes

**File**: `bassi/static/style.css`

Add styles for hint messages:

```css
/* Hint Messages */
.hint-message {
    background: var(--bg-secondary);
    border-left: 4px solid var(--accent-yellow);
    border-radius: 8px;
    padding: var(--spacing-md);
    margin-bottom: var(--spacing-md);
    animation: fadeIn 0.3s ease-in;
}

.hint-message .message-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    margin-bottom: var(--spacing-sm);
}

.hint-icon {
    font-size: 1.25rem;
}

.hint-label {
    font-weight: 600;
    color: var(--accent-yellow);
    text-transform: uppercase;
    font-size: 0.75rem;
    letter-spacing: 0.5px;
}

/* Send button in hint mode */
.send-button.hint-mode {
    background: var(--accent-yellow);
    color: var(--text-primary);
}

.send-button.hint-mode:hover {
    background: var(--accent-yellow);
    opacity: 0.9;
}
```

## Edge Cases & Considerations

### 1. Multiple Hints
**Scenario**: User sends multiple hints in rapid succession

**Solution**: Each hint is queued and sent to the agent as separate messages. Agent processes them in order.

### 2. Hint During Tool Execution
**Scenario**: Agent is running a long tool (e.g., web scraping), user sends hint

**Solution**: Hint is queued and processed when agent next checks for input. Claude Agent SDK handles this naturally.

### 3. Agent Finishes Before Hint Sent
**Scenario**: User types hint, but agent completes task before user presses enter

**Solution**: When agent finishes, state returns to IDLE. If user still presses enter, it's treated as a new message (not a hint).

### 4. Empty Hint
**Scenario**: User clicks "Send Hint" with empty input

**Solution**: Frontend validation prevents sending empty hints (same as current behavior).

### 5. Stop Button Removed?
**Question**: Should we still have a Stop functionality?

**Answer**: YES - Add a small "×" button next to status indicator for hard stop. Hint is for guidance, Stop is for cancellation.

```
┌────────────────────────────────────────────────┐
│ 🤖 Claude is thinking... [×]                   │
└────────────────────────────────────────────────┘
```

## Alternative Approaches Considered

### Approach 1: Interrupt + Resume (NOT CHOSEN)
1. Call `session.interrupt()`
2. Wait for interrupt to complete
3. Send new message with hint
4. Resume with new context

**Rejected because**: Complex state management, loses streaming benefits, potential context loss.

### Approach 2: Queue Hints (NOT CHOSEN)
1. Queue hints client-side
2. Send all hints when agent pauses between tool calls
3. Agent processes batch

**Rejected because**: Delayed feedback, complex queue management, poor UX.

### Approach 3: Live Message Stream (CHOSEN)
1. Send hint immediately as new message
2. Agent SDK handles as natural continuation
3. Simple, clean, leverages SDK's message handling

**Chosen because**: Simple, clean, natural UX, leverages existing SDK capabilities.

## Implementation Phases

### Phase 1: Frontend UI Changes (30 min)
- [ ] Remove input disable in `setAgentWorking()`
- [ ] Update placeholder text for hint mode
- [ ] Change button text/style in hint mode
- [ ] Add `addHintMessage()` method
- [ ] Update `sendMessage()` to detect hint vs normal message

### Phase 2: Backend Message Handling (20 min)
- [ ] Add `hint` message type handler
- [ ] Format hint with special prefix
- [ ] Send through existing `session.query()` flow

### Phase 3: CSS Styling (10 min)
- [ ] Add `.hint-message` styles
- [ ] Add `.hint-mode` button styles

### Phase 4: Testing (30 min)
- [ ] Test single hint
- [ ] Test multiple hints
- [ ] Test hint during tool execution
- [ ] Test agent finishing before hint sent
- [ ] Test edge cases

### Phase 5: Documentation (15 min)
- [ ] Update user documentation
- [ ] Add examples to README
- [ ] Document in CLAUDE.md

**Total Estimated Time**: ~2 hours

## Success Criteria

1. ✅ Input field stays enabled while agent is working
2. ✅ Placeholder changes to "HINT: Guide the current task..."
3. ✅ User can send hints during agent execution
4. ✅ Hints appear in chat with distinct styling
5. ✅ Agent incorporates hints and continues original task
6. ✅ No loss of context or conversation state
7. ✅ Clean UX with clear visual feedback

## Future Enhancements

1. **Hint Templates**: Pre-defined hints like "Be more concise", "Add error handling", etc.
2. **Hint History**: Show all hints sent during current task
3. **Smart Hints**: AI-suggested hints based on current task
4. **Hint Shortcuts**: Keyboard shortcuts for common hints (e.g., Ctrl+H for "hurry up")

## References

- Claude Agent SDK: Message handling and streaming
- Interactive Questions: Similar pattern for user input during execution
- Web Server V3: WebSocket message protocol
