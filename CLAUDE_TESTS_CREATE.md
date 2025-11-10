# Automated Test Creation System

This document describes the multi-agent parallel testing system for automatically creating comprehensive test coverage.

## Overview

The system uses **parallel test-writer agents** to create tests simultaneously, then **merges them intelligently** into the final test file. This approach is 5-10x faster than writing tests sequentially.

**Key Benefits:**
- ✅ **Parallel execution** - N agents write N tests simultaneously
- ✅ **No conflicts** - Each agent works on isolated temp file
- ✅ **Intelligent merging** - Automatic conflict resolution
- ✅ **Quality enforcement** - Each test must pass before completion
- ✅ **Coverage verification** - Tracks improvement automatically

## Architecture

```
User: /bel-write-tests-one-by-one bassi/module.py
    ↓
Skill: bel-create-tests-one-by-one
    ↓
Spawn N parallel agents (test-writer-agent-ONLY-ONE)
    ├─ AGENT_01 → tests/test_module_AGENT_01.py
    ├─ AGENT_02 → tests/test_module_AGENT_02.py
    └─ AGENT_03 → tests/test_module_AGENT_03.py
    ↓
Wait for all agents to complete
    ↓
Collector agent (test-collector-agent-MANY)
    ↓
Merge into tests/test_module.py
    ↓
Validate, cleanup, report
```

## Components

### 1. Command: `/bel-write-tests-one-by-one`

**Location:** `.claude/commands/bel-write-tests-one-by-one.md`

**Usage:**
```bash
/bel-write-tests-one-by-one <source_file> [num_agents] [test_types] [focus_areas]
```

**Examples:**
```bash
# Basic - 3 agents, unit + integration tests
/bel-write-tests-one-by-one bassi/core_v3/agent_session.py

# Advanced - 5 agents, only unit tests, focused areas
/bel-write-tests-one-by-one bassi/shared/permission_config.py 5 unit "error handling,edge cases"

# E2E tests - 4 agents, browser-based tests
/bel-write-tests-one-by-one bassi/core_v3/web_server_v3.py 4 e2e "WebSocket errors,file upload"
```

**Parameters:**
- `source_file` (required): File to test
- `num_agents` (optional, default: 3, max: 10): Number of parallel writers
- `test_types` (optional, default: "unit,integration"): Comma-separated test types
- `focus_areas` (optional): Specific areas to focus on

**Note:** After creating this command file, you must **restart Claude Code** for it to appear in autocomplete.

### 2. Skill: `bel-create-tests-one-by-one`

**Location:** `.claude/skills/bel-create-tests-one-by-one.md`

**Purpose:** Orchestrates the parallel test-writing workflow.

**Workflow Steps:**

1. **Analyze Source File**
   - Run coverage to identify gaps
   - Count functions/classes to test
   - Determine optimal number of tests needed

2. **Determine Strategy**
   - Calculate target: aim for 80%+ coverage
   - Decide test types (unit vs integration vs e2e)
   - Choose number of parallel agents

3. **Spawn Parallel Test-Writer Agents**
   - Launch N instances of `test-writer-agent-ONLY-ONE`
   - Each gets unique `AGENT_ID` (01, 02, 03...)
   - Each writes to isolated temp file

4. **Monitor Progress**
   - Poll for `STATUS: COMPLETE` markers
   - Timeout: 10 minutes per agent

5. **Spawn Collector Agent**
   - Launch `test-collector-agent-MANY`
   - Merge all temp files intelligently
   - Resolve conflicts automatically

6. **Final Verification**
   - Run merged tests: `pytest <test_file> -v`
   - Check coverage improvement
   - Verify temp files cleaned up

**Example Output:**
```
✓ Source: bassi/core_v3/message_converter.py (240 lines)
✓ Current coverage: 79%
✓ Strategy: 5 unit tests needed

→ Spawning 5 parallel agents...
✓ All 5 agents completed in 5 minutes

✓ Merging into tests/test_message_converter.py
✓ Final: 29 tests (24 existing + 5 new)
✓ Coverage: 79% → 100% (+21%)
✓ Execution time: 6 minutes (vs ~30 minutes serial)
```

