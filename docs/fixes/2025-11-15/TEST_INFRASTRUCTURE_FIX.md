# Test Infrastructure Fix Plan

**Date**: 2025-11-08
**Goal**: Make all tests stable and runnable individually and via `./check.sh`

---

## Problem Analysis

### 1. Event Loop Conflicts (21 tests)
**Error**: `RuntimeWarning: Cannot run the event loop while another loop is running`

**Root Cause**: FastAPI `TestClient` uses synchronous `asyncio.Runner.run()` which conflicts with pytest-asyncio's event loop.

**Affected Files**:
- `bassi/core_v3/tests/test_interactive_questions.py` (6 tests)
- `bassi/core_v3/tests/test_session_workspace.py` (8 tests)
- `bassi/core_v3/tests/test_upload_service.py` (7 tests)

**Solution**: Replace `TestClient` with `httpx.AsyncClient` for async tests

### 2. Playwright E2E Tests (6 tests)
**Problem**: Some tests pass (using fixture), others fail (missing server setup)

**Affected Files**:
- `bassi/core_v3/tests/test_web_ui_file_upload_e2e.py` (6 failed)
- `bassi/core_v3/tests/test_file_upload_simple_e2e.py` (all passed ✅)

**Solution**: Ensure all Playwright tests use the same server fixture pattern

### 3. Other Failures
- `tests/test_key_bindings.py`: pexpect "Operation not permitted" - OS-level issue, not test infrastructure
- `tests/test_task_automation_integration.py`: Needs investigation
- `tests/test_use_cases.py`: Needs investigation

---

## Implementation Strategy

### Phase 1: Fix Event Loop Conflicts (High Priority)
1. Create async HTTP client fixture using `httpx.AsyncClient`
2. Update all TestClient usages to AsyncClient
3. Ensure proper cleanup in fixtures

### Phase 2: Standardize Playwright Infrastructure (Medium Priority)
1. Verify server fixture is working correctly
2. Ensure all E2E tests use the fixture consistently
3. Add wait-for-server logic if missing

### Phase 3: Fix Remaining Tests (Low Priority)
1. Investigate task automation test failure
2. Investigate use cases test failures
3. Document pexpect OS permission issues (not fixable in tests)

---

## Success Criteria

- ✅ All tests run individually without errors
- ✅ `./check.sh` completes successfully
- ✅ No event loop conflicts
- ✅ All Playwright tests pass with proper server infrastructure
- ✅ Test suite is stable and reliable
