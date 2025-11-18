# Main.py Coverage Improvement - Session 3

## Overview
Improved test coverage for `bassi/main.py` (V1 CLI entry point).

**Coverage Impact**: 0% → 29% (+29% gain, 106 lines covered)
**Tests Added**: 12 new tests for 6 functions
**All Tests Passing**: 12/12 tests pass ✅

## Context
- **V1 CLI**: Production code serving the `bassi` command
- **Starting Point**: 0% coverage (322 lines untested)
- **Strategy**: Test simple utility functions first, defer complex async/integration functions

## Tests Added

### Test Class 1: TestParseArgs (3 tests)
Tests command-line argument parsing function (lines 221-246).

**Test 1**: `test_parse_args_defaults`
- **Lines Covered**: 221-246 (default values)
- **Purpose**: Verify default argument values with no flags
- **Assertions**: web=False, no_cli=False, port=8765, host="localhost", reload=False

**Test 2**: `test_parse_args_web_flag`
- **Lines Covered**: 226 (--web argument)
- **Purpose**: Verify --web flag enables web UI
- **Pattern**: Mock sys.argv with ["bassi", "--web"]

**Test 3**: `test_parse_args_custom_port_and_host`
- **Lines Covered**: 232-240 (--port and --host arguments)
- **Purpose**: Verify custom port and host values
- **Pattern**: Mock sys.argv with custom values

### Test Class 2: TestPrintWelcome (1 test)
Tests welcome banner printing function (lines 46-68).

**Test**: `test_print_welcome_contains_version`
- **Lines Covered**: 46-68
- **Purpose**: Verify welcome banner contains version, assistant name, directory, endpoint, commands
- **Pattern**: Replace global console with StringIO console, capture output
- **Assertions**: Check for version, "Benno's Assistant", "Working directory:", "/help", "Ctrl+C"

### Test Class 3: TestPrintConfig (1 test)
Tests configuration display function (lines 103-114).

**Test**: `test_print_config_shows_config_values`
- **Lines Covered**: 103-114
- **Purpose**: Verify configuration display shows all config values
- **Pattern**: Mock console, capture output
- **Assertions**: Check for "Configuration", "Config file:", "Root folders:", "Settings:", "Log level:"

### Test Class 4: TestPrintCommands (1 test)
Tests commands display function (lines 119-138).

**Test**: `test_print_commands_lists_all_commands`
- **Lines Covered**: 119-138
- **Purpose**: Verify all available commands are listed
- **Pattern**: Mock console, capture output
- **Assertions**: Check for "Available Commands", "/help", "/config", "/edit", "/reset", "/quit"

### Test Class 5: TestPrintHelp (1 test)
Tests detailed help display function (lines 145-182).

**Test**: `test_print_help_shows_examples`
- **Lines Covered**: 145-182
- **Purpose**: Verify help message shows examples for all use cases
- **Pattern**: Mock console, capture output
- **Assertions**: Check for "Help:", "Available Commands", "Usage Examples", "File Operations:", "Web Search:", "Python Automation:", "Email & Calendar"

### Test Class 6: TestShowCommandSelector (5 tests)
Tests interactive command selector function (lines 187-218).

**Test 1**: `test_show_command_selector_valid_choice`
- **Lines Covered**: 187-218 (happy path)
- **Purpose**: Verify valid numeric input returns correct command
- **Pattern**: Mock Prompt.ask to return "1"
- **Assertions**: Returns valid command (one of: /help, /config, /edit, etc.)

**Test 2**: `test_show_command_selector_empty_input`
- **Lines Covered**: 202-203 (empty input handling)
- **Purpose**: Verify empty input returns None
- **Pattern**: Mock Prompt.ask to return ""

**Test 3**: `test_show_command_selector_invalid_number`
- **Lines Covered**: 207-211 (out-of-range number handling)
- **Purpose**: Verify invalid number (999) returns None
- **Pattern**: Mock Prompt.ask to return "999"

**Test 4**: `test_show_command_selector_non_numeric_input`
- **Lines Covered**: 212-214 (ValueError handling)
- **Purpose**: Verify non-numeric input returns None
- **Pattern**: Mock Prompt.ask to return "not a number"

**Test 5**: `test_show_command_selector_keyboard_interrupt`
- **Lines Covered**: 216-218 (KeyboardInterrupt handling)
- **Purpose**: Verify KeyboardInterrupt is handled gracefully
- **Pattern**: Mock Prompt.ask to raise KeyboardInterrupt

## Technical Patterns Used