### 3. Agent: `test-writer-agent-ONLY-ONE`

**Location:** `.claude/agents/test-writer-agent-ONLY-ONE.md`

**Purpose:** Write ONE high-quality test and iterate until perfect.

**Process:**

1. **Read Testing Docs**
   - `CLAUDE_TESTS.md` (MUST READ - comprehensive guide)
   - Example tests in `tests/` and `bassi/core_v3/tests/`

2. **Understand Context**
   - Read source file to understand functionality
   - Check existing tests to avoid duplicates
   - Identify `AGENT_ID` from environment variable

3. **Write ONE Test**
   - Create test in temp file: `test_module_AGENT_XX.py`
   - Focus on ONE specific scenario
   - Use appropriate pattern for test type

4. **Execute and Iterate**
   - Run: `uv run pytest <temp_file> -v`
   - Fix failures
   - Check coverage contribution
   - Repeat until passing

5. **Document Completion**
   - Add completion marker:
     ```python
     # AGENT_ID: 01
     # STATUS: COMPLETE
     # COVERAGE: Added test for input validation edge case
     # TEST_TYPE: unit
     # SOURCE: bassi/module.py:45-52
     ```

**Test Type Patterns:**

**Unit Test (fast, mocked):**
```python
def test_function_validates_input():
    """Should raise ValueError for invalid input."""
    with pytest.raises(ValueError, match="Invalid"):
        validate_user_input("")
```

**Integration Test (real API):**
```python
@pytest.mark.integration
async def test_real_agent_connection():
    """Should connect to real Claude API."""
    agent = AgentSession(config)
    await agent.start()
```

**E2E Test (browser):**
```python
@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
def test_user_can_upload_file(page, live_server):
    """Should allow user to upload file via UI."""
    page.goto(live_server)
    page.set_input_files("#file-input", "test.txt")
```

**Environment Variables:**
- `TEST_AGENT_ID`: Unique ID ("01", "02", "03"...)
- `TEST_SOURCE_FILE`: Source file being tested
- `TEST_TARGET_FILE`: Final test file
- `TEST_TEMP_FILE`: Agent's temp file

**Critical Rules:**
- ✅ **ONLY work on YOUR temp file** (`test_module_AGENT_XX.py`)
- ❌ **NEVER touch other agent files** or original test file
- ✅ **Write meaningful tests** - prevent real bugs
- ✅ **Cover unhappy paths** - errors, edge cases, race conditions

### 4. Agent: `test-collector-agent-MANY`

**Location:** `.claude/agents/test-collector-agent-MANY.md`

**Purpose:** Merge all parallel test files into final test file.

**Process:**

1. **Discover Temp Files**
   - Find all `test_module_AGENT_*.py` files
   - Example: `test_logging_AGENT_01.py`, `test_logging_AGENT_02.py`...

2. **Verify Completion**
   - Check each file has `STATUS: COMPLETE`
   - If any incomplete, STOP and report error

3. **Parse All Files**
   - Extract imports
   - Parse test classes and functions
   - Parse fixtures
   - Parse module-level config (pytestmark)

4. **Intelligent Merge**

   **Imports:**
   - Consolidate and deduplicate
   - Sort: stdlib → third-party → local

   **Test Organization:**
   - Group by type: unit → integration → e2e
   - Within groups: organize by functionality

   **Conflict Resolution:**

   Duplicate test names:
   ```python
   # BEFORE:
   test_validation()  # AGENT_01
   test_validation()  # AGENT_02

   # AFTER:
   test_validation_empty_input()  # AGENT_01
   test_validation_null_input()   # AGENT_02
   ```

   Duplicate fixtures:
   ```python
   # If identical: keep one
   # If different: rename to make specific
   @pytest.fixture
   def mock_client_v1():  # From AGENT_01
       ...

   @pytest.fixture
   def mock_client_v2():  # From AGENT_02
       ...
   ```

5. **Validate Merged File**
   - Run: `uv run pytest <target_file> -v`
   - If failures, fix conflicts and retry
   - Must pass before cleanup

