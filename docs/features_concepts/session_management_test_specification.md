# Session Management Test Specification

## Overview

This document provides comprehensive test specifications for all session management fixes and features. Each test includes setup, execution steps, assertions, and acceptance criteria.

---

## Test Suite Organization

```
bassi/core_v3/tests/
├── test_message_persistence.py       # Phase 1 tests
├── test_session_deletion.py          # Phase 2 tests
├── test_session_cleanup.py           # Phase 3 tests
├── test_session_switching.py         # Phase 4 tests (E2E)
└── test_session_naming.py            # Phase 5 tests
```

---

## Phase 1: Message Persistence Tests

### Unit Tests - `test_message_persistence.py`

#### Test 1.1: User Message Saved to Workspace
```python
@pytest.mark.asyncio
async def test_user_message_saved(test_client, session_factory):
    """
    Verify user message is saved to workspace and increments message count.

    Setup:
    - Create fresh session via WebSocket
    - Message count starts at 0

    Execute:
    - Send user message via WebSocket
    - Wait for agent response

    Assert:
    - workspace.metadata["message_count"] == 1
    - history.md contains user message
    - Message timestamp is present
    - Session index is updated

    Acceptance:
    - Message count increments from 0 to 1
    - User message appears in history.md with correct role
    """
```

#### Test 1.2: Assistant Message Saved to Workspace
```python
@pytest.mark.asyncio
async def test_assistant_message_saved(test_client, session_factory):
    """
    Verify assistant response is saved to workspace and increments message count.

    Setup:
    - Create session with 1 user message (message_count=1)

    Execute:
    - Agent generates response
    - Response streamed via WebSocket

    Assert:
    - workspace.metadata["message_count"] == 2
    - history.md contains both user and assistant messages
    - Assistant message has all text blocks
    - Session index reflects new count

    Acceptance:
    - Message count increments from 1 to 2
    - Assistant response appears in history.md
    """
```

#### Test 1.3: Multiple Message Exchange
```python
@pytest.mark.asyncio
async def test_multiple_message_persistence(test_client, session_factory):
    """
    Verify message count and history persist through multiple exchanges.

    Setup:
    - Create fresh session

    Execute:
    - Send message A, get response A'
    - Send message B, get response B'
    - Send message C, get response C'

    Assert:
    - workspace.metadata["message_count"] == 6
    - history.md contains all 6 messages in order
    - Session index shows message_count=6
    - All timestamps are sequential

    Acceptance:
    - Message count accurately reflects all exchanges
    - History is complete and ordered correctly
    """
```

#### Test 1.4: Session Resume Loads History
```python
@pytest.mark.asyncio
async def test_session_resume_loads_history(test_client, session_factory):
    """
    Verify resuming a session loads previous message history.

    Setup:
    - Session with 4 messages (2 exchanges)
    - Disconnect WebSocket

    Execute:
    - Reconnect to same session ID
    - Request session history via API

    Assert:
    - GET /api/sessions/{id}/history returns 4 messages
    - Messages in correct order
    - Message metadata (timestamps, roles) intact

    Acceptance:
    - Previous conversation fully restored
    - UI can display historical messages
    """
```

#### Test 1.5: Message Count Updates Session Index
```python
def test_message_count_in_session_index(test_client, session_factory):
    """
    Verify session index is updated when messages are saved.

    Setup:
    - Create session
    - Load session index

    Execute:
    - Save user message
    - Call session_index.update_session(workspace)
    - Save assistant message
    - Call session_index.update_session(workspace)

    Assert:
    - Index entry has message_count=2
    - Index is persisted to .index.json
    - GET /api/sessions returns correct count

    Acceptance:
    - Session list shows accurate message counts
    """
```

#### Test 1.6: Concurrent Message Saving (Thread Safety)
```python
@pytest.mark.asyncio
async def test_concurrent_message_saving(test_client, session_factory):
    """
    Verify message saving is thread-safe under concurrent load.

    Setup:
    - Create session
    - Workspace uses _upload_lock for thread safety

    Execute:
    - Simulate 10 concurrent message saves
    - Each in separate async task

    Assert:
    - workspace.metadata["message_count"] == 10
    - All 10 messages in history.md
    - No race conditions or lost messages

    Acceptance:
    - Message persistence is thread-safe
    - No data corruption under load
    """
```

---

## Phase 2: Session Deletion Tests

### Unit Tests - `test_session_deletion.py`

