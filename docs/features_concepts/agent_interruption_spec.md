# Agent Interruption - Feature Specification

**Feature**: Agent Interruption (Stop Button)
**Priority**: HIGHEST ⭐⭐⭐
**Phase**: 1.1
**Status**: ⚠️ **PARTIALLY IMPLEMENTED** (Backend ✅, Frontend ❓)
**Version**: 1.0
**Last Updated**: 2025-11-16

---

## Overview

Allow users to interrupt (stop) the agent during execution via a Stop button in the web UI. This is essential UX - users must be able to halt runaway or unwanted agent operations immediately.

**Backend Status**: ✅ Already implemented (`agent.interrupt()` exists)
**Frontend Status**: ❌ Not implemented (need UI + WebSocket integration)

---

## Problem Statement

Currently in web UI:
- Users cannot stop agent once a message is sent
- Must wait for agent to complete (could be minutes)
- No way to cancel expensive operations
- No way to stop if agent goes in wrong direction

This creates frustration and wastes tokens/money.

---

## User Stories

### US-1: Stop Long-Running Operation
**As a** user
**I want to** click a Stop button during agent execution
**So that** I can halt operations that are taking too long

**Acceptance Criteria**:
- Stop button appears during streaming
- Clicking Stop halts agent immediately (<1s)
- UI shows "Interrupted" status
- Can send new message after interruption
- Partial response is visible in chat

---

### US-2: Cancel Incorrect Direction
**As a** user
**I want to** interrupt agent when it misunderstands my request
**So that** I can quickly course-correct without wasting time

**Acceptance Criteria**:
- Interrupt works during tool execution
- Interrupt works during text generation
- Agent state is clean after interrupt (no corruption)
- Next message starts fresh

---

### US-3: Emergency Stop
**As a** user
**I want to** emergency-stop agent if it starts doing something dangerous
**So that** I can prevent unwanted actions

**Acceptance Criteria**:
- Stop button always visible during execution
- Stop button works even during tool calls
- Stop is atomic (no partial tool execution)
- Clear feedback that agent was stopped

---

### US-4: Mobile Support
**As a** mobile user
**I want to** stop agent on my phone
**So that** I have same control on mobile as desktop

**Acceptance Criteria**:
- Stop button visible on mobile (not too small)
- Touch-friendly (no accidental clicks)
- Works on iOS and Android browsers

---

## UI Design

### Stop Button Placement

**Option A: In Input Area** (RECOMMENDED)
```
┌──────────────────────────────────────────┐
│  🤖 Assistant:                           │
│  I'm searching for files... [streaming]  │
│                                          │
│  [Tool Call: bash - find command]       │
│  ...still executing...                   │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  [Type message...]            [⏹ Stop]  │  ← Stop button here
└──────────────────────────────────────────┘
```

**Rationale**:
- Always visible
- Clear association with current action
- Doesn't interfere with message content

**Option B: In Message Header**
```
┌──────────────────────────────────────────┐
│  🤖 Assistant  ● streaming... [⏹ Stop]  │  ← Stop button here
│  I'm searching for files...              │
└──────────────────────────────────────────┘
```

**Rationale**:
- Contextual (associated with specific message)
- Less visual clutter when not streaming

**Decision**: Use Option A for better visibility

---

### Button States

#### 1. Idle State (Not Streaming)
```
┌──────────────────────────────────────────┐
│  [Type message...]              [Send]   │
└──────────────────────────────────────────┘
```
- Stop button not visible
- Only Send button shown

#### 2. Streaming State
```
┌──────────────────────────────────────────┐
│  [Type message...]         [⏹️ Stop]     │
└──────────────────────────────────────────┘
```
- Stop button appears (replaces or next to Send)
- Red color (danger action)
- Icon: ⏹️ (stop square) or ⏸️ (pause) or ❌ (cancel)

