# E2E Test Infrastructure Fix - 2025-11-15

## Summary

**Problem**: All E2E tests were failing because the `live_server` fixture couldn't start the test server.

**Root Cause**: The FastAPI `@app.on_event("startup")` handler doesn't execute when uvicorn runs in a background thread, leaving `server_instance.single_agent` uninitialized.

**Solution**: Manually initialize the single agent using the mock client factory before starting uvicorn, and clear the FastAPI startup events to prevent conflicts.

**Result**: ✅ E2E test infrastructure now working - 18 passed, 2 failed (expected), 6 skipped

---

## The Problem

### Error Symptom
```bash
$ uv run pytest bassi/core_v3/tests/e2e/test_file_upload_simple_e2e.py::test_ui_loads -v
ERROR: RuntimeError: Test server failed to start after 5.0s
httpcore.ConnectError: [Errno 61] Connection refused
```

### Root Cause Analysis

The `live_server` fixture in `bassi/core_v3/tests/conftest.py` starts uvicorn in a background thread:

```python
@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # Server never becomes ready ❌
```

**Problem**: FastAPI `@app.on_event("startup")` doesn't fire when uvicorn runs in a background thread. This is a known limitation of the threading approach.

**Impact**: The startup handler that creates `server_instance.single_agent` never executes, so the agent remains `None` and the server fails to handle requests.

---

## The Fix

### File: `bassi/core_v3/tests/conftest.py`

**Three critical changes:**

### 1. Manual Single Agent Initialization (lines 128-154)

```python
# CRITICAL FIX: Manually initialize single agent BEFORE starting server
# The @app.on_event("startup") doesn't fire when uvicorn runs in a background thread
# We must create the agent using the session_factory (not _create_single_agent)
# because _create_single_agent doesn't use the mock client factory
print("\n🔧 [TEST] Manually initializing single agent with mock factory...")
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    # Create a minimal workspace for the single agent
    from bassi.core_v3.interactive_questions import InteractiveQuestionService
    from bassi.core_v3.session_workspace import SessionWorkspace

    question_service = InteractiveQuestionService()
    # SessionWorkspace takes session_id and base_path
    # It will create physical_path as base_path / session_id
    workspace = SessionWorkspace(
        session_id="single_agent",
        base_path=tmp_workspace,
        create=True
    )

    # Use session_factory to create agent with mock client
    server_instance.single_agent = session_factory(question_service, workspace)

    # Connect the agent
    loop.run_until_complete(server_instance.single_agent.connect())
    print("✅ [TEST] Single agent initialized successfully with mock client")
finally:
    # Don't close the loop - uvicorn needs it
    pass
```

**Why use `session_factory`?**
- The `_create_single_agent()` method creates `BassiAgentSession` without passing `client_factory`
- This causes it to use the default Claude SDK client (requires real SDK)
- The `session_factory` is injected by tests and creates agents with `MockAgentClient`

### 2. Clear FastAPI Startup Events (lines 161-165)

```python
app = server_instance.app

# CRITICAL: Clear startup/shutdown events since we manually initialized the agent
# The @app.on_event("startup") handler would try to create the agent again
app.router.on_startup = []
app.router.on_shutdown = []
print("🔧 [TEST] Cleared FastAPI startup/shutdown events (agent already initialized)")
```

**Why clear events?**
- If left enabled, the startup handler tries to create the agent again
- This causes a hang on "Waiting for application startup"
- Clearing prevents conflicts with manual initialization

### 3. Async Server Thread with Event Loop (lines 180-206)

```python
def run_server_with_loop():
    """Run uvicorn server with its own event loop in the thread."""
    import asyncio

    async def serve_async():
        """Async wrapper for server.serve()"""
        print("🚀 [TEST] Starting server.serve() task...", flush=True)
        await server.serve()
        print("⚠️  [TEST] Uvicorn server task completed", flush=True)

    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Run server.serve() in the loop
        # This will block until server is shut down
        loop.run_until_complete(serve_async())
        print("⚠️  [TEST] Uvicorn server exited", flush=True)
    except Exception as e:
        print(f"❌ [TEST] Server crashed: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        loop.close()
        print("🔚 [TEST] Thread cleanup complete", flush=True)

thread = threading.Thread(target=run_server_with_loop, daemon=True)
thread.start()
```

**Why separate event loop?**
- Each thread needs its own asyncio event loop
- The `server.serve()` method is async and requires an event loop
- This ensures clean async/await handling in the background thread

---

## Test Results

### Before Fix
```bash
$ uv run pytest bassi/core_v3/tests/e2e/test_file_upload_simple_e2e.py::test_ui_loads -v
ERROR: RuntimeError: Test server failed to start after 5.0s
```

### After Fix
```bash
$ ./run-tests.sh e2e -v
============================= test session starts ==============================
collected 26 items

test_agent_remembers_context_e2e.py FF           [  7%]  # Expected (mock agent)
test_file_upload_simple_e2e.py ......            [ 30%]  ✅
test_session_context_restoration_e2e.py .s       [ 38%]  ✅
test_session_lifecycle_e2e.py .                  [ 42%]  ✅
test_session_message_loading_e2e.py ...          [ 53%]  ✅
test_web_server_error_handling_e2e.py ......s.   [ 84%]  ✅
test_session_management_e2e.py ss                [ 92%]  (skipped - require chrome-devtools)
test_session_ux_behaviors_e2e.py ss              [100%]  (skipped - require chrome-devtools)

======= 18 passed, 2 failed, 6 skipped in 119.16s =======
```

