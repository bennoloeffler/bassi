# Repository Cleanup Plan - V3 Transition

**Status**: PLAN ONLY - DO NOT EXECUTE YET
**Date**: 2025-11-02
**Purpose**: Clean up obsolete V1/V2 code now that V3 is working

---

## Executive Summary

V3 is working and uses the Claude Agent SDK architecture. All V1 and V2 implementations are now obsolete and should be archived to prevent confusion.

**Key Findings**:
1. ✅ V3 backend hot reload WORKS (uvicorn watches `.py` files)
2. ❌ V3 browser hot reload MISSING (no cache-control middleware)
3. 📦 Significant obsolete code can be removed (~8 files + entire `core_v2/` directory)
4. 📚 Many obsolete docs (45 total, ~30 are V1/V2 related)

---

## Hot Reload Analysis

### Backend Hot Reload (Python Files) ✅ WORKS

**Current Implementation** (bassi/core_v3/web_server_v3.py:640-649):
```python
config = uvicorn.Config(
    app=self.app,
    host=self.host,
    port=self.port,
    log_level="info",
    reload=reload,  # ✅ ENABLED
    reload_dirs=[str(Path(__file__).parent.parent)] if reload else None,
)
```

**Status**: ✅ WORKING
- Watches: `bassi/**/*.py` (all Python files in bassi directory)
- Reload time: ~2-3 seconds
- Triggered by: Any .py file change in bassi/

**How to Test**:
```bash
./run-web-v3.py
# Edit any .py file in bassi/
# Server automatically restarts in 2-3 seconds
```

---

### Browser Hot Reload (Static Files) ❌ MISSING

**Problem**: V3 is MISSING the cache-control middleware that V1 has.

**V1 Implementation** (bassi/web_server.py:256-273):
```python
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

**V3 Implementation**: ❌ MISSING ENTIRELY

**Impact**:
- Browser caches `app.js`, `style.css`, `index.html`
- Changes to static files require manual browser refresh (F5)
- During development, this is VERY annoying

**Solution Options**:

#### Option A: Add Cache-Control Middleware (Recommended)
**Pros**:
- Simple fix (~15 lines of code)
- Works with manual F5 refresh
- No external dependencies
- Consistent with V1 approach

**Cons**:
- Still requires manual browser refresh
- Not true "live reload"

**Implementation**:
Add to `bassi/core_v3/web_server_v3.py` in `_setup_routes()`:
```python
@self.app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response
```

#### Option B: Add Browser Live Reload (Advanced)
**Pros**:
- Automatic page refresh on file change
- Best developer experience
- No manual F5 needed

**Cons**:
- More complex (~100 lines)
- Adds EventSource/SSE endpoint
- Adds file watcher for static files
- More moving parts

**Implementation**:
1. Add `/events` SSE endpoint
2. Add watchfiles dependency for static file watching
3. Add client-side EventSource in app.js
4. Broadcast reload events on file change

**Code Sketch**:
```python
# Server side (web_server_v3.py)
@self.app.get("/events")
async def sse_endpoint(request: Request):
    async def event_stream():
        while True:
            if await request.is_disconnected():
                break
            yield f"data: ping\n\n"
            await asyncio.sleep(30)
    return StreamingResponse(event_stream(), media_type="text/event-stream")

# Client side (app.js)
if (location.hostname === 'localhost') {
    const evtSource = new EventSource('/events');
    evtSource.onmessage = () => location.reload();
}
```

#### Recommendation
**Start with Option A** (cache-control middleware):
- Quick win (15 lines)
- Solves 90% of the pain
- Can upgrade to Option B later if needed

---

## Files to Archive/Delete

### 1. Obsolete Python Files (Move to bin/)

#### Core V2 - Entire Directory
```
bassi/core_v2/                    # DELETE ENTIRE DIRECTORY
├── __init__.py
├── agent_session.py              # V2 agent (obsolete)
├── event_store.py                # V2 event system (obsolete)
├── events.py                     # V2 events (obsolete)
├── model_adapter.py              # V2 model adapter (obsolete)
├── tool_executor.py              # V2 tool executor (obsolete)
├── plugins/
└── tests/
    ├── test_event_store.py       # V2 tests (obsolete)
    ├── test_events.py            # V2 tests (obsolete)
    └── test_tool_executor.py     # V2 tests (obsolete)
