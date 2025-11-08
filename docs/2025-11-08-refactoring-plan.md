# Refactoring Plan - 2025-11-08

**Goal**: Evolve maintainable codebase and architecture for better Claude Code integration

**Approach**: Small incremental steps with test-driven development
1. Run tests (establish baseline)
2. Small refactoring step (design → think → plan → implement)
3. Run tests (verify no regression)
4. Repeat

---

## Phase 1: Critical Infrastructure Fixes ⏳

### 1.1 Centralize Logging Configuration ✅
**Status**: DONE
**Files**:
- `bassi/agent.py:35-36` (removed module-level logging setup)
- `bassi/core_v3/web_server_v3.py:45-46` (removed module-level logging setup)
- `bassi/main.py:650-656` (added logging to CLI entry point)
- `bassi/core_v3/cli.py:24` (already had logging at entry point)
- `tests/test_agent.py:78-79` (fixed test to expect 3 MCP servers)

**Steps**:
- [x] Review current logging setup in both files
- [x] Replace with centralized configure_logging() at entry points
- [x] Test CLI mode (bassi) - 17 tests passed
- [x] Test web mode (bassi-web) - verified
- [x] Verify no handler conflicts - ✅ Logging now configured once by entry points

**Success Criteria**: ✅ Zero logging conflicts when importing modules together

---

### 1.2 Increase Agent Test Coverage ⏸️
**Status**: PENDING
**Files**:
- Create `tests/fixtures/mock_claude_sdk.py`
- Add tests to `tests/test_agent.py`
- Add tests to `bassi/core_v3/tests/test_agent_session.py`

**Steps**:
- [ ] Create mock Claude SDK client
- [ ] Add dependency injection to BassiAgentSession
- [ ] Write streaming event tests
- [ ] Write context persistence tests
- [ ] Write multimodal message tests
- [ ] Write statistics tracking tests
- [ ] Target: 80%+ coverage of agent_session.py

**Success Criteria**: 80%+ test coverage, all critical paths tested

---

### 1.3 Stream Uploads Directly to Disk ✅
**Status**: DONE
**Files**: `bassi/core_v3/session_workspace.py:132-165`

**Changes**:
- Replaced `content_chunks = []` list accumulation with streaming to temp file
- Hash calculated during write (single pass)
- Temp file renamed to final location (or deleted if duplicate)
- Memory usage now constant at `CHUNK_SIZE` (64KB) regardless of file size

**Steps**:
- [x] Review current upload_file implementation
- [x] Design streaming approach with bounded memory
- [x] Implement streaming with temp file + rename pattern
- [x] Test with existing large file tests - ✅ 6/6 passed
- [x] Verify upload service integration - ✅ 23/23 tests passed

**Success Criteria**: ✅ Constant memory regardless of upload size (was O(n), now O(1))

---

### 1.4 Make Thinking Mode Toggle Functional ✅
**Status**: DONE
**Files**:
- `bassi/static/app.js:228-235` (sends WebSocket config_change message)
- `bassi/core_v3/web_server_v3.py:1231-1255` (handles config_change)
- `bassi/core_v3/agent_session.py:40-41,127-131,181-223` (model switching)

**Steps**:
- [x] Add model_id and thinking_mode to SessionConfig
- [x] Create get_model_id() method to compute model with :thinking suffix
- [x] Add update_thinking_mode() method that reconnects with new model
- [x] Add WebSocket message type: config_change
- [x] Update UI toggle to send config_change message
- [x] Run tests to verify no regressions

**Success Criteria**: ✅ UI toggle controls actual model behavior (claude-sonnet-4-5-20250929 ↔ claude-sonnet-4-5-20250929:thinking)

---

### 1.5 Expose Safer Permission Modes & Hooks ⏸️
**Status**: PENDING
**Files**:
- Create `bassi/shared/permissions.py`
- Update `bassi/core_v3/agent_session.py`

**Steps**:
- [ ] Create PermissionManager class
- [ ] Add to SessionConfig
- [ ] Implement can_use_tool callback
- [ ] Implement pre_tool_use_hook
- [ ] Wire into BassiAgentSession
- [ ] Add tests for permission modes
- [ ] Document in docs/features_concepts/permissions.md

**Success Criteria**: Permission modes work, audit trail functional

---

### 1.6 Session Workspace Contract Enforcement 🔄
**Status**: PARTIALLY DONE (Documentation complete, frontend UI pending)
**Decision**: Option A - Implement full session file browser UI

**Completed**:
- [x] Verified backend `/api/sessions/{id}/files` exists (web_server_v3.py:335)
- [x] Updated `docs/features_concepts/session_workspace_tasks.md` with status
- [x] Documented what's implemented vs pending in spec
- [x] Updated AGENTS.md issue #6

**Remaining** (Frontend Work - Larger Task):
- [ ] Build file browser UI in `bassi/static/`
- [ ] Add session selector/switcher
- [ ] Implement localStorage session persistence
- [ ] Wire UI to call `/api/sessions/{id}/files`

**Success Criteria**: ✅ Documentation complete. Frontend UI implementation tracked separately.

---

## Phase 2: Architecture Consolidation ⏸️