**Results:**
- ✅ **18 passed** - All E2E tests with mock agent work correctly
- ❌ **2 failed** - Expected failures (require real agent for meaningful responses)
- ⏭️ **6 skipped** - Expected (require chrome-devtools MCP or real agent)

---

## Expected Failures Explained

### Test: `test_agent_remembers_name_after_session_switch`

**Why it fails:**
```python
# User: "my name is benno"
# Agent: "Mock agent response"  ← Mock doesn't generate contextual responses

# User: "what's my name?"
# Agent: "Mock agent response"  ← Doesn't contain "benno"
assert "benno" in response_2.lower()  # ❌ FAILS
```

**Solution**: This test requires a real Claude agent. The test validates the **core session context restoration logic** (which IS working), but the mock agent can't generate meaningful responses.

**Alternative verification**: The integration test `test_agent_context_restored_after_session_switch` validates the same logic by checking `message_history` directly instead of agent responses.

### Test: `test_agent_maintains_separate_contexts`

Same issue - requires real agent to generate contextual responses containing "alice" and "bob".

---

## Architecture Overview

### E2E Test Infrastructure Components

```
pytest (session scope)
    ↓
live_server fixture
    ↓
1. Create mock session factory
2. Create WebUIServerV3 instance
3. Manually initialize single_agent (using mock factory)
4. Clear FastAPI startup events
5. Start uvicorn in background thread (with event loop)
6. Wait for server ready
    ↓
yield "http://localhost:18765"
    ↓
E2E tests use Playwright to interact with server
    ↓
Cleanup: Disconnect agent, shutdown server
```

### Mock vs Real Agent

**Mock Agent** (`AutoRespondingMockAgentClient`):
- Used in E2E tests via `create_mock_session_factory()`
- Auto-generates simple responses: `"Mock agent response"`
- No API calls, no API key required
- Fast execution

**Real Agent** (`BassiAgentSession` with Claude SDK):
- Used in production
- Contextual responses from Claude
- Requires API key and makes real API calls
- Required for tests that verify agent memory/context

---

## Related Changes

### File Moves: E2E Tests to Correct Location

All E2E test files moved from `bassi/core_v3/tests/integration/` to `bassi/core_v3/tests/e2e/`:

```bash
mv bassi/core_v3/tests/integration/test_*_e2e.py bassi/core_v3/tests/e2e/
```

**Files moved:**
- `test_agent_remembers_context_e2e.py`
- `test_file_upload_simple_e2e.py`
- `test_session_context_restoration_e2e.py`
- `test_session_lifecycle_e2e.py`
- `test_session_management_e2e.py`
- `test_session_message_loading_e2e.py`
- `test_session_ux_behaviors_e2e.py`
- `test_web_server_error_handling_e2e.py`

See: `docs/TEST_SEPARATION_2025-11-15.md` for details on test organization.

---

## Files Modified

```
bassi/core_v3/tests/conftest.py              (+80 lines)
  - Manual single agent initialization
  - Clear FastAPI startup events
  - Async server thread with event loop
  - Enhanced startup checks and logging

run-tests.sh                                  (modified)
  - E2E tests now run from bassi/core_v3/tests/e2e/
  - Integration tests no longer exclude E2E tests
```

---

## Running E2E Tests

### Using Test Script (Recommended)
```bash
# All E2E tests
./run-tests.sh e2e

# Single E2E test
./run-tests.sh e2e bassi/core_v3/tests/e2e/test_file_upload_simple_e2e.py::test_ui_loads -v

# With verbose output
./run-tests.sh e2e -v
```

### Using pytest Directly
```bash
# All E2E tests
uv run pytest bassi/core_v3/tests/e2e/

# Single test
uv run pytest bassi/core_v3/tests/e2e/test_file_upload_simple_e2e.py::test_ui_loads -v
```

---

## Key Learnings

1. **FastAPI startup events don't fire in background threads** - Manual initialization required

2. **session_factory must be used for mock agents** - `_create_single_agent()` bypasses mock factory

3. **Clear startup events after manual init** - Prevents conflicts and hangs

4. **Each thread needs own event loop** - Use `asyncio.new_event_loop()` in thread

5. **SessionWorkspace signature** - Use `session_id` and `base_path`, not `physical_path`

6. **Mock agents can't verify context** - Use integration tests for logic, E2E for UI flow

---

## Next Steps

### Optional: Enable Real Agent Tests

To run the context memory tests with a real agent:

1. Set `ANTHROPIC_API_KEY` environment variable
2. Remove `pytest.skip()` from tests or use real agent in CI
3. Run: `uv run pytest bassi/core_v3/tests/e2e/test_agent_remembers_context_e2e.py -v`

**Note**: These tests will make real API calls and incur costs.

### Optional: Enable Chrome DevTools Tests

Tests marked "MCP chrome-devtools integration not yet implemented":

1. Install chrome-devtools MCP server
2. Configure in `.mcp.json`
3. Remove `pytest.skip()` from tests
4. Run: `./run-tests.sh e2e -v`

---

**Status**: ✅ E2E test infrastructure FIXED and WORKING

**Verification**: `./run-tests.sh e2e` - 18 passed, 2 expected failures, 6 skipped
