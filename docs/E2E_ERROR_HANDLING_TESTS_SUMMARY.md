# E2E Error Handling Tests Summary

## Overview
Added 8 new E2E tests for V3 web server error handling to improve stability and prevent real user bugs. These tests focus on **unhappy paths** and **edge cases** that could crash the UI.

**Coverage Impact**: 65% → 66% overall, web_server_v3.py: 44% → 45%
**All Tests Passing**: 14/15 E2E tests pass (1 skipped: WebSocket reconnection)

## Test File Created
`bassi/core_v3/tests/test_web_server_error_handling_e2e.py` (387 lines)

## Tests Added

### 1. `test_websocket_invalid_message_format` ✅
- **Scenario**: Malformed JSON or missing required fields
- **Expected**: Server stays responsive, doesn't crash
- **Key Check**: Ping/pong still works after invalid message

### 2. `test_websocket_send_during_session_deletion` ✅
- **Scenario**: Race condition - sending message while deleting session
- **Expected**: UI handles gracefully, no crash or hang
- **Pattern Applied**: Console log listener for session readiness
- **Fix Required**: Used `window.bassiClient.sessionId` instead of `window.currentSessionId`

### 3. `test_websocket_multiple_rapid_messages` ✅
- **Scenario**: User frantically clicks send multiple times
- **Expected**: UI stays stable, doesn't crash (some messages may be queued/dropped)
- **Pattern Applied**: Console log listener + conditional clicking
- **Learning**: Send button correctly disables when input is empty (not a bug)

### 4. `test_session_list_after_server_restart` ✅
- **Scenario**: Server restarted, sessions missing (data loss)
- **Expected**: UI shows empty state gracefully, doesn't crash

### 5. `test_file_upload_invalid_file_type` ✅
- **Scenario**: Uploading unsupported file type (.exe, .dll)
- **Expected**: Clear error or graceful rejection, no crash

### 6. `test_empty_message_submission` ✅
- **Scenario**: User clicks send without typing
- **Expected**: Prevented or handled gracefully, no crash

### 7. `test_websocket_reconnection_after_disconnect` ⏭️ (SKIPPED)
- **Scenario**: Network hiccup or server restart
- **Expected**: UI shows reconnection status, doesn't hang
- **Status**: WebSocket not accessible in test context

### 8. `test_very_long_message_input` ✅
- **Scenario**: User pastes huge text block (10KB+)
- **Expected**: Server handles or rejects gracefully, no crash

## Key Patterns Discovered

### Pattern 1: Console Log Listener (DRY pattern from `test_file_upload_simple_e2e.py`)
**Purpose**: Wait for session to be truly ready before interacting with UI

```python
def check_session(msg):
    nonlocal session_ready
    if "Session ID stored" in msg.text:
        session_ready = True

page.on("console", check_session)

# Wait for session ID to be received and stored
for _ in range(50):  # Wait up to 5 seconds
    if session_ready:
        break
    page.wait_for_timeout(100)
```

**Why**: Blind `page.wait_for_timeout(2000)` is unreliable. Console log listener ensures session is actually ready.

### Pattern 2: Accessing Session ID
**Correct**: `page.evaluate("() => window.bassiClient?.sessionId || null")`
**Wrong**: `page.evaluate("() => window.currentSessionId")`

**Location in code**: `app.js` line 3610 creates `window.bassiClient`

### Pattern 3: Send Button State Management
**Discovery**: Send button is disabled when:
- Not connected to WebSocket
- Input field is empty (when agent is idle)

**Code**: `app.js` lines 1539-1540:
```javascript
if (!this.messageInput.value.trim()) {
    this.sendButton.disabled = true
}
```

**Learning**: This is correct behavior, not a bug. Tests should account for it.

## Iteration Process (Lessons Learned)

### ❌ Mistake 1: Created all 8 tests at once
- **Problem**: 2 tests failed with unclear errors
- **User Feedback**: "write ONE FUCKING TEST AT A TIME, CHECK ITS PATTERNS, improve it, run it, pass it"

### ❌ Mistake 2: Used async/await with Playwright
- **Problem**: E2E tests should use sync API
- **Fix**: `from playwright.sync_api import Page`, removed all `async`/`await`

### ❌ Mistake 3: Blind timeout instead of proper pattern
- **Problem**: Used `page.wait_for_timeout(2000)` instead of console listener
- **Fix**: Applied successful pattern from existing tests

### ✅ Correct Approach:
1. **Analyze existing successful test** (`test_file_upload_simple_e2e.py`)
2. **Extract DRY pattern** (console log listener)
3. **Write ONE test**
4. **Run it**
5. **Debug and fix**
6. **Iterate until passing**
7. **Move to next test**

## Coverage Strategy Alignment

These tests align with `docs/TEST_COVERAGE_STRATEGY.md`:
- **Phase 1, Item 2**: V3 web server edge cases
- **Target**: 70%+ coverage for web_server_v3.py (currently 45%, need 25% more)
- **Focus**: Error handling paths and stability (prevents production issues)

## Next Steps (Future Work)

To reach 70% coverage on web_server_v3.py, still need to test:
- **Session deletion/cleanup** (lines 1082-1247)
- **Complex WebSocket message processing** (lines 1276-1575)
- **Image processing** (`_process_images()` - lines 1577+)
- **Server startup edge cases** (lines 769-1051)

**Recommendation**: Continue ONE TEST AT A TIME approach for remaining coverage.

## Commands Used

```bash
# Run single test (iterate approach)
uv run pytest bassi/core_v3/tests/test_web_server_error_handling_e2e.py::test_websocket_send_during_session_deletion -v

# Run all E2E tests
uv run pytest -m e2e --tb=short

# Check total coverage
./check.sh cov_all
```

## References

- **Main test file**: `bassi/core_v3/tests/test_web_server_error_handling_e2e.py`
- **Pattern source**: `bassi/core_v3/tests/test_file_upload_simple_e2e.py` (lines 112-142)
- **Coverage strategy**: `docs/TEST_COVERAGE_STRATEGY.md`
- **Testing guide**: `CLAUDE_TESTS.md`
