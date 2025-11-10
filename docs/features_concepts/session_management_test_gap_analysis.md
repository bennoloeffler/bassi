# Session Management E2E Test Gap Analysis

## Overview

This document compares the required E2E tests (from `session_management_e2e_tests.md`) with existing tests to identify gaps and prioritize what needs to be written.

**Generated:** 2025-11-09
**Status:** Analysis Complete

---

## Existing Test Coverage

### ✅ Unit Tests (Already Exist)

1. **`test_message_persistence.py`** (9.9 KB, 13 tests)
   - ✅ User message saved to workspace
   - ✅ Assistant response saved to workspace
   - ✅ Message count increments correctly
   - ✅ Session index updated after messages
   - ✅ History.md contains all messages

2. **`test_session_deletion.py`** (9.2 KB, 8 tests)
   - ✅ DELETE endpoint success
   - ✅ Cannot delete active session (400 error)
   - ✅ 404 for non-existent session
   - ✅ Session index updated after deletion
   - ✅ Workspace files removed

3. **`test_session_naming.py`** (9.4 KB)
   - ✅ Auto-naming logic
   - ✅ Session name updates after first exchange

4. **`test_session_workspace.py`** (24 KB, 18 tests)
   - ✅ Workspace creation
   - ✅ File storage
   - ✅ Metadata management
   - ✅ Symlink creation

5. **`test_session_index.py`** (13 KB, 8 tests)
   - ✅ Session listing
   - ✅ Index updates
   - ✅ Metadata sync

6. **`test_agent_session.py`** (18 KB)
   - ✅ Agent initialization
   - ✅ Query handling
   - ✅ WebSocket integration

### ✅ Integration/E2E Tests (Partial)

1. **`test_session_lifecycle_e2e.py`** (4.3 KB, 1 test)
   - ✅ Create two sessions via UI
   - ✅ Send messages to both
   - ✅ Delete inactive session
   - ✅ Verify session list updates

---

## Test Gap Analysis

### 🔴 CRITICAL GAPS (P0) - Must Write

These tests are **essential** to verify the bugs you reported are fixed:

#### Gap 1: Message Restoration on Session Switch
**Priority:** P0 - CRITICAL
**Test Suite:** `test_session_switching_e2e.py` (NEW FILE NEEDED)

**Missing Tests:**
```python
# Test 1.1: Switch to existing session loads messages
async def test_switch_session_loads_messages():
    """
    GIVEN: Two sessions - Session A with 4 messages, Session B with 2 messages
    WHEN: User switches from A to B
    THEN: UI shows only Session B's 2 messages in correct order

    THIS DIRECTLY TESTS YOUR BUG: "clicking an old one does not restore the messages"
    """

# Test 1.2: Empty session shows no messages
async def test_empty_session_shows_no_messages():
    """
    GIVEN: Session A with messages, Session B empty
    WHEN: User switches to empty Session B
    THEN: UI shows welcome screen, no message history
    """

# Test 1.3: Messages persist after page reload
async def test_messages_persist_after_reload():
    """
    GIVEN: Session with 6 messages
    WHEN: User reloads page (F5)
    THEN: Same session reconnects with all messages visible
    """
```

**Why Critical:** Directly addresses your issue that messages aren't restored when clicking sessions.

---

#### Gap 2: Agent Context Loading
**Priority:** P0 - CRITICAL
**Test Suite:** `test_agent_context_e2e.py` (NEW FILE NEEDED)

**Missing Tests:**
```python
# Test 2.1: Agent remembers previous context
async def test_agent_remembers_context():
    """
    GIVEN: Session where user says "My name is Alice"
    WHEN: User switches away and back, asks "What's my name?"
    THEN: Agent responds "Alice" (proving context loaded)

    THIS DIRECTLY TESTS YOUR BUG: "context is not loaded into the agent"
    """

# Test 2.2: Agent sees previous tool use
async def test_agent_sees_previous_tool_use():
    """
    GIVEN: Session where agent created file "test.txt"
    WHEN: User switches away and back, asks "What file did you create?"
    THEN: Agent mentions "test.txt"
    """

# Test 2.3: Context includes file uploads
async def test_context_includes_uploaded_files():
    """
    GIVEN: Session with uploaded image
    WHEN: User switches away and back
    THEN: Agent remembers the upload
    """
```

**Why Critical:** Directly addresses your issue that context isn't loaded when resuming sessions.

---