#### 3. Stopping State
```
┌──────────────────────────────────────────┐
│  [Type message...]    [⏳ Stopping...]   │
└──────────────────────────────────────────┘
```
- Button disabled during interruption
- Shows spinner/loading state
- Prevents double-clicking

#### 4. Interrupted State
```
┌──────────────────────────────────────────┐
│  🤖 Assistant  ⚠️ Interrupted            │
│  Partial response...                     │
│  [Agent was stopped by user]             │
└──────────────────────────────────────────┘
```
- Clear indication in message
- Return to idle state (Send button)

---

### Visual Styling

**Stop Button**:
```css
.btn-stop {
    background: #e57373;  /* Red */
    color: white;
    border: none;
    border-radius: 6px;
    padding: 12px 24px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-stop:hover {
    background: #ef5350;  /* Darker red */
    transform: translateY(-1px);
}

.btn-stop:active {
    transform: translateY(0);
}

.btn-stop:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}
```

**Interrupted Message Styling**:
```css
.message.interrupted .message-header {
    border-left: 3px solid #ffd54f;  /* Yellow */
}

.message.interrupted .status {
    color: #ffd54f;
    font-weight: 600;
}
```

---

## Technical Design

### WebSocket Protocol

**New Message Type: `interrupt`**

**Client → Server**:
```json
{
    "type": "interrupt"
}
```

**Server → Client** (confirmation):
```json
{
    "type": "interrupted",
    "message": "Agent execution stopped"
}
```

**Server → Client** (if already stopped):
```json
{
    "type": "error",
    "message": "No active execution to interrupt"
}
```

---

### Backend Implementation

**File**: `bassi/web_server.py`

Add handler to `_process_message()`:

```python
async def _process_message(self, websocket: WebSocket, data: dict[str, Any]):
    msg_type = data.get("type")

    if msg_type == "interrupt":
        # Call existing interrupt method
        try:
            await self.agent.interrupt()
            await websocket.send_json({
                "type": "interrupted",
                "message": "Agent execution stopped"
            })
        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "message": f"Failed to interrupt: {str(e)}"
            })
```

**Note**: `agent.interrupt()` already exists in `bassi/agent.py:351-357`

---

### Frontend Implementation

**File**: `bassi/static/app.js`

#### 1. Add Stop Button to HTML

```javascript
// In createInputArea() or similar
const stopButton = document.createElement('button');
stopButton.id = 'stop-button';
stopButton.className = 'btn-stop';
stopButton.style.display = 'none';  // Hidden by default
stopButton.innerHTML = '<span>⏹️ Stop</span>';
stopButton.addEventListener('click', () => this.stopAgent());
inputContainer.appendChild(stopButton);
```

#### 2. Show/Hide Stop Button

```javascript
showStopButton() {
    this.sendButton.style.display = 'none';
    document.getElementById('stop-button').style.display = 'block';
}

hideStopButton() {
    document.getElementById('stop-button').style.display = 'none';
    this.sendButton.style.display = 'block';
}
```

#### 3. Send Interrupt Message

```javascript
stopAgent() {
    if (!this.isConnected || !this.currentAssistantMessage) return;

    // Disable button during interruption
    const stopBtn = document.getElementById('stop-button');
    stopBtn.disabled = true;
    stopBtn.innerHTML = '<span>⏳ Stopping...</span>';

    // Send interrupt message
    this.ws.send(JSON.stringify({
        type: 'interrupt'
    }));
}
```

#### 4. Handle Interrupted Response

```javascript
handleInterrupted(data) {
    // Mark current message as interrupted
    if (this.currentAssistantMessage) {
        const header = this.currentAssistantMessage.querySelector('.message-header');
        const statusEl = header.querySelector('.status');
        if (statusEl) {
            statusEl.textContent = '⚠️ Interrupted';
            statusEl.className = 'status interrupted';
        }

        // Add interruption notice
        const contentEl = this.currentAssistantMessage.querySelector('.message-content');
        const noticeEl = document.createElement('div');
        noticeEl.className = 'interruption-notice';
        noticeEl.textContent = 'Agent was stopped by user';
        contentEl.appendChild(noticeEl);

        // Reset state
        this.currentAssistantMessage = null;
        this.markdownBuffer = '';
    }

    // Hide stop button, show send button
    this.hideStopButton();

    // Re-enable input
    this.messageInput.disabled = false;
}
```