#### Test 2.1: Successful Session Deletion
```python
@pytest.mark.asyncio
async def test_delete_session_success(test_client):
    """
    Verify session can be deleted via DELETE endpoint.

    Setup:
    - Create session with 2 messages
    - Session is NOT active (no WebSocket connection)

    Execute:
    - DELETE /api/sessions/{session_id}

    Assert:
    - Response: 200 OK
    - Response JSON: {"success": true, "session_id": "..."}
    - Session files deleted from chats/ directory
    - Symlink removed from chats_by_name/
    - Session removed from index
    - GET /api/sessions doesn't include deleted session

    Acceptance:
    - Session completely removed from filesystem
    - No orphaned files or symlinks
    """
```

#### Test 2.2: Cannot Delete Active Session
```python
@pytest.mark.asyncio
async def test_cannot_delete_active_session(test_client):
    """
    Verify active sessions cannot be deleted.

    Setup:
    - Create session
    - Connect WebSocket (session becomes active)

    Execute:
    - DELETE /api/sessions/{session_id}

    Assert:
    - Response: 400 Bad Request
    - Response JSON: {"error": "Cannot delete active session"}
    - Session still exists in filesystem
    - Session still in index

    Acceptance:
    - Active sessions are protected from deletion
    """
```

#### Test 2.3: Delete Non-Existent Session
```python
async def test_delete_nonexistent_session(test_client):
    """
    Verify deleting non-existent session returns 404.

    Setup:
    - No session with ID "fake-session-123"

    Execute:
    - DELETE /api/sessions/fake-session-123

    Assert:
    - Response: 404 Not Found
    - Response JSON: {"error": "Session not found"}

    Acceptance:
    - Proper error handling for invalid IDs
    """
```

#### Test 2.4: Index Updated After Deletion
```python
async def test_index_updated_after_deletion(test_client):
    """
    Verify session index is updated when session is deleted.

    Setup:
    - Create 3 sessions
    - Index has 3 entries

    Execute:
    - Delete session #2

    Assert:
    - Index has 2 entries
    - Index persisted to .index.json
    - GET /api/sessions returns 2 sessions
    - Deleted session not in list

    Acceptance:
    - Index stays in sync with filesystem
    """
```

#### Test 2.5: Delete Session with Files
```python
async def test_delete_session_with_files(test_client):
    """
    Verify session deletion removes all associated files.

    Setup:
    - Create session
    - Add files to session workspace:
      - history.md
      - session.json
      - uploaded_file.txt
      - agent_output.py

    Execute:
    - DELETE /api/sessions/{session_id}

    Assert:
    - All files removed from chats/{session_id}/
    - Directory removed
    - Symlink removed

    Acceptance:
    - Complete cleanup of session data
    """
```

### E2E Tests - Delete Button UI

#### Test 2.6: Delete Button Appears on Hover
```python
@pytest.mark.e2e
async def test_delete_button_hover(browser_page):
    """
    Verify delete button appears on session hover.

    Setup:
    - Load web UI
    - Session list with 3 sessions

    Execute:
    - Hover over session #2

    Assert:
    - Delete button (🗑️) becomes visible
    - Button has opacity=1
    - Button positioned correctly

    Acceptance:
    - Delete button visible on hover
    """
```

#### Test 2.7: Delete Button Confirmation Dialog
```python
@pytest.mark.e2e
async def test_delete_confirmation_dialog(browser_page):
    """
    Verify delete shows confirmation dialog.

    Setup:
    - Session list with session "My Project Session"

    Execute:
    - Click delete button

    Assert:
    - Confirmation dialog appears
    - Dialog text: "Delete 'My Project Session'?"
    - Dialog text: "This will permanently delete all messages and files."
    - Dialog has Cancel and OK buttons

    Acceptance:
    - User must confirm deletion
    """
```

#### Test 2.8: Delete Session via UI
```python
@pytest.mark.e2e
async def test_delete_session_via_ui(browser_page):
    """
    Verify full delete flow through UI.

    Setup:
    - 3 sessions in list

    Execute:
    - Hover over session #2
    - Click delete button
    - Confirm deletion

    Assert:
    - Session removed from UI list
    - List now shows 2 sessions
    - Session files deleted from filesystem

    Acceptance:
    - Delete works end-to-end
    """
```

#### Test 2.9: Cancel Delete Dialog
```python
@pytest.mark.e2e
async def test_cancel_delete_dialog(browser_page):
    """
    Verify canceling delete keeps session.

    Setup:
    - Session list with 3 sessions

    Execute:
    - Click delete button on session #2
    - Click "Cancel" in dialog

    Assert:
    - Dialog closes
    - Session still in list
    - Session files still exist

    Acceptance:
    - Cancel works correctly
    """
```

---

