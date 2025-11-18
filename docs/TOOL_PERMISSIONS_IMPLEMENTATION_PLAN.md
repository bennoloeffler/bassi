# Tool Permissions Implementation Plan

**Status**: ✅ **IMPLEMENTED** (2025-11-16)
**Implementation**: 
- Backend: `PermissionManager` and `ConfigService` implemented ✅
- UI: Settings modal with "Allow All Tools Always" toggle ✅
- Runtime: Permission dialogs with scope options (one_time, session, persistent, global) ✅

## Overview

This document provides a step-by-step implementation plan for adding granular tool permission controls to bassi, as described in `docs/features_concepts/tool_permissions_ui.md`.

## Implementation Strategy

We'll use an **incremental approach** starting with the simplest implementation and adding complexity in phases:

### Phase 1: Settings Toggle Only (RECOMMENDED START)
- **Goal**: Single toggle to enable/disable `bypassPermissions`
- **Complexity**: Low (1-2 days)
- **Value**: Immediate control over autonomous mode

### Phase 2: Per-Tool Permissions (No Runtime Prompts)
- **Goal**: Configure which tools are allowed/blocked (applied at session start)
- **Complexity**: Medium (3-5 days)
- **Value**: Granular control without interruptions

### Phase 3: Runtime Permission Dialogs
- **Goal**: Ask user during execution when tool needs permission
- **Complexity**: High (5-7 days)
- **Value**: Maximum flexibility with "ask each time" option

## Phase 1: Global Bypass Toggle

### Step 1.1: Backend - Config Storage

**File**: `bassi/core_v3/services/config_service.py` (new)

```python
"""Configuration service for user settings."""

import json
import logging
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)


class ConfigService:
    """Manage user configuration stored in ~/.bassi/config.json"""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize config service.

        Args:
            config_path: Override default config location (for testing)
        """
        if config_path is None:
            config_path = Path.home() / ".bassi" / "config.json"

        self.config_path = config_path
        self._ensure_config_exists()

    def _ensure_config_exists(self):
        """Create default config if it doesn't exist"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.config_path.exists():
            default_config = {
                "version": "1.0",
                "global_bypass_permissions": True,  # Current behavior
                "created_at": None,  # Will be set on first save
            }
            self._save_config(default_config)

    def _load_config(self) -> dict:
        """Load configuration from disk"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            LOGGER.warning(f"Failed to load config: {e}, using defaults")
            return {"global_bypass_permissions": True}

    def _save_config(self, config: dict):
        """Save configuration to disk"""
        from datetime import datetime

        if "created_at" not in config or config["created_at"] is None:
            config["created_at"] = datetime.utcnow().isoformat()

        config["updated_at"] = datetime.utcnow().isoformat()

        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)

        # Secure file permissions (user read/write only)
        self.config_path.chmod(0o600)

    def get_global_bypass_permissions(self) -> bool:
        """Get whether bypassPermissions mode is enabled"""
        config = self._load_config()
        return config.get("global_bypass_permissions", True)

    def set_global_bypass_permissions(self, enabled: bool):
        """Set whether bypassPermissions mode is enabled"""
        config = self._load_config()
        config["global_bypass_permissions"] = enabled
        self._save_config(config)
        LOGGER.info(f"Global bypass permissions: {enabled}")
```

**Tests**: `bassi/core_v3/tests/test_config_service.py`

```python
import pytest
from pathlib import Path
from bassi.core_v3.services.config_service import ConfigService


def test_default_config_created(tmp_path):
    """Config file created with defaults if missing"""
    config_path = tmp_path / "config.json"
    service = ConfigService(config_path)

    assert config_path.exists()
    assert service.get_global_bypass_permissions() is True


def test_get_set_global_bypass(tmp_path):
    """Can get and set global bypass setting"""
    service = ConfigService(tmp_path / "config.json")

    # Default is True
    assert service.get_global_bypass_permissions() is True

    # Change to False
    service.set_global_bypass_permissions(False)
    assert service.get_global_bypass_permissions() is False

    # Persists across instances
    service2 = ConfigService(tmp_path / "config.json")
    assert service2.get_global_bypass_permissions() is False


def test_config_file_permissions(tmp_path):
    """Config file has secure permissions"""
    config_path = tmp_path / "config.json"
    service = ConfigService(config_path)

    import os
    stat_info = os.stat(config_path)
    permissions = oct(stat_info.st_mode)[-3:]

    assert permissions == "600"  # User read/write only
```

### Step 1.2: Backend - API Endpoints

**File**: `bassi/core_v3/routes/settings.py` (new)