#### Gap 3: Empty Session Prevention
**Priority:** P0 - CRITICAL
**Test Suite:** `test_empty_session_cleanup_e2e.py` (NEW FILE NEEDED)

**Missing Tests:**
```python
# Test 3.1: Empty session deleted on disconnect
async def test_empty_session_deleted_on_disconnect():
    """
    GIVEN: User connects (creates session) without sending messages
    WHEN: User closes browser
    THEN: Session NOT in list after reconnect

    THIS DIRECTLY TESTS YOUR BUG: "there are still empty sessions"
    """

# Test 3.2: Session with messages not deleted
async def test_session_with_messages_not_deleted():
    """
    GIVEN: Session with messages
    WHEN: User disconnects
    THEN: Session remains in list
    """
```

**Why Critical:** Directly addresses your issue that empty sessions clutter the list.

---

### 🟡 IMPORTANT GAPS (P1) - Should Write

#### Gap 4: Session Deletion UI Tests
**Priority:** P1
**Test Suite:** `test_session_deletion_ui_e2e.py` (NEW FILE NEEDED)

**Missing Tests:**
- Delete button appears on hover (inactive sessions only)
- Delete confirmation shows session name
- Cancel keeps session
- Cannot delete active session (no button shown)

**Note:** Backend deletion tested in unit tests, but UI workflow needs E2E verification.

---

#### Gap 5: Session Switch Confirmation
**Priority:** P1
**Test Suite:** `test_session_switch_confirmation_e2e.py` (NEW FILE NEEDED)

**Missing Tests:**
- Confirmation appears when input has unsent text
- No confirmation when input empty
- Cancel preserves current session
- Confirm switches and clears input

---

### 🟢 NICE-TO-HAVE GAPS (P2) - Optional

#### Gap 6: Auto-Naming E2E
**Priority:** P2
**Test Suite:** Extend `test_session_naming.py` or create E2E version

**Missing Tests:**
- Session auto-named after first exchange (E2E verification)
- Subsequent messages don't rename

**Note:** Unit tests exist, but E2E verification through UI would be valuable.

---

#### Gap 7: Current Session Highlighting
**Priority:** P2
**Test Suite:** `test_session_highlighting_e2e.py` (NEW FILE NEEDED)

**Missing Tests:**
- Active session has visual indicator
- Indicator moves on switch

---

#### Gap 8: Performance Tests
**Priority:** P2
**Test Suite:** `test_session_performance_e2e.py` (NEW FILE NEEDED)

**Missing Tests:**
- Many sessions load quickly (50+ sessions)
- Large message history loads quickly (100+ messages)

---

## Prioritized Implementation Plan

### Phase 1: Fix Critical Bugs (Highest Priority)
**Estimated Time:** 2-3 days

Write these 3 test files to verify bug fixes:

1. **`test_session_switching_e2e.py`** (3 tests)
   - ✅ Verifies message restoration works
   - ✅ Tests session switching workflow
   - ✅ Ensures UI shows correct content

2. **`test_agent_context_e2e.py`** (3 tests)
   - ✅ Verifies agent remembers context
   - ✅ Tests tool use persistence
   - ✅ Ensures file upload context

3. **`test_empty_session_cleanup_e2e.py`** (2 tests)
   - ✅ Verifies empty sessions are cleaned up
   - ✅ Tests sessions with messages persist

**Total:** 8 critical E2E tests

---

### Phase 2: Add Missing Features (Medium Priority)
**Estimated Time:** 2 days

4. **`test_session_deletion_ui_e2e.py`** (4 tests)
   - Verify delete button UI workflow
   - Test confirmation dialogs
   - Ensure active session protection

5. **`test_session_switch_confirmation_e2e.py`** (2 tests)
   - Verify unsent input warning
   - Test confirmation flow

**Total:** 6 additional E2E tests

---

### Phase 3: Polish & Performance (Low Priority)
**Estimated Time:** 1-2 days

6. **`test_session_highlighting_e2e.py`** (2 tests)
7. **`test_session_performance_e2e.py`** (2 tests)
8. Extend **`test_session_naming.py`** with E2E verification (1 test)

**Total:** 5 additional E2E tests

---

## Summary Statistics

### Current State
- ✅ **Unit Tests:** 56+ tests across 6 files (good coverage)
- ✅ **Integration Tests:** 1 E2E test (basic lifecycle)
- ❌ **E2E Coverage:** ~10% of required scenarios