6. **Cleanup**
   - Delete all temp files: `rm test_module_AGENT_*.py`
   - Only after validation passes

7. **Report Summary**
   ```markdown
   ## Test Merge Summary

   **Target:** tests/test_logging.py
   **Agents:** 3 (AGENT_01, AGENT_02, AGENT_03)
   **Tests Added:** 8

   **AGENT_01:**
   - test_logging_validates_level() - unit
   - Coverage: Input validation edge cases

   **AGENT_02:**
   - test_logging_file_rotation() - unit
   - Coverage: File rotation race condition

   **AGENT_03:**
   - test_logging_performance() - integration
   - Coverage: High-volume logging

   ✓ All 8 tests passing
   ✓ Coverage: 65% → 80% (+15%)
   ✓ Temp files cleaned up
   ```

**Environment Variables:**
- `TEST_TARGET_FILE`: Final test file
- `TEST_TEMP_PATTERN`: Pattern for temp files
- `TEST_SOURCE_FILE`: Source file (for verification)

**Quality Checks:**
- ✅ All temp files have `STATUS: COMPLETE`
- ✅ No duplicate test names in final file
- ✅ Imports clean and organized
- ✅ Tests grouped logically
- ✅ All tests pass: `pytest <target> -v`
- ✅ Coverage verified
- ✅ Temp files deleted
- ✅ Summary report generated

## Usage Examples

### Example 1: Improve Coverage for agent_session.py

```bash
/bel-write-tests-one-by-one bassi/core_v3/agent_session.py
```

**What happens:**
1. Skill analyzes file: 275 lines, 99% coverage, need 1-2 edge case tests
2. Spawns 2 parallel agents
3. Each writes one test:
   - AGENT_01: Test cleanup during active query (race condition)
   - AGENT_02: Test interrupt during streaming (edge case)
4. Collector merges both tests
5. Final: 99% → 100% coverage

**Time:** ~3 minutes (vs ~10 minutes manual)

### Example 2: Create E2E Tests for Web Server

```bash
/bel-write-tests-one-by-one bassi/core_v3/web_server_v3.py 4 e2e "error handling,race conditions"
```

**What happens:**
1. Skill identifies 31% coverage, needs E2E tests
2. Spawns 4 parallel agents focused on:
   - AGENT_01: WebSocket disconnect during processing
   - AGENT_02: Invalid message format handling
   - AGENT_03: Session deletion race condition
   - AGENT_04: Multiple rapid messages stability
3. Each agent writes browser-based E2E test
4. Collector merges with proper `@pytest.mark.e2e` markers
5. Final: 31% → 45% coverage (E2E tests added)

**Time:** ~8 minutes (vs ~40 minutes manual)

### Example 3: Unit Tests for New Module

```bash
/bel-write-tests-one-by-one bassi/shared/permission_config.py 5 unit
```

**What happens:**
1. Skill identifies 100% coverage needed (new file)
2. Spawns 5 parallel agents
3. Each writes comprehensive unit test:
   - AGENT_01: Test permission validation
   - AGENT_02: Test edge cases (empty/null)
   - AGENT_03: Test error handling
   - AGENT_04: Test permission combinations
   - AGENT_05: Test config parsing
4. Collector creates new test file with all tests
5. Final: 0% → 95% coverage

**Time:** ~5 minutes (vs ~30 minutes manual)

## Best Practices

### When to Use Parallel Agents

**Good Use Cases:**
- ✅ Module needs multiple tests (3+ tests)
- ✅ Want to save time (5-10x speedup)
- ✅ Need diverse test coverage (unit + integration + e2e)
- ✅ Complex module with many edge cases

**Bad Use Cases:**
- ❌ Only need 1-2 simple tests (overhead not worth it)
- ❌ Very small module (<50 lines)
- ❌ Tests require heavy coordination (shared fixtures)

### Choosing Number of Agents

**Rule of Thumb:**
- Small module (<100 lines): 2-3 agents
- Medium module (100-300 lines): 3-5 agents
- Large module (300+ lines): 5-10 agents

