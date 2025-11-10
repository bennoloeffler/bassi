# Session Management E2E Test Specification

## Overview

This document defines the comprehensive E2E test suite needed to verify that session management in Bassi V3 is fully functional. These tests should be written with Playwright to verify the complete user workflow through the web UI.

## Test Environment Setup

```python
# All tests use these common fixtures
@pytest.fixture
async def browser_context():
    """Playwright browser context with clean state"""

@pytest.fixture
async def test_client():
    """FastAPI test client with separate session workspace per test"""

@pytest.fixture
async def clean_session_dir(tmp_path):
    """Temporary chats directory for test isolation"""
```

## Critical Bugs to Fix (P0)

### Test Suite 1: Message Persistence and Counting

**File:** `bassi/core_v3/tests/test_session_persistence_e2e.py`

#### Test 1.1: User Message Increments Count
```python
async def test_user_message_increments_count(page, test_server):
    """
    GIVEN: New session with 0 messages
    WHEN: User sends a message
    THEN:
      - Message count shows 1 in session list
      - history.md contains the user message
      - session.json shows message_count = 1
    """
    # 1. Navigate to bassi-web
    # 2. Wait for WebSocket connection
    # 3. Send message "Hello, test message"
    # 4. Wait for assistant response to complete
    # 5. Check session list shows "1 message"
    # 6. Verify session.json on disk has message_count = 1
    # 7. Verify history.md contains "Hello, test message"
```

#### Test 1.2: Assistant Response Increments Count
```python
async def test_assistant_response_increments_count(page, test_server):
    """
    GIVEN: Session with 1 user message
    WHEN: Assistant responds
    THEN:
      - Message count shows 2 in session list
      - history.md contains both messages
      - session.json shows message_count = 2
    """
    # 1. Send message and wait for full response
    # 2. Check session list shows "2 messages"
    # 3. Verify session.json has message_count = 2
    # 4. Verify history.md has both user and assistant messages
```

#### Test 1.3: Multiple Exchanges Count Correctly
```python
async def test_multiple_exchanges_count_correctly(page, test_server):
    """
    GIVEN: New session
    WHEN: User sends 3 messages, assistant responds to each
    THEN:
      - Message count shows 6 (3 user + 3 assistant)
      - All messages are in history.md
      - session.json shows message_count = 6
    """
    # 1. Send 3 messages with assistant responses
    # 2. Verify final count is 6
    # 3. Verify all messages persist correctly
```

---

### Test Suite 2: Session Switching and Message Restoration

**File:** `bassi/core_v3/tests/test_session_switching_e2e.py`

#### Test 2.1: Switch to Existing Session Loads Messages
```python
async def test_switch_session_loads_messages(page, test_server):
    """
    GIVEN: Two sessions - Session A with 4 messages, Session B with 2 messages
    WHEN: User switches from A to B
    THEN:
      - UI clears and shows only Session B's 2 messages
      - Messages are displayed in correct order
      - Message content matches what was sent originally
    """
    # 1. Create session A, send 2 messages
    # 2. Create session B, send 1 message
    # 3. Switch back to session A
    # 4. Verify UI shows all 4 messages from session A
    # 5. Switch to session B
    # 6. Verify UI shows only 2 messages from session B
```

#### Test 2.2: Empty Session Shows No Messages
```python
async def test_empty_session_shows_no_messages(page, test_server):
    """
    GIVEN: Session A with messages, Session B just created (empty)
    WHEN: User switches to empty Session B
    THEN:
      - UI shows welcome screen
      - No message history displayed
      - Session list shows "0 messages" for Session B
    """
    # 1. Create session A with messages
    # 2. Click "New Session" button
    # 3. Verify new session shows welcome screen
    # 4. Verify session list shows "0 messages"
```

#### Test 2.3: Messages Persist After Page Reload
```python
async def test_messages_persist_after_reload(page, test_server):
    """
    GIVEN: Session with 6 messages
    WHEN: User reloads the page
    THEN:
      - Same session reconnects
      - All 6 messages are displayed
      - User can continue conversation
    """
    # 1. Send 3 exchanges (6 messages)
    # 2. Reload page (F5)
    # 3. Wait for reconnection
    # 4. Verify all messages are visible
    # 5. Send new message to verify continuation works
```

---

### Test Suite 3: Context Loading for Agent

**File:** `bassi/core_v3/tests/test_agent_context_e2e.py`