### After Phase 1 (Critical)
- ✅ **E2E Coverage:** ~50% of required scenarios
- ✅ **All P0 bugs verified** (message restoration, context loading, empty session cleanup)

### After Phase 2 (Important)
- ✅ **E2E Coverage:** ~75% of required scenarios
- ✅ **All P1 features verified** (deletion UI, switch confirmation)

### After Phase 3 (Polish)
- ✅ **E2E Coverage:** ~90% of required scenarios
- ✅ **Full feature parity with specification**

---

## Recommended Approach

### Option A: Incremental (Safest)
Write tests one suite at a time, fix bugs as they're discovered:

1. Write `test_session_switching_e2e.py` → Fix switching bugs
2. Write `test_agent_context_e2e.py` → Fix context loading bugs
3. Write `test_empty_session_cleanup_e2e.py` → Fix cleanup bugs
4. Continue with P1 and P2 tests

**Pros:**
- Immediate feedback on each bug
- Can verify fixes work before moving on
- Lower risk of breaking changes

**Cons:**
- Takes longer (3-5 days total)
- Multiple fix/test cycles

---

### Option B: Write All P0 Tests First (Recommended)
Write all 3 critical test suites, then fix all bugs at once:

1. Write all P0 tests (8 tests across 3 files)
2. Run tests → see all failures
3. Fix bugs systematically
4. Re-run until all pass

**Pros:**
- Comprehensive view of all issues
- Can fix related bugs together
- Faster overall (2-3 days)

**Cons:**
- Need to track multiple failures initially
- Higher cognitive load

---

## Test Writing Strategy

### Parallel Test Writing with Agents

Use the `/bel-write-tests-one-by-one` command to write tests in parallel:

```bash
# Phase 1: Write all 3 critical test files in parallel
/bel-write-tests-one-by-one "Create test_session_switching_e2e.py with 3 tests for message restoration"
/bel-write-tests-one-by-one "Create test_agent_context_e2e.py with 3 tests for context loading"
/bel-write-tests-one-by-one "Create test_empty_session_cleanup_e2e.py with 2 tests for cleanup"
```

### Manual Test Writing

If writing manually, use this template for each test:

```python
"""
End-to-end test for [feature name].

Tests:
1. [Test name 1]
2. [Test name 2]
3. [Test name 3]
"""

import pytest

# Ensure serial execution with shared server
pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.xdist_group(name="e2e_server"),
]


@pytest.mark.asyncio
async def test_feature_scenario_1(page, live_server):
    """
    GIVEN: [Initial state]
    WHEN: [Action]
    THEN: [Expected outcome]

    THIS TESTS: [Bug or feature]
    """
    # 1. Setup
    page.goto(live_server)

    # 2. Execute actions
    # ... test steps ...

    # 3. Verify outcomes
    # ... assertions ...
```

---

## Next Steps

### Immediate Actions

1. **Choose approach** (Option A or B above)

2. **If Option B (recommended):**
   - Write `test_session_switching_e2e.py` (3 tests)
   - Write `test_agent_context_e2e.py` (3 tests)
   - Write `test_empty_session_cleanup_e2e.py` (2 tests)
   - Run all 8 tests → expect failures
   - Fix bugs in web_server_v3.py
   - Re-run until all pass

3. **Verify fixes manually:**
   - Start `./run-agent-web.sh`
   - Test message restoration manually
   - Test context loading manually
   - Test empty session cleanup manually

4. **Move to Phase 2** (P1 tests)

---

## Related Files

- **Test Specification:** `docs/features_concepts/session_management_e2e_tests.md`
- **Implementation Plan:** `docs/features_concepts/session_management_implementation_plan.md`
- **Bug Analysis:** `docs/features_concepts/session_management_fixes.md`
- **Existing E2E Test:** `bassi/core_v3/tests/test_session_lifecycle_e2e.py`

---

## Conclusion

**Summary:**
- ✅ **Good unit test coverage** (56+ tests)
- ❌ **Missing critical E2E tests** (8 tests needed for P0 bugs)
- 🎯 **Focus on Phase 1** (3 test files, 8 tests total)

**The 3 critical bugs you reported need these specific tests:**

1. **Empty sessions** → `test_empty_session_cleanup_e2e.py`
2. **Messages not restored** → `test_session_switching_e2e.py`
3. **Context not loaded** → `test_agent_context_e2e.py`

**Recommendation:** Write all 3 test files first (using parallel agents if possible), then fix bugs based on failures.