## Phase 3: Auto-Cleanup Tests

### Unit Tests - `test_session_cleanup.py`

#### Test 3.1: Empty Session Deleted on Disconnect
```python
@pytest.mark.asyncio
async def test_empty_session_deleted(test_client):
    """
    Verify empty session is auto-deleted on WebSocket disconnect.

    Setup:
    - Connect WebSocket (creates session)
    - Session has message_count=0

    Execute:
    - Disconnect WebSocket immediately

    Assert:
    - Session workspace deleted
    - Session removed from index
    - GET /api/sessions doesn't include it
    - Files removed from filesystem

    Acceptance:
    - Empty sessions don't clutter list
    """
```

#### Test 3.2: Session with Messages NOT Deleted
```python
@pytest.mark.asyncio
async def test_session_with_messages_not_deleted(test_client):
    """
    Verify sessions with messages are preserved on disconnect.

    Setup:
    - Create session
    - Send 1 message (message_count=2 after response)

    Execute:
    - Disconnect WebSocket

    Assert:
    - Session still exists
    - Session in index
    - GET /api/sessions includes it
    - Files intact

    Acceptance:
    - Sessions with content are preserved
    """
```

#### Test 3.3: Cleanup Error Handling
```python
@pytest.mark.asyncio
async def test_cleanup_error_handling(test_client, monkeypatch):
    """
    Verify cleanup errors are logged but don't crash server.

    Setup:
    - Create empty session
    - Mock workspace.delete() to raise exception

    Execute:
    - Disconnect WebSocket

    Assert:
    - Error logged
    - Server still running
    - WebSocket cleanup completes

    Acceptance:
    - Graceful error handling
    """
```

---

## Phase 4: Session Switch Tests

### E2E Tests - `test_session_switching.py`

#### Test 4.1: Switch Session with Unsent Input
```python
@pytest.mark.e2e
async def test_switch_with_unsent_input(browser_page):
    """
    Verify confirmation when switching with unsent input.

    Setup:
    - Active session A
    - Type message but don't send

    Execute:
    - Click on session B

    Assert:
    - Confirmation dialog appears
    - Dialog text: "You have unsent input. Switch sessions anyway?"
    - Dialog text: "Your typed message will be lost."

    Acceptance:
    - User warned about losing input
    """
```

#### Test 4.2: Confirm Session Switch
```python
@pytest.mark.e2e
async def test_confirm_session_switch(browser_page):
    """
    Verify session switches after confirmation.

    Setup:
    - Session A active with unsent input

    Execute:
    - Click session B
    - Confirm switch

    Assert:
    - WebSocket disconnects from A
    - WebSocket connects to B
    - UI cleared
    - Session B highlighted as active
    - Input field cleared

    Acceptance:
    - Session switch completes
    """
```

#### Test 4.3: Cancel Session Switch
```python
@pytest.mark.e2e
async def test_cancel_session_switch(browser_page):
    """
    Verify canceling switch keeps current session.

    Setup:
    - Session A active with typed input

    Execute:
    - Click session B
    - Cancel switch

    Assert:
    - Still connected to session A
    - Session A still highlighted
    - Typed input still present

    Acceptance:
    - Cancel works correctly
    """
```

#### Test 4.4: Switch Without Unsent Input
```python
@pytest.mark.e2e
async def test_switch_without_unsent_input(browser_page):
    """
    Verify no confirmation if input is empty.

    Setup:
    - Session A active
    - Input field empty

    Execute:
    - Click session B

    Assert:
    - No confirmation dialog
    - Switch happens immediately
    - Session B becomes active

    Acceptance:
    - Smooth switch when no input
    """
```

---

## Phase 5: Auto-Naming Tests

### Integration Tests - `test_session_naming.py`

#### Test 5.1: Session Auto-Named After First Exchange
```python
@pytest.mark.asyncio
async def test_auto_naming_after_first_exchange(test_client):
    """
    Verify session gets meaningful name after first exchange.

    Prerequisites:
    - Phase 1 complete (message tracking works)

    Setup:
    - Create session (default name: "Unnamed Session")

    Execute:
    - Send: "Help me write a Python script to parse CSV files"
    - Receive assistant response

    Assert:
    - workspace.metadata["message_count"] == 2
    - SessionNamingService.should_auto_name() returns True
    - Session gets renamed
    - New name is relevant (e.g., "CSV Parsing Script")
    - Symlink updated to new name
    - GET /api/sessions shows new name

    Acceptance:
    - Auto-naming triggers correctly
    - Names are meaningful
    """
```