#### Test 3.1: Agent Remembers Previous Context
```python
async def test_agent_remembers_context(page, test_server):
    """
    GIVEN: Session where user says "My name is Alice"
    WHEN: User switches away and back, then asks "What's my name?"
    THEN:
      - Agent responds with "Alice" (proving context was loaded)
    """
    # 1. Create session, send "My name is Alice"
    # 2. Wait for response
    # 3. Create new session
    # 4. Switch back to first session
    # 5. Send "What's my name?"
    # 6. Verify response contains "Alice"
```

#### Test 3.2: Agent Sees Previous Tool Use
```python
async def test_agent_sees_previous_tool_use(page, test_server):
    """
    GIVEN: Session where agent used a tool (e.g., file creation)
    WHEN: User asks about that tool use after session switch
    THEN:
      - Agent knows about the previous tool use
      - Can reference the file it created
    """
    # 1. Ask agent to "Create a file called test.txt with content 'Hello'"
    # 2. Wait for tool use completion
    # 3. Switch to new session
    # 4. Switch back
    # 5. Ask "What file did you create?"
    # 6. Verify agent mentions "test.txt"
```

#### Test 3.3: Context Includes File Uploads
```python
async def test_context_includes_uploaded_files(page, test_server):
    """
    GIVEN: Session with uploaded image "diagram.png"
    WHEN: User switches away and back, then asks "What's in the image?"
    THEN:
      - Agent can access and describe the uploaded image
    """
    # 1. Upload image file
    # 2. Ask "What's in this image?"
    # 3. Get response describing image
    # 4. Switch to new session
    # 5. Switch back
    # 6. Ask "What image did I upload?"
    # 7. Verify agent remembers the upload
```

---

## Missing Features (P1)

### Test Suite 4: Empty Session Auto-Cleanup

**File:** `bassi/core_v3/tests/test_empty_session_cleanup_e2e.py`

#### Test 4.1: Empty Session Deleted on Disconnect
```python
async def test_empty_session_deleted_on_disconnect(page, test_server):
    """
    GIVEN: User connects and creates new session
    WHEN: User closes browser without sending messages
    THEN:
      - Session is NOT in session list after reconnect
      - Session directory is deleted from disk
    """
    # 1. Connect to bassi-web (creates session)
    # 2. Note session ID
    # 3. Close browser without sending messages
    # 4. Reconnect
    # 5. Verify session list doesn't show empty session
    # 6. Verify session directory doesn't exist
```

#### Test 4.2: Session With Messages Not Deleted
```python
async def test_session_with_messages_not_deleted(page, test_server):
    """
    GIVEN: Session with at least 1 message
    WHEN: User disconnects
    THEN:
      - Session remains in list
      - Can be resumed later
    """
    # 1. Send message
    # 2. Close browser
    # 3. Reconnect
    # 4. Verify session is in list
    # 5. Click session to verify it works
```

---

### Test Suite 5: Session Deletion Feature

**File:** `bassi/core_v3/tests/test_session_deletion_ui_e2e.py`

#### Test 5.1: Delete Button Appears on Hover
```python
async def test_delete_button_appears_on_hover(page, test_server):
    """
    GIVEN: Session list with multiple sessions
    WHEN: User hovers over an inactive session
    THEN:
      - Delete button (🗑️) appears
      - Delete button is hidden for active session
    """
    # 1. Create two sessions
    # 2. Switch to session A (active)
    # 3. Hover over session B (inactive)
    # 4. Verify delete button is visible
    # 5. Hover over session A (active)
    # 6. Verify delete button is NOT visible
```

#### Test 5.2: Delete with Confirmation Works
```python
async def test_delete_session_with_confirmation(page, test_server):
    """
    GIVEN: Session list with "Test Session"
    WHEN: User clicks delete and confirms
    THEN:
      - Confirmation dialog shows session name
      - After confirm, session disappears from list
      - Session directory is deleted from disk
    """
    # 1. Create session with known name
    # 2. Hover and click delete button
    # 3. Verify confirmation dialog shows session name
    # 4. Click "OK" to confirm
    # 5. Verify session removed from list
    # 6. Verify session directory deleted
```

#### Test 5.3: Delete Cancellation Keeps Session
```python
async def test_delete_cancellation_keeps_session(page, test_server):
    """
    GIVEN: Session about to be deleted
    WHEN: User clicks delete but cancels confirmation
    THEN:
      - Session remains in list
      - All data intact
    """
    # 1. Click delete button
    # 2. Click "Cancel" in confirmation
    # 3. Verify session still in list
    # 4. Verify can still open session
```

