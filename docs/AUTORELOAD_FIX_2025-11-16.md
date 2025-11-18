# Autoreload Fix - 2025-11-16

## Problem

Uvicorn reload was not working despite being enabled. Changes to Python files (like `session_index.py`, `cli.py`) were not triggering automatic server reload.

## Root Cause

Uvicorn's reload feature **does not work** with the programmatic `uvicorn.Config()` API. It requires:
- Using uvicorn CLI (`uvicorn` command) with `--reload` flag
- A module path string (e.g., `bassi.core_v3.web_server_v3:get_app`)
- The `--factory` flag to use a factory function

The warning message was:
```
WARNING: Current configuration will not reload as not all conditions are met, please refer to documentation.
```

## Solution

### Changes Made

1. **Updated `bassi/core_v3/web_server_v3.py`**:
   - When `reload=True`, now uses uvicorn CLI via `subprocess.run()` instead of programmatic API
   - Added `get_app()` factory function required by uvicorn's `--factory` flag
   - Properly configures `--reload-dir` to watch `bassi/` directory

2. **Updated `bassi/core_v3/cli.py`**:
   - Changed `reload=False` → `reload=True` to enable autoreload by default

3. **Updated `run-agent-web.sh`**:
   - Removed `watchfiles` wrapper (was causing double reload)
   - Now directly calls `uv run bassi-web` which uses uvicorn reload

### Implementation Details

**Before (Broken)**:
```python
config = uvicorn.Config(
    self.app,
    host="localhost",
    port=8765,
    reload=reload,  # ❌ Doesn't work programmatically
    reload_dirs=["bassi"] if reload else None,
)
server = uvicorn.Server(config)
await server.serve()
```

**After (Working)**:
```python
if reload:
    subprocess.run([
        sys.executable,
        "-m",
        "uvicorn",
        "bassi.core_v3.web_server_v3:get_app",  # ✅ Module path string
        "--factory",  # ✅ Factory function flag
        "--host", "localhost",
        "--port", "8765",
        "--reload",  # ✅ CLI reload flag
        "--reload-dir", reload_dir,
    ])
```

**Factory Function**:
```python
def get_app() -> FastAPI:
    """Factory function for uvicorn CLI reload mode."""
    server = WebUIServerV3(workspace_base_path="chats")
    return server.app
```

## Verification

After restarting the server, you should see:
```
🔥 Hot reload enabled - server will restart on file changes
INFO: Started reloader process [PID] using WatchFiles
```

Changes to any Python file in `bassi/` will now trigger automatic reload:
- `session_index.py` → ✅ Reloads
- `cli.py` → ✅ Reloads (full process restart)
- `web_server_v3.py` → ✅ Reloads
- Any other `.py` file → ✅ Reloads

## Files Modified

- `bassi/core_v3/web_server_v3.py` - Fixed reload implementation
- `bassi/core_v3/cli.py` - Enabled reload by default
- `run-agent-web.sh` - Removed watchfiles wrapper

## Related Documentation

- `docs/HOT_RELOAD_V3.md` - General hot reload documentation
- `docs/HOT_RELOAD_SCRIPTS.md` - Script documentation (needs update)

