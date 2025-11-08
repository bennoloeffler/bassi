# Session Management - Implementation Roadmap (Option B + Symlinks)

**Date**: 2025-11-08
**Approach**: Full Implementation (8-10 days, no tests - tests deferred)
**Enhancement**: Human-readable symlink structure

---

## Architecture: Physical + Symlink Structure

### Physical Storage (Stable)
```
chats/
  e4b2c8d9-1234-5678-90ab-cdef01234567/
    session.json
    history.md
    DATA_FROM_USER/
    RESULTS_FROM_AGENT/
    SCRIPTS_FROM_AGENT/
    DATA_FROM_AGENT/
```

### Human-Readable Symlinks (Mutable)
```
chats-human-readable/
  2025-11-08T14-30-15__new-session__e4b2c8 -> ../chats/e4b2c8d9.../
  # After first LLM naming:
  2025-11-08T14-30-15__analyze-pdf-documents__e4b2c8 -> ../chats/e4b2c8d9.../
  # After finalization (optional):
  2025-11-08T14-30-15__comprehensive-pdf-analysis__e4b2c8 -> ../chats/e4b2c8d9.../
```

### Symlink Lifecycle
1. **Session Creation**: `{timestamp}__new-session__{short-id}` → `../chats/{session_id}`
2. **After First Response**: Update symlink to `{timestamp}__{llm-name}__{short-id}`
3. **On Finalization** (optional): Update symlink to final name
4. **On Deletion**: Remove symlink + target directory

---

## Phase 1: File Browser UI (Days 1-3)

### Backend Changes

#### 1.1 Add Symlink Management to SessionWorkspace
**File**: `bassi/core_v3/session_workspace.py`

```python
import os
from pathlib import Path

class SessionWorkspace:
    SYMLINK_DIR = Path("chats-human-readable")

    def __init__(self, session_id: str, base_path: Path = Path("chats"), create: bool = True):
        # Existing initialization...
        self.session_id = session_id
        self.physical_path = base_path / session_id

        if create:
            self._create_directory_structure()
            self._create_initial_symlink()

    def _create_initial_symlink(self) -> None:
        """Create initial symlink with timestamp and placeholder name."""
        self.SYMLINK_DIR.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        short_id = self.session_id[:8]
        symlink_name = f"{timestamp}__new-session__{short_id}"
        symlink_path = self.SYMLINK_DIR / symlink_name

        # Create symlink pointing to physical workspace
        target = Path("..") / "chats" / self.session_id

        if not symlink_path.exists():
            os.symlink(target, symlink_path)

        # Store current symlink in metadata
        self.metadata["current_symlink"] = symlink_name
        self._save_metadata()

    def update_symlink(self, new_name: str) -> None:
        """Update symlink with new LLM-generated or user name."""
        # Remove old symlink
        old_symlink = self.metadata.get("current_symlink")
        if old_symlink:
            old_path = self.SYMLINK_DIR / old_symlink
            if old_path.exists():
                old_path.unlink()

        # Create new symlink
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        short_id = self.session_id[:8]
        # Clean name for filesystem
        clean_name = self._sanitize_name(new_name)
        symlink_name = f"{timestamp}__{clean_name}__{short_id}"
        symlink_path = self.SYMLINK_DIR / symlink_name

        target = Path("..") / "chats" / self.session_id
        os.symlink(target, symlink_path)

        # Update metadata
        self.metadata["current_symlink"] = symlink_name
        self._save_metadata()

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for filesystem (kebab-case)."""
        import re
        # Convert to lowercase, replace spaces/underscores with hyphens
        name = name.lower().replace(" ", "-").replace("_", "-")
        # Remove invalid characters
        name = re.sub(r'[^a-z0-9-]', '', name)
        # Collapse multiple hyphens
        name = re.sub(r'-+', '-', name)
        # Trim hyphens
        name = name.strip('-')
        return name[:50]  # Max 50 chars

    def delete(self) -> None:
        """Delete workspace and symlink."""
        # Remove symlink
        symlink_name = self.metadata.get("current_symlink")
        if symlink_name:
            symlink_path = self.SYMLINK_DIR / symlink_name
            if symlink_path.exists():
                symlink_path.unlink()

        # Remove physical directory
        if self.physical_path.exists():
            shutil.rmtree(self.physical_path)
```

**Tasks**:
- [x] Add `_create_initial_symlink()` method
- [x] Add `update_symlink()` method
- [x] Add `_sanitize_name()` helper
- [x] Add `delete()` method
- [x] Store current symlink name in metadata