#### Test 5.4: Cannot Delete Active Session
```python
async def test_cannot_delete_active_session(page, test_server):
    """
    GIVEN: Currently active session
    WHEN: User attempts to delete (if button exists)
    THEN:
      - Either no delete button shown, OR
      - Delete returns error "Cannot delete active session"
    """
    # 1. Verify active session has no delete button
    # 2. Or if API is called directly, verify 400 error
```

---

### Test Suite 6: Session Switch Confirmation

**File:** `bassi/core_v3/tests/test_session_switch_confirmation_e2e.py`

#### Test 6.1: Confirmation When Input Has Text
```python
async def test_switch_confirmation_with_unsent_input(page, test_server):
    """
    GIVEN: User has typed message but not sent it
    WHEN: User clicks another session
    THEN:
      - Confirmation dialog appears
      - Dialog warns about losing unsent input
      - Canceling keeps current session
      - Confirming switches and clears input
    """
    # 1. Type message but don't send
    # 2. Click different session
    # 3. Verify confirmation dialog appears
    # 4. Click "Cancel"
    # 5. Verify still in current session, input preserved
    # 6. Click different session again
    # 7. Click "OK"
    # 8. Verify switched, input cleared
```

#### Test 6.2: No Confirmation When Input Empty
```python
async def test_no_confirmation_with_empty_input(page, test_server):
    """
    GIVEN: Empty message input field
    WHEN: User clicks another session
    THEN:
      - No confirmation dialog
      - Switches immediately
    """
    # 1. Ensure input is empty
    # 2. Click different session
    # 3. Verify no confirmation dialog
    # 4. Verify switched immediately
```

---

## Polish Features (P2)

### Test Suite 7: Auto-Naming

**File:** `bassi/core_v3/tests/test_auto_naming_e2e.py`

#### Test 7.1: Session Gets Named After First Exchange
```python
async def test_session_auto_names_after_first_exchange(page, test_server):
    """
    GIVEN: New session with default name "Session {id}"
    WHEN: User asks "Explain quantum computing" and gets response
    THEN:
      - Session name changes to something relevant (e.g., "quantum-computing-explanation")
      - New name appears in session list
    """
    # 1. Note initial session name
    # 2. Send message about specific topic
    # 3. Wait for response
    # 4. Wait for auto-naming (may take a moment)
    # 5. Verify session name updated in list
    # 6. Verify name is relevant to topic
```

#### Test 7.2: Subsequent Messages Don't Rename
```python
async def test_subsequent_messages_dont_rename(page, test_server):
    """
    GIVEN: Session already auto-named
    WHEN: User sends more messages
    THEN:
      - Name stays the same
      - No additional renaming occurs
    """
    # 1. Send first message, wait for auto-naming
    # 2. Note the auto-generated name
    # 3. Send 2 more messages
    # 4. Verify name unchanged
```

---

### Test Suite 8: Current Session Highlighting

**File:** `bassi/core_v3/tests/test_session_highlighting_e2e.py`

#### Test 8.1: Active Session Has Visual Indicator
```python
async def test_active_session_highlighted(page, test_server):
    """
    GIVEN: Multiple sessions in list
    WHEN: User is in Session B
    THEN:
      - Session B has "active" class/styling
      - Other sessions don't have active styling
    """
    # 1. Create 3 sessions
    # 2. Switch to session 2
    # 3. Check CSS class "active" on session 2
    # 4. Verify sessions 1 and 3 don't have "active"
```

#### Test 8.2: Active Indicator Moves on Switch
```python
async def test_active_indicator_moves_on_switch(page, test_server):
    """
    GIVEN: Session A is active
    WHEN: User switches to Session B
    THEN:
      - Active indicator moves from A to B
    """
    # 1. Verify session A is highlighted
    # 2. Click session B
    # 3. Verify session A no longer highlighted
    # 4. Verify session B now highlighted
```

---

## Integration Test: Full Workflow

**File:** `bassi/core_v3/tests/test_session_full_workflow_e2e.py`

### Test: Complete Session Lifecycle
```python
async def test_complete_session_lifecycle(page, test_server):
    """
    Complete end-to-end workflow covering all features.

    1. Create new session (auto-named)
    2. Send messages (count updates)
    3. Upload file (appears in context)
    4. Switch to new session
    5. Switch back (messages restored, context loaded)
    6. Ask agent about previous conversation (context works)
    7. Delete old session (cleanup)
    8. Verify data persistence across reload
    """
    # Detailed step-by-step workflow combining all features
```

---

## Performance & Stress Tests

**File:** `bassi/core_v3/tests/test_session_performance_e2e.py`

