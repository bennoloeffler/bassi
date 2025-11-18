# Test Separation: Unit, Integration, and E2E - 2025-11-15

## Summary

This document explains the **clear separation** between unit, integration, and E2E tests in bassi, including:
- **Why** they are separated
- **How** they are organized
- **When** to use each type
- **How** to run them efficiently

---

## The Three Test Types

### Unit Tests
**Location**: `bassi/core_v3/tests/unit/`

**What**: Fast, isolated tests of individual functions/classes with mocked dependencies.

**Characteristics**:
- ✅ **Fast**: ~100ms per test
- ✅ **Parallel**: Run with `-n auto` (multiple workers)
- ✅ **No I/O**: No file system, network, or database access
- ✅ **Fully mocked**: All external dependencies mocked
- ✅ **No API key required**

**Example**:
```python
def test_convert_user_message_to_event():
    """Test SDK message to WebSocket event conversion (pure logic)."""
    msg = UserMessage(content="Hello")
    event = convert_sdk_message_to_event(msg)
    assert event["type"] == "user"
    assert event["content"] == "Hello"
```

**Run command**:
```bash
./run-tests.sh unit        # All unit tests in parallel
./run-tests.sh unit -v     # Verbose output
```

---

### Integration Tests
**Location**: `bassi/core_v3/tests/integration/`

**What**: Tests that verify multiple components working together (services, APIs, file I/O).

**Characteristics**:
- ⚡ **Medium speed**: ~1-5 seconds per test
- ✅ **Parallel**: Run with `-n auto`
- ✅ **Real I/O**: File system, workspace operations
- ⚠️ **Partial mocking**: Mock agent, real services
- ✅ **No API key required** (uses `MockAgentClient`)

**Example**:
```python
async def test_session_workspace_creation():
    """Test creating session workspace with real file I/O."""
    workspace = SessionWorkspace(session_id="test", base_path=tmp_path)
    workspace.save_message({"role": "user", "content": "Hello"})

    messages = workspace.load_messages()
    assert len(messages) == 1
    assert messages[0]["content"] == "Hello"
```

**Run command**:
```bash
./run-tests.sh integration        # All integration tests in parallel
./run-tests.sh integration -v     # Verbose output
```

---

### E2E Tests (End-to-End)
**Location**: `bassi/core_v3/tests/e2e/`

**What**: Browser-based tests using Playwright that verify the entire system from UI to backend.

**Characteristics**:
- 🐌 **Slowest**: ~5-10 seconds per test
- ❌ **Serial only**: Cannot run in parallel (shared server port)
- ✅ **Full stack**: Browser → WebSocket → Server → Agent → File system
- ⚠️ **Mock agent**: Uses `AutoRespondingMockAgentClient` (no API calls)
- ✅ **No API key required**
- 🎭 **Requires browser**: Uses Playwright (chromium, firefox, webkit)

**Example**:
```python
def test_ui_loads(page, live_server):
    """Test that the web UI loads and connects to server."""
    page.goto(live_server)
    page.wait_for_selector(".chat-container")

    # Verify WebSocket connection
    session_id = page.evaluate(
        "() => window.bassiClient ? window.bassiClient.sessionId : null"
    )
    assert session_id is not None
```

**Run command**:
```bash
./run-tests.sh e2e        # All E2E tests serially
./run-tests.sh e2e -v     # Verbose output
```

---

## Why This Separation?

### 1. Performance Optimization

**Problem**: Running all tests together takes too long.

**Solution**: Separate by speed and parallelization capability.

```bash
# Before separation (serial execution)
pytest bassi/core_v3/tests/  # ~5 minutes (all serial)

# After separation (parallel where possible)
./run-tests.sh unit          # ~10 seconds (parallel)
./run-tests.sh integration   # ~30 seconds (parallel)
./run-tests.sh e2e           # ~2 minutes (serial only)
```

### 2. Different Execution Requirements

| Aspect | Unit | Integration | E2E |
|--------|------|-------------|-----|
| Parallel execution | ✅ Yes | ✅ Yes | ❌ No (shared server) |
| File I/O | ❌ No | ✅ Yes | ✅ Yes |
| Network | ❌ No | ❌ No | ✅ Yes (WebSocket) |
| Browser | ❌ No | ❌ No | ✅ Yes (Playwright) |
| Server | ❌ No | ❌ No | ✅ Yes (live_server) |

**E2E tests CANNOT run in parallel** because:
1. They share a single `live_server` fixture (port 18765)
2. Tests mark with `@pytest.mark.xdist_group(name="e2e_server")` to ensure same worker
3. Server state persists across tests (session list, etc.)