---

### Frontend Changes

#### 1.2 Session Persistence
**File**: `bassi/static/app.js`

**Location**: After line 1514 (where sessionId is set)

```javascript
// Around line 1514 in handleMessage(msg)
case 'connected':
    console.log('🔷 [FRONTEND] Got "connected" event, Session ID:', msg.session_id)

    // Store session ID for file uploads and session management
    this.sessionId = msg.session_id
    console.log('✅ [FRONTEND] Session ID stored:', this.sessionId)

    // NEW: Persist to localStorage
    this.saveSessionToLocalStorage(msg.session_id)

    // NEW: Load session files
    await this.loadSessionFiles()

    // ... rest of existing code
```

**Add methods**:
```javascript
saveSessionToLocalStorage(sessionId) {
    localStorage.setItem('bassi_active_session', JSON.stringify({
        id: sessionId,
        lastActivity: Date.now()
    }))
}

loadSessionFromLocalStorage() {
    const stored = localStorage.getItem('bassi_active_session')
    if (stored) {
        const session = JSON.parse(stored)
        // Check if session is recent (< 24h)
        if (Date.now() - session.lastActivity < 24 * 60 * 60 * 1000) {
            return session.id
        }
    }
    return null
}

async loadSessionFiles() {
    if (!this.sessionId) return

    try {
        const response = await fetch(`/api/sessions/${this.sessionId}/files`)
        const data = await response.json()

        this.sessionFiles = data.files || []
        console.log(`📁 Loaded ${this.sessionFiles.length} file(s) from session`)

        // Update file list UI
        this.renderFileList()
    } catch (error) {
        console.error('Failed to load session files:', error)
    }
}
```

**Tasks**:
- [ ] Add `saveSessionToLocalStorage()` method
- [ ] Add `loadSessionFromLocalStorage()` method
- [ ] Add `loadSessionFiles()` method
- [ ] Call `saveSessionToLocalStorage()` on connect
- [ ] Call `loadSessionFiles()` after session is set

---

#### 1.3 File List UI Component
**File**: `bassi/static/app.js` (add new component class)

**Add after existing classes** (around line 2900):

```javascript
class FileListArea {
    constructor(container, client) {
        this.container = container
        this.client = client
        this.expanded = false
        this.files = []
    }

    setFiles(files) {
        this.files = files
        this.render()
    }

    toggle() {
        this.expanded = !this.expanded
        this.render()
    }

    render() {
        const fileCount = this.files.length

        this.container.innerHTML = `
            <div class="file-list-area ${this.expanded ? 'expanded' : 'collapsed'}">
                <div class="file-area-header" onclick="window.fileListArea.toggle()">
                    <span class="file-count">📎 ${fileCount} file${fileCount !== 1 ? 's' : ''} in session</span>
                    <span class="toggle-icon">${this.expanded ? '▲' : '▼'}</span>
                </div>
                ${this.expanded ? this.renderFileList() : ''}
            </div>
        `
    }

    renderFileList() {
        if (this.files.length === 0) {
            return '<div class="file-list-empty">No files uploaded yet</div>'
        }

        return `
            <div class="file-list">
                ${this.files.map(file => this.renderFile(file)).join('')}
            </div>
        `
    }

    renderFile(file) {
        const icon = this.getFileIcon(file.name)
        const size = this.formatSize(file.size)
        const time = this.formatTime(file.uploaded_at)

        return `
            <div class="file-item">
                <span class="file-icon">${icon}</span>
                <div class="file-info">
                    <div class="file-name">${file.name}</div>
                    <div class="file-meta">${size} · ${time}</div>
                </div>
            </div>
        `
    }

    getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase()
        const icons = {
            'pdf': '📄',
            'png': '🖼️',
            'jpg': '🖼️',
            'jpeg': '🖼️',
            'gif': '🖼️',
            'csv': '📊',
            'xlsx': '📊',
            'txt': '📝',
            'md': '📝',
            'py': '🐍',
            'js': '📜'
        }
        return icons[ext] || '📎'
    }

    formatSize(bytes) {
        if (bytes < 1024) return `${bytes} B`
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    formatTime(isoString) {
        const date = new Date(isoString)
        const now = new Date()
        const diffMs = now - date
        const diffMins = Math.floor(diffMs / 60000)

        if (diffMins < 1) return 'just now'
        if (diffMins < 60) return `${diffMins} min ago`
        const diffHours = Math.floor(diffMins / 60)
        if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
        const diffDays = Math.floor(diffHours / 24)
        return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
    }
}
```

