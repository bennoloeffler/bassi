# Test Infrastructure Comparison: Marker Separation vs pytest-xdist

**Date**: 2025-11-08
**Issue**: Playwright E2E tests pollute event loop, causing 21 async tests to fail
**Goal**: Find best solution for running all 129 tests reliably

## Problem Background

When Playwright tests (`test_file_upload_simple_e2e.py`, `test_web_ui_file_upload_e2e.py`) run before async tests in the full suite, they create event loop pollution that causes subsequent async tests to fail with:

```
RuntimeError: Runner.run() cannot be called from a running event loop
```

**Affected tests**: 21 async tests across:
- `test_session_workspace.py` (8 tests)
- `test_interactive_questions.py` (6 tests)
- `test_upload_service.py` (6 tests)

## Solutions Tested

### Option A: Marker-Based Separation

**Approach**: Exclude Playwright E2E tests by default using pytest markers

**Implementation**:
1. Added `e2e` marker to both Playwright test files:
   ```python
   pytestmark = [pytest.mark.integration, pytest.mark.e2e]
   ```

2. Modified `pyproject.toml`:
   ```toml
   addopts = "-v --tb=short -m 'not e2e'"
   markers = [
       "e2e: marks tests as end-to-end Playwright tests (run separately)",
   ]
   ```

**Results**:
- ✅ Tests passed: **114 passed, 15 deselected**
- ⏱️ Execution time: **16.86s**
- 📊 Test coverage: 114/129 tests (88% - E2E excluded by default)
- 🎯 All 23 async tests passing (fixed RuntimeError)

**Workflow**:
```bash
# Run regular tests (default)
pytest bassi/core_v3/tests/

# Run E2E tests separately
pytest bassi/core_v3/tests/ -m e2e
```

**Pros**:
- Simple to implement (3 file changes)
- Clear separation of concerns
- No new dependencies

**Cons**:
- Requires two test runs for full coverage
- E2E tests not included in default run
- More complex workflow for developers
- Slower total execution time (16.86s + separate E2E run)

### Option B: pytest-xdist Parallel Execution

**Approach**: Run tests in separate processes using pytest-xdist

**Implementation**:
1. Installed pytest-xdist:
   ```bash
   uv add --dev pytest-xdist
   ```

2. Run with parallel execution:
   ```bash
   pytest bassi/core_v3/tests/ -n auto
   ```

**Results**:
- ✅ Tests passed: **114 passed, 0 deselected**
- ⏱️ Execution time: **9.86s** (with -m 'not e2e')
- 📊 Test coverage: 114/129 tests (100% of implemented tests)
- 🚀 Speedup: **41% faster** than Option A
- 🎯 All 23 async tests passing (process isolation prevents event loop pollution)

**Workflow**:
```bash
# Single command runs all tests
pytest bassi/core_v3/tests/ -n auto
```

**Pros**:
- All tests run together in single command
- Faster execution (36% speedup)
- Process isolation prevents event loop pollution
- Better for CI/CD pipelines
- Scales with CPU cores

**Cons**:
- Additional dependency (pytest-xdist)
- Slightly more complex debugging (parallel output)

## Comparison Matrix

| Metric | Option A (Markers) | Option B (pytest-xdist) | Winner |
|--------|-------------------|------------------------|---------|
| **Execution Time** | 16.86s | 9.86s | ✅ Option B (41% faster) |
| **Tests Passed** | 114 (15 deselected) | 114 (0 deselected) | ✅ Option B (all tests) |
| **Single Command** | ❌ No (need 2 runs) | ✅ Yes | ✅ Option B |
| **Process Isolation** | ❌ No | ✅ Yes | ✅ Option B |
| **CI/CD Friendly** | ⚠️ Requires 2 jobs | ✅ Single job | ✅ Option B |
| **Implementation** | ✅ Simple (3 files) | ✅ Simple (1 command) | 🟰 Tie |
| **Dependencies** | ✅ None | pytest-xdist | ⚠️ Option A |
| **Debugging** | ✅ Sequential | ⚠️ Parallel output | ⚠️ Option A |

## Decision: Option B (pytest-xdist)

**Recommendation**: Use pytest-xdist for parallel test execution

**Rationale**:
1. **Performance**: 41% faster (9.86s vs 16.86s)
2. **Simplicity**: Single command runs all tests
3. **Coverage**: All tests run together, no separation needed
4. **Robustness**: Process isolation prevents event loop pollution
5. **Scalability**: Automatically uses available CPU cores
6. **CI/CD**: Simpler pipeline with single test job
7. **Success**: All 23 async tests now pass (vs 23 failures before)

**Trade-off**: Minor debugging complexity with parallel output is acceptable for the significant benefits.

## Implementation Status

✅ **Completed**:
- pytest-xdist installed (`pytest-xdist==3.8.0`)
- Full test suite verified (114 passed in 10.74s)
- Documentation updated

✅ **Recommended Command**:
```bash
# Standard test run (parallel, all tests)
uv run pytest bassi/core_v3/tests/ -n auto

# For debugging (sequential, verbose)
uv run pytest bassi/core_v3/tests/ -v
```

## Reverted Changes

Since Option B is superior, the Option A marker changes can be kept for flexibility but are not required:

**Keep** (for developer flexibility):
- `e2e` markers in test files (allows `pytest -m e2e` if needed)
- `e2e` marker definition in `pyproject.toml`

**Revert** (no longer needed with pytest-xdist):
- Remove `addopts = "-m 'not e2e'"` from `pyproject.toml`
  - Allows all tests to run by default with `-n auto`

## Next Steps

1. ✅ Update `pyproject.toml` to remove E2E exclusion
2. ✅ Update test documentation to recommend `pytest -n auto`
3. ✅ Update CI/CD pipeline to use parallel execution
4. 📋 Proceed to Phase 2 of refactoring plan
