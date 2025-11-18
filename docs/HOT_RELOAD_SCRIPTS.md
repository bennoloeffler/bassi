# Hot Reload Scripts

## Overview

This document describes the new hot reload wrapper scripts for running Bassi in development mode with automatic file watching and reloading.

## Scripts

### `./run-agent-web.sh` - Web UI with Hot Reload

**Purpose**: Start V3 web UI with automatic backend reload on file changes

**Features**:
- 🔥 Backend auto-restarts when Python files change (2-3 seconds)
- 🌐 Web UI on http://localhost:8765
- 💬 WebSocket streaming interface
- ❓ Interactive questions support
- 🔍 Startup discovery (shows available MCP servers, commands, skills)
- 📝 Logs to both stdout and `/tmp/bassi-web.log`

**Usage**:
```bash
./run-agent-web.sh
# Then open browser to http://localhost:8765
# Edit any Python file in bassi/ → server auto-restarts
# Edit static files → press F5 to reload browser
```

**How it works**:
1. Runs `uv run bassi-web` which calls `bassi/core_v3/cli.py:main()`
2. CLI sets `reload=True` when calling `start_web_server_v3()`
3. Server detects reload mode and uses uvicorn CLI with `--reload` flag
4. Uvicorn uses `watchfiles` library (built-in) to monitor `bassi/` directory
5. When Python files change, uvicorn restarts the entire server process
6. Uses `get_app()` factory function for proper reload support

**Technical Details**:
- Uses uvicorn CLI (not programmatic API) for proper reload support
- Requires `watchfiles` package (installed via `uv add watchfiles`)
- Watches: `bassi/core_v3/**/*.py` and entire `bassi/` directory
- Browser cache-control headers ensure F5 reloads frontend changes instantly

### `./run-agent-cli.sh` - CLI with Hot Reload

**Purpose**: Start V1 CLI with automatic restart on file changes

**Features**:
- 🔥 CLI auto-restarts when Python files change
- 💬 Rich console interface
- ⌨️  Keyboard shortcuts
- 💾 Session persistence (use session_id to resume after restart)

**Usage**:
```bash
./run-agent-cli.sh
# Edit any Python file in bassi/ → CLI restarts
# ⚠️ Restart loses current conversation (use session_id to resume)
```

**How it works**:
1. Uses `watchfiles` command to monitor `bassi/` directory
2. When Python files change, watchfiles kills and restarts `uv run bassi`
3. CLI session is lost on restart (by design - interactive REPL)

**Technical Details**:
- Uses `watchfiles` CLI tool (not uvicorn)
- Command: `uv run watchfiles --filter python 'uv run bassi' /path/to/bassi/`
- Ignores: `.venv/`, `__pycache__/`

## Comparison with Direct Commands

| Command | Hot Reload | When to Use |
|---------|-----------|-------------|
| `./run-agent-web.sh` | ✅ Yes (backend) | Development - frequent code changes |
| `bassi-web` | ✅ Yes (backend) | Development - same as script |
| `./run-agent-cli.sh` | ✅ Yes (full restart) | Development - testing CLI changes |
| `bassi` | ❌ No | Production - stable CLI usage |
| `bassi --web` | ❌ No | **Deprecated** - use bassi-web instead |

## Requirements

### Installed Packages
```bash
uv add watchfiles  # Already installed in pyproject.toml
```

### System Requirements
- Python 3.11+
- uv package manager
- Bash shell (for .sh scripts)

## Troubleshooting

### "WARNING: Current configuration will not reload..."

**Problem**: Uvicorn shows warning about reload not working

**Cause**: Using programmatic uvicorn API instead of CLI

**Solution**: ✅ **Fixed** - Updated `bassi/core_v3/web_server_v3.py` to use uvicorn CLI when `reload=True`

**Verification**:
```bash
./run-agent-web.sh
# Should show: "INFO: Started reloader process [PID] using WatchFiles"
# Should NOT show: "WARNING: Current configuration will not reload..."
```

### Reload Not Working

**Check**:
1. Is `watchfiles` installed? `uv pip list | grep watchfiles`
2. Are you editing files in the watched directory? (bassi/)
3. Check logs: `tail -f /tmp/bassi-web.log`

### CLI Keeps Restarting

**Problem**: CLI restarts in a loop

**Cause**: Editing files while CLI is running triggers constant restarts

**Solution**: Use `bassi` directly without hot reload when actively working in CLI

## Implementation Details

### Web Server (bassi/core_v3/web_server_v3.py)

Key changes:

1. **Conditional Reload Logic** (lines 775-807):
```python
if reload:
    # Use uvicorn CLI for proper reload support
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "bassi.core_v3.web_server_v3:get_app",
        "--factory",
        "--host", self.host,
        "--port", str(self.port),
        "--reload",
        "--reload-dir", reload_dir,
    ], check=True)
else:
    # Use programmatic API for production
    config = uvicorn.Config(app=self.app, ...)
    server = uvicorn.Server(config)
    await server.serve()
```

2. **App Factory** (lines 911-918):
```python
def get_app():
    """Get or create the FastAPI app instance for uvicorn CLI"""
    global _app_instance
    if _app_instance is None:
        session_factory = create_default_session_factory()
        server = WebUIServerV3(session_factory, "localhost", 8765)
        _app_instance = server.app
    return _app_instance
```

## Deleted Files

The following deprecated scripts were removed:

- `run-agent.sh` - Replaced by `run-agent-web.sh`
- `run-web-v3.py` - Replaced by `bassi-web` command

## Related Documentation

- `docs/DUAL_MODE_IMPLEMENTATION.md` - V1 vs V3 architecture
- `docs/features_concepts/startup_discovery.md` - Startup discovery feature
- `CLAUDE.md` - Development commands reference