#### 5. Update Message Handlers

```javascript
handleContentDelta(data) {
    // Show stop button when streaming starts
    if (!this.currentAssistantMessage) {
        this.showStopButton();
        // ... rest of existing code
    }
    // ... rest of existing code
}

handleMessageComplete(data) {
    // Hide stop button when complete
    this.hideStopButton();
    // ... rest of existing code
}
```

---

## Edge Cases & Error Handling

### Edge Case 1: Interrupt During Tool Execution
**Scenario**: Agent is executing a bash command
**Behavior**:
- Interrupt immediately sent to agent
- Agent attempts to stop tool execution
- Partial output may be returned
- Next message starts fresh

**Test**: Send command like "find / -name '*.txt'" then interrupt mid-execution

### Edge Case 2: Double-Click Stop
**Scenario**: User clicks Stop button multiple times
**Behavior**:
- First click: Send interrupt
- Subsequent clicks: Ignored (button disabled)
- Button re-enabled after confirmation

**Implementation**: Disable button after first click

### Edge Case 3: Network Disconnect During Interrupt
**Scenario**: WebSocket disconnects while sending interrupt
**Behavior**:
- Client shows connection error
- Auto-reconnect attempts
- Agent times out naturally
- Next connection starts fresh

**No special handling needed** (existing reconnect logic handles this)

### Edge Case 4: Interrupt After Completion
**Scenario**: User clicks Stop just as message completes
**Behavior**:
- Backend returns "no active execution" error
- Client ignores error (already in idle state)
- UI remains in normal state

**Implementation**: Check `currentAssistantMessage` before sending

### Edge Case 5: Mobile Long-Press
**Scenario**: User accidentally long-presses Stop button
**Behavior**:
- Treated as single click
- Standard touch event handling
- No confirmation dialog (too slow)

**Implementation**: Use `touchstart` instead of `click` on mobile

---

## Security & Safety

### Interrupt Abuse Prevention
**Risk**: User rapidly clicking Stop repeatedly
**Mitigation**:
- Rate limit: Max 1 interrupt per second
- Button disabled during interruption
- No impact on backend (interrupt is idempotent)

### Agent State Corruption
**Risk**: Interrupt leaves agent in corrupted state
**Mitigation**:
- Existing `agent.interrupt()` handles cleanup
- Test with various agent states
- Verify next message works correctly

### Partial Tool Execution
**Risk**: Tool partially executes before interrupt
**Mitigation**:
- Document that partial execution may occur
- User should verify state after interrupt
- Future: Add transaction/rollback for critical tools

---

## Testing Plan

### Unit Tests

**Backend**:
```python
async def test_interrupt_message_handler():
    """Test interrupt message handling"""
    # Send interrupt message via WebSocket
    # Verify agent.interrupt() called
    # Verify confirmation sent back
```

**Frontend**:
```javascript
test('Stop button appears during streaming', () => {
    // Simulate streaming start
    // Check stop button visibility
});

test('Stop button sends interrupt message', () => {
    // Click stop button
    // Verify WebSocket message sent
});
```

### Integration Tests

```python
async def test_full_interrupt_flow():
    """Test complete interrupt flow"""
    # Start agent execution
    # Send interrupt via WebSocket
    # Verify agent stops
    # Verify UI updated
    # Verify next message works
```

### Manual Test Cases

1. **Basic Interrupt**:
   - Start long operation
   - Click Stop
   - Verify agent stops
   - Send new message, verify it works

2. **Interrupt During Tool Call**:
   - Trigger bash command
   - Interrupt mid-execution
   - Verify clean state