```

**Reason**: V3 uses Claude Agent SDK, V2 custom implementation is obsolete.

#### Web Servers - Old Versions
```
bassi/web_server_old.py           # DELETE - V0 implementation
bassi/web_server_v2.py            # DELETE - V2 implementation
bassi/web_server.py               # KEEP - V1 (has cache middleware we need)
```

**Note**: Keep `web_server.py` temporarily to copy cache-control middleware to V3.

#### Static Files - Old Versions
```
bassi/static/app_old.js           # DELETE - obsolete frontend
```

#### Test Files - Obsolete
```
test_event_system.py              # DELETE - V2 event system tests
test_websocket.py                 # DELETE - old websocket tests
test_websocket_tools.py           # DELETE - old websocket tests
```

#### Demo/Development Scripts
```
demo_agent_v2.py                  # DELETE - V2 demo (obsolete)
run-web-v2.sh                     # DELETE - V2 launcher
run-dev.sh                        # CHECK - might still be useful?
run-uvicorn.sh                    # CHECK - might still be useful?
temp_analysis.py                  # DELETE - temporary analysis script
temp_read_emails.py               # DELETE - temporary email script
test_*.py (root level)            # REVIEW - some might be useful
```

---

### 2. Obsolete Documentation (Move to docs/archive/)

#### V2 Implementation Docs
```
docs/V2_IMPLEMENTATION_STATUS.md
docs/V2_COMPLETE.md
docs/QUICKSTART_V2.md
docs/implementation_progress_v2.md
docs/webui_architecture_rethink.md
docs/option3_implementation_plan.md
docs/implementation_complete.md
```

#### Bugfix Docs (Historical)
```
docs/bugfix_async_tool_results.md
docs/bugfix_complete_protocol_fix.md
docs/bugfix_hot_reload.md
docs/bugfix_session_isolation_and_ui.md
docs/bugfix_streaming_performance.md
docs/bugfix_streaming_protocol_final.md
docs/bugfix_tool_display_webui.md
docs/bugfix_tool_output_formatting.md
docs/bugfix_tool_output_webui.md
docs/bugfix_v3_tool_display.md
```

#### Hot Reload Docs (Partially Obsolete)
```
docs/hot_reload_development.md    # REVIEW - might have useful info
docs/HOT_RELOAD_WORKING.md        # REVIEW - might have useful info
docs/HOTRELOAD_FIX_FINAL.md       # REVIEW - might have useful info
```

#### Session/Analysis Docs (Obsolete)
```
docs/ANALYSIS_COMPLETE.md
docs/SESSION_RESUMPTION_ANALYSIS.md
docs/SESSION_RESUMPTION_SUMMARY.md
docs/INDEX_SESSION_RESUMPTION.md
docs/ENDPOINT_DEBUG.md
docs/SDK_MESSAGE_TYPES.md
```

#### Keep These Docs (Active/Useful)
```
docs/vision.md                    # ✅ KEEP - project vision
docs/design.md                    # ✅ KEEP - design philosophy
docs/requirements.md              # ✅ KEEP - technical requirements
docs/V3_ARCHITECTURE.md           # ✅ KEEP - current architecture
docs/V3_IMPLEMENTATION_COMPLETE.md # ✅ KEEP - V3 status
docs/OPENAPI_MCP_FEATURE.md       # ✅ KEEP - feature doc
docs/features_concepts/           # ✅ KEEP - all feature docs
docs/ARCHITECTURE_*.md            # ✅ KEEP - architecture docs
docs/MCP_SERVER_ARCHITECTURE.md   # ✅ KEEP - MCP docs
docs/ms_graph_implementation_guide.md # ✅ KEEP - O365 integration
docs/MS365_INTEGRATION_COMPLETE.md    # ✅ KEEP - O365 status
docs/PLAYWRIGHT_INTEGRATION_STATUS.md # ✅ KEEP - Playwright status
docs/SOFTERIA_MS365_MCP_SERVER.md     # ✅ KEEP - MCP server doc
docs/deepseek-setup.md                # ✅ KEEP - model setup
docs/agent_sdk_usage_review.md        # ✅ KEEP - SDK review
docs/ALLOWED_TOOLS_NONE_IMPLEMENTATION.md # ✅ KEEP - permission mode
```

---

## Cleanup Strategy

### Phase 1: Archive (Safe First Step)
Create archive directories, don't delete yet:

```bash
mkdir -p bin/obsolete_v2
mkdir -p bin/obsolete_scripts
mkdir -p docs/archive/v2_implementation
mkdir -p docs/archive/bugfixes
mkdir -p docs/archive/sessions
```

Move files to archive:
```bash
# V2 core
mv bassi/core_v2 bin/obsolete_v2/

# Old web servers
mv bassi/web_server_old.py bin/obsolete_v2/
mv bassi/web_server_v2.py bin/obsolete_v2/

