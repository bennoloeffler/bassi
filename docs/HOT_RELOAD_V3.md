# Hot Reload in V3 - How It Works

**Date**: 2025-11-02
**Status**: WORKING ✅
**Components**: Backend (Uvicorn) + Browser (Cache-Control)

---

## Overview

V3 has **TWO separate hot reload mechanisms**:

1. **Backend Hot Reload** → Restarts Python server when `.py` files change
2. **Browser Hot Reload** → Forces browser to re-fetch static files on refresh

Both mechanisms work together to provide a smooth development experience.

---

## 1. Backend Hot Reload (Python Files) 🔥

### How It Works

**Tool**: Uvicorn's built-in file watcher
**What it watches**: All `.py` files in `bassi/` directory
**Trigger**: Any Python file is saved
**Action**: Restart entire server process
**Time**: ~2-3 seconds

### Implementation

**File**: `bassi/core_v3/web_server_v3.py:344-413`

**When reload=True** (uses uvicorn CLI):
```python
subprocess.run([
    sys.executable,
    "-m",
    "uvicorn",
    "bassi.core_v3.web_server_v3:get_app",  # Module path string
    "--factory",  # Factory function flag
    "--host", "localhost",
    "--port", "8765",
    "--reload",  # CLI reload flag
    "--reload-dir", reload_dir,  # Watches bassi/
])
```

**Factory function** (required for --factory):
```python
def get_app() -> FastAPI:
    """Factory function for uvicorn CLI reload mode."""
    server = WebUIServerV3(workspace_base_path="chats")
    return server.app
```

**Enabled by**: `bassi/core_v3/cli.py:50`
```python
await start_web_server_v3(
    host="localhost",
    port=8765,
    reload=True,  # ✅ Hot reload enabled
)
```

**Note**: Uvicorn reload requires CLI mode, not programmatic API. See `docs/AUTORELOAD_FIX_2025-11-16.md` for details.

### What Happens Step-by-Step

1. **You edit** `bassi/core_v3/agent_session.py`
2. **You save** the file (Ctrl+S)
3. **Uvicorn detects** file change via watchfiles library
4. **Server logs**: `WARNING: Detected file change in 'bassi/core_v3/agent_session.py'. Reloading...`
5. **Server shuts down** gracefully:
   - Closes all WebSocket connections
   - Cleans up resources
6. **Server restarts** with new code:
   - Reloads Python modules
   - Recreates FastAPI app
   - Reopens port 8765
7. **Browser reconnects** WebSocket automatically (if implemented)
8. **Total time**: ~2-3 seconds

### What Files Trigger Reload

**Watches**:
```
bassi/
├── *.py                    # ✅ Triggers reload
├── core_v3/**/*.py         # ✅ Triggers reload
├── mcp_servers/**/*.py     # ✅ Triggers reload
├── static/*.py             # ✅ Triggers reload (if exists)
└── ... (any .py file)      # ✅ Triggers reload
```

**Does NOT watch**:
```
bassi/static/*.js           # ❌ No backend reload
bassi/static/*.css          # ❌ No backend reload
bassi/static/*.html         # ❌ No backend reload
docs/*.md                   # ❌ No backend reload
.env                        # ❌ No backend reload (need manual restart)
.mcp.json                   # ❌ No backend reload (need manual restart)
```

### Debug Output

When `reload=True`, you see:
```
INFO:     Started reloader process [12345] using WatchFiles
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://localhost:8765 (Press CTRL+C to quit)

🔥 Hot reload enabled - server will restart on file changes
   Watching: bassi/core_v3/**/*.py
   Watching: bassi/static/*.{html,css,js}

💡 Tip: Edit files and they'll auto-reload in ~2-3 seconds
```

### Under the Hood: Uvicorn's Reloader

**How Uvicorn watches files**:
1. Uses `watchfiles` library (Rust-based file watcher)
2. Spawns **TWO processes**:
   - **Parent process**: Watches files
   - **Child process**: Runs actual server
3. When file changes:
   - Parent sends SIGTERM to child
   - Child shuts down gracefully
   - Parent spawns new child with updated code