**Initialize in BassiClient constructor**:
```javascript
constructor() {
    // ... existing code

    // NEW: File list area
    this.sessionFiles = []
    const fileListContainer = document.createElement('div')
    fileListContainer.id = 'file-list-area'
    document.querySelector('.input-section').insertBefore(
        fileListContainer,
        document.querySelector('.input-wrapper')
    )
    this.fileListArea = new FileListArea(fileListContainer, this)
    window.fileListArea = this.fileListArea  // For onclick handlers
}

renderFileList() {
    this.fileListArea.setFiles(this.sessionFiles)
}
```

**Tasks**:
- [ ] Create `FileListArea` class
- [ ] Add `render()` method (collapsed/expanded states)
- [ ] Add `renderFileList()` method
- [ ] Add `renderFile()` method
- [ ] Add helper methods (getFileIcon, formatSize, formatTime)
- [ ] Initialize in BassiClient constructor
- [ ] Insert into DOM before input wrapper

---

#### 1.4 CSS Styling
**File**: `bassi/static/style.css`

**Add at end**:

```css
/* File List Area */
.file-list-area {
    background: #f5f5f5;
    border-radius: 8px;
    margin-bottom: 16px;
    transition: all 0.3s ease;
}

.file-list-area.collapsed .file-area-header {
    padding: 12px 16px;
    cursor: pointer;
}

.file-list-area.collapsed:hover {
    background: #ebebeb;
}

.file-list-area.expanded {
    border: 1px solid #ddd;
}

.file-area-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 500;
    padding: 12px 16px;
    cursor: pointer;
    user-select: none;
}

.file-count {
    color: #333;
}

.toggle-icon {
    color: #666;
    font-size: 12px;
}

.file-list {
    padding: 8px;
    max-height: 300px;
    overflow-y: auto;
}

.file-list-empty {
    padding: 24px;
    text-align: center;
    color: #999;
    font-style: italic;
}

.file-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    background: white;
    border-radius: 6px;
    margin-bottom: 8px;
}

.file-item:hover {
    background: #fafafa;
}

.file-icon {
    font-size: 24px;
}

.file-info {
    flex: 1;
}

.file-name {
    font-weight: 500;
    margin-bottom: 4px;
    color: #333;
}

.file-meta {
    font-size: 12px;
    color: #666;
}
```

**Tasks**:
- [ ] Add `.file-list-area` styles
- [ ] Add collapsed/expanded states
- [ ] Add `.file-area-header` styles
- [ ] Add `.file-list` scrollable area
- [ ] Add `.file-item` styles with hover
- [ ] Add responsive styles

---

## Phase 2: Session Management (Days 4-6)

### Backend Endpoints

#### 2.1 Session List Endpoints
**File**: `bassi/core_v3/web_server_v3.py`

**Add after existing endpoints** (around line 380):

```python
# Session management endpoints
@self.app.get("/api/sessions")
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "last_activity",
    filter_state: Optional[str] = None
):
    """List all sessions with pagination and filtering."""
    sessions = self.session_index.list_sessions(
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        filter_state=filter_state
    )

    return {
        "sessions": sessions,
        "total": len(self.session_index.index["sessions"]),
        "limit": limit,
        "offset": offset
    }

@self.app.get("/api/sessions/{session_id}")
async def get_session_details(session_id: str):
    """Get detailed session information."""
    if SessionWorkspace.exists(session_id):
        workspace = SessionWorkspace.load(session_id)
    else:
        raise HTTPException(404, "Session not found")

    return {
        "id": session_id,
        "display_name": workspace.display_name,
        "created_at": workspace.metadata["created_at"],
        "last_activity": workspace.metadata["last_activity"],
        "state": workspace.metadata.get("state", "CREATED"),
        "files": [
            {
                "name": f.name,
                "size": f.size,
                "path": str(f.path),
                "uploaded_at": f.uploaded_at
            }
            for f in workspace.list_files()
        ],
        "message_count": workspace.metadata.get("message_count", 0)
    }

@self.app.post("/api/sessions")
async def create_session(body: dict = None):
    """Create new session."""
    session_id = str(uuid.uuid4())
    workspace = SessionWorkspace(session_id, create=True)

    if body and "display_name" in body:
        workspace.update_display_name(body["display_name"])

    self.session_index.add_session(workspace)

    return {
        "id": session_id,
        "display_name": workspace.display_name
    }

@self.app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete session and its workspace."""
    if SessionWorkspace.exists(session_id):
        workspace = SessionWorkspace.load(session_id)
        workspace.delete()

        # Remove from index
        if session_id in self.session_index.index["sessions"]:
            del self.session_index.index["sessions"][session_id]
            self.session_index._save_index()

        return {"deleted": session_id}
    else:
        raise HTTPException(404, "Session not found")
```