```python
"""Settings API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bassi.core_v3.services.config_service import ConfigService

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Singleton instance
_config_service: ConfigService | None = None


def get_config_service() -> ConfigService:
    """Get or create ConfigService singleton"""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service


class GlobalBypassRequest(BaseModel):
    """Request to update global bypass setting"""
    enabled: bool


class GlobalBypassResponse(BaseModel):
    """Response with current global bypass setting"""
    enabled: bool


@router.get("/global-bypass", response_model=GlobalBypassResponse)
async def get_global_bypass():
    """Get current global bypass permissions setting"""
    service = get_config_service()
    enabled = service.get_global_bypass_permissions()
    return GlobalBypassResponse(enabled=enabled)


@router.post("/global-bypass", response_model=GlobalBypassResponse)
async def set_global_bypass(request: GlobalBypassRequest):
    """Update global bypass permissions setting"""
    service = get_config_service()
    service.set_global_bypass_permissions(request.enabled)
    return GlobalBypassResponse(enabled=request.enabled)
```

**Register Routes**: Update `bassi/core_v3/web_server_v3.py`

```python
# Add import
from bassi.core_v3.routes import settings

# In setup_routes():
app.include_router(settings.router)
```

**Tests**: `bassi/core_v3/tests/test_settings_routes.py`

```python
import pytest
from fastapi.testclient import TestClient
from bassi.core_v3.web_server_v3 import create_app
from bassi.core_v3.routes.settings import _config_service
from bassi.core_v3.services.config_service import ConfigService


@pytest.fixture
def client(tmp_path):
    """Test client with temporary config"""
    global _config_service
    _config_service = ConfigService(tmp_path / "config.json")

    app = create_app()
    yield TestClient(app)

    _config_service = None


def test_get_global_bypass_default(client):
    """GET returns default value (True)"""
    response = client.get("/api/settings/global-bypass")
    assert response.status_code == 200
    assert response.json() == {"enabled": True}


def test_set_global_bypass(client):
    """POST updates the setting"""
    # Disable bypass
    response = client.post(
        "/api/settings/global-bypass",
        json={"enabled": False}
    )
    assert response.status_code == 200
    assert response.json() == {"enabled": False}

    # Verify persisted
    response = client.get("/api/settings/global-bypass")
    assert response.json() == {"enabled": False}
```

### Step 1.3: Backend - Apply to Session

**File**: `bassi/core_v3/agent_session.py`

**Modify `SessionConfig.__post_init__`**:

```python
def __post_init__(self):
    """Apply configuration from ConfigService"""
    from bassi.core_v3.services.config_service import ConfigService

    # Load user preferences
    config_service = ConfigService()
    global_bypass = config_service.get_global_bypass_permissions()

    # Override permission_mode if not explicitly set
    if self.permission_mode is None:
        self.permission_mode = (
            "bypassPermissions" if global_bypass else "default"
        )
```

**Alternative (Cleaner)**: Use factory function

```python
# In agent_session.py

def create_session_config_from_user_settings(**overrides) -> SessionConfig:
    """Create SessionConfig with user preferences from config file.

    Args:
        **overrides: Explicit overrides for any SessionConfig field

    Returns:
        SessionConfig with user preferences applied
    """
    from bassi.core_v3.services.config_service import ConfigService

    config_service = ConfigService()
    global_bypass = config_service.get_global_bypass_permissions()

    # Start with defaults
    defaults = {
        "permission_mode": "bypassPermissions" if global_bypass else "default",
        "system_prompt": None,
        "allowed_tools": None,
        # ... other defaults
    }

    # Apply user overrides
    defaults.update(overrides)

    return SessionConfig(**defaults)
```

**Update WebSocket Handler**: Use factory

```python
# In websocket/connection.py or wherever SessionConfig is created

config = create_session_config_from_user_settings(
    resume_session_id=resume_session_id,
    include_partial_messages=True,
    thinking_mode=thinking_mode,
)
```

### Step 1.4: Frontend - Settings UI

**File**: `bassi/static/index.html`

**Update Settings Modal**:

```html
<!-- Settings Modal -->
<div id="settings-modal" class="modal" style="display: none;">
    <div class="modal-content">
        <div class="modal-header">
            <h2>Settings</h2>
            <button class="modal-close" id="settings-close">×</button>
        </div>
        <div class="modal-body">
            <!-- Existing: Thinking Process -->
            <div class="setting-item">
                <div class="setting-info">
                    <label class="setting-label">Show Thinking Process</label>
                    <p class="setting-description">
                        Display Claude's step-by-step reasoning before final responses
                    </p>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" id="thinking-toggle" checked>
                    <span class="toggle-slider"></span>
                </label>
            </div>

            <!-- NEW: Tool Permissions -->
            <div class="setting-item">
                <div class="setting-info">
                    <label class="setting-label">Allow All Tools Always</label>
                    <p class="setting-description">
                        Skip permission prompts - agent can use any tool autonomously (bash, web search, file operations, etc.)
                        <br>
                        <span class="warning-text">⚠️ Only enable if you trust the agent completely</span>
                    </p>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" id="global-bypass-toggle" checked>
                    <span class="toggle-slider"></span>
                </label>
            </div>
        </div>
    </div>
</div>
```