**Example:**
```bash
# Small module - 2 agents
/bel-write-tests-one-by-one bassi/shared/sdk_loader.py 2

# Medium module - 4 agents
/bel-write-tests-one-by-one bassi/core_v3/agent_session.py 4

# Large module - 8 agents
/bel-write-tests-one-by-one bassi/main.py 8
```

### Test Type Selection

**Unit Tests (default):**
- Fast execution
- No external dependencies
- Use MockAgentClient
- Good for: logic, validation, edge cases

**Integration Tests:**
- Real API calls
- Require API keys
- Mark with `@pytest.mark.integration`
- Good for: end-to-end workflows, real data

**E2E Tests:**
- Browser-based (Playwright)
- Sequential execution required
- Mark with `@pytest.mark.e2e` + `@pytest.mark.xdist_group(name="e2e_server")`
- Good for: UI workflows, user scenarios

**Example:**
```bash
# Only unit tests (fast, no API keys)
/bel-write-tests-one-by-one bassi/core_v3/tools.py 3 unit

# Unit + integration (comprehensive)
/bel-write-tests-one-by-one bassi/core_v3/agent_session.py 5 "unit,integration"

# Only E2E (browser tests)
/bel-write-tests-one-by-one bassi/core_v3/web_server_v3.py 4 e2e
```

### Focus Areas

Guide agents to specific areas needing coverage:

```bash
# Focus on specific concerns
/bel-write-tests-one-by-one bassi/module.py 4 unit "error handling,edge cases"

# Focus on specific functionality
/bel-write-tests-one-by-one bassi/module.py 5 unit "validation,race conditions,performance"

# Focus on user scenarios
/bel-write-tests-one-by-one bassi/web_server.py 6 e2e "file upload,WebSocket errors,session management"
```

## Monitoring and Debugging

### Watching Agent Progress

Agents create temp files as they work:

```bash
# Check which agents are working
ls tests/test_*_AGENT_*.py

# Check completion status
grep "STATUS:" tests/test_module_AGENT_*.py
```

**Expected patterns:**
```
tests/test_logging_AGENT_01.py  # Working or complete
tests/test_logging_AGENT_02.py  # Working or complete
tests/test_logging_AGENT_03.py  # Working or complete
```

### Debugging Agent Failures

If agent fails to complete:

```bash
# 1. Check the temp file for errors
cat tests/test_module_AGENT_02.py

# 2. Try running the test manually
uv run pytest tests/test_module_AGENT_02.py -v

# 3. Check for syntax errors
python -m py_compile tests/test_module_AGENT_02.py
```

### Common Issues

**Issue: Agent times out (10 minutes)**
- **Cause:** Test is too complex or failing repeatedly
- **Fix:** Check temp file, simplify test scope, or reduce num_agents

**Issue: Collector reports incomplete agents**
- **Cause:** Agent crashed or didn't mark STATUS: COMPLETE
- **Fix:** Check temp files, relaunch specific agent

**Issue: Merged tests fail**
- **Cause:** Naming conflicts, import issues, or fixture problems
- **Fix:** Collector should auto-fix; if not, check temp files for conflicts

**Issue: Coverage didn't improve**
- **Cause:** Tests don't execute relevant code paths
- **Fix:** Review focus_areas, ensure tests target missing coverage

## Technical Details

### Parallel Safety

**No Conflicts Possible:**
- Each agent has **exclusive file access**
- Pattern: `test_module_AGENT_01.py` (AGENT_01 only)
- Original file (`test_module.py`) never touched until merge
- No race conditions, no file locks needed

### Test Diversity

Agents avoid duplicate tests by:
- Reading existing tests before writing
- Checking other AGENT_* files for duplicates
- Receiving unique AGENT_ID to differentiate
- Focusing on different scenarios

### Quality Assurance

**Agent-Level:**
- Must pass: `pytest <temp_file> -v`
- Must add coverage (verified)
- Must follow CLAUDE_TESTS.md patterns
- Must use appropriate markers

**Collector-Level:**
- Verifies all STATUS: COMPLETE
- Resolves naming conflicts
- Validates merged tests pass
- Confirms coverage improvement

