# Hot Reload - Final Solution

**Date**: 2025-10-31
**Status**: ✅ WORKING
**Severity**: CRITICAL (development blocker)

---

## The Problem

Hot reload didn't work at all - neither for Python files nor static files (JS/CSS).

Changes to files didn't trigger any server restart.

---

## Root Cause Analysis

### The Fatal Flaw: Python Interpreter Mismatch

When running `uv run uvicorn ...`, here's what happened:

1. `uv run` set up the correct Python environment (`.venv/bin/python3`)
2. Started uvicorn reloader process with correct Python ✓
3. Uvicorn spawned a **CHILD PROCESS** (worker) to run the app
4. The child process used **WRONG PYTHON** → `/Users/benno/.pyenv/versions/3.10.13/bin/python3` ❌
5. Wrong Python didn't have `claude_agent_sdk` installed ❌
6. Worker crashed with `ModuleNotFoundError` ❌
7. Reloader couldn't detect this and kept trying ❌

**Evidence from logs**:
```
File "/Users/benno/.pyenv/versions/3.10.13/lib/python3.10/site-packages/uvicorn/server.py"
...
ModuleNotFoundError: No module named 'claude_agent_sdk'
```

Notice: `/Users/benno/.pyenv/versions/3.10.13/` - this is WRONG Python!

### Why `uv run` Failed

`uv run` works by:
1. Activating the virtualenv for the FIRST process
2. But child processes inherit `$PATH` from parent
3. Pyenv's Python was earlier in `$PATH`
4. Uvicorn spawned subprocess picked up wrong Python

---

## The Solution

**Use the FULL PATH to project's Python directly!**

### Before (BROKEN):
```bash
uv run uvicorn bassi.web_server:create_app ...
```

### After (WORKS):
```bash
.venv/bin/python3 -m uvicorn bassi.web_server:create_app ...
```

---

## How to Use Hot Reload

### Option 1: Use the Script (EASIEST)

```bash
./run-uvicorn.sh
```

This script:
- Uses `.venv/bin/python3` directly
- Starts uvicorn with `--reload` flag
- Watches ALL Python files in the project
- Auto-restarts in ~2-3 seconds on any change

### Option 2: Manual Command

```bash
cd /path/to/bassi
.venv/bin/python3 -m uvicorn bassi.web_server:create_app --factory \
  --host localhost \
  --port 8765 \
  --reload
```

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│ .venv/bin/python3 -m uvicorn ...  --reload                  │
│                                                              │
│  ┌──────────────────────────────────┐                       │
│  │ Reloader Process (watches files) │                       │
│  │ PID: 84403                       │                       │
│  │ Python: .venv/bin/python3  ✓     │                       │
│  └────────────┬─────────────────────┘                       │
│               │ spawns                                       │
│               │                                              │
│               v                                              │
│  ┌──────────────────────────────────┐                       │
│  │ Worker Process (runs app)        │                       │
│  │ PID: 84406 → 84995 (on reload)   │                       │
│  │ Python: .venv/bin/python3  ✓     │                       │
│  │ Has claude_agent_sdk!  ✓         │                       │
│  └──────────────────────────────────┘                       │
│                                                              │
│  File change detected → Kill worker → Spawn new worker      │
└─────────────────────────────────────────────────────────────┘
```

---

## Verification

```bash
# Terminal 1: Start server
./run-uvicorn.sh

# Terminal 2: Watch logs
tail -f /tmp/bassi_uvicorn.log

# Terminal 3: Make a change
echo "" >> bassi/agent.py

# Check Terminal 2 - you should see:
# WARNING:  StatReload detected changes in 'bassi/agent.py'. Reloading...
# INFO:     Shutting down
# INFO:     Started server process [NEW_PID]
# INFO:     Application startup complete.
```

---

## Files Modified

1. **`run-uvicorn.sh`** (NEW)
   - Simple script to run uvicorn with correct Python
   - Uses `.venv/bin/python3` directly

2. **`bassi/web_server.py`**
   - Added `create_app()` factory function
   - Reads config from environment variables
   - Works with uvicorn's `--factory` flag

---

## What About Static Files (JS/CSS)?

Uvicorn's `--reload` flag ONLY watches Python files by default.

**For static files**:
- Edit JS/CSS files
- Browser caches them aggressively
- Solution: Added no-cache headers in `web_server.py` middleware
- Just refresh browser (F5) - no hard refresh needed!

**Browser auto-refresh** (optional):
Install a browser extension like "Live Reload" or "Auto Refresh" to automatically reload when server restarts.

---

## Lessons Learned

1. **Never use `uv run` for long-running servers with subprocesses**
   - Subprocess inherits wrong Python
   - Always use `.venv/bin/python3` directly

2. **Uvicorn's reload is subprocess-based**
   - Reloader process watches files
   - Worker process runs app
   - On change: kill worker, spawn new one
   - Reloader PID stays same, worker PID changes

3. **ModuleNotFoundError in subprocess = wrong Python**
   - Check subprocess Python path in stack traces
   - Use `which python3` to verify

4. **Don't overcomplicate**
   - Uvicorn's built-in `--reload` works perfectly
   - No need to wrap it in custom code
   - Just use the right Python!

---

## Success Criteria

- ✅ Edit Python file → server restarts in ~2-3 seconds
- ✅ No ModuleNotFoundError
- ✅ Both reloader and worker use correct Python
- ✅ Edit JS/CSS → refresh browser sees changes
- ✅ No manual server restart needed
- ✅ Fast development iteration

---

**Status**: ✅ FULLY WORKING
**Verified**: 2025-10-31
**Breaking Changes**: None (added new script, old methods still work for non-reload)
**Production Impact**: None (reload only used in development)

---

## Quick Reference

```bash
# Development with hot reload (RECOMMENDED)
./run-uvicorn.sh

# Production (no reload)
uv run bassi --web --no-cli

# Or use systemd/docker in production
```

That's it! Hot reload now works perfectly. 🎉
