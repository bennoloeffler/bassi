# Tool Permissions UI Feature

## Overview

This feature provides **granular, user-friendly control** over which tools the AI agent can use, replacing the current all-or-nothing `bypassPermissions` mode with flexible permission management.

## Problem Statement

Currently, bassi operates in one of two extremes:
1. **`bypassPermissions`** - Agent can use ANY tool without asking (current default)
2. **`default`** - Agent must ask for EVERY tool use (via SDK permission prompts)

Users need **middle-ground options** to:
- Allow specific tools without prompts (e.g., web search, file reading)
- Block dangerous tools entirely (e.g., bash commands in production)
- Grant temporary permissions for a single session
- Store permanent preferences across sessions

## User Stories

### Story 1: Quick Allow for This Session
> "I want to let the agent search the web for this conversation, but I don't want it to always have web access"

**Solution**: One-click "Allow this session" button when agent requests web search

### Story 2: Permanent Tool Allowlist
> "I trust the agent with file operations and web search, but I want to manually approve bash commands"

**Solution**: Settings panel with per-tool permissions that persist across sessions

### Story 3: Trust All Tools
> "I'm working on a personal project and want the agent to work autonomously like it does now"

**Solution**: Single toggle: "Allow all tools always" (equivalent to current `bypassPermissions`)

### Story 4: Quick Review Before Execution
> "I want to see what bash command the agent is about to run before it executes"

**Solution**: Permission prompt with command details, allow this time or allow always

## Design Principles

1. **Progressive Trust**: Start conservative, easy to grant more permissions
2. **Context-Aware**: Different permissions for different sessions
3. **Non-Intrusive**: Don't break flow for trusted operations
4. **Transparent**: Always show what permissions are active
5. **Reversible**: Easy to revoke permissions

## Permission Scopes

### 1. One-Time Permission
- **Scope**: Single tool invocation
- **Duration**: This tool call only
- **Use Case**: "Let me see what it does first"
- **Storage**: None (ephemeral)

### 2. Session Permission
- **Scope**: All uses of this tool in current session
- **Duration**: Until browser refresh or session switch
- **Use Case**: "Allow web search while researching"
- **Storage**: Browser memory (sessionStorage)

### 3. Permanent Permission (per tool)
- **Scope**: Specific tool across all sessions
- **Duration**: Until explicitly revoked
- **Use Case**: "Always allow file reading"
- **Storage**: Backend config file (`~/.bassi/permissions.json`)

### 4. Global Permission (all tools)
- **Scope**: ALL tools, equivalent to `bypassPermissions`
- **Duration**: Until explicitly disabled
- **Use Case**: "I'm the only user, trust everything"
- **Storage**: Backend config file

## UI Components

### 1. Settings Modal - Permissions Tab

**Location**: Gear icon (⚙️) → New "Tool Permissions" tab

**Content**:
```
┌─────────────────────────────────────────────────┐
│ Settings                                    × │
├─────────────────────────────────────────────────┤
│ [Thinking Process] [Tool Permissions]          │
├─────────────────────────────────────────────────┤
│                                                 │
│ ☑ Allow All Tools Always                       │
│   Skip permission prompts for all operations   │
│   ⚠️  Current behavior (bypassPermissions)      │
│                                                 │
│ ── Or Configure Individual Tools ──            │
│                                                 │
│ 🔍 Web Search (WebSearch)                      │
│    ○ Ask each time                             │
│    ● Allow always                              │
│    ○ Block always                              │
│                                                 │
│ 📁 File Operations (Read, Write, Edit)         │
│    ○ Ask each time                             │
│    ● Allow always                              │
│    ○ Block always                              │
│                                                 │
│ 💻 Bash Commands (Bash)                        │
│    ● Ask each time                             │
│    ○ Allow always                              │
│    ○ Block always                              │
│                                                 │
│ 📧 Microsoft 365 (MS365 tools)                 │
│    ○ Ask each time                             │
│    ○ Allow always                              │
│    ● Block always                              │
│                                                 │
│ [View All Tools...] ▼                          │
│                                                 │
│ Session Permissions (this conversation only):  │
│ • WebSearch: Allowed                      [×]  │
│ • Bash: Allowed                           [×]  │
│                                                 │
│              [Save] [Cancel]                   │
└─────────────────────────────────────────────────┘
```

