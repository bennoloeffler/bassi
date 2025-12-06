# `/permissions` Command - Show Active Permissions

## Status: ✅ IMPLEMENTED

**Implementation Date**: 2025-12-04

The `/permissions` command is fully implemented. See "Implementation Status" section below.

## Overview

A built-in command that displays all currently active permissions in a clear, human-readable format. This helps users understand what the agent is allowed to do without asking.

## User Story

As a bassi user, I want to quickly see what permissions are active so I understand what the agent can do autonomously vs what will require my approval.

## Command Output Format

### Case 1: Global Bypass Enabled (No Restrictions)

```
/permissions

🔓 PERMISSIONS: NO RESTRICTIONS

Global bypass is ENABLED - all tools run without asking.

To enable permission checks, toggle the "brain" icon in the UI
or run: curl -X POST localhost:8765/api/settings/global-bypass -d '{"enabled":false}'
```

### Case 2: Permission Checks Active

```
/permissions

🔐 PERMISSIONS: ACTIVE

Global bypass: OFF (tools require permission)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 THIS SESSION ONLY (cleared on disconnect):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • Bash
  • Read
  • mcp__ms365__list-mail-messages

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💾 ALL SESSIONS (persistent, saved to config):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • mcp__postgresql__describe_table
  • mcp__ms365__verify-login
  • mcp__ms365__get-mail-message

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️  ONE-TIME (pending, will be consumed on next use):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • Write (1 use remaining)

Any tool NOT listed above will prompt for permission.
```

### Case 3: No Specific Permissions (Clean State)

```
/permissions

🔐 PERMISSIONS: ACTIVE

Global bypass: OFF (tools require permission)

No specific tool permissions granted yet.
Each tool use will prompt for your approval.

Permission options when prompted:
  • One-time: Allow just this invocation
  • Session: Allow for this browser session
  • Persistent: Allow forever (saved to config)
  • Global: Disable all permission checks
```

## Implementation Approach

### Option A: API Endpoint + Frontend Display (Recommended)

Create a new API endpoint that returns permission state, then display in chat.

**Backend: New endpoint in `routes/settings.py`**

```python
@router.get("/permissions", response_model=PermissionsResponse)
async def get_permissions(browser_id: Optional[str] = None):
    """Get all active permissions for display"""
    ...
```

**Response Model:**

```python
class PermissionsResponse(BaseModel):
    global_bypass: bool
    session_permissions: list[str]  # Tools allowed this session
    persistent_permissions: list[str]  # Tools allowed forever
    one_time_permissions: dict[str, int]  # Tool -> remaining uses
```

**Frontend: Handle `/permissions` as special command**

When user types `/permissions`, instead of sending to agent:
1. Call `GET /api/settings/permissions?browser_id=xxx`
2. Format response as styled message
3. Display in chat (not sent to Claude)

### Option B: Slash Command via Agent

Create `.claude/commands/permissions.md` that the agent processes.

**Pros:** Uses existing slash command system
**Cons:** Costs tokens, slower, agent might hallucinate

### Option C: Built-in WebSocket Command

Handle `/permissions` directly in WebSocket handler before sending to agent.

**Pros:** Instant, no API call needed
**Cons:** Requires frontend+backend coordination

## Recommended: Option A (API + Frontend)

1. **New API endpoint**: `GET /api/settings/permissions`
2. **Frontend intercepts** `/permissions` before sending to WebSocket
3. **Frontend calls API** and displays formatted result
4. **No tokens used**, instant response

## Data Sources

| Permission Type | Source | Lifetime |
|----------------|--------|----------|
| Global bypass | `ConfigService.get_global_bypass_permissions()` | Until toggled |
| Session | `PermissionManager.session_permissions` | Until disconnect |
| Persistent | `ConfigService.get_persistent_permissions()` | Forever (in config.json) |
| One-time | `PermissionManager.one_time_permissions` | Until used |

## Challenge: Accessing Session Permissions

Session and one-time permissions live in `PermissionManager` which is per-browser-session. The API needs to know which browser session to query.

**Solution:** Pass `browser_id` to the endpoint, look up the PermissionManager for that session.