3. **Rapid Interrupts**:
   - Send message
   - Click Stop rapidly (5x)
   - Verify only one interrupt sent

4. **Mobile Test**:
   - Open on mobile browser
   - Trigger agent
   - Tap Stop button
   - Verify works correctly

5. **Edge Cases**:
   - Interrupt immediately after send
   - Interrupt just before completion
   - Interrupt with network issues

---

## Performance Considerations

### Latency
**Target**: Interrupt acknowledged within 1 second
**Measurement**: Time from button click to "Interrupted" status

**Optimization**:
- Direct WebSocket message (no queueing)
- Agent interrupt is async (non-blocking)
- UI update is immediate (optimistic)

### Resource Cleanup
- Agent cleans up SDK resources
- No memory leaks from interrupted operations
- Temporary files deleted

### User Perception
- Immediate button state change (optimistic UI)
- Don't wait for confirmation before showing "Stopping..."
- Fast feedback is more important than perfect accuracy

---

## Success Criteria

### Must Have
- [ ] Stop button visible during streaming
- [ ] Clicking Stop halts agent within 1 second
- [ ] UI shows clear interrupted status
- [ ] Can send new message after interrupt
- [ ] No crashes or errors
- [ ] Works on desktop and mobile
- [ ] All tests passing

### Nice to Have
- [ ] Keyboard shortcut (Esc) to stop
- [ ] Confirmation dialog for long operations
- [ ] Interrupt history (show in logs)
- [ ] Resume capability (probably not needed)

---

## Future Enhancements

### Version 2.0
- **Keyboard Shortcut**: Esc key to interrupt
- **Pause/Resume**: Pause agent instead of full stop
- **Undo Interrupt**: Resume interrupted operation
- **Interrupt History**: Log all interruptions
- **Confirmation Dialog**: For destructive operations

### Integration with Other Features
- Verbose Mode: Show interrupt in tool log
- Thinking Mode: Interrupt during thinking phase
- File Upload: Cancel file upload

---

## Documentation

### User Documentation
Add to README.md:
```markdown
## Stopping the Agent

If the agent is taking too long or going in the wrong direction:

1. Click the **Stop** button (appears during execution)
2. Wait for confirmation (~1 second)
3. Send a new message to course-correct

**Note**: Partial tool execution may occur before interrupt.
```

### Developer Documentation
Add to docs/design.md:
```markdown
### Agent Interruption

The web UI supports interrupting agent execution via WebSocket:

1. User clicks Stop button
2. Client sends `{"type": "interrupt"}` message
3. Server calls `agent.interrupt()`
4. Agent stops gracefully
5. Server sends `{"type": "interrupted"}` confirmation
6. UI updates to idle state

Backend implementation: `agent.interrupt()` in bassi/agent.py
```

---

## Implementation Checklist

### Phase 1: Backend
- [ ] Verify `agent.interrupt()` works correctly
- [ ] Add interrupt message handler in web_server.py
- [ ] Test interrupt during tool execution
- [ ] Test interrupt during text generation
- [ ] Add error handling for edge cases

### Phase 2: Frontend
- [ ] Add Stop button to UI
- [ ] Implement show/hide logic
- [ ] Add interrupt message sender
- [ ] Handle interrupted response
- [ ] Add CSS styling
- [ ] Update existing event handlers

### Phase 3: Testing
- [ ] Write unit tests (backend)
- [ ] Write unit tests (frontend)
- [ ] Integration tests
- [ ] Manual testing (all scenarios)
- [ ] Mobile testing
- [ ] Cross-browser testing

### Phase 4: Documentation
- [ ] Update README.md
- [ ] Update design.md
- [ ] Add JSDoc comments
- [ ] Add Python docstrings

---

**Status**: Ready for implementation
**Estimated Time**: 1-2 days
**Next Steps**: Begin backend integration testing, then frontend implementation