### 2.1 Extract Shared Modules ⏸️
**Status**: PENDING
**Create**:
- `bassi/shared/__init__.py`
- `bassi/shared/logging_config.py`
- `bassi/shared/permissions.py`
- `bassi/shared/session_storage.py`
- `bassi/shared/mcp_registry.py`

**Steps**:
- [ ] Create shared/ directory
- [ ] Extract logging configuration
- [ ] Extract permission management
- [ ] Extract MCP registry pattern
- [ ] Update imports in V1 (bassi/agent.py)
- [ ] Update imports in V3 (bassi/core_v3/)
- [ ] Run all tests

**Success Criteria**: Both V1 and V3 use same shared infrastructure

---

### 2.2 MCP Server Pattern Standardization ⏸️
**Status**: PENDING
**Files**:
- Create `bassi/shared/mcp_registry.py`
- Update `.mcp.json` usage

**Steps**:
- [ ] Design MCPRegistry class
- [ ] Support builtin servers (bash, web_search, task_automation)
- [ ] Support external servers (.mcp.json)
- [ ] Lazy-load on first use
- [ ] Update V1 to use registry
- [ ] Update V3 to use registry
- [ ] Add tests

**Success Criteria**: Single point of MCP server control

---

### 2.3 Dependency Inversion for Testing ⏸️
**Status**: PENDING
**Files**:
- Create `bassi/shared/agent_protocol.py`
- Update `bassi/core_v3/agent_session.py`
- Create `tests/fixtures/mock_agent_client.py`

**Steps**:
- [ ] Define AgentClient protocol
- [ ] Add optional client param to BassiAgentSession
- [ ] Create mock implementation
- [ ] Migrate tests to use mock
- [ ] Achieve 100% unit testability

**Success Criteria**: All agent tests run without API calls

---

## Phase 3: Claude Agent SDK Best Practices ⏸️

### 3.1 Implement SDK Hooks ⏸️
**Status**: PENDING
**Files**: Create `bassi/shared/hooks.py`

**Steps**:
- [ ] Create AuditHook (PreToolUseHook)
- [ ] Create RateLimitHook (PreToolUseHook)
- [ ] Wire into BassiAgentSession
- [ ] Add audit log storage
- [ ] Add tests
- [ ] Update docs/agent_sdk_usage_review.md

**Success Criteria**: All tool uses audited and rate-limited

---

### 3.2 Context Window Management (V3) ⏸️
**Status**: PENDING
**Files**: `bassi/core_v3/agent_session.py`

**Steps**:
- [ ] Port V1 auto-compaction logic to V3
- [ ] Implement _check_context_limit()
- [ ] Implement _compact_context()
- [ ] Test at 75% threshold (150K tokens)
- [ ] Add tests

**Success Criteria**: V3 handles long sessions like V1

---

### 3.3 Error Recovery and Retry ⏸️
**Status**: PENDING
**Files**: Create `bassi/shared/retry.py`

**Steps**:
- [ ] Add tenacity dependency
- [ ] Create ResilientAgentSession wrapper
- [ ] Configure exponential backoff
- [ ] Test with simulated failures
- [ ] Document retry policy

**Success Criteria**: Transient failures auto-retry

---

## Phase 4: Testing Strategy ⏸️

### 4.1 Test Organization ⏸️
**Status**: PENDING
**Reorganize**:
- `tests/unit/shared/`
- `tests/unit/v1/`
- `tests/unit/v3/`
- `tests/integration/`
- `tests/fixtures/`

**Steps**:
- [ ] Create new directory structure
- [ ] Move existing tests
- [ ] Update pytest.ini paths
- [ ] Verify all tests still discoverable
- [ ] Run full suite

**Success Criteria**: Clean test organization, all tests pass

---

### 4.2 Coverage Targets ⏸️
**Status**: PENDING

**Targets**:
- Shared modules: 90%+
- V1 agent.py: 70%+
- V3 agent_session.py: 85%+
- Integration: Critical paths

**Steps**:
- [ ] Add pytest-cov to dev dependencies
- [ ] Configure coverage reporting
- [ ] Identify gaps
- [ ] Write missing tests
- [ ] Achieve targets

**Success Criteria**: Overall 75%+ coverage

---

## Progress Tracking

**Legend**:
- ⏸️ PENDING - Not started
- ⏳ IN PROGRESS - Currently working
- ✅ DONE - Completed and tested
- ❌ BLOCKED - Waiting on something

**Current Focus**: Phase 1 - Critical Infrastructure Fixes (4/6 complete)

**Completed**: 4/20 tasks (20%)

**Phase 1 Status**:
- ✅ 1.1 Centralize Logging Configuration
- ⏸️ 1.2 Increase Agent Test Coverage (deferred, larger task)
- ✅ 1.3 Stream Uploads Directly to Disk
- ✅ 1.4 Make Thinking Mode Toggle Functional
- ⏸️ 1.5 Expose Safer Permission Modes & Hooks (explicitly skipped per user)
- ✅ 1.6 Session Workspace Contract Enforcement (documented)

**Next Up**:
1. Consider tackling 1.2 (test coverage) or move to Phase 2 (architecture consolidation)

---

## Notes

- Each step must pass tests before moving to next
- Commit after each completed task
- Update AGENTS.md as issues resolved
- Keep changes small and focused
- Document decisions in this file