```python
@router.get("/permissions")
async def get_permissions(browser_id: str):
    # Get the PermissionManager for this browser session
    session = browser_session_manager.get_session(browser_id)
    if session and session.permission_manager:
        session_perms = list(session.permission_manager.session_permissions.keys())
        one_time = dict(session.permission_manager.one_time_permissions)
    else:
        session_perms = []
        one_time = {}

    # Get persistent from config
    config_service = get_config_service()
    persistent = config_service.get_persistent_permissions()
    global_bypass = config_service.get_global_bypass_permissions()

    return PermissionsResponse(
        global_bypass=global_bypass,
        session_permissions=session_perms,
        persistent_permissions=persistent,
        one_time_permissions=one_time,
    )
```

## Files to Modify

1. **`bassi/core_v3/routes/settings.py`** - Add `/api/settings/permissions` endpoint
2. **`bassi/core_v3/static/js/app.js`** - Intercept `/permissions` command
3. **`bassi/core_v3/websocket/browser_session_manager.py`** - Expose method to get session's PermissionManager

## Alternative: WebSocket-Only (Simpler)

Handle entirely via WebSocket without new API:

1. Frontend sends `{"type": "command", "command": "permissions"}`
2. Backend `browser_session_manager` handles it
3. Backend sends back `{"type": "permissions_info", "data": {...}}`
4. Frontend displays formatted result

This keeps it self-contained in the WebSocket flow.

## Priority

**Medium** - Nice to have for debugging and user transparency, but not blocking core functionality.

## Implementation Status

### ✅ Completed

1. **Backend API** (`bassi/core_v3/routes/settings.py:287-323`)
   - `GET /api/settings/permissions` endpoint
   - Returns `PermissionsResponse` with all permission types

2. **Frontend command** (`bassi/static/app.js`)
   - `/permissions` intercepted in `sendMessage()`
   - `showPermissions()` method displays formatted output
   - Added to autocomplete list in `buildCommandRegistry()`

3. **Tests** (`bassi/core_v3/tests/integration/test_settings_routes.py:135-238`)
   - 6 tests covering all permission scenarios

4. **Delete Permission Feature** (`bassi/core_v3/routes/settings.py:326-383`)
   - `DELETE /api/settings/permissions/{scope}/{tool_name}` endpoint
   - Frontend `deletePermission()` method in `app.js`
   - Red "×" delete buttons next to each permission in `/permissions` output
   - CSS styles for `.permission-chip` and `.permission-delete`
   - 6 additional tests for DELETE endpoint

---

# Delete Permission from `/permissions` Display

## Status: ✅ IMPLEMENTED

**Implementation Date**: 2025-12-04

## Overview

Add a clickable red "×" (delete) button next to each tool permission displayed in the `/permissions` command output. This allows users to quickly revoke individual permissions without needing to use API commands.

## User Story

As a bassi user, when I view my active permissions with `/permissions`, I want to click a delete button next to any permission to revoke it immediately.

## UI Mockup

```
🔐 PERMISSIONS: ACTIVE

Global bypass: OFF (tools require permission)

💾 ALL SESSIONS (persistent, saved to config):
┌─────────────────────────────────────────────┐
│ mcp__postgresql__describe_table        [×]  │
│ mcp__ms365__list-mail-messages         [×]  │
│ mcp__ms365__get-mail-message           [×]  │
│ mcp__ms365__verify-login               [×]  │
└─────────────────────────────────────────────┘

📍 THIS SESSION ONLY:
┌─────────────────────────────────────────────┐
│ Bash                                   [×]  │
│ Read                                   [×]  │
└─────────────────────────────────────────────┘

⏱️ ONE-TIME:
┌─────────────────────────────────────────────┐
│ Write (1 use remaining)                [×]  │
└─────────────────────────────────────────────┘
```

The `[×]` is a red, clickable button that:
- On hover: Shows tooltip "Remove this permission"
- On click: Removes the permission and updates the display

## Technical Approach

### Option A: Frontend-Only with API Calls (Recommended)

**New API Endpoint**: `DELETE /api/settings/permissions/{scope}/{tool_name}`

Where `scope` is one of: `session`, `persistent`, `one_time`

**Example:**
```bash
DELETE /api/settings/permissions/persistent/mcp__ms365__verify-login
DELETE /api/settings/permissions/session/Bash
DELETE /api/settings/permissions/one_time/Write
```

**Frontend Changes:**
1. Render each permission as a clickable chip with delete button
2. On click, call DELETE endpoint
3. On success, re-fetch permissions and update display (or optimistically remove from DOM)

