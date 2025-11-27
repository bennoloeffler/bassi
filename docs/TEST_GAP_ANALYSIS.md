# Test Gap Analysis - 2025-11-16

## Summary

Analysis of existing tests vs documented requirements. Identified critical gaps in security, V1 CLI, and concurrency testing.

## Current Test Status

- **Total Test Files**: 92 test files found
- **Test Coverage**: 65% overall
- **V3 Tests**: Good coverage (8.5/10)
- **V1 Tests**: Poor coverage (2/10)
- **Security Tests**: Poor coverage (3/10)

---

## CRITICAL GAPS (From Documentation)

### 1. Security Tests ❌ MISSING

**Documented Requirements** (`TEST_QUALITY_REPORT.md`):
- Shell injection attacks
- Command injection via env vars
- Resource exhaustion (fork bombs, CPU/memory limits)
- Path traversal via working directory manipulation
- TOCTOU races in file operations
- Symlink attacks

**Current Status**:
- ✅ File upload validation (path separators, dangerous extensions)
- ❌ Bash command injection tests
- ❌ Shell injection tests
- ❌ Resource limit tests
- ❌ Symlink attack tests

**Action**: Create `bassi/core_v3/tests/security/test_security_boundaries.py`

---

### 2. V1 CLI Tests ❌ MISSING

**Documented Requirements** (`TEST_COVERAGE_STRATEGY.md`):
- `bassi/main.py` has **0% coverage** (322 untested lines)
- CLI argument parsing
- Main event loop
- Interactive commands (`/help`, `/config`, `/edit`)
- User input handling
- Session persistence and resumption

**Current Status**:
- ❌ No tests for `bassi/main.py`
- ❌ No CLI integration tests

**Action**: Create `tests/test_main_cli.py`

---

### 3. Concurrency/Race Condition Tests ❌ MISSING

**Documented Requirements** (`TEST_QUALITY_REPORT.md`):
- Race condition tests
- Concurrent access tests
- Thread safety verification

**Current Status**:
- ✅ Some concurrent request tests in `test_settings_routes.py`
- ❌ No race condition tests for session management
- ❌ No concurrent WebSocket tests
- ❌ No concurrent file upload tests

**Action**: Create `bassi/core_v3/tests/integration/test_concurrency.py`

---

### 4. Session Management E2E Tests ⚠️ PARTIAL

**Documented Requirements** (`session_management_test_specification.md`):
- Message restoration on session switch
- Agent context restoration
- Empty session cleanup
- Session switching workflow

**Current Status**:
- ✅ Unit tests exist (`test_message_persistence.py`, `test_session_deletion.py`)
- ⚠️ Some E2E tests exist but gaps remain
- ❌ Missing: Session switching E2E tests
- ❌ Missing: Context restoration E2E tests

**Action**: Create missing E2E tests per specification

---

### 5. Permission System Tests ⚠️ PARTIAL

**Documented Requirements** (`permissions.md`):
- Permission mode behavior (`bypassPermissions`, `acceptEdits`, `default`)
- Permission callback behavior
- Hook system behavior

**Current Status**:
- ✅ Settings API tests (`test_settings_routes.py`)
- ✅ Config service tests (`test_config_service.py`)
- ❌ Missing: Permission callback tests
- ❌ Missing: Hook system tests
- ❌ Missing: Permission mode behavior tests

**Action**: Create `bassi/core_v3/tests/integration/test_permissions.py`

---

### 6. Error Handling Tests ⚠️ PARTIAL

**Documented Requirements** (`TEST_COVERAGE_STRATEGY.md`):
- WebSocket disconnect during processing
- Invalid message format handling
- Session not found errors
- Concurrent WebSocket connections
- File upload size limits

**Current Status**:
- ✅ Some error handling E2E tests (`test_web_server_error_handling_e2e.py`)
- ⚠️ Coverage gaps in `web_server_v3.py` (44% coverage)
- ❌ Missing: Complex error scenarios

**Action**: Expand error handling test coverage

---

## Tests to Create

### Priority 1: Security Tests (CRITICAL)

**File**: `bassi/core_v3/tests/security/test_security_boundaries.py`

