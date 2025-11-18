# Web Server V3 Coverage Improvement - Session 2

## Overview
Continued improving test coverage for `bassi/core_v3/web_server_v3.py` (V3 web server).

**Coverage Impact**: 45% → 48% (+3% gain, 19 lines covered)
**Tests Added**: 9 new integration tests
**All Tests Passing**: 28/28 tests pass ✅

## Tests Added

### Test 1: `test_upload_file_success_returns_file_info`
- **Lines Covered**: 310-319 (file upload success path)
- **Purpose**: Test happy path - successful file upload returns file info
- **Key Pattern**: Handle random filename suffix added by upload service
- **Assertion Fix**: Changed from exact match to pattern match (startswith/endswith)

### Test 2: `test_upload_file_too_large_returns_413`
- **Lines Covered**: 321-326 (FileTooLargeError handling)
- **Purpose**: Test file size limit enforcement
- **HTTP Status**: 413 Payload Too Large
- **Pattern**: Monkeypatch upload_service.upload_to_session to raise FileTooLargeError

### Test 3: `test_upload_invalid_filename_returns_400`
- **Lines Covered**: 328-333 (InvalidFilenameError handling)
- **Purpose**: Test path traversal protection
- **HTTP Status**: 400 Bad Request
- **Pattern**: Mock upload to raise InvalidFilenameError with malicious filename

### Test 4: `test_upload_generic_error_returns_500`
- **Lines Covered**: 335-340 (generic exception handling)
- **Purpose**: Test unexpected upload errors
- **HTTP Status**: 500 Internal Server Error
- **Pattern**: Mock upload to raise RuntimeError (disk I/O error)

### Test 5: `test_list_sessions_sorts_by_created_at`
- **Lines Covered**: 371-374 (created_at sorting)
- **Purpose**: Test session list sorting by creation timestamp
- **Both Orders**: Ascending (oldest first) and descending (newest first)
- **Pattern**: Direct manipulation of session_index.index

### Test 6: `test_list_sessions_sorts_by_last_activity`
- **Lines Covered**: 376-379 (last_activity sorting)
- **Purpose**: Test session list sorting by activity timestamp
- **Both Orders**: Ascending (least recent) and descending (most recent)

### Test 7: `test_list_sessions_error_handling`
- **Lines Covered**: 399-404 (list sessions error handling)
- **Purpose**: Test error handling when session index fails
- **HTTP Status**: 500 Internal Server Error
- **Pattern**: Monkeypatch session_index.index property to raise exception

### Test 8: `test_capabilities_endpoint_error_handling`
- **Lines Covered**: 273-277 (capabilities endpoint error handling)
- **Purpose**: Test error handling in GET /api/capabilities
- **HTTP Status**: 500 Internal Server Error
- **Pattern**: Mock BassiDiscovery in bassi.core_v3.discovery module
- **Key Learning**: Mock imports at source module, not usage module

### Test 9: `test_get_session_error_handling`
- **Lines Covered**: 435-440 (get_session endpoint error handling)
- **Purpose**: Test error handling in GET /api/sessions/{session_id}
- **HTTP Status**: 500 Internal Server Error
- **Pattern**: Monkeypatch workspace.get_stats() to raise exception

## Technical Patterns Used

### Pattern 1: FastAPI TestClient
```python
response = test_client.get("/api/sessions")
assert response.status_code == 200
data = response.json()
```
- REST endpoint testing without starting actual server
- Clean HTTP request/response testing

### Pattern 2: Monkeypatch for Exception Injection
```python
def mock_function():
    raise RuntimeError("Simulated error")

monkeypatch.setattr(service, "method", mock_function)
```
- Trigger specific error conditions
- Test error handling paths

### Pattern 3: Workspace Creation
```python
from bassi.core_v3.session_workspace import SessionWorkspace

workspace = SessionWorkspace(session_id, base_path=tmp_path, create=True)
web_server.workspaces[session_id] = workspace
```
- Create isolated test workspaces
- Clean separation between tests

### Pattern 4: Module-Level Mocking
```python
import bassi.core_v3.discovery
monkeypatch.setattr(bassi.core_v3.discovery, "BassiDiscovery", MockClass)
```
- Mock classes imported inside functions
- Mock at source module, not usage site

