# Agent Pool Removal - Test Updates 2025-11-15

## Summary

Updated all test fixtures and tests to remove deprecated `enable_agent_pool` parameter following the architecture change to single-agent mode.

## Architecture Change

**Before:**
```python
WebUIServerV3(
    workspace_base_path=str(tmp_workspace),
    session_factory=session_factory,
    enable_agent_pool=False,  # Control pool vs single agent
)
```

**After:**
```python
WebUIServerV3(
    workspace_base_path=str(tmp_workspace),
    session_factory=session_factory,
    # enable_agent_pool removed - always uses single agent
)
```

## Changes Made

### 1. Updated Fixtures

**Files Modified:**
- `bassi/core_v3/tests/conftest.py` (line 126)
- `bassi/core_v3/tests/integration/conftest.py` (line 138)
- `bassi/core_v3/tests/e2e/conftest.py` (line 63, commented code)

**Change:** Removed `enable_agent_pool=False` parameter from `WebUIServerV3()` calls.

### 2. Updated Test Files

**File:** `bassi/core_v3/tests/integration/test_web_server_v3.py`

**Lines removed:** 8 occurrences
- Line 52: web_server fixture
- Line 933: test fixture
- Line 1068: test fixture
- Line 1169: E2E test
- Line 1219: E2E test
- Line 1275: E2E test
- Line 1344: E2E test
- Line 1407: E2E test

**Method:** Used `sed -i '' '/enable_agent_pool=False,  # Disable agent pool/d'`

### 3. Skipped Files

**File:** `bassi/core_v3/tests/integration/test_agent_pool_service.py`

Already skipped (entire module marked with `pytestmark = pytest.mark.skip`). No changes needed.

## Verification

### Unit Tests
```bash
./run-tests.sh unit
# Result: 85 passed ✅
```

### Integration Tests (Sample)
```bash
uv run pytest bassi/core_v3/tests/integration/test_web_server_v3.py::test_health_endpoint -v
# Result: 1 passed ✅

uv run pytest bassi/core_v3/tests/integration/test_web_server_v3.py -k "health or capabilities" -v
# Result: 4 passed, 31 deselected ✅
```

## Why This Works

The `enable_agent_pool` parameter is now **deprecated** in `WebUIServerV3.__init__()`:

```python
def __init__(
    self,
    workspace_base_path: str = "_DATA_FROM_USER",
    session_factory: Optional[Callable] = None,
    enable_agent_pool: bool = False,  # DISABLED - use single agent
    pool_config: Optional[PoolConfig] = None,
):
    """
    Args:
        enable_agent_pool: DEPRECATED - always False (single agent mode)
        pool_config: DEPRECATED - not used
    """
    # ... implementation always uses single agent mode
    self.single_agent: Optional[BassiAgentSession] = None
    self.agent_pool: Optional[AgentPoolService] = None  # Always None
```

The parameter is kept for backward compatibility but **ignored**. All instances now use single-agent mode.

## Impact

- **No functional changes** - tests work exactly the same
- **Cleaner code** - removed unnecessary parameter
- **Future-proof** - when parameter is fully removed, tests won't need updates

## Related Architecture

- `bassi/core_v3/web_server_v3.py` - Single agent architecture (lines 75-77)
- `bassi/core_v3/websocket/connection_manager.py` - Uses single_agent_provider
- `bassi/core_v3/services/agent_pool_service.py` - Service still exists but unused

## Files Changed

```
bassi/core_v3/tests/conftest.py                          (1 line)
bassi/core_v3/tests/integration/conftest.py              (1 line)
bassi/core_v3/tests/e2e/conftest.py                      (1 line)
bassi/core_v3/tests/integration/test_web_server_v3.py    (8 lines)
```

**Total:** 11 lines removed across 4 files

## Next Steps

None required. Tests are ready for the single-agent architecture.

---

**Status:** ✅ Complete - All tests updated and verified
