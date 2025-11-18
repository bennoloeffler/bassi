# Testing Infrastructure

## Architecture Principle: One Runtime Per Block

**Never mix Playwright (browser/E2E) with asyncio-based tests in the same pytest process.**

This ensures:
- No event loop pollution
- No shared resource conflicts
- Deterministic test execution
- Clean process boundaries

## Directory Structure

```
bassi/core_v3/tests/
├── unit/              # Pure logic, no IO, no async
│   ├── test_message_converter.py
│   ├── test_session_naming.py
│   ├── test_config_service.py
│   └── test_discovery.py
│
├── integration/       # httpx/FastAPI + pytest-asyncio (NO browser)
│   ├── conftest.py    # running_server fixture (ephemeral ports)
│   ├── test_agent_session.py
│   ├── test_interactive_questions.py
│   ├── test_session_workspace.py
│   ├── test_upload_service.py
│   ├── test_web_server_v3.py
│   └── ...            # 20 total integration test files
│
├── e2e/               # Playwright browser tests (sync, NO @pytest.mark.asyncio)
│   ├── conftest.py    # Playwright-specific fixtures
│   └── ...            # Future browser tests
│
├── fixtures/          # Shared test helpers (MockAgentClient, etc.)
│   └── mock_agent_client.py
│
└── conftest.py        # Root fixtures (live_server for Playwright tests)
```

## Test Markers

- `@pytest.mark.unit` - Fast, no IO
- `@pytest.mark.integration` - Uses asyncio/HTTP server
- `@pytest.mark.e2e` - Uses Playwright/browser
- `@pytest.mark.xdist_group(name="e2e_server")` - Serialized group for Playwright tests

## Execution Model

### Three Separate Pytest Runs

**CRITICAL: Run each test type in a separate process to avoid event loop conflicts:**

```bash
# 1. Unit tests (fast, parallel OK)
pytest bassi/core_v3/tests/unit/ -n auto

# 2. Integration tests (asyncio, parallel OK)
pytest bassi/core_v3/tests/integration/ -n auto

# 3. E2E tests (Playwright, serial execution required)
pytest bassi/core_v3/tests/integration/ -m e2e
```

**Note:** Currently E2E tests (Playwright) are in `integration/` directory because they test integration with the web UI. They'll be moved to `e2e/` in a future refactoring.

### Quick Test Runner Script

Use the provided `run-tests.sh` script to run all tests in the correct order:

```bash
./run-tests.sh          # Run all test suites
./run-tests.sh unit     # Run only unit tests
./run-tests.sh integration  # Run only integration tests
./run-tests.sh e2e      # Run only E2E tests
```

## Fixtures

### Unit Tests
No special fixtures needed - pure logic testing.

### Integration Tests (`integration/conftest.py`)

**`running_server(tmp_path)`** - Function-scoped server with ephemeral port

```python
def test_api_endpoint(running_server):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{running_server['base_url']}/api/sessions")
        assert response.status_code == 200
```

Features:
- Ephemeral port (no conflicts)
- Health check before yielding
- Bulletproof teardown
- Mock agent client (no API calls)
- Isolated workspace per test

### E2E Tests (Playwright)

**`live_server(tmp_path_factory)`** - Session-scoped server on port 18765

```python
@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
def test_ui_loads(page, live_server):
    page.goto(live_server)
    assert page.query_selector("#message-input") is not None
```

**CRITICAL RULES for Playwright tests:**
- ✅ Use `def test_*` (synchronous functions)
- ✅ Use `page` fixture (Playwright provides)
- ✅ Use `@pytest.mark.xdist_group(name="e2e_server")`
- ❌ Never use `async def test_*`
- ❌ Never use `@pytest.mark.asyncio`
- ❌ Never use `await` (Playwright is sync API)

## Test Patterns

### Pattern A: Pure Unit Test

```python
# bassi/core_v3/tests/unit/test_example.py
def test_pure_logic():
    result = my_function(input_data)
    assert result == expected
```

### Pattern B: Integration Test (httpx + asyncio)

```python
# bassi/core_v3/tests/integration/test_example.py
import httpx
import pytest

async def test_api_endpoint(running_server):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{running_server['base_url']}/api/sessions",
            json={"name": "Test Session"}
        )
        assert response.status_code == 201
```

### Pattern C: E2E Test (Playwright, sync)

```python
# bassi/core_v3/tests/integration/test_example_e2e.py
import pytest

@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
def test_ui_interaction(page, live_server):
    page.goto(live_server)
    page.fill("#message-input", "Hello")
    page.click("#send-button")
    assert "Hello" in page.content()
```

## Server Ports & Health Checks