**Tasks**:
- [ ] Add `GET /api/sessions` (list with pagination)
- [ ] Add `GET /api/sessions/{id}` (detail view)
- [ ] Add `POST /api/sessions` (create new)
- [ ] Add `DELETE /api/sessions/{id}` (delete)
- [ ] Add missing imports (uuid, HTTPException, Optional)

---

### Frontend Session Sidebar

#### 2.2 Session Sidebar Component
**File**: `bassi/static/components/session-sidebar.js` (NEW FILE)

```javascript
class SessionSidebar {
    constructor(container, client) {
        this.container = container
        this.client = client
        this.sessions = []
        this.filter = 'all'  // 'all', 'active', 'archived'
        this.searchTerm = ''
    }

    async load() {
        const response = await fetch('/api/sessions?limit=100')
        const data = await response.json()
        this.sessions = data.sessions
        this.render()
    }

    render() {
        const grouped = this.groupByDate(this.filteredSessions())

        this.container.innerHTML = `
            <div class="session-sidebar">
                <div class="sidebar-header">
                    <h2>🏠 BASSI</h2>
                    <button class="new-session-btn" onclick="sessionSidebar.createNewSession()">⊕</button>
                </div>

                <div class="search-bar">
                    <input type="text"
                           placeholder="🔍 Search sessions..."
                           oninput="sessionSidebar.handleSearch(event)"
                           value="${this.searchTerm}">
                </div>

                <div class="filter-tabs">
                    <button class="${this.filter === 'all' ? 'active' : ''}"
                            onclick="sessionSidebar.setFilter('all')">All</button>
                    <button class="${this.filter === 'active' ? 'active' : ''}"
                            onclick="sessionSidebar.setFilter('active')">Active</button>
                    <button class="${this.filter === 'archived' ? 'active' : ''}"
                            onclick="sessionSidebar.setFilter('archived')">Archived</button>
                </div>

                <div class="session-list">
                    ${Object.entries(grouped).map(([group, sessions]) => `
                        <div class="session-group">
                            <div class="group-header">📅 ${group}</div>
                            ${sessions.map(session => this.renderSession(session)).join('')}
                        </div>
                    `).join('')}
                </div>
            </div>
        `
    }

    renderSession(session) {
        const isActive = session.id === this.client.sessionId

        return `
            <div class="session-item ${isActive ? 'active' : ''}"
                 onclick="sessionSidebar.selectSession('${session.id}')">
                <div class="session-header">
                    ${isActive ? '●' : ''} ${session.display_name}
                </div>
                <div class="session-meta">
                    📎 ${session.file_count} files · ${session.message_count} messages
                </div>
                <div class="session-actions">
                    <button onclick="sessionSidebar.resumeSession('${session.id}'); event.stopPropagation()">Resume</button>
                    <button onclick="sessionSidebar.deleteSession('${session.id}'); event.stopPropagation()">Delete</button>
                </div>
            </div>
        `
    }

    groupByDate(sessions) {
        const groups = {
            'Today': [],
            'Yesterday': [],
            'This Week': [],
            'Older': []
        }

        const now = new Date()
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000)
        const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)

        for (const session of sessions) {
            const sessionDate = new Date(session.last_activity)

            if (sessionDate >= today) {
                groups['Today'].push(session)
            } else if (sessionDate >= yesterday) {
                groups['Yesterday'].push(session)
            } else if (sessionDate >= weekAgo) {
                groups['This Week'].push(session)
            } else {
                groups['Older'].push(session)
            }
        }

        // Remove empty groups
        return Object.fromEntries(
            Object.entries(groups).filter(([_, sessions]) => sessions.length > 0)
        )
    }

    filteredSessions() {
        let filtered = this.sessions

        // Apply state filter
        if (this.filter === 'active') {
            filtered = filtered.filter(s => s.state !== 'ARCHIVED')
        } else if (this.filter === 'archived') {
            filtered = filtered.filter(s => s.state === 'ARCHIVED')
        }

        // Apply search
        if (this.searchTerm) {
            const term = this.searchTerm.toLowerCase()
            filtered = filtered.filter(s =>
                s.display_name.toLowerCase().includes(term)
            )
        }

        return filtered
    }

    handleSearch(event) {
        this.searchTerm = event.target.value
        this.render()
    }

    setFilter(filter) {
        this.filter = filter
        this.render()
    }

    async createNewSession() {
        const response = await fetch('/api/sessions', { method: 'POST' })
        const session = await response.json()

        // Reload page with new session
        location.reload()
    }

    async resumeSession(sessionId) {
        // Will implement in Phase 4
        console.log('Resume session:', sessionId)
        location.reload()
    }

    async deleteSession(sessionId) {
        if (!confirm('Delete this session? This cannot be undone.')) {
            return
        }

        await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' })
        await this.load()
    }

    selectSession(sessionId) {
        console.log('Selected session:', sessionId)
    }
}
```

