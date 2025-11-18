# Bug Fix: Permission Dialog Not Appearing

**Date**: 2025-11-15
**Issue**: Permission dialogs were not appearing - tools were auto-approved even with global bypass OFF

## Problem

When a user had the "Bypass all permissions" toggle OFF in settings, the agent was still auto-approving all tool uses without showing the interactive permission dialog. The UI would briefly show a red MCP box with "permission required", then it would turn green and execute.

## Root Cause

In `bassi/shared/permission_config.py`, the `get_permission_mode()` function was converting the global bypass boolean to a permission mode:

```python
# OLD CODE (BUGGY)
global_bypass = config_service.get_global_bypass_permissions()
mode = "bypassPermissions" if global_bypass else "default"
```

**Problem**: When `permission_mode="bypassPermissions"`, the Claude Agent SDK bypasses ALL permission checks internally and NEVER calls the `can_use_tool_callback`. This meant our `PermissionManager.can_use_tool_callback()` was never invoked, so the interactive permission dialog logic was completely skipped.

## Solution

Changed `get_permission_mode()` to ALWAYS return `"default"` mode:

```python
# NEW CODE (FIXED)
global_bypass = config_service.get_global_bypass_permissions()
mode = "default"  # Always use "default" so callback gets called
```

This ensures the SDK always calls `can_use_tool_callback()` for every tool use. The callback (PermissionManager) then handles the permission logic internally:

1. Check global bypass → if ON, allow immediately (no dialog)
2. Check one-time permission → if exists, allow and decrement
3. Check session permission → if exists, allow
4. Check persistent permission → if exists, allow
5. **Otherwise** → Show interactive permission dialog to user

## Files Changed

- `bassi/shared/permission_config.py`:
  - Changed `fallback` parameter from `"bypassPermissions"` to `"default"`
  - Changed logic to always return `"default"` mode
  - Updated docstring to explain the new behavior
- `bassi/core_v3/services/permission_manager.py`:
  - Added type annotations for `future` and `scope` variables (mypy compliance)

## Testing

To verify the fix works:

1. Start server: `./run-agent-web.sh`
2. Go to Settings → Turn OFF "Bypass all permissions"
3. Ask agent to use a tool (e.g., "search for Python tutorials")
4. **Expected**: Permission dialog appears with 4 options
5. **Before fix**: Tool executed immediately without dialog

## Impact

- **Global bypass ON**: Still works (callback checks global bypass first and allows)
- **Global bypass OFF**: Now correctly shows interactive permission dialog
- **No breaking changes**: All existing permission logic still works

## Related Files

- `bassi/core_v3/services/permission_manager.py` - Permission callback implementation
- `bassi/core_v3/services/config_service.py` - Persistent storage
- `bassi/static/app.js` - Frontend permission dialog UI
- `bassi/static/style.css` - Permission dialog styling
