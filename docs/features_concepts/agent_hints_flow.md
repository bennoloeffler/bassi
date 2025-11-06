# Agent Hints: Detailed Flow & State Transitions

## Complete Message Flow

### Scenario: User sends hint during agent execution

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. INITIAL TASK SUBMISSION                                         │
└─────────────────────────────────────────────────────────────────────┘

USER                    FRONTEND                 BACKEND              CLAUDE
  │                         │                         │                  │
  │ Types: "Create scraper" │                         │                  │
  ├────────────────────────>│                         │                  │
  │                         │                         │                  │
  │ Presses Enter           │                         │                  │
  ├────────────────────────>│                         │                  │
  │                         │                         │                  │
  │                         │ addUserMessage()        │                  │
  │                         │ setAgentWorking(true)   │                  │
  │                         │   ↓ placeholder =       │                  │
  │                         │   "HINT: Guide..."      │                  │
  │                         │   ↓ button = "Send Hint"│                  │
  │                         │                         │                  │
  │                         │ {type: "user_message"}  │                  │
  │                         ├────────────────────────>│                  │
  │                         │                         │                  │
  │                         │                         │ query(prompt)    │
  │                         │                         ├─────────────────>│
  │                         │                         │                  │
  │                         │                  ┌──────┴──────┐           │
  │                         │                  │ Agent starts │           │
  │                         │                  │ processing   │           │
  │                         │                  └──────┬──────┘           │
  │                         │                         │                  │
  │                         │<──── Stream Messages ───┤<─────────────────┤
  │<── UI Updates ──────────┤                         │                  │
  │                         │                         │                  │

┌─────────────────────────────────────────────────────────────────────┐
│ 2. HINT SENT DURING EXECUTION                                       │
└─────────────────────────────────────────────────────────────────────┘

USER                    FRONTEND                 BACKEND              CLAUDE
  │                         │                         │                  │
  │                         │                   [Agent is still         │
  │                         │                    working...]             │
  │                         │                         │                  │
  │ Types: "Handle          │                         │                  │
  │ pagination"             │                         │                  │
  ├────────────────────────>│                         │                  │
  │                         │                         │                  │
  │ Presses Enter           │                         │                  │
  ├────────────────────────>│                         │                  │
  │                         │                         │                  │
  │                         │ addHintMessage()        │                  │
  │                         │   ↓ Shows hint in UI    │                  │
  │                         │   with 💡 icon          │                  │
  │                         │                         │                  │
  │                         │ {type: "hint",          │                  │
  │                         │  content: "Handle..."}  │                  │
  │                         ├────────────────────────>│                  │
  │                         │                         │                  │
  │                         │                    ┌────┴────┐             │
  │                         │                    │ Format  │             │
  │                         │                    │ hint:   │             │
  │                         │                    │         │             │
  │                         │                    │ "Task   │             │
  │                         │                    │ was     │             │
  │                         │                    │ inter-  │             │
  │                         │                    │ rupted.."│            │
  │                         │                    └────┬────┘             │
  │                         │                         │                  │
  │                         │                         │ query(formatted) │
  │                         │                         ├─────────────────>│
  │                         │                         │                  │
  │                         │                         │           ┌──────┴──────┐
  │                         │                         │           │ Claude reads│
  │                         │                         │           │ hint and    │
  │                         │                         │           │ continues   │
  │                         │                         │           │ with task   │
  │                         │                         │           └──────┬──────┘
  │                         │                         │                  │
  │                         │<──── Stream Updated ────┤<─────────────────┤
  │                         │      Messages           │                  │
  │<── UI Updates ──────────┤                         │                  │
  │ (shows hint incorporated)│                        │                  │
  │                         │                         │                  │

┌─────────────────────────────────────────────────────────────────────┐
│ 3. TASK COMPLETION                                                  │
└─────────────────────────────────────────────────────────────────────┘

USER                    FRONTEND                 BACKEND              CLAUDE
  │                         │                         │                  │
  │                         │                         │                  │
  │                         │                         │<───── Done ──────┤
  │                         │                         │                  │
  │                         │<──── Completion Msg ────┤                  │
  │                         │                         │                  │
  │                         │ setAgentWorking(false)  │                  │
  │                         │   ↓ placeholder =       │                  │
  │                         │   "Ask me anything..."  │                  │
  │                         │   ↓ button = "Send"     │                  │
  │                         │                         │                  │
  │<── Task Complete ───────┤                         │                  │
  │                         │                         │                  │