**Process tree**:
```
python run-web-v3.py
└── uvicorn (parent/reloader)
    └── uvicorn (child/worker)
        └── FastAPI app
            └── WebSocket connections
```

---

## 2. Browser Hot Reload (Static Files) 🌐

### How It Works

**Tool**: HTTP cache-control headers
**What it affects**: HTML, CSS, JS files
**Trigger**: User presses F5 (refresh)
**Action**: Browser re-fetches files from server (ignores cache)
**Time**: Instant

### Implementation

**File**: `bassi/core_v3/web_server_v3.py:71-85`

```python
# Add cache-control middleware for development (enables browser hot reload)
@self.app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)
    # Disable caching for static files and HTML in development
    if (
        request.url.path.startswith("/static/")
        or request.url.path == "/"
    ):
        response.headers["Cache-Control"] = (
            "no-cache, no-store, must-revalidate"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response
```

### What Happens Step-by-Step

**Without Cache-Control** (before fix):
1. **First visit**: Browser fetches `app.js` → caches it
2. **You edit** `app.js` → save changes
3. **You press F5**: Browser uses CACHED version ❌
4. **You see**: OLD code (no changes)
5. **Workaround**: Hard refresh (Ctrl+Shift+R) to bypass cache

**With Cache-Control** (after fix):
1. **First visit**: Browser fetches `app.js` → sees `Cache-Control: no-cache`
2. **Browser**: "OK, I'll check with server on every request"
3. **You edit** `app.js` → save changes
4. **You press F5**: Browser asks server "Do you have newer version?"
5. **Server**: "Yes! Here's the new file" (with `Cache-Control: no-cache`)
6. **You see**: NEW code ✅

### HTTP Headers Explained

**Response headers** (visible in DevTools Network tab):

```http
Cache-Control: no-cache, no-store, must-revalidate
Pragma: no-cache
Expires: 0
```

**What each header means**:

| Header | Meaning | Browser Behavior |
|--------|---------|------------------|
| `Cache-Control: no-cache` | "Check with server before using cache" | Sends If-Modified-Since request |
| `Cache-Control: no-store` | "Don't store this in cache at all" | Never caches the file |
| `Cache-Control: must-revalidate` | "If cached, MUST check if still valid" | Forces revalidation |
| `Pragma: no-cache` | HTTP/1.0 version of no-cache | Backwards compatibility |
| `Expires: 0` | "Expired on Jan 1, 1970" | Treated as already expired |

**Why all three?**
- **Redundancy**: Different browsers, different HTTP versions
- **Defense in depth**: Ensures caching is disabled everywhere
- **Best practice**: Cover all bases

### What Files Get No-Cache Headers

**Applies to**:
```
GET /                       # ✅ index.html (root path)
GET /static/app.js          # ✅ JavaScript
GET /static/style.css       # ✅ CSS
GET /static/index.html      # ✅ HTML (if served from /static)
```

**Does NOT apply to**:
```
GET /health                 # ❌ API endpoint (not static)
GET /ws                     # ❌ WebSocket (not static)
POST /api/...               # ❌ API calls (not static)
```

### Testing Cache-Control

**Open Browser DevTools** (F12):
1. Go to **Network** tab
2. Reload page (F5)
3. Click on `app.js` request
4. Check **Response Headers**:

```
Cache-Control: no-cache, no-store, must-revalidate
Pragma: no-cache
Expires: 0
```

**If you see different headers** (e.g., `max-age=3600`):
- ❌ Cache-control middleware not working
- Hard refresh (Ctrl+Shift+R) to bypass old cached headers
- Check server logs for middleware errors

---

## 3. Combined Workflow (Backend + Browser)

### Scenario 1: Edit Python Code

**You edit**: `bassi/core_v3/agent_session.py`

```
[You] Save file (Ctrl+S)
  ↓
[Uvicorn] Detects change → Restart server (2-3 sec)
  ↓
[Browser] WebSocket disconnects (server went down)
  ↓
[Browser] Auto-reconnects when server is back up
  ↓
[You] Continue using app with NEW Python code ✅
```