## Key Learning: Import Mocking

When a class is imported inside a function:
```python
async def get_capabilities():
    try:
        from bassi.core_v3.discovery import BassiDiscovery
        discovery = BassiDiscovery()
```

**Mock at source**: `bassi.core_v3.discovery.BassiDiscovery` ✅
**Not at usage**: `bassi.core_v3.web_server_v3.BassiDiscovery` ❌

## Coverage Progress

### Starting Point (Session 1)
- **Coverage**: 45% (316 lines untested)
- **Tests**: 19 existing tests

### Current State (Session 2)
- **Coverage**: 48% (297 lines untested)
- **Tests**: 28 total tests (9 new)
- **Improvement**: +3% coverage, ~19 lines covered

### Remaining Untested Areas

**Small/Manageable** (next targets):
- Lines 120-132: Session initialization edge cases
- Lines 257-258: WebSocket connection edge cases
- Lines 744-754: Session management edge cases

**Medium** (require more setup):
- Lines 1256-1264: WebSocket message handling
- Lines 1276-1316: Tool call processing
- Lines 1325-1337: Question handling

**Large** (save for later):
- Lines 769-1051: Help message generation (283 lines)
- Lines 1082-1247: Session deletion/cleanup (166 lines)
- Lines 1346-1499: Complex WebSocket processing (154 lines)

## Test Execution

### Run All Tests
```bash
uv run pytest bassi/core_v3/tests/test_web_server_v3.py -v
# 28 tests pass in ~4.8 seconds
```

### Run Single Test
```bash
uv run pytest bassi/core_v3/tests/test_web_server_v3.py::test_upload_file_success_returns_file_info -v
```

### Check Coverage
```bash
uv run pytest bassi/core_v3/tests/ --cov=bassi/core_v3 --cov-report=term | grep web_server_v3
```

## Workflow Used (ONE TEST AT A TIME)

1. **Pick specific line range** (e.g., lines 321-326)
2. **Examine code** to understand what needs testing
3. **Write ONE test** using established patterns
4. **Run test individually** to verify it passes
5. **Fix if needed** (e.g., filename suffix issue)
6. **Mark completed in todo list**
7. **Move to next test**

**Key**: NEVER batch create tests. Write, run, verify, iterate.

## Next Steps (Future Work)

To reach 70%+ coverage on web_server_v3.py:

### Phase 3: Small Edge Cases (2-3 tests, +2-3% coverage)
1. Lines 120-132: Session initialization edge cases
2. Lines 257-258: WebSocket connection edge cases
3. Lines 744-754: Session management edge cases

### Phase 4: Medium WebSocket Paths (5-7 tests, +5-7% coverage)
1. Lines 1256-1264: WebSocket message handling
2. Lines 1276-1316: Tool call processing
3. Lines 1325-1337: Question handling

### Phase 5: Large Complex Areas (Later)
- Lines 769-1051: Help message generation
- Lines 1082-1247: Session deletion/cleanup
- Lines 1346-1499: Complex WebSocket processing

**Strategy**: Continue ONE TEST AT A TIME approach for all future work.

## References

- **Test Coverage Strategy**: `docs/TEST_COVERAGE_STRATEGY.md`
- **Testing Guide**: `CLAUDE_TESTS.md`
- **Session 1 Summary**: `docs/E2E_ERROR_HANDLING_TESTS_SUMMARY.md`
- **Main test file**: `bassi/core_v3/tests/test_web_server_v3.py` (788 lines, 28 tests)
- **Code under test**: `bassi/core_v3/web_server_v3.py` (611 lines)

## Commands Reference

```bash
# Run all V3 tests with coverage
uv run pytest bassi/core_v3/tests/ --cov=bassi/core_v3 --cov-report=term

# Run web server tests only
uv run pytest bassi/core_v3/tests/test_web_server_v3.py -v

# Run single test with verbose output
uv run pytest bassi/core_v3/tests/test_web_server_v3.py::test_name -v

# Full quality check (format, lint, type, test)
./check.sh

# Coverage for all tests
./check.sh cov_all
```