**Features**:
- Master toggle: "Allow All Tools Always" (grays out individual controls when enabled)
- Tool categories with expand/collapse (grouped by function)
- Per-tool 3-state radio: Ask / Allow / Block
- Session permissions list with revoke buttons
- Real-time permission status indicator

### 2. Permission Prompt Dialog

**Triggered When**: Agent attempts to use a tool that requires permission

**Content**:
```
┌─────────────────────────────────────────────────┐
│ Permission Request                          × │
├─────────────────────────────────────────────────┤
│                                                 │
│ 🔍 Bassi wants to use: Web Search              │
│                                                 │
│ Query: "latest Python 3.12 features"           │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ {                                           │ │
│ │   "query": "latest Python 3.12 features"    │ │
│ │ }                                           │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ [Deny]  [Allow This Time]  [Allow This Session]│
│                                                 │
│ ☐ Always allow this tool (remember preference) │
│ ☐ Never ask again for any tool                 │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Actions**:
1. **Deny** - Block this tool call, agent continues without it
2. **Allow This Time** - Execute once, ask again next time
3. **Allow This Session** - Execute and remember for this session
4. **Checkbox: Always allow** - Save permanent permission
5. **Checkbox: Never ask again** - Enable global bypass

### 3. Status Indicator

**Location**: Near connection status (top-right)

**Visual**:
```
🔓 Bypass Permissions    (green - all tools allowed)
🔐 Managed Permissions   (yellow - selective permissions)
🔒 Restricted Access     (red - most tools blocked)
```

**Tooltip**: Shows current permission mode and count of allowed tools

## Permission Storage

### Backend Storage Structure

**File**: `~/.bassi/permissions.json`

```json
{
  "version": "1.0",
  "global_bypass": false,
  "permanent_permissions": {
    "mcp__web-search__search": "allow",
    "Read": "allow",
    "Write": "ask",
    "Edit": "ask",
    "Bash": "ask",
    "mcp__ms365__*": "block"
  },
  "tool_groups": {
    "file_operations": ["Read", "Write", "Edit", "Glob"],
    "ms365": ["mcp__ms365__*"],
    "web": ["mcp__web-search__search", "WebFetch"]
  },
  "metadata": {
    "last_modified": "2025-11-15T10:30:00Z",
    "created": "2025-11-15T08:00:00Z"
  }
}
```

**Permission Values**:
- `"allow"` - Auto-approve without prompt
- `"ask"` - Show permission dialog
- `"block"` - Always deny, don't even ask

**Wildcards**:
- `"mcp__ms365__*"` - All MS365 tools
- `"*"` - All tools (equivalent to `global_bypass: true`)

### Frontend Storage (Session-Scoped)

**Location**: `sessionStorage` (per browser tab)

```javascript
// sessionStorage key: 'bassi_session_permissions'
{
  "session_id": "abc-123-def",
  "permissions": {
    "WebSearch": "allow",
    "Bash": "allow"
  },
  "expires": "2025-11-15T12:00:00Z"  // Clear on session end
}
```

## Backend Implementation

### 1. New API Endpoints

#### `GET /api/permissions`
**Purpose**: Retrieve current permission configuration

**Response**:
```json
{
  "global_bypass": false,
  "permanent_permissions": { ... },
  "available_tools": [
    {
      "name": "WebSearch",
      "category": "web",
      "description": "Search the web for information",
      "mcp_server": "web-search"
    },
    // ... all discovered tools
  ]
}
```

#### `POST /api/permissions`
**Purpose**: Update permanent permissions

**Request**:
```json
{
  "global_bypass": true,  // or individual tool updates
  "permanent_permissions": {
    "WebSearch": "allow"
  }
}
```

**Response**:
```json
{
  "success": true,
  "updated_at": "2025-11-15T10:30:00Z"
}
```

### 2. Permission Checking Flow

```
Agent wants to use tool X
    ↓