### Pattern 1: Mocking sys.argv for CLI Argument Testing
```python
def test_parse_args_defaults(self, monkeypatch):
    from bassi.main import parse_args

    monkeypatch.setattr(sys, "argv", ["bassi"])
    args = parse_args()

    assert args.web is False
    assert args.port == 8765
```

### Pattern 2: Rich Console Mocking with StringIO
```python
from rich.console import Console
from io import StringIO

output = StringIO()
test_console = Console(file=output, force_terminal=False, width=120)

import bassi.main
monkeypatch.setattr(bassi.main, "console", test_console)

# Call function that prints to console
print_welcome()

# Verify output
result = output.getvalue()
assert "bassi v" in result
```

### Pattern 3: Mocking Rich Prompt.ask for Interactive Testing
```python
from rich.prompt import Prompt

# Mock to return specific value
monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "1")

# Mock to raise exception
def mock_ask(*args, **kwargs):
    raise KeyboardInterrupt
monkeypatch.setattr(Prompt, "ask", mock_ask)
```

## Coverage Progress

### Session 3 Timeline
- **Start**: 0% (322 lines untested)
- **After 4 tests**: 12% (276 lines untested)
- **After 6 tests**: 16% (259 lines untested)
- **After 7 tests**: 22% (237 lines untested)
- **After 12 tests**: 29% (216 lines untested)

### Remaining Untested Areas

**Small/Simple** (covered in this session):
- ✅ Lines 221-246: parse_args() - COVERED
- ✅ Lines 46-68: print_welcome() - COVERED
- ✅ Lines 103-114: print_config() - COVERED
- ✅ Lines 119-138: print_commands() - COVERED
- ✅ Lines 145-182: print_help() - COVERED
- ✅ Lines 187-218: show_command_selector() - COVERED

**Complex/Async** (deferred):
- Line 43: `pass` (disabled signal handler) - not testable
- Lines 74-98: get_user_input() - async readline function (24 lines)
- Lines 251-543: cli_main_loop() - main CLI loop (292 lines)
- Lines 548-652: main_async() - async entry point (104 lines)
- Lines 658-671: main() - entry point (13 lines)

## Workflow Used (ONE TEST AT A TIME)

1. **Pick specific function** to test
2. **Write ONE test** using established patterns
3. **Run test individually** to verify it passes
4. **Mark completed in todo list**
5. **Check coverage progress**
6. **Move to next test**

**Key**: NEVER batch create tests. Write, run, verify, iterate.

## Test Execution

### Run All Tests
```bash
uv run pytest tests/test_main.py -v
# 12 tests pass in ~0.03 seconds
```

### Run Single Test
```bash
uv run pytest tests/test_main.py::TestParseArgs::test_parse_args_defaults -v
```

### Check Coverage
```bash
uv run pytest tests/test_main.py --cov=bassi --cov-report=term | grep main.py
```

## Next Steps (Future Work)

To reach 70%+ coverage on main.py, need to test the complex async/integration functions:

### Phase 4: Async Input Function (1-2 tests, +3-5% coverage)
- Lines 74-98: get_user_input() - async readline with history
- Requires mocking: readline module, anyio.to_thread.run_sync

### Phase 5: Main Loop (Integration tests, +15-20% coverage)
- Lines 251-543: cli_main_loop() - 292 lines
- Requires: MockAgentClient, session state, command handling
- Complex: Multiple command paths, error handling, interruption

### Phase 6: Entry Points (Integration tests, +5-10% coverage)
- Lines 548-652: main_async() - async entry point
- Lines 658-671: main() - CLI entry point
- Requires: Full integration setup, process management

**Strategy**: Focus on integration tests with MockAgentClient for remaining functions.

## References

- **Main test file**: `tests/test_main.py` (355 lines, 12 tests)
- **Code under test**: `bassi/main.py` (322 lines)
- **Coverage strategy**: `docs/TEST_COVERAGE_STRATEGY.md`
- **Testing guide**: `CLAUDE_TESTS.md`
- **Session 2 summary**: `docs/WEB_SERVER_V3_COVERAGE_SESSION_2.md`

## Commands Reference

```bash
# Run all main.py tests
uv run pytest tests/test_main.py -v

# Run single test with verbose output
uv run pytest tests/test_main.py::TestParseArgs::test_parse_args_defaults -v

# Check coverage for main.py
uv run pytest tests/test_main.py --cov=bassi --cov-report=term | grep main.py

# Full quality check (format, lint, type, test)
./check.sh

# Coverage for all tests
./check.sh cov_all
```