#### Test 5.2: Auto-Naming Not Triggered Before First Exchange
```python
@pytest.mark.asyncio
async def test_no_auto_naming_before_exchange(test_client):
    """
    Verify auto-naming waits for first exchange.

    Setup:
    - Create session
    - message_count=0

    Execute:
    - Check naming service

    Assert:
    - SessionNamingService.should_auto_name() returns False
    - Session keeps default name

    Acceptance:
    - No premature naming
    """
```

#### Test 5.3: Auto-Naming Uses Message Context
```python
@pytest.mark.asyncio
async def test_auto_naming_uses_context(test_client):
    """
    Verify auto-naming generates relevant names from conversation.

    Test Cases:
    1. "Help debug React component" → "React Debugging"
    2. "Write SQL query for user table" → "SQL User Query"
    3. "Explain Docker networking" → "Docker Networking"

    For each:
    - Send user message
    - Get response
    - Assert name is relevant

    Acceptance:
    - Names reflect conversation topic
    """
```

---

## Phase 6: Current Session Highlighting

### E2E Tests

#### Test 6.1: Current Session Highlighted
```python
@pytest.mark.e2e
async def test_current_session_highlighted(browser_page):
    """
    Verify active session is visually highlighted.

    Setup:
    - 3 sessions in list
    - Session B is active

    Assert:
    - Session B has class "active"
    - Session B styled differently (background, border)
    - Sessions A and C don't have "active" class

    Acceptance:
    - Clear visual indication of active session
    """
```

#### Test 6.2: Highlight Updates on Switch
```python
@pytest.mark.e2e
async def test_highlight_updates_on_switch(browser_page):
    """
    Verify highlight moves when switching sessions.

    Setup:
    - Session A active (highlighted)

    Execute:
    - Click session C

    Assert:
    - Session A loses "active" class
    - Session C gains "active" class
    - Highlight visually moves

    Acceptance:
    - Highlight stays in sync
    """
```

---

## Integration Test Scenarios

### Scenario 1: Complete Message Flow
```python
@pytest.mark.integration
async def test_complete_message_flow(test_client):
    """
    Test full message lifecycle from user to persistence.

    Flow:
    1. User sends message via WebSocket
    2. Message saved to workspace
    3. Message sent to Claude API
    4. Assistant response streamed back
    5. Response saved to workspace
    6. Session index updated
    7. History file contains both messages

    Assertions at each step verify correct state.
    """
```

### Scenario 2: Session Lifecycle
```python
@pytest.mark.integration
async def test_session_lifecycle(test_client):
    """
    Test complete session from creation to deletion.

    Flow:
    1. Create session (WebSocket connect)
    2. Exchange 3 messages
    3. Disconnect
    4. Resume session
    5. Verify history loaded
    6. Delete session
    7. Verify cleanup

    Covers: persistence, resume, deletion, cleanup.
    """
```

### Scenario 3: Multiple Sessions Concurrently
```python
@pytest.mark.integration
async def test_multiple_concurrent_sessions(test_client):
    """
    Test multiple sessions running simultaneously.

    Setup:
    - 3 WebSocket connections
    - 3 separate sessions

    Execute:
    - Send messages to all 3 concurrently
    - Each gets unique responses

    Assert:
    - No message cross-contamination
    - Each session has correct message count
    - Each history file has correct messages

    Acceptance:
    - Sessions are properly isolated
    """
```

---

## Test Data and Fixtures

### Mock Agent Responses
```python
# conftest.py additions
@pytest.fixture
def mock_agent_responses():
    """Predefined agent responses for testing."""
    return {
        "greeting": "Hello! How can I help you today?",
        "code_help": "Here's a Python script to parse CSV files...",
        "debug_help": "Let me help you debug that React component...",
    }
```

### Test Session Data
```python
@pytest.fixture
def test_sessions():
    """Pre-created test sessions with known state."""
    return [
        {
            "session_id": "test-session-1",
            "display_name": "Test Session 1",
            "message_count": 4,
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
                {"role": "user", "content": "How are you?"},
                {"role": "assistant", "content": "I'm good!"},
            ],
        },
        {
            "session_id": "test-session-2",
            "display_name": "Empty Session",
            "message_count": 0,
            "messages": [],
        },
    ]
```

---

## Acceptance Criteria Matrix