**Tasks**:
- [ ] Create `session-sidebar.js` file
- [ ] Implement `SessionSidebar` class
- [ ] Add `load()`, `render()`, `renderSession()` methods
- [ ] Add `groupByDate()` logic
- [ ] Add `filteredSessions()` with search/filter
- [ ] Add session actions (create, delete, resume placeholder)

---

#### 2.3 Sidebar CSS & Integration
**File**: `bassi/static/style.css`

```css
/* Session Sidebar */
.session-sidebar {
    width: 300px;
    height: 100vh;
    background: #f8f9fa;
    border-right: 1px solid #dee2e6;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.sidebar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    border-bottom: 1px solid #dee2e6;
}

.sidebar-header h2 {
    margin: 0;
    font-size: 18px;
}

.new-session-btn {
    width: 32px;
    height: 32px;
    border: none;
    background: #4CAF50;
    color: white;
    border-radius: 50%;
    cursor: pointer;
    font-size: 20px;
}

.search-bar {
    padding: 12px;
}

.search-bar input {
    width: 100%;
    padding: 8px;
    border: 1px solid #dee2e6;
    border-radius: 4px;
}

.filter-tabs {
    display: flex;
    gap: 8px;
    padding: 0 12px 12px;
}

.filter-tabs button {
    flex: 1;
    padding: 6px;
    border: 1px solid #dee2e6;
    background: white;
    border-radius: 4px;
    cursor: pointer;
}

.filter-tabs button.active {
    background: #1976d2;
    color: white;
    border-color: #1976d2;
}

.session-list {
    flex: 1;
    overflow-y: auto;
    padding: 0 12px;
}

.session-group {
    margin-bottom: 16px;
}

.group-header {
    font-weight: 600;
    margin-bottom: 8px;
    color: #666;
}

.session-item {
    background: white;
    padding: 12px;
    border-radius: 6px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: all 0.2s;
}

.session-item:hover {
    background: #f0f0f0;
}

.session-item.active {
    background: #e3f2fd;
    border-left: 3px solid #1976d2;
}

.session-header {
    font-weight: 500;
    margin-bottom: 4px;
}

.session-meta {
    font-size: 12px;
    color: #666;
    margin-bottom: 8px;
}

.session-actions {
    display: none;
    gap: 4px;
}

.session-item:hover .session-actions {
    display: flex;
}

.session-actions button {
    flex: 1;
    padding: 4px 8px;
    font-size: 11px;
    border: 1px solid #dee2e6;
    background: white;
    border-radius: 3px;
    cursor: pointer;
}
```

**File**: `bassi/static/index.html`

Update layout to add sidebar:
```html
<body>
    <div id="sidebar-container"></div>
    <div id="main-container">
        <!-- existing content -->
    </div>
</body>
```

Update CSS for 2-column layout:
```css
body {
    display: flex;
    margin: 0;
    height: 100vh;
}

#main-container {
    flex: 1;
    overflow: hidden;
}
```

**File**: `bassi/static/app.js`

Initialize sidebar in constructor:
```javascript
// Load sidebar component
const script = document.createElement('script')
script.src = '/static/components/session-sidebar.js'
script.onload = () => {
    const sidebarContainer = document.getElementById('sidebar-container')
    window.sessionSidebar = new SessionSidebar(sidebarContainer, this)
    window.sessionSidebar.load()
}
document.head.appendChild(script)
```

**Tasks**:
- [ ] Add sidebar CSS styles
- [ ] Update `index.html` layout (2-column)
- [ ] Create sidebar container in HTML
- [ ] Load `session-sidebar.js` dynamically
- [ ] Initialize sidebar in BassiClient

---

## Phase 3: LLM Naming + Symlinks (Days 7-9)

### Backend Implementation