# Old static files
mv bassi/static/app_old.js bin/obsolete_v2/

# Test files
mv test_event_system.py bin/obsolete_scripts/
mv test_websocket*.py bin/obsolete_scripts/
mv demo_agent_v2.py bin/obsolete_scripts/
mv temp_*.py bin/obsolete_scripts/

# Scripts
mv run-web-v2.sh bin/obsolete_scripts/

# Docs
mv docs/V2_*.md docs/archive/v2_implementation/
mv docs/bugfix_*.md docs/archive/bugfixes/
mv docs/*SESSION*.md docs/archive/sessions/
mv docs/ANALYSIS_COMPLETE.md docs/archive/sessions/
mv docs/ENDPOINT_DEBUG.md docs/archive/sessions/
mv docs/SDK_MESSAGE_TYPES.md docs/archive/sessions/
```

### Phase 2: Verify V3 Still Works
After archiving, run comprehensive tests:

```bash
# Run V3 server
./run-web-v3.py

# Check web UI
# - Open http://localhost:8765
# - Send a message
# - Verify tools work
# - Verify /help works

# Run tests
./check.sh

# Check agent CLI
./run-agent.sh
```

### Phase 3: Delete Archive (After Confirmation)
Once V3 is verified working for 1-2 weeks:

```bash
rm -rf bin/obsolete_v2
rm -rf bin/obsolete_scripts
rm -rf docs/archive
```

---

## Cleanup Execution Plan

### Before Cleanup
```bash
# 1. Create backup branch
git checkout -b backup-pre-cleanup
git add -A
git commit -m "Backup before V3 cleanup"
git checkout main

# 2. Create archive directories
mkdir -p bin/obsolete_v2
mkdir -p bin/obsolete_scripts
mkdir -p docs/archive/{v2_implementation,bugfixes,sessions}
```

### Execute Cleanup
```bash
# 3. Move V2 core
git mv bassi/core_v2 bin/obsolete_v2/

# 4. Move old web servers (keep web_server.py for now)
git mv bassi/web_server_old.py bin/obsolete_v2/
git mv bassi/web_server_v2.py bin/obsolete_v2/

# 5. Move old static files
git mv bassi/static/app_old.js bin/obsolete_v2/

# 6. Move test files
git mv test_event_system.py bin/obsolete_scripts/
git mv test_websocket.py bin/obsolete_scripts/
git mv test_websocket_tools.py bin/obsolete_scripts/

# 7. Move demo/temp files
git mv demo_agent_v2.py bin/obsolete_scripts/
git mv temp_analysis.py bin/obsolete_scripts/
git mv temp_read_emails.py bin/obsolete_scripts/

# 8. Move scripts
git mv run-web-v2.sh bin/obsolete_scripts/

# 9. Move docs
git mv docs/V2_*.md docs/archive/v2_implementation/
git mv docs/bugfix_*.md docs/archive/bugfixes/
git mv docs/*SESSION*.md docs/archive/sessions/
git mv docs/ANALYSIS_COMPLETE.md docs/archive/sessions/
git mv docs/ENDPOINT_DEBUG.md docs/archive/sessions/
git mv docs/SDK_MESSAGE_TYPES.md docs/archive/sessions/
git mv docs/implementation_complete.md docs/archive/v2_implementation/
git mv docs/implementation_progress_v2.md docs/archive/v2_implementation/
git mv docs/webui_architecture_rethink.md docs/archive/v2_implementation/
git mv docs/option3_implementation_plan.md docs/archive/v2_implementation/
```

### After Cleanup
```bash
# 10. Update .gitignore to ignore bin/
echo "bin/" >> .gitignore

# 11. Run tests
./check.sh

# 12. Test V3
./run-web-v3.py
# Open http://localhost:8765 and verify

# 13. Commit
git add -A
git commit -m "Archive obsolete V1/V2 code - V3 is now primary"

# 14. Create docs update commit
# Update README.md to remove V2 references
git add README.md
git commit -m "docs: Update README for V3-only codebase"
```

---

## Hot Reload Implementation Plan

### Step 1: Add Cache-Control Middleware to V3
**File**: `bassi/core_v3/web_server_v3.py`
**Location**: In `_setup_routes()` method, right after `def _setup_routes(self):`

```python
def _setup_routes(self):
    """Set up FastAPI routes"""

    # Add cache-control middleware for development
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

    # Serve static files (existing code below)
    static_dir = Path(__file__).parent.parent / "static"
    # ... rest of existing code
```

### Step 2: Test Cache-Control
```bash
# 1. Start V3 server
./run-web-v3.py

# 2. Open browser DevTools (F12)
# 3. Go to Network tab
# 4. Load http://localhost:8765
# 5. Check response headers for /static/app.js:
#    - Cache-Control: no-cache, no-store, must-revalidate
#    - Pragma: no-cache
#    - Expires: 0

# 6. Edit bassi/static/app.js (add console.log)
# 7. Refresh browser (F5)
# 8. Verify change appears (no hard refresh needed)
```

### Step 3: Document Hot Reload (Optional)
Create `docs/HOT_RELOAD_V3.md`:

```markdown
# Hot Reload in V3

## Backend (Python Files) ✅
- **Watches**: bassi/**/*.py
- **Tool**: uvicorn --reload
- **Trigger**: Save any .py file
- **Time**: 2-3 seconds
- **Automatic**: Yes