**Add CSS** (`bassi/static/style.css`):

```css
/* Warning text styling */
.warning-text {
    color: var(--warning, #f59e0b);
    font-size: 0.85em;
    font-weight: 500;
}
```

### Step 1.5: Frontend - JavaScript Logic

**File**: `bassi/static/app.js`

**Add to `initSettings()` method**:

```javascript
initSettings() {
    const settingsButton = document.getElementById('settings-button')
    const settingsModal = document.getElementById('settings-modal')
    const settingsClose = document.getElementById('settings-close')
    const thinkingToggle = document.getElementById('thinking-toggle')
    const globalBypassToggle = document.getElementById('global-bypass-toggle')

    // Load settings on init
    this.loadSettings()

    // Show modal
    settingsButton.addEventListener('click', () => {
        settingsModal.style.display = 'flex'
    })

    // Close modal
    settingsClose.addEventListener('click', () => {
        settingsModal.style.display = 'none'
    })

    // Click outside to close
    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            settingsModal.style.display = 'none'
        }
    })

    // Thinking toggle
    thinkingToggle.addEventListener('change', async (e) => {
        const enabled = e.target.checked
        localStorage.setItem('thinking_mode', enabled ? 'true' : 'false')
        this.showNotification(
            `Thinking mode ${enabled ? 'enabled' : 'disabled'}. Refresh to apply.`,
            'info'
        )
    })

    // Global bypass toggle (NEW)
    globalBypassToggle.addEventListener('change', async (e) => {
        const enabled = e.target.checked
        await this.updateGlobalBypass(enabled)
    })
}

async loadSettings() {
    """Load all settings from backend and localStorage"""

    // Load thinking mode from localStorage
    const thinkingMode = localStorage.getItem('thinking_mode') !== 'false'
    document.getElementById('thinking-toggle').checked = thinkingMode

    // Load global bypass from backend
    try {
        const response = await fetch('/api/settings/global-bypass')
        if (response.ok) {
            const data = await response.json()
            document.getElementById('global-bypass-toggle').checked = data.enabled
        }
    } catch (error) {
        console.error('Failed to load global bypass setting:', error)
    }
}

async updateGlobalBypass(enabled) {
    """Update global bypass setting on backend"""

    try {
        const response = await fetch('/api/settings/global-bypass', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled })
        })

        if (response.ok) {
            this.showNotification(
                enabled
                    ? '🔓 All tools allowed - agent runs autonomously'
                    : '🔐 Tool permissions managed - agent will ask before using tools',
                'success'
            )

            // Suggest refresh if session is active
            if (this.sessionId) {
                this.showNotification(
                    'Start a new session for changes to take effect',
                    'info'
                )
            }
        } else {
            throw new Error('Failed to update setting')
        }
    } catch (error) {
        console.error('Failed to update global bypass:', error)

        // Revert toggle on error
        document.getElementById('global-bypass-toggle').checked = !enabled

        this.showNotification(
            'Failed to update permission setting',
            'error'
        )
    }
}

showNotification(message, type = 'info') {
    """Show a toast notification to the user"""

    // Create notification element
    const notification = document.createElement('div')
    notification.className = `notification notification-${type}`
    notification.textContent = message

    // Style
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#3b82f6'};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `

    document.body.appendChild(notification)

    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out'
        setTimeout(() => {
            document.body.removeChild(notification)
        }, 300)
    }, 3000)
}
```

**Add CSS animations** (`bassi/static/style.css`):

```css
/* Notification animations */
@keyframes slideIn {
    from {
        transform: translateX(400px);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

@keyframes slideOut {
    from {
        transform: translateX(0);
        opacity: 1;
    }
    to {
        transform: translateX(400px);
        opacity: 0;
    }
}
```

### Step 1.6: Testing

**E2E Test**: `bassi/core_v3/tests/test_settings_e2e.py`

```python
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_global_bypass_toggle(page: Page, bassi_server):
    """User can toggle global bypass in settings"""

    # Open app
    page.goto("http://localhost:8765")

    # Wait for connection
    expect(page.locator("#connection-status")).to_contain_text("Connected")

    # Open settings
    page.click("#settings-button")
    expect(page.locator("#settings-modal")).to_be_visible()

    # Global bypass should be enabled by default
    toggle = page.locator("#global-bypass-toggle")
    expect(toggle).to_be_checked()

    # Disable it
    toggle.click()
    expect(toggle).not_to_be_checked()

    # Should show notification
    expect(page.locator(".notification")).to_contain_text("managed")

    # Close settings
    page.click("#settings-close")

    # Verify persisted (reload page)
    page.reload()
    page.click("#settings-button")

    expect(page.locator("#global-bypass-toggle")).not_to_be_checked()
```

## Phase 2: Per-Tool Permissions (Future)

### Backend Changes

1. **Expand ConfigService**:
   - `get_tool_permission(tool_name: str) -> str`  # "allow" | "ask" | "block"
   - `set_tool_permission(tool_name: str, decision: str)`
   - `get_all_tool_permissions() -> dict`

2. **Add Discovery Endpoint**:
   - `GET /api/tools` - List all available tools from MCP servers

3. **Update SessionConfig**:
   - Add `can_use_tool` callback that checks ConfigService

### Frontend Changes

1. **Settings UI**:
   - Add "Tool Permissions" tab
   - List all tools with radio buttons (Allow / Ask / Block)
   - Group by category (File Ops, Web, MS365, etc.)

2. **Tool Discovery**:
   - Fetch available tools from backend
   - Display in settings

## Phase 3: Runtime Permission Dialogs (Future)

### Backend Changes

1. **Permission Request Events**:
   - `permission_request` WebSocket event
   - `permission_response` WebSocket event

2. **Session-Scoped Permissions**:
   - Track per-session grants in memory
   - Apply before checking persistent config

### Frontend Changes

1. **Permission Dialog Component**:
   - Modal with tool details
   - Buttons: Deny / Allow Once / Allow Session / Allow Always
   - JSON preview of tool input

2. **Event Handlers**:
   - Listen for `permission_request`
   - Show dialog
   - Send `permission_response`

## File Structure

```
bassi/
├── core_v3/
│   ├── routes/
│   │   └── settings.py              # NEW: Settings API
│   ├── services/
│   │   ├── config_service.py        # NEW: Config storage
│   │   └── permission_service.py    # FUTURE: Permission logic
│   ├── tests/
│   │   ├── test_config_service.py   # NEW: Config tests
│   │   ├── test_settings_routes.py  # NEW: API tests
│   │   └── test_settings_e2e.py     # NEW: E2E tests
│   ├── agent_session.py             # MODIFY: Use config
│   └── web_server_v3.py             # MODIFY: Register routes
├── static/
│   ├── app.js                       # MODIFY: Add settings logic
│   ├── index.html                   # MODIFY: Add toggle UI
│   └── style.css                    # MODIFY: Add styles
└── ~/.bassi/
    └── config.json                  # NEW: User config file
```

## Testing Checklist

- [ ] Unit tests for ConfigService
- [ ] Unit tests for settings routes
- [ ] Integration test: Config persists across sessions
- [ ] E2E test: Toggle in UI updates backend
- [ ] E2E test: Setting applies to new sessions
- [ ] E2E test: File permissions (chmod 600)
- [ ] Manual test: Verify `bypassPermissions` actually changes

## Documentation Updates

- [ ] Update `docs/features_concepts/permissions.md`
- [ ] Add section in `CLAUDE.md` about settings
- [ ] Update `docs/vision.md` with completed feature

## Rollout Plan

1. **Develop on branch**: `feature/tool-permissions-toggle`
2. **Test locally**: Run `./check.sh` + manual testing
3. **PR review**: Get feedback on UX
4. **Merge to main**: Deploy to production
5. **User communication**: Announce in README

## Success Criteria

- [ ] Toggle visible in settings modal
- [ ] Toggle state persists across browser refreshes
- [ ] Setting applies to new agent sessions
- [ ] All tests pass (`./check.sh`)
- [ ] Config file created with secure permissions (600)
- [ ] No breaking changes to existing functionality

## Estimated Timeline

**Phase 1 (Settings Toggle Only)**:
- Backend (ConfigService + Routes): 4 hours
- Frontend (UI + Logic): 3 hours
- Tests (Unit + E2E): 3 hours
- **Total**: 1-2 days

**Phase 2 (Per-Tool Permissions)**:
- Backend: 1-2 days
- Frontend: 2-3 days
- Tests: 1 day
- **Total**: 1 week

**Phase 3 (Runtime Dialogs)**:
- Backend: 2-3 days
- Frontend: 2-3 days
- Tests: 1-2 days
- **Total**: 1-1.5 weeks

**Grand Total**: 2-3 weeks for complete feature