### 3. Different Failure Modes

**Unit tests fail → Logic bug**
- Fix the function/class
- Fast iteration (~10 seconds to re-run)

**Integration tests fail → Service interaction bug**
- Fix how components work together
- Medium iteration (~30 seconds to re-run)

**E2E tests fail → UI, WebSocket, or system integration bug**
- Complex debugging (browser, network, server logs)
- Slow iteration (~2 minutes to re-run)

---

## How They Are Organized

### Directory Structure

```
bassi/core_v3/tests/
├── unit/                    # Unit tests (fast, parallel)
│   ├── conftest.py         # Unit test fixtures
│   ├── test_message_converter.py
│   ├── test_session_naming.py
│   └── ...
│
├── integration/             # Integration tests (medium, parallel)
│   ├── conftest.py         # Integration fixtures
│   ├── test_session_index.py
│   ├── test_upload_service.py
│   └── ...
│
├── e2e/                     # E2E tests (slow, serial)
│   ├── conftest.py         # E2E fixtures (live_server)
│   ├── test_file_upload_simple_e2e.py
│   ├── test_session_lifecycle_e2e.py
│   └── ...
│
├── conftest.py              # Shared fixtures (all test types)
└── fixtures/
    ├── mock_agent_client.py
    └── mcp_client.py
```

### Shared vs. Type-Specific Fixtures

**Shared** (`bassi/core_v3/tests/conftest.py`):
- `mock_agent_client` - Used by all test types
- `create_mock_session_factory()` - Used by integration and E2E tests

**E2E specific** (`bassi/core_v3/tests/e2e/conftest.py`):
- `live_server` - Starts web server on port 18765
- `running_server` - Alias for live_server
- `chrome_devtools_client` - Browser automation client

---

## When to Use Each Type

### Use Unit Tests When:
✅ Testing a single function/method in isolation
✅ Testing pure logic (no side effects)
✅ Testing data transformations
✅ Testing utility functions
✅ Testing error handling logic

**Example scenarios**:
- "Does `convert_sdk_message_to_event()` correctly transform a UserMessage?"
- "Does `format_session_name()` handle edge cases?"
- "Does `parse_workspace_context()` validate input?"

### Use Integration Tests When:
✅ Testing multiple components together
✅ Testing service interactions
✅ Testing file I/O operations
✅ Testing workspace management
✅ Testing session lifecycle (without browser)

**Example scenarios**:
- "Does `SessionIndex` correctly save and load session metadata?"
- "Does `SessionWorkspace` handle message persistence?"
- "Does `ConnectionManager` properly manage WebSocket connections?"
- "Does `UploadService` save files to correct location?"

### Use E2E Tests When:
✅ Testing entire user flows (browser → server → agent)
✅ Testing UI interactions
✅ Testing WebSocket communication
✅ Testing multi-session scenarios
✅ Testing error handling in browser

**Example scenarios**:
- "Can user create a session and send a message?"
- "Does file upload work from UI to server?"
- "Does session switching restore message history in UI?"
- "Does error handling show correct message in browser?"

---

## Running Tests

### Test Runner Script: `./run-tests.sh`

**Usage**:
```bash
./run-tests.sh [type] [pytest args...]
```

**Available types**:
- `unit` - Run unit tests (parallel)
- `integration` - Run integration tests (parallel)
- `e2e` - Run E2E tests (serial)
- `all` - Run all test types in sequence

**Examples**:
```bash
# Run all unit tests
./run-tests.sh unit

# Run all unit tests with verbose output
./run-tests.sh unit -v

# Run specific unit test
./run-tests.sh unit bassi/core_v3/tests/unit/test_message_converter.py::test_convert_user_message

# Run all integration tests
./run-tests.sh integration

# Run all E2E tests
./run-tests.sh e2e

# Run all test types
./run-tests.sh all
```

### Direct pytest (Alternative)

**Unit tests**:
```bash
uv run pytest bassi/core_v3/tests/unit/ -n auto
```

**Integration tests**:
```bash
uv run pytest bassi/core_v3/tests/integration/ -n auto
```

**E2E tests**:
```bash
uv run pytest bassi/core_v3/tests/e2e/
```

**Note**: E2E tests should NOT use `-n auto` (parallel execution breaks shared server).

---

## Test Markers (Legacy System)

**Historical note**: Before the directory separation, tests were marked with:
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - E2E tests

**Current approach**: Directory-based separation (no markers needed).

**Why changed**:
1. Simpler - test location determines type
2. Easier - just move file to change type
3. Clearer - directory structure self-documenting
4. Less error-prone - can't forget marker

