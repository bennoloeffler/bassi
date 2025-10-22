# Fully Dynamic Tool Discovery: `allowed_tools=None` Implementation

**Date**: 2025-01-22
**Status**: ✅ Implemented and Tested
**Impact**: MAJOR - Eliminates all manual tool list maintenance

---

## Summary

Bassi now uses `allowed_tools=None` to enable **fully automatic tool discovery and allowlisting** from MCP servers. This eliminates the need to manually maintain tool lists when adding/removing MCP servers or tools.

---

## The Problem

**Before** (Manual Tool Lists):
```python
# Lines 177-213 in agent.py (OLD)
allowed_tools = [
    "mcp__bash__execute",
    "mcp__web__search",
    "mcp__task_automation__execute_python",  # Had to manually add!
]

# Add MS365 tools if configured
if "ms365" in self.external_mcp_servers:
    ms365_tools = [
        "mcp__ms365__login",
        "mcp__ms365__verify-login",
        ... # 6 tools hardcoded
    ]
    allowed_tools.extend(ms365_tools)

# Add Playwright tools if configured
if "playwright" in self.external_mcp_servers:
    playwright_tools = [
        "mcp__playwright__browser_navigate",
        ... # 8 tools hardcoded
    ]
    allowed_tools.extend(playwright_tools)
```

**Issues**:
- ❌ Manual maintenance required for every new tool
- ❌ Easy to forget to add tools (task_automation was missing!)
- ❌ Doesn't scale (imagine 50+ tools)
- ❌ Code drift when tools change
- ❌ Defeats the purpose of "dynamic" discovery

---

## The Solution

**After** (`allowed_tools=None`):
```python
# Lines 176-181 in agent.py (NEW)
# Dynamic tool discovery: allowed_tools=None means "allow ALL discovered tools"
# This eliminates the need to manually maintain tool lists
# The Agent SDK will automatically discover and inject all tools from MCP servers
allowed_tools = None  # Allow all discovered tools!

logger.info("🔓 Dynamic tool discovery enabled - all MCP tools allowed")
```

**Benefits**:
- ✅ **Zero maintenance** - Add MCP servers, tools are automatically available
- ✅ **Scales effortlessly** - Works with 10 or 1000 tools
- ✅ **Always accurate** - No code drift or stale lists
- ✅ **True dynamic discovery** - SDK handles everything
- ✅ **"Dangerously-skip-permissions"** - Exactly what the user requested!

---

## How It Works

### Parameter Semantics

The `allowed_tools` parameter in `ClaudeAgentOptions` has three states:

| Value | Meaning | Use Case |
|-------|---------|----------|
| `None` | Allow ALL discovered tools | Fully autonomous agents |
| `[]` (empty list) | Allow none (restrictive) | Limited agents |
| `[...]` (explicit list) | Allow only specific tools | Controlled environments |

### Discovery Flow

```
┌─────────────────────────────────────────────────────────┐
│  Startup: allowed_tools=None                             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. BassiAgent loads MCP servers:                       │
│     ├─ SDK servers (bash, web, task_automation)         │
│     └─ External servers from .mcp.json (ms365, etc.)    │
│                                                          │
│  2. Agent SDK initialization:                           │
│     ├─ Queries each server's list_tools()               │
│     ├─ Builds complete tool catalog                     │
│     └─ allowed_tools=None → ALL tools allowed!          │
│                                                          │
│  3. Claude has access to ALL discovered tools           │
│     ├─ No manual filtering                              │
│     ├─ No hardcoded lists                               │
│     └─ Automatic updates when servers change            │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### Code Changes

**File**: `bassi/agent.py`

**Lines 176-181** (Tool Allowlisting):
```python
# OLD (40+ lines of hardcoded tools)
allowed_tools = ["mcp__bash__execute", ...]
if "ms365" in self.external_mcp_servers:
    allowed_tools.extend([...])
# ... more manual lists

