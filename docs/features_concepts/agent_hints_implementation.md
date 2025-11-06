# Agent Hints - Actual Implementation Code

## 🔌 Agent SDK API

### The API Methods We're Using

From `bassi/core_v3/agent_session.py`:

```python
class BassiAgentSession:
    async def query(self, prompt: str, session_id: str = "default") -> AsyncIterator[Message]:
        """
        Send a query and stream responses.

        This is THE method we use to send messages to Claude.
        It maintains session context automatically.
        """
        await self.client.query(prompt, session_id=session_id)
        async for message in self.client.receive_response():
            yield message

    async def interrupt(self):
        """
        Interrupt the current execution.
        Stops Claude Code from executing further actions.
        """
        await self.client.interrupt()
```

**Key Insight**:
- `query()` sends ANY message to Claude (user message OR hint)
- Multiple `query()` calls with same `session_id` = same conversation
- No need to interrupt! Just send another message.

---

## 🎨 UI Design: TWO Buttons

### Current UI (Agent Idle)
```
┌────────────────────────────────────────────────────┐
│ [Ask me anything...                    ] [Send]    │
└────────────────────────────────────────────────────┘
```

### NEW UI (Agent Working)
```
┌────────────────────────────────────────────────────┐
│ [HINT: Guide the current task...  ] [Stop] [Hint] │
└────────────────────────────────────────────────────┘
```

**Two separate buttons**:
- **Stop**: Calls `interrupt()` - hard stop
- **Hint**: Sends formatted message via `query()` - continues with guidance

---

## 📝 Frontend Implementation

### File: `bassi/static/app.js`

#### 1. Update HTML Structure for Input Area

Find this in `index.html` (lines 63-76):

```html
<!-- CURRENT CODE -->
<div class="input-container">
    <div class="input-wrapper">
        <textarea
            id="message-input"
            placeholder="Ask me anything..."
            rows="1"
        ></textarea>
        <button id="send-button" disabled>
            Send
        </button>
    </div>
</div>
```

**Change to**:

```html
<!-- NEW CODE -->
<div class="input-container">
    <div class="input-wrapper">
        <textarea
            id="message-input"
            placeholder="Ask me anything..."
            rows="1"
        ></textarea>
        <div class="button-group">
            <button id="stop-button" style="display: none;">
                ⏹ Stop
            </button>
            <button id="send-button" disabled>
                Send
            </button>
        </div>
    </div>
</div>
```

#### 2. Update JavaScript Constructor

In `app.js`, find the constructor (around line 48):

```javascript
// ADD this line after line 48:
this.stopButton = document.getElementById('stop-button')
```

#### 3. Update init() Method

Find `init()` method (around line 76), ADD after the sendButton event listener:

```javascript
// ADD THIS CODE after line 82:
this.stopButton.addEventListener('click', () => {
    this.stopAgent()
})
```

#### 4. Replace setAgentWorking() Method

Find `setAgentWorking()` method (around line 622), **REPLACE ENTIRE METHOD**:

```javascript
setAgentWorking(working) {
    this.isAgentWorking = working

    if (working) {
        // Agent is working - show BOTH stop and hint buttons
        this.messageInput.disabled = false  // Keep input enabled!
        this.messageInput.placeholder = 'HINT: Guide the current task...'

        // Show stop button
        this.stopButton.style.display = 'inline-block'

        // Change send button to "Send Hint"
        this.sendButton.textContent = 'Send Hint'
        this.sendButton.classList.add('hint-mode')
        this.sendButton.disabled = false  // Enable for hints

        // Show status indicator
        this.showServerStatus('🤖 Claude is thinking...')
    } else {
        // Agent is idle - hide stop button, regular send
        this.messageInput.disabled = false
        this.messageInput.placeholder = 'Ask me anything...'

        // Hide stop button
        this.stopButton.style.display = 'none'

        // Restore send button
        this.sendButton.textContent = 'Send'
        this.sendButton.classList.remove('hint-mode')

        // Disable if no input
        if (!this.messageInput.value.trim()) {
            this.sendButton.disabled = true
        }

        // Hide status indicator
        this.hideServerStatus()
    }
}
```

#### 5. Update sendMessage() Method

Find `sendMessage()` method (around line 533), **REPLACE THE MESSAGE SENDING LOGIC**:

```javascript
sendMessage() {
    const content = this.messageInput.value.trim()
    if (!content || !this.isConnected) return

    const lowerContent = content.toLowerCase()

    // Intercept meta-commands (handle locally, don't send to server)
    if (lowerContent === '/help') {
        this.addUserMessage(content)
        this.showDynamicHelp()
        this.messageInput.value = ''
        this.messageInput.style.height = 'auto'
        return
    }

    // ... (keep other meta-command handlers) ...

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

    // Clear input and reset height
    this.messageInput.value = ''
    this.messageInput.style.height = 'auto'

    // If this was a regular message, set agent working
    if (messageType === 'user_message') {
        this.setAgentWorking(true)
    }
    // If it was a hint, agent is already working - do nothing
}
```

#### 6. Add New Method: addHintMessage()

Add this method anywhere in the class (suggest after `addUserMessage()`):