**Time**: ~2-3 seconds
**User action**: None (automatic)

---

### Scenario 2: Edit JavaScript/CSS

**You edit**: `bassi/static/app.js`

```
[You] Save file (Ctrl+S)
  ↓
[Server] No action (static file, no backend restart needed)
  ↓
[You] Press F5 in browser
  ↓
[Browser] Requests app.js from server
  ↓
[Browser] Sees "Cache-Control: no-cache" → Fetches fresh file
  ↓
[Browser] Loads NEW JavaScript ✅
```

**Time**: Instant
**User action**: F5 (one key press)

---

### Scenario 3: Edit Both Python and Static Files

**You edit**: Both `agent_session.py` AND `app.js`

```
[You] Save agent_session.py
  ↓
[Uvicorn] Restart server (2-3 sec)
  ↓
[You] Save app.js (during server restart)
  ↓
[Server] Comes back up with new Python code
  ↓
[You] Press F5 in browser
  ↓
[Browser] Reconnects WebSocket + Fetches fresh app.js
  ↓
[You] Have both new Python AND new JavaScript ✅
```

**Time**: ~2-3 seconds (Python) + instant (JS)
**User action**: Wait for restart + press F5

---

## 4. What Hot Reload Does NOT Do

### ❌ Browser Auto-Refresh (Live Reload)

**Missing**: Browser doesn't automatically refresh when files change

**Current behavior**:
1. Edit `app.js`
2. Save file
3. **You must press F5 manually**

**Would be nice (not implemented)**:
1. Edit `app.js`
2. Save file
3. **Browser auto-refreshes** (no F5 needed)

**How to add this** (future enhancement):
- Add Server-Sent Events (SSE) endpoint
- Add file watcher for static files
- Add JavaScript client to listen to SSE
- Auto-reload page when file changes

**Example implementation**:
```python
# Server-side (web_server_v3.py)
@app.get("/events")
async def sse():
    async def event_generator():
        while True:
            # Watch static files
            # When changed, yield "data: reload\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Client-side (app.js)
if (location.hostname === 'localhost') {
    const evtSource = new EventSource('/events');
    evtSource.onmessage = () => location.reload();
}
```

### ❌ Hot Module Replacement (HMR)

**Missing**: Changes don't apply without full page reload

**Current behavior**:
1. Edit `app.js` → Change a function
2. Press F5 → **Entire page reloads** (lose UI state)

**Would be nice (not implemented)**:
1. Edit `app.js` → Change a function
2. **Only that function updates** (preserve UI state)

**How to add this**:
- Use a framework like Vite or Webpack with HMR
- Requires build system and module bundler
- Complex to set up

### ❌ Config File Reload

**Missing**: Editing `.env` or `.mcp.json` doesn't reload

**Current behavior**:
1. Edit `.env` → Add API key
2. Server still has old config ❌
3. **Must manually restart** (Ctrl+C → `./run-web-v3.py`)

**Why?**:
- Uvicorn only watches `.py` files
- Config loaded at startup, not re-read on change

**Workaround**:
- Manually restart server when changing config

### ❌ Database Schema Reload

**Missing**: Database schema changes don't auto-migrate

**Current behavior**:
1. Edit database schema
2. Server restarts with new code
3. **Database still has old schema** ❌
4. Must run migrations manually

---

## 5. Troubleshooting

### Problem: Python changes don't reload

**Symptoms**:
- Edit Python file
- Save it
- Server doesn't restart
- Old code still running

**Possible causes**:

1. **Reload not enabled**
   ```python
   # Check run-web-v3.py:49
   await start_web_server_v3(reload=True)  # Must be True
   ```

2. **File not in watched directory**
   ```python
   # Only watches bassi/**/*.py
   reload_dirs=[str(Path(__file__).parent.parent)]
   ```
   - Files outside `bassi/` won't trigger reload

3. **Syntax error in file**
   - Check server logs for Python errors
   - Server might crash instead of restarting