# NEW (6 lines, zero maintenance)
allowed_tools = None  # Allow all discovered tools!
logger.info("🔓 Dynamic tool discovery enabled - all MCP tools allowed")
```

**Lines 255-270** (Startup Display):
```python
# OLD (showed detailed tool list from allowed_tools)
total_tools = len(self.options.allowed_tools)
for tool in self.options.allowed_tools:
    # ... parse and display

# NEW (shows dynamic discovery mode)
self.console.print("📋 Tool Discovery Mode:")
self.console.print("  🔓 Dynamic Discovery Enabled")
self.console.print("  All tools from configured MCP servers are automatically allowed")
```

**File**: `bassi/mcp_servers/__init__.py`

**Line 8**: Added missing `create_task_automation_server` export

### Startup Output

**Before**:
```
📋 Total Available Tools: 16
  • Bash: 1 tool(s)
    → execute
  • Ms365: 6 tool(s)
    → login, verify-login, ...
  • Playwright: 8 tool(s)
    → browser_navigate, ...
  # task_automation MISSING!
```

**After**:
```
📋 Tool Discovery Mode:
  🔓 Dynamic Discovery Enabled - All tools from configured MCP servers are automatically allowed

  The Agent SDK will automatically discover and inject all available tools at runtime.
  No manual tool list maintenance required!
```

---

## Testing

### Verification Test

```bash
# Start bassi
./run-agent.sh

# Expected output:
# - Shows "🔓 Dynamic Discovery Enabled"
# - No manual tool list displayed
# - All MCP servers listed
```

### Functional Test

To verify tools are actually available:
1. Add a new MCP server to `.mcp.json`
2. Restart bassi
3. Server appears immediately
4. All tools from that server are automatically available to Claude
5. No code changes needed!

---

## Documentation Updates

### Updated Files

1. **`docs/features_concepts/dynamic_tool_discovery.md`**
   - Added section on `allowed_tools=None`
   - Updated version to 2.0
   - Explained parameter semantics
   - Updated "Adding New Tools" section

2. **`docs/features_concepts/permissions.md`**
   - Updated "Allowed Tools" section
   - Explained `allowed_tools=None` behavior
   - Documented benefits

3. **`bassi/mcp_servers/__init__.py`**
   - Added `create_task_automation_server` export

---

## Benefits

### For Users
✅ New MCP servers = instant tool availability
✅ No waiting for code updates
✅ Always have latest tools from configured servers

### For Developers
✅ Zero maintenance overhead
✅ No tool list synchronization
✅ Scales to unlimited tools
✅ No code drift risk

### For Operations
✅ Add/remove servers via `.mcp.json` only
✅ No deployment needed for tool changes
✅ Configuration-driven tool availability

---

## User's Original Question

**User**: "isnt there a way to allow ALL tools about like: claude --dangerously-skip-permissions"

**Answer**: YES! Setting `allowed_tools=None` is exactly that - it's the MCP equivalent of `--dangerously-skip-permissions` for tool allowlisting.

---

## Related Documentation

- **Dynamic Tool Discovery**: `docs/features_concepts/dynamic_tool_discovery.md`
- **Permissions**: `docs/features_concepts/permissions.md`
- **MCP Server Architecture**: `docs/MCP_SERVER_ARCHITECTURE.md`

---

## Future Enhancements

With `allowed_tools=None` now working, possible future improvements:

1. **Runtime Tool Discovery Display**
   - Query SDK for actual discovered tools after initialization
   - Show complete tool list at startup (like before, but dynamically)

2. **Tool Usage Analytics**
   - Track which tools are actually used
   - Identify unused MCP servers

3. **Per-Server Allowlisting**
   - Allow all tools from specific servers
   - Block tools from other servers
   - `allowed_servers` parameter?

4. **Tool Categories in SDK**
   - MCP servers expose tool categories
   - Automatic system prompt generation from categories

---

**Status**: Complete ✅
**Next Steps**: Monitor tool discovery in production, gather user feedback