```javascript
addHintMessage(content) {
    const hintMsg = document.createElement('div')
    hintMsg.className = 'message hint-message message-fade-in'
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

---

## 🔧 Backend Implementation

### File: `bassi/core_v3/web_server_v3.py`

Find the message handler in `_handle_client_message()` method (around line 800).

**ADD THIS CODE** right after the `interrupt` handler (after line 868):

```python
elif msg_type == "hint":
    # User sent a hint while agent is working
    hint_content = data.get("content", "")
    logger.info(f"💡 Hint received: {hint_content}")

    try:
        # Format the hint with special context for Claude
        formatted_hint = f"""Task was interrupted. Received this hint:

{hint_content}

Now continue with the interrupted task/plan/intention. Go on..."""

        logger.debug(f"Formatted hint: {formatted_hint[:100]}...")

        # Send hint as a continuation message (same session)
        # This maintains conversation context
        async for message in session.query(
            formatted_hint,
            session_id=data.get("session_id", "default")
        ):
            # Convert SDK message to WebSocket event
            event = convert_message_to_websocket(message)
            if event:
                await websocket.send_json(event)
                logger.debug(f"Sent hint response: {event.get('type')}")

        logger.info("✅ Hint processed successfully")

    except Exception as e:
        logger.error(f"❌ Error processing hint: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to process hint: {str(e)}",
        })
```

**That's it!** No other backend changes needed. The existing `user_message` handler stays the same.

---

## 🎨 CSS Styling

### File: `bassi/static/style.css`

Add these styles at the end of the file:

```css
/* ========== Hint Messages ========== */

.hint-message {
    background: var(--bg-secondary);
    border-left: 4px solid var(--accent-yellow);
    border-radius: 8px;
    padding: var(--spacing-md);
    margin-bottom: var(--spacing-md);
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

.hint-message .message-content {
    color: var(--text-primary);
    line-height: 1.6;
}

/* ========== Button Group ========== */

.button-group {
    display: flex;
    gap: var(--spacing-sm);
}

#stop-button {
    background: var(--accent-red);
    color: white;
    border: none;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-fast);
}

#stop-button:hover {
    opacity: 0.9;
    transform: translateY(-1px);
}

#send-button.hint-mode {
    background: var(--accent-yellow);
    color: var(--bg-primary);
}

#send-button.hint-mode:hover {
    background: var(--accent-yellow);
    opacity: 0.9;
}
```

---

## 📊 Message Flow - The Actual API Calls

### Initial Task

```javascript
// FRONTEND
ws.send(JSON.stringify({
    type: 'user_message',
    content: 'Create a web scraper'
}))
```

```python
# BACKEND
async for message in session.query(
    prompt="Create a web scraper",
    session_id="default"
):
    # Stream responses back to frontend
    event = convert_message_to_websocket(message)
    await websocket.send_json(event)
```

### User Sends Hint

```javascript
// FRONTEND (while agent is working)
ws.send(JSON.stringify({
    type: 'hint',
    content: 'Handle pagination'
}))
```

```python
# BACKEND
formatted_hint = """Task was interrupted. Received this hint:

Handle pagination

Now continue with the interrupted task/plan/intention. Go on..."""

async for message in session.query(
    prompt=formatted_hint,
    session_id="default"  # SAME session!
):
    # Stream responses back to frontend
    event = convert_message_to_websocket(message)
    await websocket.send_json(event)
```

**Key**: Both use the **same `session.query()` method** with the **same `session_id`**.

The Agent SDK maintains conversation context automatically!

---

## 🚨 Your Concerns Addressed

### "Hint after completion: not possible"

**You're 100% correct!** When agent completes:

```javascript
setAgentWorking(false)
// ↓
this.messageInput.placeholder = 'Ask me anything...'
this.sendButton.textContent = 'Send'
```

So if user types and sends, it's a **new message**, not a hint. The state prevents confusion.

**This is actually PERFECT** - no edge case to handle!

### "Don't remove the stop button"

**Fixed!** Now we have:
- **Stop button**: Visible only when working, calls `interrupt()`
- **Send button**: Changes to "Send Hint" when working

Both are separate buttons, both visible during work.

### "Show me code. I have doubts about implementation"

The doubt is probably: **"Can we really just call `query()` again while the first one is still streaming?"**

**Answer: YES!**

The Agent SDK handles this internally:
1. First `query()` is streaming responses
2. Second `query()` (the hint) is sent with same `session_id`
3. SDK queues it, Claude processes it as next message
4. Streaming continues with the hint incorporated

It's just **another message in the conversation**.

---

## 🧪 Test It

1. Start web server: `./run-agent-web.sh`
2. Send task: "Create a Python script to analyze CSV files"
3. While agent is working, type hint: "Use pandas library"
4. Click "Send Hint"
5. Watch agent incorporate the hint and continue

---

## ❓ Still Have Doubts?

The implementation is actually **simpler** than it seems because:

1. **No state management** - Agent SDK handles it
2. **No interruption** - Just another message
3. **No context loss** - Same session_id
4. **No queue logic** - SDK handles queuing

It's literally just:
- Frontend: Detect if working → send `type: 'hint'`
- Backend: Format hint → call same `query()` method

That's it!