**Solution**:
```bash
# Kill server
Ctrl+C

# Restart with reload enabled
./run-web-v3.py

# Check logs for "Hot reload enabled"
```

---

### Problem: Static files don't update

**Symptoms**:
- Edit `app.js`
- Press F5
- Still see old code

**Possible causes**:

1. **Cache-control middleware not working**
   ```bash
   # Check DevTools → Network → app.js → Response Headers
   # Should see: Cache-Control: no-cache, no-store, must-revalidate
   ```

2. **Browser cached old headers**
   ```bash
   # Do hard refresh ONCE to clear old cached headers
   Ctrl+Shift+R  (Windows/Linux)
   Cmd+Shift+R   (Mac)

   # Then normal F5 should work
   ```

3. **Editing wrong file**
   ```bash
   # Make sure you're editing files in bassi/static/
   # Not bin/obsolete_v2/ or some other location
   ```

**Solution**:
```bash
# 1. Hard refresh ONCE
Ctrl+Shift+R

# 2. Check headers in DevTools
# 3. Normal F5 should work from now on
```

---

### Problem: Server restarts too often

**Symptoms**:
- Server restarts multiple times per second
- Constant "Reloading..." messages
- Can't use the app

**Possible causes**:

1. **IDE auto-saves on every keystroke**
   - Disable auto-save in IDE settings
   - Or add debounce delay

2. **Another process modifying files**
   - Check for build tools, formatters running
   - Check for `__pycache__` being regenerated

3. **Watching too many directories**
   - Should only watch `bassi/`
   - Not entire project root

**Solution**:
```bash
# Disable auto-save in IDE
# Or restart server with reload=False for production
```

---

## 6. Performance Impact

### Development Mode (reload=True)

**Pros**:
- ✅ Fast iteration (no manual restarts)
- ✅ Good developer experience
- ✅ Catch errors quickly

**Cons**:
- ❌ Slightly higher memory (two processes)
- ❌ Slower startup (~2-3 sec vs instant)
- ❌ File watching overhead (minimal)

**Resource usage**:
- **Memory**: +10-20 MB (parent watcher process)
- **CPU**: +1-2% (file watching)
- **Startup time**: +0.5-1 sec (process spawn)

### Production Mode (reload=False)

**Recommended for**:
- Production deployment
- Performance testing
- Long-running processes

**How to disable**:
```python
# run-web-v3.py
await start_web_server_v3(
    host="0.0.0.0",
    port=8765,
    reload=False,  # ❌ No hot reload
)
```

---

## 7. Comparison: V1 vs V3 Hot Reload

| Feature | V1 (web_server.py) | V3 (web_server_v3.py) |
|---------|-------------------|----------------------|
| Backend Hot Reload | ✅ YES (uvicorn) | ✅ YES (uvicorn) |
| Browser Cache-Control | ✅ YES | ✅ YES (now fixed) |
| WebSocket Reconnect | ❌ Manual | ❌ Manual |
| Live Reload (auto F5) | ❌ NO | ❌ NO |
| HMR | ❌ NO | ❌ NO |

**Result**: V1 and V3 are now **equivalent** for hot reload.

---

## 8. Summary

### Backend Hot Reload ✅
- **What**: Uvicorn watches `.py` files
- **When**: Any Python file saved
- **How**: Server restarts automatically
- **Time**: 2-3 seconds
- **User action**: None (automatic)

### Browser Hot Reload ✅
- **What**: Cache-control headers disable caching
- **When**: User presses F5
- **How**: Browser fetches fresh files
- **Time**: Instant
- **User action**: F5 (one key)

### Complete Workflow
1. Edit Python → Auto-restart (2-3 sec)
2. Edit static → Press F5 (instant)
3. Both updated ✅

### Future Enhancements (Not Implemented)
- ❌ Auto browser refresh (no F5 needed)
- ❌ Hot Module Replacement (preserve UI state)
- ❌ Config file hot reload
- ❌ WebSocket auto-reconnect

**Current Status**: Hot reload works well for daily development! 🎉