| Phase | Feature | Acceptance Criteria | Test File |
|-------|---------|-------------------|-----------|
| 1 | Message Persistence | ✅ Message count increments correctly<br>✅ Messages saved to history.md<br>✅ Session index updated | test_message_persistence.py |
| 2 | Session Deletion | ✅ DELETE endpoint works<br>✅ Active sessions protected<br>✅ Files cleaned up<br>✅ UI delete button functional | test_session_deletion.py |
| 3 | Auto-Cleanup | ✅ Empty sessions deleted on disconnect<br>✅ Sessions with messages preserved | test_session_cleanup.py |
| 4 | Switch Confirmation | ✅ Confirmation shown with unsent input<br>✅ No confirmation if input empty<br>✅ Cancel works | test_session_switching.py |
| 5 | Auto-Naming | ✅ Names generated after first exchange<br>✅ Names are meaningful<br>✅ Symlinks updated | test_session_naming.py |
| 6 | Highlighting | ✅ Current session visually distinct<br>✅ Highlight updates on switch | test_session_switching.py |

---

## Test Execution Plan

### Step 1: Write All Tests First
```bash
# Create test files (empty, with @pytest.mark.skip)
touch bassi/core_v3/tests/test_message_persistence.py
touch bassi/core_v3/tests/test_session_deletion.py
touch bassi/core_v3/tests/test_session_cleanup.py
touch bassi/core_v3/tests/test_session_switching.py
touch bassi/core_v3/tests/test_session_naming.py
```

### Step 2: Implement Tests Phase by Phase
```bash
# Phase 1: Write message persistence tests
# Run to verify failures (no implementation yet)
uv run pytest bassi/core_v3/tests/test_message_persistence.py -v

# Expected: All tests FAIL (feature not implemented)
```

### Step 3: Implement Features
```bash
# Implement Phase 1 fix
# Run tests again
uv run pytest bassi/core_v3/tests/test_message_persistence.py -v

# Expected: All tests PASS
```

### Step 4: Repeat for Each Phase
- Write tests
- Verify failures
- Implement feature
- Verify passes
- Move to next phase

### Step 5: Run Full Suite
```bash
# After all phases complete
uv run pytest bassi/core_v3/tests/ -v

# Expected: All session management tests PASS
```

### Step 6: Integration with Existing Tests
```bash
# Run complete test suite
uv run pytest

# Expected: No regressions, all tests PASS
```

---

## Performance Testing

### Load Test: Message Persistence
```python
@pytest.mark.performance
async def test_message_persistence_performance():
    """
    Verify message persistence doesn't degrade under load.

    Execute:
    - Send 100 messages rapidly
    - Measure time to persist each

    Assert:
    - Average < 50ms per message
    - No memory leaks
    - No file handle leaks

    Acceptance:
    - Performance acceptable for real-world use
    """
```

### Load Test: Concurrent Sessions
```python
@pytest.mark.performance
async def test_concurrent_sessions_performance():
    """
    Verify server handles multiple concurrent sessions.

    Execute:
    - Create 20 concurrent WebSocket connections
    - Send messages to all simultaneously

    Assert:
    - All messages processed
    - Response time < 2s per message
    - No crashes or errors

    Acceptance:
    - Server scales to multiple users
    """
```

---

## Manual Testing Checklist

After automated tests pass, verify manually:

### Browser Testing
- [ ] Chrome: Delete button appears on hover
- [ ] Firefox: Delete button appears on hover
- [ ] Safari: Delete button appears on hover
- [ ] Confirmation dialogs work in all browsers
- [ ] Session switching works smoothly

### UX Testing
- [ ] Message counts update in real-time
- [ ] Session names are readable and meaningful
- [ ] Delete confirmation shows correct session name
- [ ] Current session clearly highlighted
- [ ] No visual glitches during operations

### Edge Cases
- [ ] Delete last remaining session
- [ ] Switch sessions during agent response
- [ ] Refresh browser during conversation
- [ ] Multiple tabs/windows same session
- [ ] Network interruption handling

---

## Success Metrics

### Coverage Targets
- **Unit Tests**: >90% coverage of session management code
- **Integration Tests**: All critical paths covered
- **E2E Tests**: All user workflows covered

### Quality Gates
- ✅ All tests pass
- ✅ No regressions in existing tests
- ✅ Code reviewed and approved
- ✅ Manual testing checklist complete
- ✅ Documentation updated

---

## Rollback Plan

If critical bug found after deployment:

1. **Immediate**: Revert to previous commit
2. **Short-term**: Fix bug, add regression test
3. **Long-term**: Improve test coverage to prevent recurrence

---

## Future Test Enhancements

1. **Visual Regression Testing**: Screenshot comparison for UI
2. **Accessibility Testing**: Screen reader compatibility
3. **Security Testing**: XSS, CSRF, injection attacks
4. **Stress Testing**: 1000+ sessions, long-running sessions
5. **Mobile Testing**: Touch interactions, responsive design