#### 3.1 Session Naming Service
**File**: `bassi/core_v3/session_naming.py` (NEW FILE)

```python
"""Session naming service using LLM to generate meaningful names."""

import re
from anthropic import AsyncAnthropic

class SessionNamingService:
    """Generate session names using LLM."""

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)

    async def generate_name(
        self,
        first_user_msg: str,
        first_assistant_msg: str
    ) -> str:
        """
        Generate kebab-case session name from first exchange.

        Returns:
            Kebab-case name (e.g., "analyze-pdf-documents")
        """
        prompt = f"""Generate a short descriptive name for this conversation.

Requirements:
- 3-5 words maximum
- Lowercase with hyphens (kebab-case)
- Descriptive of the task/topic
- No special characters except hyphens

User: {first_user_msg[:500]}
Assistant: {first_assistant_msg[:500]}

Examples:
- "analyze-pdf-documents"
- "create-sales-presentation"
- "debug-python-script"
- "research-competitors"

Name (just the kebab-case string):"""

        response = await self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )

        name = response.content[0].text.strip().lower()

        # Clean up
        name = re.sub(r'[^a-z0-9-]', '', name)
        name = re.sub(r'-+', '-', name)
        name = name.strip('-')

        return name[:50] if name else "untitled-session"
```

**Tasks**:
- [ ] Create `session_naming.py` file
- [ ] Implement `SessionNamingService` class
- [ ] Implement `generate_name()` method
- [ ] Add LLM prompt for name generation
- [ ] Add name cleaning/validation
- [ ] Add fallback for errors

---

#### 3.2 State Machine in SessionWorkspace
**File**: `bassi/core_v3/session_workspace.py`

```python
from enum import Enum

class SessionState(Enum):
    CREATED = "CREATED"           # Just created
    AUTO_NAMED = "AUTO_NAMED"     # LLM generated name
    FINALIZED = "FINALIZED"       # User explicitly ended
    ARCHIVED = "ARCHIVED"         # Auto-archived after 24h

class SessionWorkspace:
    # Add to existing class

    @property
    def state(self) -> SessionState:
        return SessionState(self.metadata.get("state", "CREATED"))

    def transition_to_auto_named(self, generated_name: str) -> None:
        """Transition from CREATED → AUTO_NAMED with symlink update."""
        if self.state != SessionState.CREATED:
            raise ValueError(f"Cannot auto-name from state {self.state}")

        self.update_display_name(generated_name)
        self.metadata["state"] = SessionState.AUTO_NAMED.value
        self.metadata["auto_named_at"] = datetime.now().isoformat()
        self._save_metadata()

        # Update symlink with new name
        self.update_symlink(generated_name)

    def finalize(self, final_name: Optional[str] = None) -> None:
        """Transition to FINALIZED (explicit end)."""
        if self.state == SessionState.FINALIZED:
            return  # Already finalized

        if final_name:
            self.update_display_name(final_name)
            self.update_symlink(final_name)

        self.metadata["state"] = SessionState.FINALIZED.value
        self.metadata["finalized_at"] = datetime.now().isoformat()
        self._save_metadata()
```

**Tasks**:
- [ ] Add `SessionState` enum
- [ ] Add `state` property
- [ ] Add `transition_to_auto_named()` method
- [ ] Add `finalize()` method
- [ ] Update symlink on state transitions

---

#### 3.3 Auto-Naming Integration in Web Server
**File**: `bassi/core_v3/web_server_v3.py`

```python
from bassi.core_v3.session_naming import SessionNamingService

class BassiWebServerV3:
    def __init__(self):
        # ... existing init

        # Session naming service
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self.naming_service = SessionNamingService(api_key)

        # Track if session has been named
        self.session_named: set[str] = set()

    async def _auto_name_session(
        self,
        session_id: str,
        user_msg: str,
        assistant_msg: str
    ):
        """Auto-generate name after first exchange."""
        # Only name once
        if session_id in self.session_named:
            return

        workspace = self.workspaces.get(session_id)
        if not workspace or workspace.state != SessionState.CREATED:
            return

        try:
            # Generate name asynchronously
            name = await self.naming_service.generate_name(
                user_msg, assistant_msg
            )
            workspace.transition_to_auto_named(name)
            self.session_index.add_session(workspace)
            self.session_named.add(session_id)

            logger.info(f"✨ Auto-named session: {name}")

            # Notify client
            await self._send_session_named_event(session_id, name)
        except Exception as e:
            logger.error(f"Failed to auto-name session: {e}")
            # Non-critical, continue without name

    async def _send_session_named_event(self, session_id: str, name: str):
        """Send session_named event to WebSocket client."""
        # Find active connection for this session
        for conn_id, session in self.agent_sessions.items():
            if conn_id == session_id:
                # Send event (implement based on your WebSocket structure)
                await self._send_event_to_session(session_id, {
                    "type": "session_named",
                    "name": name
                })
                break
```