```

## State Transition Diagram

```
                    ┌──────────────┐
                    │              │
         ┌─────────>│     IDLE     │<─────────┐
         │          │              │          │
         │          └──────┬───────┘          │
         │                 │                  │
         │                 │ User sends       │
         │                 │ message          │
         │                 ▼                  │
         │          ┌──────────────┐          │
         │          │              │          │
         │    ┌─────│   WORKING    │          │
         │    │     │              │          │
         │    │     └──────┬───────┘          │
         │    │            │                  │
         │    │            │ User sends       │
         │    │            │ hint             │
         │    │            ▼                  │
         │    │     ┌──────────────┐          │
         │    │     │              │          │
         │    │     │  HINT_SENT   │          │
         │    │     │              │          │
         │    │     └──────┬───────┘          │
         │    │            │                  │
         │    │            │ Hint processed   │
         │    │            │ immediately      │
         │    │            ▼                  │
         │    └────────────┘                  │
         │                                    │
         │             Agent completes        │
         │             task                   │
         └────────────────────────────────────┘


STATE DETAILS:

IDLE
  Input: enabled
  Placeholder: "Ask me anything..."
  Button: "Send"
  Action: Send user_message, transition to WORKING

WORKING
  Input: enabled (NEW!)
  Placeholder: "HINT: Guide the current task..."
  Button: "Send Hint"
  Actions:
    - User sends hint → transition to HINT_SENT
    - Agent completes → transition to IDLE

HINT_SENT (transient state)
  Input: enabled
  Placeholder: "HINT: Guide the current task..."
  Button: "Send Hint"
  Actions:
    - Display hint in UI
    - Send formatted hint to backend
    - Immediately return to WORKING
```

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (app.js)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐          ┌──────────────┐                    │
│  │  User Input  │          │   UI State   │                    │
│  │              │          │              │                    │
│  │ - textarea   │          │ - isAgent    │                    │
│  │ - button     │─────────>│   Working    │                    │
│  │              │          │              │                    │
│  └──────┬───────┘          └──────┬───────┘                    │
│         │                         │                            │
│         │                         ▼                            │
│         │              ┌──────────────────┐                    │
│         │              │ Message Type     │                    │
│         └─────────────>│ Detection        │                    │
│                        │                  │                    │
│                        │ if isAgentWorking│                    │
│                        │   → "hint"       │                    │
│                        │ else             │                    │
│                        │   → "user_msg"   │                    │
│                        └────────┬─────────┘                    │
│                                 │                              │
└─────────────────────────────────┼──────────────────────────────┘
                                  │
                                  ▼ WebSocket
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (web_server_v3.py)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐                                           │
│  │ Message Router   │                                           │
│  │                  │                                           │
│  │ - user_message  ├──────> query(prompt, session_id)          │
│  │ - hint          ├──────> format + query(hint, session_id)   │
│  │ - interrupt     ├──────> interrupt()                        │
│  │                  │                                           │
│  └──────────────────┘                                           │
│                                                                 │
│  ┌──────────────────────────────────────────┐                  │
│  │ Hint Formatter                           │                  │
│  │                                          │                  │
│  │ Input: "Handle pagination"               │                  │
│  │                                          │                  │
│  │ Output:                                  │                  │
│  │ "Task was interrupted. Received this     │                  │
│  │  hint:                                   │                  │
│  │                                          │                  │
│  │  Handle pagination                       │                  │
│  │                                          │                  │
│  │  Now continue with the interrupted       │                  │
│  │  task/plan/intention. Go on..."          │                  │
│  └──────────────────┬───────────────────────┘                  │
│                     │                                          │
│                     ▼                                          │
└─────────────────────────────────────────────────────────────────┘
                      │
                      ▼ Agent SDK
┌─────────────────────────────────────────────────────────────────┐
│                  CLAUDE AGENT SDK                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Session Context:                                               │
│  ┌───────────────────────────────────────────────────┐          │
│  │ Message 1: "Create a web scraper"                │          │
│  │ Message 2: [Agent's work in progress]            │          │
│  │ Message 3: "Task was interrupted... hint..."     │          │
│  │ Message 4: [Agent continues with hint]           │          │
│  └───────────────────────────────────────────────────┘          │
│                                                                 │
│  All messages maintain conversation context                    │
│  Hints are seamlessly integrated                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Edge Case Handling

### 1. Multiple Rapid Hints

```
Time ──────────────────────────────────────────────>