### Test 9.1: Many Sessions Load Quickly
```python
async def test_many_sessions_load_quickly(page, test_server):
    """
    GIVEN: 50 sessions with various message counts
    WHEN: User loads session list
    THEN:
      - List appears within 2 seconds
      - No UI freezing
    """
```

### Test 9.2: Large Message History Loads Quickly
```python
async def test_large_message_history_loads_quickly(page, test_server):
    """
    GIVEN: Session with 100+ messages
    WHEN: User switches to that session
    THEN:
      - Messages load within 3 seconds
      - UI remains responsive
    """
```

---

## Bug Regression Tests

**File:** `bassi/core_v3/tests/test_session_regressions_e2e.py`

### Test 10.1: No Empty Sessions in List (Bug Fix Verification)
```python
async def test_no_empty_sessions_in_list(page, test_server):
    """
    REGRESSION TEST for issue: "Empty sessions clutter list"

    GIVEN: User creates 5 sessions but only uses 2
    WHEN: Page loads session list
    THEN:
      - Only 2 sessions with messages appear
      - No "0 messages" sessions shown
    """
```

### Test 10.2: Message Count Shows Correctly (Bug Fix Verification)
```python
async def test_message_count_shows_correctly(page, test_server):
    """
    REGRESSION TEST for issue: "All sessions show 0 messages"

    GIVEN: Session with known message count (e.g., 8 messages)
    WHEN: User views session list
    THEN:
      - Correct count "8 messages" is displayed
    """
```

### Test 10.3: Context Restored on Switch (Bug Fix Verification)
```python
async def test_context_restored_on_switch(page, test_server):
    """
    REGRESSION TEST for issue: "Context not loaded into agent"

    GIVEN: Session where user previously said "My favorite color is blue"
    WHEN: User switches away and back, asks "What's my favorite color?"
    THEN:
      - Agent responds "Your favorite color is blue"
    """
```

---

## Test Execution Strategy

### Parallel Execution Groups

```python
# pytest.ini configuration
[pytest]
markers =
    e2e_session: Session management E2E tests
    e2e_critical: Critical P0 tests (must pass)
    e2e_cleanup: Empty session cleanup tests
    e2e_deletion: Session deletion UI tests
    e2e_switching: Session switching tests
    e2e_context: Agent context loading tests
```

### Execution Order

1. **Critical Tests First** (P0): Suites 1-3
2. **Feature Tests** (P1): Suites 4-6
3. **Polish Tests** (P2): Suites 7-8
4. **Integration Test**: Suite 9
5. **Regression Tests**: Suite 10

### CI/CD Pipeline

```bash
# Stage 1: Critical tests (must pass)
pytest bassi/core_v3/tests/ -m "e2e_critical"

# Stage 2: All E2E tests
pytest bassi/core_v3/tests/ -m "e2e_session"

# Stage 3: Full regression suite
pytest bassi/core_v3/tests/ -m "e2e_session or e2e_critical"
```

---

## Success Criteria

### Definition of Done

A test suite is considered complete when:

1. ✅ All test files written with proper fixtures
2. ✅ Each test has clear GIVEN/WHEN/THEN structure
3. ✅ Tests run in parallel without race conditions
4. ✅ Tests clean up after themselves (no leftover files)
5. ✅ All P0 tests pass
6. ✅ 80%+ of P1 tests pass
7. ✅ Manual verification confirms UI matches test results

### Acceptance Criteria

Session management is considered fully functional when:

- [ ] All 10 test suites pass
- [ ] No empty sessions appear in list
- [ ] Message counts are accurate
- [ ] Switching sessions restores full message history
- [ ] Agent remembers context across switches
- [ ] Delete button works with confirmation
- [ ] Auto-cleanup removes abandoned sessions
- [ ] Auto-naming generates meaningful names
- [ ] Page reload preserves state

---

## Implementation Priority

### Phase 1: Fix Critical Bugs (Week 1)
- Test Suites 1-3 (Message Persistence, Switching, Context)
- Must pass 100%

### Phase 2: Add Missing Features (Week 2)
- Test Suites 4-6 (Cleanup, Deletion, Confirmation)
- Should pass 80%+

### Phase 3: Polish & Performance (Week 3)
- Test Suites 7-10 (Auto-naming, Highlighting, Performance, Regressions)
- Nice to have, continuous improvement

---

## Related Documentation

- **Implementation Plan**: `docs/features_concepts/session_management_implementation_plan.md`
- **Bug Analysis**: `docs/features_concepts/session_management_fixes.md`
- **Testing Guide**: `CLAUDE_TESTS.md`
- **Architecture**: `docs/DUAL_MODE_IMPLEMENTATION.md`