## Performance

**Typical Speedup:**
- Sequential (1 test at a time): 6-8 minutes per test
- Parallel (N tests simultaneously): 6-8 minutes total for N tests
- **Speedup: 5-10x faster**

**Example:**
```
Task: Add 5 tests to bassi/core_v3/message_converter.py

Sequential approach:
- Write test 1: 7 minutes
- Write test 2: 6 minutes
- Write test 3: 8 minutes
- Write test 4: 7 minutes
- Write test 5: 6 minutes
Total: ~34 minutes

Parallel approach (5 agents):
- All 5 agents work simultaneously
- Longest agent: 7 minutes
- Merge: 1 minute
Total: ~8 minutes

Speedup: 4.25x faster
```

## Limitations

**Current Limitations:**
- Max 10 agents (practical limit for coordination)
- Requires restart Claude Code to see new commands
- E2E tests must run sequentially (xdist_group)
- Each agent writes ONE test only (not multiple)

**Future Enhancements:**
- Auto-detect optimal num_agents from file size
- Support for test suites (multiple related tests per agent)
- Coverage-gap targeting (agents receive specific line ranges)
- Automatic retry for failed agents

## Integration with Existing Workflow

### Before: Manual Test Creation

```bash
# 1. Check coverage
./check.sh cov_all

# 2. Identify low-coverage file
# bassi/module.py: 45% coverage

# 3. Manually write tests
# - Open tests/test_module.py
# - Write test 1, run, fix, iterate (7 min)
# - Write test 2, run, fix, iterate (6 min)
# - Write test 3, run, fix, iterate (8 min)
# Total: ~21 minutes

# 4. Run all tests
./check.sh
```

### After: Automated Parallel Creation

```bash
# 1. Check coverage
./check.sh cov_all

# 2. Identify low-coverage file
# bassi/module.py: 45% coverage

# 3. Launch parallel agents
/bel-write-tests-one-by-one bassi/module.py 3

# Wait ~7 minutes while agents work in parallel
# → 3 tests created, merged, validated automatically

# 4. Run all tests
./check.sh
```

**Time saved:** 21 minutes → 7 minutes (3x faster)

## Troubleshooting

### Command Not Appearing

**Symptom:** `/bel` doesn't autocomplete

**Solutions:**
1. **Restart Claude Code** (most common fix)
2. Check file exists: `ls .claude/commands/bel-write-tests-one-by-one.md`
3. Check YAML frontmatter is valid
4. Check file permissions: `chmod 644 .claude/commands/bel-write-tests-one-by-one.md`

### Agents Not Spawning

**Symptom:** Skill doesn't launch agents

**Solutions:**
1. Check Task tool is available
2. Verify agent files exist in `.claude/agents/`
3. Check skill file exists in `.claude/skills/`
4. Review error messages in output

### Tests Not Merging

**Symptom:** Collector doesn't merge temp files

**Solutions:**
1. Check all agents have `STATUS: COMPLETE`
2. Verify temp files exist: `ls tests/test_*_AGENT_*.py`
3. Check for syntax errors in temp files
4. Try manual merge as debug step

## References

- **Main Testing Guide:** `CLAUDE_TESTS.md` - Comprehensive testing patterns
- **Skill Documentation:** `.claude/skills/bel-create-tests-one-by-one.md`
- **Writer Agent:** `.claude/agents/test-writer-agent-ONLY-ONE.md`
- **Collector Agent:** `.claude/agents/test-collector-agent-MANY.md`
- **Command:** `.claude/commands/bel-write-tests-one-by-one.md`

## Summary

The multi-agent parallel testing system provides:

✅ **5-10x speedup** over sequential test writing
✅ **Automatic conflict resolution** via intelligent merging
✅ **Quality enforcement** through validation at agent and collector levels
✅ **Coverage verification** to ensure meaningful improvement
✅ **Flexible configuration** for different test types and focus areas

**Quick Start:**
```bash
# Restart Claude Code to enable command
# Then use:
/bel-write-tests-one-by-one <source_file>
```

That's it! The system handles the rest automatically.