### Backend Implementation

**In `routes/settings.py`:**

```python
@router.delete("/permissions/{scope}/{tool_name}")
async def delete_permission(scope: str, tool_name: str):
    """Remove a specific permission.

    Args:
        scope: One of 'session', 'persistent', 'one_time'
        tool_name: The tool name to remove

    Returns:
        Success status and updated permissions
    """
    config = get_config_service()
    pm = get_permission_manager()

    if scope == "persistent":
        # Remove from config file
        current = config.get_persistent_permissions()
        if tool_name in current:
            current.remove(tool_name)
            config.set_persistent_permissions(current)

    elif scope == "session" and pm:
        # Remove from session memory
        pm.session_permissions.pop(tool_name, None)

    elif scope == "one_time" and pm:
        # Remove from one-time memory
        pm.one_time_permissions.pop(tool_name, None)

    else:
        raise HTTPException(400, f"Invalid scope: {scope}")

    return {"success": True, "tool": tool_name, "scope": scope}
```

### Frontend Implementation

**In `showPermissions()` in `app.js`:**

```javascript
// For each permission, render with delete button
const renderPermission = (toolName, scope) => {
    return `
        <span class="permission-chip">
            <code>${toolName}</code>
            <button class="permission-delete"
                    onclick="app.deletePermission('${scope}', '${toolName}')"
                    title="Remove this permission">×</button>
        </span>
    `
}

// New method to delete a permission
async deletePermission(scope, toolName) {
    try {
        const response = await fetch(
            `/api/settings/permissions/${scope}/${encodeURIComponent(toolName)}`,
            { method: 'DELETE' }
        )
        if (response.ok) {
            // Refresh the permissions display
            this.showPermissions()
        } else {
            this.addSystemMessage(`Failed to remove permission: ${toolName}`)
        }
    } catch (error) {
        this.addSystemMessage(`Error: ${error.message}`)
    }
}
```

### CSS Styling

```css
.permission-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
    margin: 4px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.2);
}

.permission-delete {
    color: #ff6b6b;
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 16px;
    font-weight: bold;
    padding: 0 4px;
    opacity: 0.6;
    transition: opacity 0.2s;
}

.permission-delete:hover {
    opacity: 1;
    color: #ff4444;
}
```

## Files to Modify

1. **`bassi/core_v3/routes/settings.py`**
   - Add `DELETE /api/settings/permissions/{scope}/{tool_name}` endpoint

2. **`bassi/static/app.js`**
   - Update `showPermissions()` to render delete buttons
   - Add `deletePermission(scope, toolName)` method

3. **`bassi/static/styles.css`**
   - Add styles for `.permission-chip` and `.permission-delete`

4. **`bassi/core_v3/tests/integration/test_settings_routes.py`**
   - Add tests for DELETE endpoint

## Why No Agent Update Needed

Permissions are checked **live on each tool call** via `can_use_tool_callback`:

```python
# In PermissionManager.can_use_tool_callback():
# 1. Check global bypass - reads from ConfigService (file)
# 2. Check one_time_permissions - reads from dict (memory)
# 3. Check session_permissions - reads from dict (memory)
# 4. Check persistent permissions - reads from ConfigService (file)
```

The agent does NOT cache permissions. It calls `can_use_tool_callback` before every tool use, which reads fresh values. So:

- **Session/one-time**: Delete from `PermissionManager` dict → immediate effect
- **Persistent**: Delete from `ConfigService` file → immediate effect (read fresh each time)

No need to notify or update the agent - the next tool call will simply not find the permission and will prompt the user.

## Edge Cases

1. **Permission doesn't exist**: Return success anyway (idempotent)
2. **Invalid scope**: Return 400 Bad Request
3. **URL encoding**: Tool names like `mcp__ms365__list-mail-messages` need URL encoding
4. **Concurrent access**: ConfigService already handles file locking
5. **Tool in-flight**: If a tool is currently executing when permission is deleted, it continues (permission was already granted). Only future calls are affected.

## Priority

**Low** - Nice enhancement for power users, but `/permissions` display is already useful without it.

## Related

- `docs/features_concepts/permissions.md` - Permission model documentation
- `bassi/core_v3/services/permission_manager.py` - Permission state management
- `bassi/core_v3/services/config_service.py` - Persistent config storage
