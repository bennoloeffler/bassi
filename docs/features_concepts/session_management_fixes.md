# Session Management Fixes

## Current Issues Analysis

### Critical Bugs

#### 1. Message Count Always Shows 0 ❌
**Problem:** All sessions display "0 messages" even though conversations have occurred.

**Root Cause:**
- `SessionWorkspace.save_message()` method exists but is **never called**
- Messages flow through WebSocket but aren't persisted to workspace metadata
- `workspace.metadata["message_count"]` remains at 0 after initialization

**Impact:**
- Users can't see which sessions have content
- Session list appears broken/uninformative
- Auto-naming logic can't detect first exchange (relies on message_count)

**Evidence:**
- `web_server_v3.py:1168` reads `workspace.metadata.get("message_count", 0)` for auto-naming
- No calls to `workspace.save_message()` anywhere in web_server_v3.py
- User screenshot shows multiple sessions all with "0 messages"

---

#### 2. Message History Not Persisted ❌
**Problem:** When resuming a session, previous messages aren't visible.

**Root Cause:**
- Messages aren't being saved to `history.md` file
- No persistence layer between WebSocket events and workspace
- Session resume loads workspace but has no message history to display

**Impact:**
- Users lose conversation context when switching sessions
- Can't review previous conversations
- Session isolation is broken

---

#### 3. Sessions with 0 Messages Are Saved ❌
**Problem:** Empty sessions clutter the session list.

**Root Cause:**
- Session workspace created immediately on WebSocket connect (web_server_v3.py:530)
- No cleanup logic for abandoned sessions
- No check for message count before persisting

**Impact:**
- Session list becomes cluttered
- User confusion about which sessions contain work
- Harder to find meaningful sessions

---

### Missing Features

#### 4. No Delete Button ❌
**What's Missing:**
- No DELETE endpoint for sessions
- No UI button to delete sessions
- No confirmation dialog

**User Impact:**
- Can't clean up test/abandoned sessions
- Session list grows indefinitely
- No way to manage storage

---

#### 5. Sessions Have Generic Names ⚠️
**Current State:**
- Auto-naming feature exists (SessionNamingService)
- Gets triggered after first exchange (web_server_v3.py:1174)
- BUT doesn't work properly because message_count is always 0

**What's Needed:**
- Fix message tracking so auto-naming triggers
- Verify naming service generates meaningful names
- Add manual rename capability

---

#### 6. Current Session Not Highlighted ⚠️
**What's Missing:**
- No way to identify which session is active
- `isActive` logic exists in frontend (app.js:3442) but compares `this.sessionId`
- Need to track and display current session

---

#### 7. No Confirmation When Switching Sessions ❌
**What's Missing:**
- Clicking another session immediately switches
- No warning about abandoning current work
- Could lose unsent messages

---

## Implementation Architecture

### Message Flow (Current vs Needed)

**Current (Broken):**
```
User Message → WebSocket → Agent SDK → Claude API
                  ↓
            Display in UI
                  ↓
           (nowhere - lost!)
```

**Needed:**
```
User Message → WebSocket → Save to Workspace → Agent SDK → Claude API
                                ↓                    ↓
                         Update message_count   Display in UI
                                ↓
                         Update session index
                                ↓
                         Save to history.md
```

### Components Involved

1. **SessionWorkspace** (`bassi/core_v3/session_workspace.py`)
   - `save_message(role, content, timestamp)` - EXISTS but unused
   - `metadata["message_count"]` - EXISTS but never incremented
   - Need to call these methods from WebSocket handler

2. **SessionIndex** (`bassi/core_v3/session_index.py`)
   - `update_session(workspace)` - EXISTS
   - Need to update after each message

3. **WebSocket Handler** (`bassi/core_v3/web_server_v3.py`)
   - `handle_websocket()` - Processes all messages
   - Need to intercept user/assistant messages and persist them

4. **Frontend** (`bassi/static/app.js`)
   - `renderSessions()` - Displays session list
   - Need to add delete buttons
   - Need to add confirmation dialogs

---

## Root Cause Summary

The core issue is a **missing persistence layer**:

```python
# web_server_v3.py - WebSocket message handling
# Currently:
async for message in session.query(user_message_text, session_id=connection_id):
    event = convert_message_to_websocket(message)
    await websocket.send_json(event)
    # ❌ Message is NOT saved to workspace here!

# What's needed:
async for message in session.query(user_message_text, session_id=connection_id):
    # ✅ Save user message first
    workspace.save_message("user", user_message_text)

    event = convert_message_to_websocket(message)
    await websocket.send_json(event)

    # ✅ Save assistant response
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                workspace.save_message("assistant", block.text)

    # ✅ Update session index
    session_index.update_session(workspace)
```

---

## Priority Classification

### P0 - Critical (Breaks UX)
1. Fix message count tracking
2. Add message persistence
3. Add delete button

### P1 - Important (Enhances UX)
4. Auto-cleanup empty sessions
5. Fix auto-naming (depends on P0)
6. Add session switch confirmation

### P2 - Nice to Have
7. Manual rename feature
8. Current session highlighting
9. Search/filter improvements

---

## Blockers

None. All infrastructure exists:
- ✅ SessionWorkspace.save_message() already implemented
- ✅ SessionIndex.update_session() already implemented
- ✅ Auto-naming service already implemented
- ✅ Session deletion method exists

Just need to **wire them together** in the WebSocket handler.