### Integration Tests
- **Port allocation**: Ephemeral (OS-assigned via `socket.socket().bind(("", 0))`)
- **Health endpoint**: `GET /health` returns 200 when ready
- **Timeout**: 5 seconds (100 retries × 50ms)
- **Scope**: Function (new server per test)

### E2E Tests
- **Port**: Fixed 18765 (to avoid conflicts with dev server on 8765)
- **Health endpoint**: `GET /health` returns 200 when ready
- **Timeout**: 5 seconds (50 retries × 100ms)
- **Scope**: Session (one server shared by all E2E tests)

## Async Policy

### Unit Tests
- No async by default (pure logic)
- If needed: `@pytest.mark.asyncio` auto-detected

### Integration Tests
- `asyncio_mode = "auto"` - pytest detects `async def` automatically
- `asyncio_default_fixture_loop_scope = "function"` - isolated event loops
- Use `async with httpx.AsyncClient()` for HTTP requests

### E2E Tests (Playwright)
- **Always synchronous** - `def test_*` (not `async def`)
- Playwright handles async internally (you use sync API)
- **Never** use `@pytest.mark.asyncio`

## xdist Isolation

### Unit Tests
- Parallel execution OK: `-n auto`
- No shared resources

### Integration Tests
- Parallel execution OK: `-n auto`
- Each test gets isolated server (ephemeral port)

### E2E Tests (Playwright)
- **Serial execution required** (no `-n auto`)
- **OR** use xdist groups: `@pytest.mark.xdist_group(name="e2e_server")`
- All tests in same group run in same worker (share session-scoped server)

## Common Test Failures

### "Event loop is closed" Error

**Cause:** Mixing Playwright with pytest-asyncio in same process

**Solution:** Run E2E tests separately:
```bash
pytest bassi/core_v3/tests/integration/ -m e2e  # NO -n auto!
```

### "Address already in use" Error

**Cause:** Integration tests trying to bind same port

**Solution:** Tests now use ephemeral ports - if you still see this, check for zombie processes:
```bash
lsof -i :18765  # Check if test server still running
kill -9 <PID>   # Force kill zombie server
```

### Tests Pass Individually, Fail in Suite

**Cause:** Shared state pollution or resource conflicts

**Solution:** This is why we run each test type separately! Integration tests share nothing (ephemeral ports, tmp_path workspaces).

## Debugging Test Failures

### Enable verbose output
```bash
pytest bassi/core_v3/tests/integration/ -vv
```

### Show test duration
```bash
pytest bassi/core_v3/tests/integration/ --durations=10
```

### Run specific test
```bash
pytest bassi/core_v3/tests/integration/test_agent_session.py::test_agent_initialization -v
```

### Debug with pdb
```bash
pytest bassi/core_v3/tests/integration/test_agent_session.py::test_agent_initialization --pdb
```

### Check server logs (E2E tests)
E2E tests use `log_level="error"`. To see all logs:
1. Edit `conftest.py` → change `log_level="error"` to `log_level="debug"`
2. Run test with `-s` flag to see stdout

## Sanity Checks

After making changes, verify:

```bash
# 1. Unit tests pass (fast)
pytest bassi/core_v3/tests/unit/ -n auto
# Expected: ~85 tests, <1 second

# 2. Integration tests pass (slower)
pytest bassi/core_v3/tests/integration/ -n auto
# Expected: ~163 tests, ~30-60 seconds

# 3. E2E tests pass (slowest)
pytest bassi/core_v3/tests/integration/ -m e2e
# Expected: ~40 tests, ~60-120 seconds

# 4. All tests pass (full suite)
./run-tests.sh
# Expected: ~288 tests total
```

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync

      - name: Run unit tests
        run: uv run pytest bassi/core_v3/tests/unit/ -n auto

      - name: Run integration tests
        run: uv run pytest bassi/core_v3/tests/integration/ -n auto

      - name: Run E2E tests
        run: uv run pytest bassi/core_v3/tests/integration/ -m e2e
```

## Summary

✅ **DO:**
- Run each test type in separate process
- Use ephemeral ports for integration tests
- Mark Playwright tests with `@pytest.mark.xdist_group`
- Write synchronous Playwright tests (`def test_*`)
- Use health checks before yielding fixtures

❌ **DON'T:**
- Mix Playwright and pytest-asyncio in same process
- Use `@pytest.mark.asyncio` with Playwright
- Run E2E tests with `-n auto` (unless using xdist groups)
- Share servers across integration tests
- Use `async def` for Playwright tests

For more details on testing patterns, see [CLAUDE_TESTS.md](CLAUDE_TESTS.md).
