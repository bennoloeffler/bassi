# Test Coverage Improvement Strategy

## Current State (cov_all)
- **Total Coverage**: 65% (2618 statements, 838 missed)
- **Target**: 80%+ coverage for production code

## Priority Analysis

### 🔴 CRITICAL (0-50% coverage, high risk)

#### 1. `bassi/main.py` - **0% coverage** (322 untested lines)
**Impact**: HIGHEST - This is the V1 CLI entry point (production code)

**What's untested**:
- CLI argument parsing (`parse_args()`)
- Main event loop (`main_async()`, `cli_main_loop()`)
- Interactive commands (`/help`, `/config`, `/edit`, etc.)
- User input handling (`get_user_input()`)
- Session persistence and resumption
- Rich console integration

**Testing Strategy**:
```python
# Tests needed:
tests/test_main_cli.py:
  - test_parse_args_with_various_flags
  - test_print_welcome_output
  - test_print_config_display
  - test_command_selector_interaction
  - test_help_command_output
  - test_main_with_prompt_argument
  - test_session_resumption_flow
  - test_context_file_handling
```

**Effort**: Medium (2-3 days)
**ROI**: Very High - Catches CLI bugs before production

---

#### 2. `bassi/core_v3/web_server_v3.py` - **44% coverage** (322 untested lines)
**Impact**: HIGH - Main V3 web server (experimental but critical)

**What's tested** (44%):
- Basic WebSocket connection ✅
- Session creation/listing ✅
- File upload endpoints ✅

**What's untested** (missing lines: 769-1051, 1082-1247, 1276-1575):
- Error handling paths (lines 769-1051)
- Session deletion/cleanup (lines 1082-1247)
- Complex WebSocket message processing (lines 1276-1575)
- Image processing (`_process_images()` - lines 1577+)
- Server startup edge cases

**Testing Strategy**:
```python
# Tests needed (add to bassi/core_v3/tests/):
test_web_server_error_handling.py:
  - test_websocket_disconnect_during_processing
  - test_invalid_message_format_handling
  - test_session_not_found_error
  - test_concurrent_websocket_connections
  - test_file_upload_size_limits

test_web_server_session_management.py:
  - test_delete_active_session
  - test_switch_session_during_execution
  - test_session_cleanup_on_disconnect

test_web_server_image_processing.py:
  - test_process_images_from_content_blocks
  - test_image_base64_decoding
  - test_image_format_validation
```

**Effort**: High (3-4 days)
**ROI**: High - Prevents production issues in V3

---

### 🟡 MEDIUM (50-80% coverage, moderate risk)

#### 3. `bassi/agent.py` - **59% coverage** (138 untested lines)
**Impact**: MEDIUM - Core V1 agent logic

**What's tested** (59%):
- Basic agent initialization ✅
- Message handling ✅
- Tool execution ✅

**What's untested** (missing lines: 491-578, 588-808, 836-915):
- Error recovery logic (lines 491-578)
- Context compaction (lines 588-808)
- Verbose mode handling (lines 836-915)
- Keyboard interrupt handling

**Testing Strategy**:
```python
# Tests needed (add to tests/):
test_agent_error_recovery.py:
  - test_agent_handles_api_errors
  - test_agent_recovers_from_tool_failures
  - test_agent_handles_interrupted_execution

test_agent_context_management.py:
  - test_context_auto_compaction_at_threshold
  - test_context_preserves_important_messages
  - test_context_size_calculation

test_agent_verbose_mode.py:
  - test_verbose_mode_shows_all_tool_calls
  - test_verbose_toggle_during_execution
```

**Effort**: Medium (2-3 days)
**ROI**: Medium - Improves reliability of core features

---

#### 4. `bassi/config.py` - **78% coverage** (9 untested lines)
**Impact**: LOW - Configuration management

**What's untested** (missing lines: 84-85, 95, 115-119, 129-131):
- Edge cases in config file parsing
- Environment variable fallbacks
- Default value handling

**Testing Strategy**:
```python
# Tests needed:
test_config_edge_cases.py:
  - test_missing_config_file_uses_defaults
  - test_invalid_config_format_handling
  - test_environment_override_precedence
```

**Effort**: Low (1 day)
**ROI**: Low - But completes config coverage

---

### 🟢 GOOD (80%+ coverage, low risk)

These files have excellent coverage and are low priority:
- `bassi/core_v3/agent_session.py` - 99% ✅
- `bassi/core_v3/session_workspace.py` - 98% ✅
- `bassi/core_v3/upload_service.py` - 99% ✅
- `bassi/shared/mcp_registry.py` - 100% ✅
- `bassi/shared/permission_config.py` - 100% ✅

---

## Recommended Implementation Order

### Phase 1: Critical Production Code (Week 1-2)
1. **bassi/main.py** - CLI entry point tests
   - Test CLI argument parsing
   - Test interactive command loop
   - Test session persistence
   - **Target**: 70%+ coverage

2. **bassi/core_v3/web_server_v3.py** - Web server edge cases
   - Test error handling paths
   - Test session management edge cases
   - **Target**: 70%+ coverage

### Phase 2: Core Logic (Week 3)
3. **bassi/agent.py** - Agent error recovery
   - Test error handling
   - Test context management
   - **Target**: 75%+ coverage

### Phase 3: Cleanup (Week 4)
4. **bassi/config.py** - Config edge cases
   - Complete config coverage
   - **Target**: 90%+ coverage

---

## Expected Outcomes

| Phase | New Tests | Coverage Gain | Total Coverage |
|-------|-----------|---------------|----------------|
| Current | 52 tests | - | 65% |
| Phase 1 | +25 tests | +10% | 75% |
| Phase 2 | +15 tests | +5% | 80% |
| Phase 3 | +5 tests | +2% | 82% |

---

## Quick Wins (Can do immediately)

1. **bassi/shared/sdk_types.py** - 56% coverage (only 7 lines)
   - Add 2-3 simple unit tests
   - Get to 100% in 30 minutes

2. **bassi/mcp_servers/task_automation_server.py** - 98% coverage (2 lines missed)
   - Add edge case test
   - Get to 100% in 1 hour

3. **bassi/core_v3/session_index.py** - 86% coverage (15 lines missed)
   - Add error handling tests
   - Get to 95% in 2 hours

---

## Maintenance Strategy

Going forward:
1. **No new code < 80% coverage** - Enforce in CI
2. **Test-driven development** - Write tests first (see CLAUDE_TESTS.md)
3. **Monitor trends** - Run `./check.sh cov_all` before each commit
4. **Target 85% overall coverage** - Industry standard for production code

---

## Commands to Track Progress

```bash
# Check current coverage
./check.sh cov_all

# Check specific file coverage
uv run pytest --cov=bassi/main.py --cov-report=term-missing

# Generate HTML coverage report
uv run pytest --cov=bassi --cov-report=html
# Open htmlcov/index.html in browser
```