T0: User sends task "Create scraper"
    └─> Agent starts working

T1: User sends hint "Use BeautifulSoup"
    └─> Hint queued in Agent SDK

T2: User sends hint "Handle errors"
    └─> Hint queued in Agent SDK

T3: Agent processes hint 1
    └─> Incorporates BeautifulSoup

T4: Agent processes hint 2
    └─> Adds error handling

T5: Agent completes task
```

**Result**: All hints processed in order, naturally queued by Agent SDK.

### 2. Hint After Completion

```
Time ──────────────────────────────────────────────>

T0: User sends task
    └─> Agent starts working

T1: Agent completes task
    └─> setAgentWorking(false)
    └─> Placeholder: "Ask me anything..."

T2: User types hint (but sees regular placeholder)
    └─> User realizes task is done

T3: User sends message
    └─> Treated as NEW message (not hint)
    └─> Starts new conversation
```

**Result**: No confusion - UI state clearly indicates what mode we're in.

### 3. Hint During Long Tool Execution

```
Time ──────────────────────────────────────────────>

T0: User sends task
    └─> Agent starts working

T1: Agent calls long-running tool (e.g., web scraping)
    └─> Tool is executing...

T2: User sends hint "Skip images"
    └─> Hint sent to Agent SDK
    └─> SDK queues it

T3: Tool completes
    └─> Agent reads queued hint
    └─> Adjusts approach for next steps

T4: Agent continues with hint
```

**Result**: Hints are processed when agent next checks for input.

## Implementation Checklist

### Frontend (`bassi/static/app.js`)

- [ ] **Line 629**: Remove `this.messageInput.disabled = true`
  ```javascript
  // BEFORE:
  this.messageInput.disabled = true

  // AFTER:
  this.messageInput.disabled = false  // Keep enabled for hints
  ```

- [ ] **setAgentWorking()**: Update placeholder and button text
  ```javascript
  if (working) {
      this.messageInput.placeholder = 'HINT: Guide the current task...'
      this.sendButton.textContent = 'Send Hint'
      this.sendButton.classList.add('hint-mode')
  } else {
      this.messageInput.placeholder = 'Ask me anything...'
      this.sendButton.textContent = 'Send'
      this.sendButton.classList.remove('hint-mode')
  }
  ```

- [ ] **sendMessage()**: Detect message type
  ```javascript
  const messageType = this.isAgentWorking ? 'hint' : 'user_message'

  if (messageType === 'hint') {
      this.addHintMessage(content)
  } else {
      this.addUserMessage(content)
      this.currentMessage = null
      this.blocks.clear()
      this.textBuffers.clear()
  }

  this.ws.send(JSON.stringify({ type: messageType, content }))

  if (messageType === 'user_message') {
      this.setAgentWorking(true)
  }
  ```

- [ ] **addHintMessage()**: New method for hint UI
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

### Backend (`bassi/core_v3/web_server_v3.py`)

- [ ] **Add hint handler** after line 848:
  ```python
  elif msg_type == "hint":
      hint_content = data.get("content", "")
      logger.info(f"Hint received: {hint_content}")

      try:
          formatted_hint = f"""Task was interrupted. Received this hint:

{hint_content}

Now continue with the interrupted task/plan/intention. Go on..."""

          async for message in session.query(
              formatted_hint,
              session_id=data.get("session_id", "default")
          ):
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

### CSS (`bassi/static/style.css`)

- [ ] **Add hint message styles**:
  ```css
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

  .send-button.hint-mode {
      background: var(--accent-yellow);
      color: var(--text-primary);
  }
  ```

### Testing

- [ ] **Test 1**: Send hint during agent work
- [ ] **Test 2**: Send multiple hints in sequence
- [ ] **Test 3**: Send hint during tool execution
- [ ] **Test 4**: Type hint but agent finishes first
- [ ] **Test 5**: Verify hint incorporated in agent response
- [ ] **Test 6**: Verify UI state transitions
- [ ] **Test 7**: Verify no context loss

## Summary

This design provides a seamless way for users to guide Claude mid-execution without losing context or interrupting the flow. The key insight is treating hints as **continuation messages** rather than interruptions, leveraging the Agent SDK's natural message handling capabilities.