Check global_bypass == true?
    YES → Execute immediately ✅
    NO  → Continue
    ↓
Check permanent_permissions[X]
    "allow"  → Execute immediately ✅
    "block"  → Deny, send error event ❌
    "ask"    → Send permission_request event to frontend 🤔
    ↓
Frontend shows permission dialog
    ↓
User chooses: Deny / Allow Once / Allow Session / Allow Always
    ↓
Frontend sends permission_response event
    ↓
Backend processes response:
    - "allow_once": Execute tool, don't store
    - "allow_session": Execute tool, frontend stores in sessionStorage
    - "allow_always": Execute tool, backend saves to permissions.json
    - "deny": Send tool error, agent continues
```

### 3. New WebSocket Events

#### `permission_request` (Backend → Frontend)

```json
{
  "type": "permission_request",
  "tool_name": "WebSearch",
  "tool_server": "web-search",
  "tool_input": {
    "query": "latest Python 3.12 features"
  },
  "request_id": "req-123",
  "description": "Search the web for information"
}
```

#### `permission_response` (Frontend → Backend)

```json
{
  "type": "permission_response",
  "request_id": "req-123",
  "decision": "allow_session",  // allow_once | allow_session | allow_always | deny
  "remember_preference": false
}
```

### 4. Backend Service: PermissionManager

**Location**: `bassi/core_v3/services/permission_service.py`

**Responsibilities**:
- Load/save permissions.json
- Check if tool is allowed
- Update permissions
- Handle permission requests
- Apply defaults

**Key Methods**:
```python
class PermissionManager:
    def is_tool_allowed(self, tool_name: str) -> PermissionDecision
    def request_permission(self, tool_name: str, tool_input: dict) -> Awaitable[bool]
    def save_permission(self, tool_name: str, decision: str)
    def get_all_permissions(self) -> dict
    def set_global_bypass(self, enabled: bool)
```

### 5. Integration with SessionConfig

**Modify**: `bassi/core_v3/agent_session.py`

**Current**:
```python
config = SessionConfig(
    permission_mode="bypassPermissions",  # hardcoded
    ...
)
```

**New**:
```python
config = SessionConfig(
    permission_mode=self._get_permission_mode(),  # dynamic
    can_use_tool=self._check_tool_permission,     # callback
    ...
)

def _get_permission_mode(self) -> str:
    """Determine permission mode from config"""
    if self.permission_manager.global_bypass:
        return "bypassPermissions"
    else:
        return "default"  # Use can_use_tool callback

async def _check_tool_permission(self, tool_name: str, tool_input: dict) -> bool:
    """Check if tool is allowed, prompt user if needed"""
    return await self.permission_manager.is_tool_allowed(
        tool_name, tool_input, session_id=self.session_id
    )
```

## Frontend Implementation

### 1. Settings UI Update

**Location**: `bassi/static/index.html`

**Add**:
- New tab in settings modal: "Tool Permissions"
- Master toggle: "Allow All Tools Always"
- Tool list with radio buttons (Ask / Allow / Block)
- Session permissions display

### 2. Permission Dialog Component

**Location**: `bassi/static/app.js`

**New Class**:
```javascript
class PermissionDialog {
    constructor(client) { ... }

    show(request) {
        // Display permission dialog
        // Handle user decision
        // Send response to backend
    }

    handleResponse(decision, rememberPreference) {
        // Send WebSocket message
        // Update session storage if needed
    }
}
```

### 3. WebSocket Event Handlers

**Add to**: `bassi/static/app.js`

```javascript
handlePermissionRequest(event) {
    // Show permission dialog
    // Wait for user decision
    // Send permission_response
}

handlePermissionDenied(event) {
    // Show notification that tool was blocked
}
```

### 4. Settings Persistence

**Location**: `bassi/static/app.js`

```javascript
async loadPermissions() {
    const response = await fetch('/api/permissions')
    this.permissions = await response.json()
    this.renderPermissionsUI()
}