## Frontend (Static Files) ✅
- **Watches**: Browser cache-control headers
- **Tool**: FastAPI middleware
- **Trigger**: Manual F5 refresh
- **Time**: Instant
- **Automatic**: No (requires F5)

## Usage
1. Start: `./run-web-v3.py`
2. Edit Python: Auto-reloads
3. Edit JS/CSS/HTML: Press F5

## Future Enhancement
Add browser live reload with EventSource/SSE for automatic page refresh.
```

---

## Testing Plan

### Before Cleanup
- [x] V3 web UI works ✅
- [x] V3 backend hot reload works ✅
- [ ] V3 browser hot reload works (needs middleware)

### After Cleanup
- [ ] V3 web UI still works
- [ ] V3 tests pass (`./check.sh`)
- [ ] V3 agent CLI works (`./run-agent.sh`)
- [ ] No import errors from removed modules
- [ ] Documentation is accurate

### After Hot Reload Fix
- [ ] Static file changes visible with F5
- [ ] No browser hard-refresh needed (Ctrl+Shift+R)
- [ ] Cache headers present in response

---

## Summary of Changes

### Files to Archive (Move to bin/)
- **V2 Core**: `bassi/core_v2/` (entire directory)
- **Old Web Servers**: `web_server_old.py`, `web_server_v2.py`
- **Old Static**: `app_old.js`
- **Test Files**: `test_event_system.py`, `test_websocket*.py`
- **Scripts**: `demo_agent_v2.py`, `run-web-v2.sh`, `temp_*.py`

### Docs to Archive (Move to docs/archive/)
- **V2 Docs**: 7 files
- **Bugfix Docs**: 9 files
- **Session Docs**: 5 files
- **Total**: ~21 obsolete docs

### Files to Keep
- **V3 Core**: `bassi/core_v3/` ✅
- **Web Server V1**: `bassi/web_server.py` (temporarily, for cache middleware)
- **Active Docs**: ~15 files (vision, design, architecture, features)
- **Current Static**: `index.html`, `app.js`, `style.css`

### Code to Add
- **Cache-Control Middleware**: ~15 lines in `web_server_v3.py`

---

## Risk Assessment

### Low Risk
- Archiving V2 code (not used anymore)
- Adding cache-control middleware (proven pattern from V1)

### Medium Risk
- Deleting test files (some might have useful patterns)
- Moving docs (might need to reference them)

### Mitigation
1. **Archive first, delete later** (Phase 1-3 approach)
2. **Create backup branch** before cleanup
3. **Keep archive for 2 weeks** before permanent deletion
4. **Comprehensive testing** after each phase

---

## Questions for User

1. **Should we execute cleanup now or wait?**
   - Recommendation: Add hot reload fix first, then cleanup

2. **Archive strategy:**
   - Option A: Move to `bin/` (local only, .gitignored)
   - Option B: Move to `docs/archive/` (committed to git)
   - Recommendation: Option A for code, Option B for docs

3. **Hot reload preference:**
   - Option A: Cache-control only (F5 to refresh)
   - Option B: Full live reload (auto refresh)
   - Recommendation: Option A (simpler, good enough)

4. **Test file review:**
   - Some test_*.py files might have useful patterns
   - Should we review before archiving?
   - Recommendation: Quick review, keep useful ones

---

## Next Steps (Do Not Execute Yet)

1. **Review this plan** with user
2. **Get approval** for cleanup strategy
3. **Add cache-control middleware** to V3 (low risk)
4. **Test hot reload** works correctly
5. **Execute Phase 1** (archive files)
6. **Test V3 thoroughly**
7. **Wait 1-2 weeks** for stability
8. **Execute Phase 3** (delete archive)
9. **Update documentation**

**END OF PLAN - WAITING FOR APPROVAL**
