# CLAUDE_TESTS.md

**Testing Architecture and Best Practices for bassi**

This document is the authoritative guide for testing in the bassi project. **Always consult this document when writing or modifying tests** to ensure consistency and avoid breaking the test suite.

---

## Table of Contents

1. [Test Organization](#test-organization)
2. [Test Types and Markers](#test-types-and-markers)
3. [Fixtures and Test Isolation](#fixtures-and-test-isolation)
4. [Parallel Testing with pytest-xdist](#parallel-testing-with-pytest-xdist)
5. [Unit Tests](#unit-tests)
6. [Integration Tests](#integration-tests)
7. [E2E Tests with Playwright](#e2e-tests-with-playwright)
8. [Mock Patterns](#mock-patterns)
9. [Async Testing](#async-testing)
10. [Critical Rules to Avoid Breaking Tests](#critical-rules-to-avoid-breaking-tests)
11. [Common Patterns and Examples](#common-patterns-and-examples)

---

## Quick Start: Running Tests the Right Way

### TL;DR

```bash
# Fast mode (default) - Skip slow E2E tests, ~30s
./check.sh              # Or: ./check.sh fast

# E2E tests only - Slow browser tests, ~2min
./check.sh e2e

# Everything - Full pipeline, ~3min
./check.sh all

# Marker-based filtering (pytest -m)
./check.sh "not integration"              # Skip integration tests
./check.sh "not integration and not e2e"  # Pure unit tests only
./check.sh "integration"                  # Integration tests only
./check.sh "e2e or integration"           # All slow tests
```

### The `./check.sh` Script

The `./check.sh` script is the **recommended way** to run tests. It intelligently handles:

- ✅ **Parallel execution for unit tests** (fast)
- ✅ **Sequential execution for E2E tests** (prevents port conflicts)
- ✅ **Automatic cleanup of leftover test servers**
- ✅ **Exit on first failure** (fast feedback)
- ✅ **Quality checks** (black, ruff, mypy)

#### Modes

| Mode | Command | Time | What It Does |
|------|---------|------|--------------|
| **Fast** (default) | `./check.sh` or `./check.sh fast` | ~30s | Code quality + unit tests (parallel). **Skips E2E tests**. Use this for rapid iteration. |
| **E2E** | `./check.sh e2e` | ~2min | E2E tests only (sequential). Skips code quality checks. Use when working on UI features. |
| **All** | `./check.sh all` | ~3min | Everything: code quality + unit tests (parallel) + E2E tests (sequential). **Run before committing**. |
| **Marker Filter** | `./check.sh "<expression>"` | Varies | Custom marker filtering (e.g., `"not integration"`). Skips code quality checks. Auto-detects parallel vs sequential. |

#### Marker-Based Filtering

Any argument that's **not** `fast`, `e2e`, or `all` is treated as a pytest marker expression:

```bash
# Skip integration tests (fast, parallel)
./check.sh "not integration"

# Pure unit tests - skip integration AND E2E (fastest, parallel)
./check.sh "not integration and not e2e"

# Integration tests only (no E2E, can be parallel)
./check.sh "integration"

# All slow tests (E2E + integration, sequential)
./check.sh "e2e or integration"
```

**Smart Parallel Detection**: The script automatically runs tests in parallel (`-n auto`) if the marker expression contains `"not e2e"`, otherwise it runs sequentially to avoid port conflicts.

#### Why Use This Script?

**Problem**: E2E tests use a session-scoped `live_server` fixture that binds to port 8765. Running them with `pytest -n auto` causes multiple workers to create duplicate servers → port binding conflicts → test crashes.

**Solution**: The script runs:
1. **Unit tests** with `-n auto -m "not e2e"` (parallel, fast)
2. **E2E tests** with `-m e2e` (sequential, no `-n` flag)
3. **Cleanup** of leftover servers on port 8765

**Example Output (Fast Mode)**:
```
=============================================
Quality Assurance Pipeline
=============================================

Usage:
  ./check.sh           # Fast mode (skip slow E2E tests) ~30s
  ./check.sh fast      # Same as default
  ./check.sh e2e       # E2E tests only ~2min
  ./check.sh all       # Everything (unit + E2E) ~3min

Running mode: fast
=============================================

1. Code Formatting (black)...
All done! ✨ 🍰 ✨

2. Linting (ruff)...
All checks passed!

3. Type Checking (mypy)...
Success: no issues found in 42 source files

4. Running Unit Tests (parallel, ~20s)...
   • V1 tests: tests/
   • V3 tests: bassi/core_v3/tests/
   • Parallel workers: auto
   • Skipping: E2E tests (marked with @pytest.mark.e2e)

=============================================
✅ All quality checks passed!
=============================================

Test Summary (unit tests only):
325 passed in 18.34s

💡 Tip: Run './check.sh all' to include E2E tests
```

#### When to Use Each Mode

| Scenario | Command | Why |
|----------|---------|-----|
| **Daily development** | `./check.sh` (fast) | Rapid iteration, skip slow E2E tests (~30s) |
| **UI work** | `./check.sh e2e` | Test browser interactions without code quality checks (~2min) |
| **Before committing** | `./check.sh all` | Verify everything passes (~3min) |
| **From Claude Code** | `./check.sh` (fast) | Keep tests quick during coding |
| **Skip API tests** | `./check.sh "not integration"` | No API keys needed, fastest (~20s) |
| **Pure unit tests** | `./check.sh "not integration and not e2e"` | Absolutely fastest, no external deps (~15s) |
| **Integration only** | `./check.sh "integration"` | Test API integrations without E2E (~30s) |
| **All slow tests** | `./check.sh "e2e or integration"` | Test everything that needs external resources (~2min) |

---

## Test Organization

### Directory Structure

```
bassi/
├── tests/                          # V1 CLI tests (15+ tests)
│   ├── conftest.py                # V1 fixtures
│   ├── test_agent.py              # Agent tests
│   ├── test_*.py                  # Other V1 tests
│   └── fixtures/
│       └── mock_agent_client.py   # Shared mock client
│
└── core_v3/
    └── tests/                      # V3 Web UI tests (309 tests)
        ├── conftest.py            # Shared fixtures (all test types)
        ├── unit/                  # Unit tests (fast, parallel)
        │   ├── conftest.py       # Unit test fixtures
        │   └── test_*.py         # Unit tests
        │
        ├── integration/           # Integration tests (medium, parallel)
        │   ├── conftest.py       # Integration fixtures
        │   └── test_*.py         # Integration tests
        │
        ├── e2e/                   # E2E tests (slow, serial)
        │   ├── conftest.py       # E2E fixtures (live_server)
        │   └── test_*_e2e.py     # Playwright browser tests
        │
        └── fixtures/
            ├── mock_agent_client.py
            └── mcp_client.py
```

### Naming Conventions

- **Test files**: `test_*.py` (e.g., `test_agent.py`, `test_file_upload_simple_e2e.py`)
- **Test classes**: `Test*` (optional, e.g., `class TestFileUpload:`)
- **Test functions**: `test_*` (e.g., `def test_agent_initialization():`)

### Running Tests

#### Recommended: Use `run-tests.sh` Script

The `run-tests.sh` script is the **recommended way** to run tests by type:

```bash
# Run all unit tests (parallel)
./run-tests.sh unit

# Run all integration tests (parallel)
./run-tests.sh integration

# Run all E2E tests (serial - cannot run in parallel)
./run-tests.sh e2e

# Run all test types in sequence
./run-tests.sh all

# Run with verbose output
./run-tests.sh unit -v
./run-tests.sh e2e -v

# Run specific test
./run-tests.sh unit bassi/core_v3/tests/unit/test_message_converter.py::test_convert_user_message -v
```

**Why use this script?**
- ✅ Automatically runs unit/integration tests in parallel (`-n auto`)
- ✅ Automatically runs E2E tests serially (avoids port conflicts)
- ✅ Clear separation by test type (unit, integration, e2e)
- ✅ Consistent test execution across team

#### Alternative: Direct pytest

```bash
# Run all tests (V1 + V3)
uv run pytest

# Run V1 tests only
uv run pytest tests/

# Run V3 unit tests (parallel)
uv run pytest bassi/core_v3/tests/unit/ -n auto

# Run V3 integration tests (parallel)
uv run pytest bassi/core_v3/tests/integration/ -n auto

# Run V3 E2E tests (serial - no -n flag!)
uv run pytest bassi/core_v3/tests/e2e/

# Run specific test file
uv run pytest tests/test_agent.py

# Run specific test function
uv run pytest tests/test_agent.py::test_agent_initialization -v

# Run with coverage
uv run pytest --cov=bassi

# Watch mode (auto-rerun on changes)
uv run pytest-watch
```

**⚠️ CRITICAL**: Never use `-n auto` with E2E tests! E2E tests use a shared `live_server` fixture that binds to port 18765. Parallel execution will cause port conflicts.

---

## Test Types and Markers

### Test Markers

Tests are categorized using pytest markers defined in `pyproject.toml`:

```python
# Unit test (no marker needed)
def test_config_manager():
    """Fast, isolated, no external dependencies"""
    pass

# Integration test (requires API keys or external services)
@pytest.mark.integration
def test_api_call():
    """May require ANTHROPIC_API_KEY or other credentials"""
    pass

# E2E test (Playwright, shared server)
@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
def test_ui_interaction(page, live_server):
    """Browser-based end-to-end tests"""
    pass

# Async test (auto-detected, but can be explicit)
@pytest.mark.asyncio
async def test_async_function():
    """Async function tests"""
    pass
```

### Test Type Comparison

| Type | Speed | Dependencies | Parallel | Location |
|------|-------|--------------|----------|----------|
| **Unit** | Fast (~100ms) | None (mocks) | ✅ Yes (`-n auto`) | `bassi/core_v3/tests/unit/` |
| **Integration** | Medium (~1-5s) | File I/O, services | ✅ Yes (`-n auto`) | `bassi/core_v3/tests/integration/` |
| **E2E** | Slow (~5-10s) | Browser, server | ❌ No (shared server) | `bassi/core_v3/tests/e2e/` |

**Key difference**: E2E tests MUST run serially because they share a `live_server` fixture on port 18765.

---

## Fixtures and Test Isolation

### Automatic Test Isolation (V1)

The `test_environment` fixture in `tests/conftest.py` automatically provides:

```python
@pytest.fixture(autouse=True)
def test_environment(monkeypatch, tmp_path):
    """
    Automatic test isolation for ALL V1 tests:
    - Isolated temporary directory
    - Mock API key (no real API calls)
    - Test-specific HOME directory
    - Project import paths preserved
    """
    # Changes to tmp_path, restores on teardown
    yield tmp_path
```

**What this means:**
- Every test runs in a fresh temporary directory
- No test can pollute another test's state
- API key is mocked by default
- No need to manually clean up files

### Common Fixtures

#### V1 Fixtures (`tests/conftest.py`)

```python
@pytest.fixture
def mock_api_key(monkeypatch):
    """Provide mock API key"""

@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Temporary config directory"""

@pytest.fixture
def mock_agent_client():
    """Reusable mock AgentClient"""
```

#### V3 Fixtures (`bassi/core_v3/tests/conftest.py`)

```python
@pytest.fixture
def mock_agent_client():
    """Mock client for V3 tests"""

@pytest.fixture(scope="session")
@pytest.mark.xdist_group(name="e2e_server")
def live_server():
    """
    Shared web server for E2E tests
    - Session-scoped (runs once)
    - Shared by all E2E tests in same xdist worker
    - Uses mock client (no API calls)
    """

@pytest.fixture
def temp_workspace(tmp_path):
    """Temporary SessionWorkspace for tests"""
```

### Fixture Scopes

- **`function`** (default): New instance per test function
- **`class`**: Shared by all tests in a class
- **`module`**: Shared by all tests in a file
- **`session`**: Shared by entire test session (use with caution!)

**Rule:** Use session scope ONLY for expensive resources that are safe to share (like `live_server` for E2E tests).

---

## Parallel Testing with pytest-xdist

### How It Works

Pytest-xdist runs tests in parallel across multiple CPU cores:

```bash
# Sequential execution (default - required for E2E tests)
uv run pytest

# Parallel execution for unit tests (optional speedup)
uv run pytest -n auto  # Distributes tests across CPU cores
```

**IMPORTANT**: By default, tests run sequentially (no `-n auto` in pyproject.toml) because E2E tests require a single server instance on port 8765. Parallel execution would cause port binding conflicts.

### xdist Groups: When Tests Must Run Together

Some tests share expensive resources (like a web server). Use `xdist_group` to ensure they run in the same worker:

```python
# Mark ALL E2E tests in a file
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.xdist_group(name="e2e_server"),  # Run in same worker
]

@pytest.fixture(scope="session")
@pytest.mark.xdist_group(name="e2e_server")
def live_server():
    """Shared server - only one instance per worker"""
    # Start server once
    yield server
    # Cleanup once
```

### Critical xdist Rules

1. **Session-scoped fixtures with xdist_group must match**
   ```python
   # ✅ Correct: fixture and tests have same group
   @pytest.fixture(scope="session")
   @pytest.mark.xdist_group(name="e2e_server")
   def live_server():
       ...

   @pytest.mark.xdist_group(name="e2e_server")
   def test_ui(live_server):
       ...

   # ❌ Wrong: group mismatch = fixture runs multiple times
   @pytest.mark.xdist_group(name="wrong_group")
   def test_ui(live_server):
       ...
   ```

2. **File-level pytestmark applies to ALL tests**
   ```python
   # Apply markers to entire file
   pytestmark = [
       pytest.mark.e2e,
       pytest.mark.xdist_group(name="e2e_server"),
   ]
   ```

3. **Don't share mutable state across workers**
   - Each worker has separate Python process
   - Global variables won't be shared
   - Use fixtures or databases for shared state

---

## Unit Tests

### Characteristics

- **Fast**: Run in milliseconds
- **Isolated**: No external dependencies
- **Mocked**: Use MockAgentClient, not real API
- **No markers needed**: Run by default

### Example: Testing with MockAgentClient

```python
@pytest.mark.asyncio
async def test_agent_chat_with_mock(monkeypatch):
    """Test agent chat without API calls."""
    from bassi.agent import BassiAgent

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    # Create mock client
    mock_client = MockAgentClient()
    mock_client.queue_response(
        AssistantMessage(
            content=[TextBlock(text="Hello!")],
            model="test-model"
        ),
        ResultMessage(
            subtype="complete",
            duration_ms=100,
            is_error=False,
            num_turns=1,
            usage={"input_tokens": 1, "output_tokens": 2},
        ),
    )

    # Inject mock via factory
    agent = BassiAgent(client_factory=lambda _config: mock_client)

    # Test
    messages = []
    async for item in agent.chat("Test"):
        messages.append(item)

    assert len(messages) == 2
    assert mock_client.sent_prompts[0]["prompt"] == "Test"
```

### Best Practices

- Use `MockAgentClient` for agent tests
- Use `monkeypatch` to set environment variables
- Use fixtures from `conftest.py` for common setup
- Assert on behavior, not implementation details

---

## Integration Tests

### Characteristics

- **Require external resources**: API keys, databases, services
- **Marked with `@pytest.mark.integration`**
- **Skipped by default** unless explicitly run
- **May make real API calls** (cost money)

### Example

```python
@pytest.mark.integration
def test_real_api_call():
    """
    Integration test - requires ANTHROPIC_API_KEY

    Run with: pytest -m integration
    """
    from bassi.agent import BassiAgent

    agent = BassiAgent()
    response = agent.chat("What is 2+2?")

    assert response is not None
    assert isinstance(response, str)
```

### Running Integration Tests

```bash
# Run only integration tests
uv run pytest -m integration

# Skip integration tests (default)
uv run pytest -m "not integration"
```

---

## E2E Tests with Playwright

### Characteristics

- **Browser-based**: Test actual UI interactions
- **Shared server**: Use `live_server` fixture
- **Marked with `@pytest.mark.e2e` + `xdist_group`**
- **Slower**: Browser startup, WebSocket connections
- **Use sync def, not async def**: Playwright handles async internally

### Critical Patterns

#### 1. File-Level Markers

```python
"""E2E test file - test_file_upload_simple_e2e.py"""

# Apply to ALL tests in file
pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.xdist_group(name="e2e_server"),  # Share server
]
```

#### 2. Cleanup Between Tests

```python
@pytest.fixture(autouse=True)
def cleanup_between_tests():
    """
    CRITICAL: Allow SDK client to disconnect between tests

    Without this, tests fail with connection errors.
    """
    yield
    # Wait for Claude Agent SDK to fully disconnect
    time.sleep(2)  # 2 seconds minimum
```

#### 3. Wait for WebSocket Connection

```python
def test_ui_loads(page, live_server):
    """Test UI with proper wait patterns."""
    page.goto(live_server)

    # ✅ Wait for connection FIRST
    page.wait_for_selector(
        "#connection-status:has-text('Connected')",
        timeout=10000  # 10 seconds
    )

    # Now test interactions
    assert page.query_selector("#message-input") is not None
```

#### 4. Playwright Sync API (Not Async)

```python
# ✅ Correct: Sync function
def test_playwright(page, live_server):
    page.goto(live_server)
    page.click("#button")

# ❌ Wrong: Async function
async def test_playwright(page, live_server):
    await page.goto(live_server)  # Don't do this
```

#### 5. Browser Context Configuration

```python
@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser for tests."""
    return {
        **browser_context_args,
        "viewport": {
            "width": 1280,
            "height": 720,
        },
    }
```

### Complete E2E Test Example

```python
"""test_upload_e2e.py"""
import time
import pytest

# File-level markers
pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.xdist_group(name="e2e_server"),
]

@pytest.fixture(autouse=True)
def cleanup_between_tests():
    """Critical: SDK cleanup time"""
    yield
    time.sleep(2)

@pytest.fixture
def test_file(tmp_path):
    """Create test file"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test content")
    return test_file

def test_upload_file(page, live_server, test_file):
    """Test file upload workflow."""
    # Navigate and wait for connection
    page.goto(live_server)
    page.wait_for_selector(
        "#connection-status:has-text('Connected')",
        timeout=10000
    )

    # Upload file
    file_input = page.query_selector('input[type="file"]')
    file_input.set_input_files(str(test_file))

    # Wait for UI update
    page.wait_for_selector(
        "#file-chips-container.has-files",
        state="visible",
        timeout=10000
    )

    # Verify
    file_chip = page.query_selector(".file-chip")
    assert file_chip is not None
```

### E2E Testing Checklist

- [ ] Use `pytestmark` with `xdist_group(name="e2e_server")`
- [ ] Add `cleanup_between_tests` fixture with `time.sleep(2)`
- [ ] Use sync `def`, not `async def`
- [ ] Wait for WebSocket connection before testing
- [ ] Use proper timeout values (5-10 seconds)
- [ ] Test one feature per test function
- [ ] Clean up browser contexts if opening multiple pages

---

## Mock Patterns

### MockAgentClient

Located in `tests/fixtures/mock_agent_client.py`, used by both V1 and V3 tests.

```python
from tests.fixtures.mock_agent_client import MockAgentClient

# Create mock
mock_client = MockAgentClient()

# Queue response
mock_client.queue_response(
    AssistantMessage(content=[TextBlock(text="Response")]),
    ResultMessage(subtype="complete", num_turns=1),
)

# Inject via factory
agent = BassiAgent(client_factory=lambda _config: mock_client)

# Test behavior
async for message in agent.chat("Prompt"):
    process(message)

# Verify calls
assert len(mock_client.sent_prompts) == 1
assert mock_client.sent_prompts[0]["prompt"] == "Prompt"
```

### Factory Pattern for Sessions

```python
def create_mock_session_factory():
    """Factory that creates sessions with mock client."""

    def mock_client_factory(config):
        return MockAgentClient()

    def factory(question_service, workspace):
        config = SessionConfig(
            permission_mode="bypassPermissions",
            # ... other config
        )
        session = BassiAgentSession(config, client_factory=mock_client_factory)
        return session

    return factory
```

---

## Async Testing

### Async Mode Configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # Auto-detect async tests
asyncio_default_fixture_loop_scope = "function"  # Isolate event loops
```

**What this means:**
- Pytest automatically detects async test functions
- No need for `@pytest.mark.asyncio` (but doesn't hurt)
- Each test gets a fresh event loop
- No event loop conflicts

### Writing Async Tests

```python
# Auto-detected as async test
async def test_async_function():
    result = await some_async_operation()
    assert result == expected

# Explicit marker (optional)
@pytest.mark.asyncio
async def test_with_marker():
    result = await another_async_operation()
    assert result == expected
```

### Async Fixtures

```python
@pytest.fixture
async def async_resource():
    """Async fixture setup/teardown."""
    resource = await create_resource()
    yield resource
    await resource.cleanup()

async def test_with_async_fixture(async_resource):
    result = await async_resource.do_something()
    assert result is not None
```

---

## Critical Rules to Avoid Breaking Tests

### 1. Never Use Real API Keys in Tests

```python
# ✅ Good: Mock API key
monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

# ❌ Bad: Real API key
# Don't rely on environment API key
```

### 2. Always Use Temporary Directories

```python
# ✅ Good: Use fixture-provided tmp_path
def test_file_creation(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

# ❌ Bad: Write to project directory
def test_file_creation():
    Path("test.txt").write_text("content")  # Pollutes repo
```

### 3. Respect xdist_group for Shared Resources

```python
# ✅ Good: Matching groups
@pytest.fixture(scope="session")
@pytest.mark.xdist_group(name="e2e_server")
def live_server():
    ...

@pytest.mark.xdist_group(name="e2e_server")
def test_ui(live_server):
    ...

# ❌ Bad: No group on test
def test_ui(live_server):  # Will create multiple servers!
    ...
```

### 4. Clean Up Resources in E2E Tests

```python
# ✅ Good: Cleanup fixture
@pytest.fixture(autouse=True)
def cleanup_between_tests():
    yield
    time.sleep(2)  # SDK disconnect time

# ❌ Bad: No cleanup
def test_upload(page, live_server):
    # Test runs, but next test fails due to stale connection
    ...
```

### 5. Use Proper Wait Patterns in Playwright

```python
# ✅ Good: Explicit wait
page.wait_for_selector("#element", timeout=5000)
element = page.query_selector("#element")

# ❌ Bad: No wait
element = page.query_selector("#element")  # Flaky!
```

### 6. Don't Modify Shared State

```python
# ✅ Good: Test-local state
def test_config(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text('{"key": "value"}')

# ❌ Bad: Modify global config
def test_config():
    ConfigManager.set_value("key", "value")  # Affects other tests
```

### 7. Mark Integration Tests Properly

```python
# ✅ Good: Marked as integration
@pytest.mark.integration
def test_real_api():
    response = api.call()

# ❌ Bad: No marker, runs by default
def test_real_api():  # Will fail without API key!
    response = api.call()
```

### 8. Use Sync Functions for Playwright Tests

```python
# ✅ Good: Sync function
def test_ui(page, live_server):
    page.goto(live_server)

# ❌ Bad: Async function
async def test_ui(page, live_server):
    await page.goto(live_server)  # pytest-playwright doesn't support this
```

---

## Common Patterns and Examples

### Pattern 1: Unit Test with Mock Client

```python
@pytest.mark.asyncio
async def test_agent_with_mock(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    mock = MockAgentClient()
    mock.queue_response(
        AssistantMessage(content=[TextBlock(text="Response")]),
        ResultMessage(subtype="complete", num_turns=1),
    )

    agent = BassiAgent(client_factory=lambda _: mock)

    messages = []
    async for msg in agent.chat("Test"):
        messages.append(msg)

    assert len(messages) > 0
```

### Pattern 2: E2E Test with File Upload

```python
# File: test_upload_e2e.py
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.xdist_group(name="e2e_server"),
]

@pytest.fixture(autouse=True)
def cleanup():
    yield
    time.sleep(2)

@pytest.fixture
def test_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("content")
    return f

def test_upload(page, live_server, test_file):
    page.goto(live_server)
    page.wait_for_selector("#connection-status:has-text('Connected')")

    file_input = page.query_selector('input[type="file"]')
    file_input.set_input_files(str(test_file))

    page.wait_for_selector(".file-chip", state="visible")
    assert page.query_selector(".file-chip") is not None
```

### Pattern 3: Async Test with Workspace

```python
@pytest.fixture
def temp_workspace(tmp_path):
    workspace = SessionWorkspace("test-session", base_path=tmp_path)
    return workspace

@pytest.mark.asyncio
async def test_upload_file(temp_workspace, mock_upload_file):
    upload = mock_upload_file("test.txt", b"content")

    path = await temp_workspace.upload_file(upload)

    assert path.exists()
    assert path.read_bytes() == b"content"
```

### Pattern 4: Integration Test (Skipped by Default)

```python
@pytest.mark.integration
def test_real_api():
    """
    Integration test - requires ANTHROPIC_API_KEY

    Run with: pytest -m integration
    """
    pytest.skip("Integration test - requires API key")

    agent = BassiAgent()
    response = agent.chat("Test")
    assert response is not None
```

---

## Quick Reference

### Test Commands

```bash
# All tests
uv run pytest

# V1 tests
uv run pytest tests/

# V3 tests
uv run pytest bassi/core_v3/tests/

# Specific file
uv run pytest tests/test_agent.py

# Integration tests
uv run pytest -m integration

# Skip integration
uv run pytest -m "not integration"

# With coverage
uv run pytest --cov=bassi

# Quality checks (before commit)
./check.sh
```

### Key Markers

```python
@pytest.mark.integration           # Requires API keys
@pytest.mark.e2e                   # Playwright E2E test
@pytest.mark.asyncio               # Async test (optional)
@pytest.mark.xdist_group(name="x") # Group for shared resources
```

### Critical Fixtures

```python
test_environment      # Auto: isolated tmp_path, mock API key (V1)
mock_agent_client     # MockAgentClient instance
live_server          # Shared web server for E2E tests
temp_workspace       # Temporary SessionWorkspace
cleanup_between_tests # E2E: SDK disconnect time (autouse)
```

---

## Troubleshooting

### "Test failed with connection error"

**Problem:** E2E tests fail with WebSocket connection errors.

**Solution:** Add cleanup fixture:
```python
@pytest.fixture(autouse=True)
def cleanup_between_tests():
    yield
    time.sleep(2)  # SDK needs time to disconnect
```

### "Session-scoped fixture created multiple times"

**Problem:** `live_server` fixture runs multiple times in parallel tests.

**Solution:** Ensure test has matching `xdist_group`:
```python
@pytest.mark.xdist_group(name="e2e_server")
def test_ui(live_server):
    ...
```

### "Test fails with API key error"

**Problem:** Test tries to use real API without key.

**Solution:** Mark as integration test:
```python
@pytest.mark.integration
def test_api():
    ...
```

### "Playwright test hangs or times out"

**Problem:** WebSocket not connected or element not ready.

**Solution:** Add explicit waits:
```python
page.wait_for_selector("#connection-status:has-text('Connected')", timeout=10000)
page.wait_for_selector("#element", state="visible", timeout=5000)
```

### "TypeError: 'SdkMcpTool' object is not callable"

**Problem:** MCP server tests fail with `TypeError: 'SdkMcpTool' object is not callable` when `claude_agent_sdk` is installed.

**Root Cause:** The `@tool` decorator from the SDK wraps functions in `SdkMcpTool` objects. Tests call functions directly and expect raw functions, not wrapped objects.

**Solution:** The `pytest_configure` hook in `tests/conftest.py` already handles this by monkey-patching SDK functions with stubs. If you see this error:

1. Verify `pytest_configure` is present in `tests/conftest.py`
2. Check that SDK modules are deleted before importing:
   ```python
   def pytest_configure(config):
       import sys
       # Delete SDK modules if already imported
       if "bassi.shared.sdk_loader" in sys.modules:
           del sys.modules["bassi.shared.sdk_loader"]
       for module_name in list(sys.modules.keys()):
           if module_name.startswith("bassi.mcp_servers."):
               del sys.modules[module_name]

       # Import and patch SDK
       import bassi.shared.sdk_loader
       bassi.shared.sdk_loader.SDK_AVAILABLE = False
       bassi.shared.sdk_loader.tool = stub_tool  # Replace decorator
       bassi.shared.sdk_loader.create_sdk_mcp_server = stub_create_sdk_mcp_server
   ```

### "OSError: address already in use (port 8765)"

**Problem:** E2E tests fail with `OSError: [Errno 48] error while attempting to bind on address ('127.0.0.1', 8765): address already in use`.

**Root Cause:** When pytest-xdist runs with `-n auto`, it creates multiple workers. Each worker tries to create its own `live_server` fixture instance, causing port conflicts.

**Solution:** Tests run sequentially by default (no `-n auto` in `pyproject.toml`). If you need parallel execution for unit tests, use:
```bash
# Parallel unit tests only (exclude E2E)
uv run pytest -n auto -m "not e2e"
```

### "Marks applied to fixtures have no effect" (pytest warning)

**Problem:** Pytest warning `PytestRemovedIn9Warning: Marks applied to fixtures have no effect` and E2E tests fail with port binding errors during test execution (server crashes mid-test with `SystemExit(1)`).

**Root Cause:** Applying `@pytest.mark.xdist_group` to a fixture does nothing - markers only work on test functions. Without proper grouping, multiple xdist workers can create separate `live_server` instances, causing port conflicts and server crashes.

**Solution:**
1. **NEVER** put markers on fixtures:
   ```python
   # ❌ Wrong: Marker on fixture does nothing
   @pytest.fixture(scope="session")
   @pytest.mark.xdist_group(name="e2e_server")
   def live_server():
       ...

   # ✅ Correct: Marker only on test functions
   @pytest.mark.xdist_group(name="e2e_server")
   def test_ui(live_server):
       ...
   ```

2. Add note in fixture docstring reminding developers:
   ```python
   @pytest.fixture(scope="session")
   def live_server():
       """
       NOTE: Tests using this fixture MUST have @pytest.mark.xdist_group(name="e2e_server")
       to ensure they run in the same worker. Markers on fixtures have no effect.
       """
   ```

3. If tests still fail, check for leftover server processes:
   ```bash
   # Find processes on port 8765
   lsof -ti:8765

   # Kill them
   kill -9 $(lsof -ti:8765)
   ```

---

## Summary Checklist

Before committing tests:

- [ ] Run `./check.sh` (black, ruff, mypy, pytest)
- [ ] All tests pass locally
- [ ] No real API keys used
- [ ] Integration tests marked with `@pytest.mark.integration`
- [ ] E2E tests use `xdist_group(name="e2e_server")`
- [ ] E2E tests have cleanup fixture with `time.sleep(2)`
- [ ] Playwright tests use sync `def`, not `async def`
- [ ] Proper wait patterns for async operations
- [ ] Tests use temporary directories (fixtures)
- [ ] No shared mutable state between tests

---

**Remember:** When in doubt, check this document or look at existing tests for patterns. Consistency is key to maintaining a reliable test suite!