async savePermissions(updates) {
    await fetch('/api/permissions', {
        method: 'POST',
        body: JSON.stringify(updates)
    })
}
```

## Migration Strategy

### Phase 1: Backend Foundation (Week 1)
1. Create `permission_service.py` with PermissionManager
2. Add `GET /api/permissions` endpoint
3. Add `POST /api/permissions` endpoint
4. Create `~/.bassi/permissions.json` config file
5. Write unit tests for permission logic

### Phase 2: WebSocket Integration (Week 1)
1. Add `permission_request` event type
2. Add `permission_response` event type
3. Integrate with agent session `can_use_tool` callback
4. Test permission flow end-to-end

### Phase 3: Frontend UI (Week 2)
1. Add "Tool Permissions" tab to settings modal
2. Implement master "Allow All Tools" toggle
3. Create per-tool permission controls
4. Show session permissions list
5. Add permission status indicator

### Phase 4: Permission Dialog (Week 2)
1. Create modal dialog component
2. Implement user decision handling
3. Add "remember preference" checkbox
4. Test all decision paths (deny, once, session, always)

### Phase 5: Testing & Polish (Week 3)
1. E2E tests for permission flows
2. Test session permissions (browser storage)
3. Test permanent permissions (file persistence)
4. UX polish (animations, error states)
5. Documentation updates

## Simplified First Implementation

For a **minimal viable feature** (Phase 1 only):

### Settings Only (No Runtime Prompts)

**Frontend**:
- Add single toggle in settings: "Allow All Tools Always"
- No per-tool configuration yet
- No runtime dialogs

**Backend**:
- Store single boolean in `~/.bassi/permissions.json`
- Set `permission_mode` based on this boolean
- No `can_use_tool` callback yet

**Implementation Time**: 1-2 days

**Code Changes**:
1. Add toggle to `bassi/static/index.html` settings modal
2. Add `GET/POST /api/settings/global-bypass` endpoints
3. Read boolean from config file in `SessionConfig` initialization
4. Update `permission_mode` accordingly

### Example Simplified Code

**Backend** (`bassi/core_v3/routes/settings.py`):
```python
@router.get("/settings/global-bypass")
async def get_global_bypass():
    config = load_config()  # from ~/.bassi/permissions.json
    return {"global_bypass": config.get("global_bypass", True)}

@router.post("/settings/global-bypass")
async def set_global_bypass(request: Request):
    data = await request.json()
    save_config({"global_bypass": data["enabled"]})
    return {"success": True}
```

**Frontend** (`bassi/static/app.js`):
```javascript
async loadGlobalBypass() {
    const resp = await fetch('/api/settings/global-bypass')
    const data = await resp.json()
    document.getElementById('global-bypass-toggle').checked = data.global_bypass
}

async toggleGlobalBypass(enabled) {
    await fetch('/api/settings/global-bypass', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({enabled})
    })
}
```

## Security Considerations

1. **Default Deny**: If no permission found, default to "ask"
2. **Validate Tool Names**: Prevent injection via malformed tool names
3. **Audit Log**: Log all permission decisions to `~/.bassi/audit.log`
4. **File Permissions**: Ensure `permissions.json` is only readable by user (chmod 600)
5. **Session Isolation**: Session permissions don't leak across browser tabs

## Future Enhancements

1. **Permission Groups**: Bulk manage related tools (e.g., "All file operations")
2. **Temporary Grants**: "Allow for 1 hour" time-based permissions
3. **Context-Aware**: Different permissions for different directories
4. **Audit Dashboard**: View history of all tool uses and decisions
5. **Import/Export**: Share permission profiles across machines
6. **Tool Usage Analytics**: "You've used Bash 47 times, maybe allow it?"

## Related Documentation

- `docs/features_concepts/permissions.md` - Current permission model
- `CLAUDE_BBS.md` - Black Box Design principles
- `docs/requirements.md` - Security requirements

## Success Metrics

- User can disable `bypassPermissions` without breaking workflow
- Clear visual feedback on what permissions are active
- Less than 5 clicks to grant permanent permission to a tool
- Zero permission prompts when "Allow All Tools" is enabled
- Permissions persist across browser refreshes