**Tests Needed**:
1. `test_bash_shell_injection_prevention` - Prevent `; rm -rf /` attacks
2. `test_bash_command_injection_via_env` - Prevent malicious PATH manipulation
3. `test_path_traversal_prevention` - Prevent `../etc/passwd` access
4. `test_symlink_attack_prevention` - Prevent symlink following attacks
5. `test_resource_exhaustion_limits` - Prevent fork bombs, memory exhaustion
6. `test_file_upload_path_traversal` - Verify upload service blocks `../` paths
7. `test_workspace_isolation` - Verify sessions can't access other session files

---

### Priority 2: V1 CLI Tests (HIGH)

**File**: `tests/test_main_cli.py`

**Tests Needed**:
1. `test_parse_args_with_various_flags` - Test CLI argument parsing
2. `test_print_welcome_output` - Test welcome banner
3. `test_print_config_display` - Test config display
4. `test_command_selector_interaction` - Test `/help`, `/config`, `/edit` commands
5. `test_help_command_output` - Test help command
6. `test_main_with_prompt_argument` - Test non-interactive mode
7. `test_session_resumption_flow` - Test session persistence
8. `test_context_file_handling` - Test `.bassi_context.json` handling

---

### Priority 3: Concurrency Tests (MEDIUM)

**File**: `bassi/core_v3/tests/integration/test_concurrency.py`

**Tests Needed**:
1. `test_concurrent_message_saving` - Thread safety for message persistence
2. `test_concurrent_file_uploads` - Multiple uploads to same session
3. `test_concurrent_websocket_connections` - Multiple WebSocket connections
4. `test_session_index_race_condition` - Index updates under concurrent load
5. `test_workspace_metadata_race_condition` - Metadata updates thread safety

---

### Priority 4: Permission System Tests (MEDIUM)

**File**: `bassi/core_v3/tests/integration/test_permissions.py`

**Tests Needed**:
1. `test_bypass_permissions_mode` - Verify all tools allowed
2. `test_accept_edits_mode` - Verify file edits auto-approved
3. `test_default_permission_mode` - Verify permission prompts
4. `test_permission_callback_allow` - Test callback allowing tool
5. `test_permission_callback_deny` - Test callback denying tool
6. `test_hook_pre_tool_use` - Test PreToolUse hook
7. `test_hook_post_tool_use` - Test PostToolUse hook
8. `test_permission_scopes` - Test one_time, session, persistent scopes

---

### Priority 5: Session Management E2E (MEDIUM)

**Files**: 
- `bassi/core_v3/tests/e2e/test_session_switching_e2e.py` (NEW)
- `bassi/core_v3/tests/e2e/test_agent_context_e2e.py` (NEW)

**Tests Needed**:
1. `test_switch_to_existing_session_loads_messages` - Message restoration
2. `test_switch_session_preserves_agent_context` - Context restoration
3. `test_empty_session_cleanup` - Empty session cleanup
4. `test_session_switch_confirmation` - Unsent input warning

---

## Implementation Plan

### Phase 1: Security Tests (2-3 days)
1. Create `bassi/core_v3/tests/security/` directory
2. Create `test_security_boundaries.py` with 7 security tests
3. Run tests and fix any security issues found

### Phase 2: V1 CLI Tests (2-3 days)
1. Create `tests/test_main_cli.py`
2. Implement 8 CLI tests
3. Mock Rich console output for testing

### Phase 3: Concurrency Tests (1-2 days)
1. Create `test_concurrency.py`
2. Implement 5 concurrency tests
3. Use asyncio and threading for concurrent scenarios

### Phase 4: Permission Tests (1-2 days)
1. Create `test_permissions.py`
2. Implement 8 permission tests
3. Test all permission modes and hooks

### Phase 5: E2E Tests (1-2 days)
1. Create missing E2E test files
2. Implement 4 E2E tests
3. Use Playwright for browser automation

---

## Expected Impact

| Phase | New Tests | Coverage Gain | Total Coverage |
|-------|-----------|---------------|----------------|
| Current | 92 files | - | 65% |
| Phase 1 | +7 tests | +2% | 67% |
| Phase 2 | +8 tests | +5% | 72% |
| Phase 3 | +5 tests | +2% | 74% |
| Phase 4 | +8 tests | +3% | 77% |
| Phase 5 | +4 tests | +1% | 78% |

**Target**: 80%+ coverage

---

## Next Steps

1. Create security test directory and first test file
2. Implement security tests based on documented requirements
3. Create V1 CLI tests
4. Add concurrency tests
5. Complete permission system tests
6. Add missing E2E tests