---

## Debugging Test Failures

### Unit Test Failures

**Symptoms**: Pure logic errors, assertion failures

**Debug approach**:
1. Run single failing test with `-v` and `-s` (show print statements)
2. Add `print()` or `logger.debug()` statements
3. Use Python debugger (`import pdb; pdb.set_trace()`)
4. Fix logic, re-run in ~10 seconds

**Example**:
```bash
# Run single test with print output
uv run pytest bassi/core_v3/tests/unit/test_message_converter.py::test_convert_user_message -v -s
```

### Integration Test Failures

**Symptoms**: File I/O errors, service interaction bugs

**Debug approach**:
1. Check test workspace (`/tmp/pytest-of-<user>/...`)
2. Verify file permissions and paths
3. Check service initialization
4. Use mock assertions to verify calls
5. Fix service logic, re-run in ~30 seconds

**Example**:
```bash
# Run single test with verbose output
uv run pytest bassi/core_v3/tests/integration/test_session_workspace.py::test_save_message -v -s
```

### E2E Test Failures

**Symptoms**: Browser errors, WebSocket disconnections, UI elements not found

**Debug approach**:
1. Check server logs (captured in test output)
2. Use Playwright headed mode: `pytest --headed`
3. Take screenshots: `page.screenshot(path="debug.png")`
4. Check browser console: `page.evaluate("() => console.log(...)")`
5. Verify WebSocket connection
6. Check live_server fixture logs
7. Fix issue, re-run in ~2 minutes

**Example**:
```bash
# Run single E2E test with headed browser
uv run pytest bassi/core_v3/tests/e2e/test_file_upload_simple_e2e.py::test_ui_loads --headed -v -s
```

---

## CI/CD Implications

### Recommended CI Pipeline

```yaml
# .github/workflows/tests.yml (example)

test-unit:
  runs-on: ubuntu-latest
  steps:
    - run: ./run-tests.sh unit
  # Fast (~10 seconds), parallel

test-integration:
  runs-on: ubuntu-latest
  steps:
    - run: ./run-tests.sh integration
  # Medium (~30 seconds), parallel

test-e2e:
  runs-on: ubuntu-latest
  steps:
    - run: ./run-tests.sh e2e
  # Slow (~2 minutes), serial
  # Requires browser installation
```

**Benefits**:
1. **Fast feedback**: Unit tests fail first (10s)
2. **Parallelization**: Unit and integration can run concurrently in CI
3. **Resource optimization**: E2E tests use dedicated runner
4. **Clear failure signals**: Know immediately which layer failed

---

## Migration Notes

### Moving Tests Between Types

**From integration to unit**:
1. Remove all I/O operations
2. Mock all external dependencies
3. Move file to `bassi/core_v3/tests/unit/`
4. Verify it runs in parallel (`-n auto`)

**From integration to E2E**:
1. Add Playwright page fixture
2. Replace direct API calls with browser interactions
3. Move file to `bassi/core_v3/tests/e2e/`
4. Add `@pytest.mark.xdist_group(name="e2e_server")` if needed

**From E2E to integration**:
1. Remove Playwright dependencies
2. Replace browser interactions with direct API calls
3. Move file to `bassi/core_v3/tests/integration/`
4. Verify it runs in parallel (`-n auto`)

---

## Summary

| Test Type | Location | Speed | Parallel | Purpose |
|-----------|----------|-------|----------|---------|
| **Unit** | `bassi/core_v3/tests/unit/` | ~100ms | ✅ Yes | Pure logic, no I/O |
| **Integration** | `bassi/core_v3/tests/integration/` | ~1-5s | ✅ Yes | Services, file I/O |
| **E2E** | `bassi/core_v3/tests/e2e/` | ~5-10s | ❌ No | Full stack, browser |

**Run commands**:
```bash
./run-tests.sh unit          # Fast unit tests (parallel)
./run-tests.sh integration   # Service tests (parallel)
./run-tests.sh e2e           # Browser tests (serial)
./run-tests.sh all           # All tests in sequence
```

**Key principle**: **Test separation enables fast feedback and efficient parallelization.**

---

**Related Documentation**:
- `docs/E2E_TEST_INFRASTRUCTURE_FIX_2025-11-15.md` - E2E test infrastructure fix details
- `CLAUDE_TESTS.md` - Comprehensive testing patterns and best practices
- `bassi/core_v3/tests/conftest.py` - Shared test fixtures
- `bassi/core_v3/tests/e2e/conftest.py` - E2E-specific fixtures