Hook into message flow (in WebSocket handler):
```python
# After assistant responds to first user message
if not session_id in self.session_named:
    # Extract first user/assistant messages
    first_user_msg = ... # from conversation history
    first_assistant_msg = ... # from current response

    # Trigger auto-naming (non-blocking)
    asyncio.create_task(
        self._auto_name_session(session_id, first_user_msg, first_assistant_msg)
    )
```

**Add endpoint**:
```python
@self.app.post("/api/sessions/{session_id}/finalize")
async def finalize_session(session_id: str, body: dict = None):
    """Explicitly end and finalize session."""
    workspace = self.workspaces.get(session_id)
    if not workspace:
        raise HTTPException(404, "Session not found")

    final_name = body.get("name") if body else None
    workspace.finalize(final_name)

    return {
        "id": session_id,
        "state": workspace.state.value,
        "display_name": workspace.display_name
    }
```

**Tasks**:
- [ ] Initialize `SessionNamingService` in `__init__`
- [ ] Add `_auto_name_session()` method
- [ ] Hook into message flow (detect first response)
- [ ] Add `session_named` event to WebSocket
- [ ] Add `POST /api/sessions/{id}/finalize` endpoint

---

### Frontend Updates

#### 3.4 Handle Session Named Event
**File**: `bassi/static/app.js`

```javascript
// In handleMessage(msg)
case 'session_named':
    console.log('✨ Session named:', msg.name)
    // Update sidebar if visible
    if (window.sessionSidebar) {
        await window.sessionSidebar.load()
    }
    // Show notification
    this.showNotification(`Session named: "${msg.name}"`)
    break
```

**Tasks**:
- [ ] Add `session_named` event handler
- [ ] Reload sidebar on name change
- [ ] Show notification to user

---

## Phase 4: Resume + Agent Awareness (Days 10-12)

### Backend Implementation

#### 4.1 Session Resume Endpoint
**File**: `bassi/core_v3/web_server_v3.py`

```python
@self.app.post("/api/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume session with full context restoration."""
    if not SessionWorkspace.exists(session_id):
        raise HTTPException(404, "Session not found")

    workspace = SessionWorkspace.load(session_id)

    # Load conversation history
    history = workspace.load_history()

    # Load SDK context if available
    sdk_context = None
    context_path = workspace.physical_path / "context.json"
    if context_path.exists():
        with open(context_path, encoding="utf-8") as f:
            sdk_context = json.load(f)

    return {
        "id": session_id,
        "display_name": workspace.display_name,
        "history": history,
        "context": sdk_context,
        "files": [
            {
                "name": f.name,
                "size": f.size,
                "path": str(f.path),
                "uploaded_at": f.uploaded_at
            }
            for f in workspace.list_files()
        ]
    }
```

Add history loading to SessionWorkspace:
```python
def load_history(self) -> list[dict]:
    """Load conversation history from history.md."""
    history_path = self.physical_path / "history.md"
    if not history_path.exists():
        return []

    # Parse markdown history
    # (Implement based on your history format)
    return []
```

**Tasks**:
- [ ] Add `POST /api/sessions/{id}/resume` endpoint
- [ ] Add `load_history()` method to SessionWorkspace
- [ ] Return history, context, and files

---

#### 4.2 Workspace-Aware System Prompt
**File**: `bassi/core_v3/agent_session.py`

```python
def _build_system_prompt(self, workspace: SessionWorkspace) -> str:
    """Build system prompt with workspace awareness."""

    user_files = [f.name for f in workspace.list_files()]

    base_prompt = f"""You are Claude, an AI assistant working in a session workspace.

## Your Current Workspace

**Path**: {workspace.physical_path}
**Session**: {workspace.display_name}
**Files Available**: {len(user_files)}

## Workspace Structure

Your session has an organized directory structure:

1. **DATA_FROM_USER/**: Files uploaded by the user
   - Current files: {', '.join(user_files) if user_files else 'none'}
   - You can read these directly

2. **RESULTS_FROM_AGENT/**: Your final outputs (save here)
   - Use this for reports, analyses, cleaned data
   - Example: analysis_report.md, summary.csv

3. **SCRIPTS_FROM_AGENT/**: Python scripts you create
   - Use this for reusable automation
   - Example: data_processor.py, web_scraper.py

4. **DATA_FROM_AGENT/**: Intermediate data
   - Use this for web fetches, API responses
   - Example: api_response.json, temp_data.csv

## Guidelines

- When you create files, use the appropriate directory
- You can search across all workspace files
- Scripts in SCRIPTS_FROM_AGENT/ can be re-run by user
- Final outputs should go in RESULTS_FROM_AGENT/
- Intermediate/temporary data goes in DATA_FROM_AGENT/

**Current working directory**: {workspace.physical_path / "DATA_FROM_USER"}
"""

    return base_prompt
```

Update agent initialization to pass workspace:
```python
# In web_server_v3.py when creating agent
config = SessionConfig(
    cwd=str(workspace.physical_path / "DATA_FROM_USER"),
    system_prompt=self._build_system_prompt(workspace)
)
```

**Tasks**:
- [ ] Add `_build_system_prompt()` method
- [ ] Include workspace path and file list
- [ ] Explain folder structure
- [ ] Pass to SessionConfig on agent creation

---

### Frontend Resume Implementation

#### 4.3 Resume Session in Sidebar
**File**: `bassi/static/components/session-sidebar.js`

```javascript
async resumeSession(sessionId) {
    try {
        // Get session details
        const response = await fetch(`/api/sessions/${sessionId}/resume`, {
            method: 'POST'
        })
        const session = await response.json()

        // Switch session
        this.client.sessionId = sessionId
        this.client.saveSessionToLocalStorage(sessionId)

        // Restore UI
        this.client.sessionFiles = session.files
        this.client.renderFileList()

        // Render history messages
        if (session.history && session.history.length > 0) {
            this.client.conversationEl.innerHTML = ''
            for (const msg of session.history) {
                // Render based on message type
                if (msg.role === 'user') {
                    this.client.addUserMessage(msg.content)
                } else if (msg.role === 'assistant') {
                    this.client.addAssistantMessage(msg.content)
                }
            }
        }

        // Reconnect WebSocket with new session
        // (May need to close and reopen connection)
        this.client.reconnect()

        // Show success
        this.client.showNotification(`Resumed: ${session.display_name}`)

    } catch (error) {
        console.error('Failed to resume session:', error)
        this.client.showNotification('Failed to resume session', 'error')
    }
}
```

**Tasks**:
- [ ] Implement `resumeSession()` method
- [ ] Fetch session from resume endpoint
- [ ] Restore file list
- [ ] Render conversation history
- [ ] Reconnect WebSocket

---

## Summary: Implementation Order

### Days 1-3: Phase 1 (File Browser)
1. Backend: Add symlink management to SessionWorkspace
2. Frontend: Add localStorage session persistence
3. Frontend: Create FileListArea component
4. Frontend: Add CSS styling
5. Integration: Wire everything together

### Days 4-6: Phase 2 (Session Management)
1. Backend: Add session endpoints (list, detail, create, delete)
2. Frontend: Create SessionSidebar component
3. Frontend: Add sidebar CSS
4. Integration: Update HTML layout for 2-column
5. Testing: Verify session operations

### Days 7-9: Phase 3 (Auto-Naming)
1. Backend: Create SessionNamingService
2. Backend: Add state machine to SessionWorkspace
3. Backend: Integrate auto-naming in web server
4. Backend: Update symlinks on naming
5. Frontend: Handle session_named events

### Days 10-12: Phase 4 (Resume + Workspace)
1. Backend: Add resume endpoint
2. Backend: Add workspace-aware system prompt
3. Frontend: Implement resume in sidebar
4. Integration: Test full resume flow
5. Polish: Final testing and fixes

---

## Notes

- **No Tests**: Tests deferred (being reworked)
- **Symlinks**: Created on session creation, updated on naming
- **Physical Storage**: Always uses `chats/{session_id}/`
- **Human-Readable**: Symlinks in `chats-human-readable/`
- **Naming**: `{timestamp}__{name}__{short-id}` → `../chats/{session_id}`

---

## Success Criteria

- ✅ Files persist in UI across refreshes
- ✅ Session history sidebar shows all sessions
- ✅ Sessions auto-name with meaningful names
- ✅ Symlinks provide human-readable filesystem browsing
- ✅ Resume restores full conversation context
- ✅ Agent knows workspace structure

---

## Ready to Start?

Beginning with **Phase 1: File Browser UI** implementation.
