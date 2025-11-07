# Session Workspace - Implementation Plan

**Status**: Ready for Implementation
**Version**: 1.0
**Date**: 2025-11-07
**Estimated Duration**: 10-12 days (2 weeks)

---

## Executive Summary

This plan implements session-aware workspaces with persistent file storage, browsable history, and resumable sessions. The implementation follows a **4-phase approach** with each phase delivering tangible user value.

**Key Deliverables**:
- ✅ Session-specific file storage
- ✅ Expandable/collapsible file UI
- ✅ Session history sidebar with search
- ✅ Session resume functionality
- ✅ LLM-generated session names
- ✅ Agent folder awareness

---

## Architecture Decisions (Finalized)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Architecture** | C (Hybrid) | SDK owns conversation, workspace owns files |
| **Storage Location** | Project root (`bassi/chats/`) | Simple, keeps all data together |
| **Naming** | `iso-date-time__session_id__description` | Immutable physical path + mutable display name |
| **Naming Strategy** | Progressive (CREATED → AUTO_NAMED → FINALIZED) | Allows evolution from generic to meaningful |
| **File UI** | Collapsed by default, expand on drop | Unobtrusive but accessible |
| **Scope** | Full (Phases 1-4) | ~2 weeks implementation |

---

## Phase 1: Core Infrastructure (Days 1-3)

**Goal**: Session-specific file storage with persistent UI

### Backend Work (Day 1-2)

#### 1.1: Create SessionWorkspace Class
**File**: `bassi/core_v3/session_workspace.py` (new)

**Implementation**:
```python
class SessionWorkspace:
    """
    Manages session-specific file storage and organization.

    Physical path: chats/{session_id}/
    Display name: Stored in metadata (mutable)
    """

    def __init__(self, session_id: str, base_path: Path = Path("chats")):
        self.session_id = session_id
        self.physical_path = base_path / session_id
        self.metadata = self._load_or_create_metadata()
        self._upload_lock = asyncio.Lock()

    def _create_directory_structure(self):
        """Create DATA_FROM_USER, RESULTS_FROM_AGENT, etc."""
        for folder in ["DATA_FROM_USER", "RESULTS_FROM_AGENT",
                       "SCRIPTS_FROM_AGENT", "DATA_FROM_AGENT"]:
            (self.physical_path / folder).mkdir(parents=True, exist_ok=True)

    async def upload_file(self, file: UploadFile) -> Path:
        """Upload file to DATA_FROM_USER/ with hash-based deduplication"""
        async with self._upload_lock:
            # Stream upload + hash calculation
            # Check for duplicates
            # Save with unique name

    def list_files(self) -> list[FileInfo]:
        """List all files in DATA_FROM_USER/"""

    def save_message(self, message: Message):
        """Append to history.md"""

    @property
    def display_name(self) -> str:
        """Get human-readable name from metadata"""
        return self.metadata.get("display_name", f"Session {self.session_id[:8]}")

    def update_display_name(self, name: str):
        """Update display name WITHOUT moving folder"""
        self.metadata["display_name"] = name
        self._save_metadata()
```

**Tests**: `bassi/core_v3/tests/test_session_workspace.py`
- Test workspace creation
- Test directory structure
- Test file upload with deduplication
- Test metadata management
- Test display name updates

**Acceptance Criteria**:
- ✅ Workspace creates all required directories
- ✅ Files upload to DATA_FROM_USER/
- ✅ Duplicate files are detected and rejected
- ✅ Metadata persists correctly
- ✅ Display name updates don't affect physical path

---

#### 1.2: Session Index Manager
**File**: `bassi/core_v3/session_index.py` (new)

**Implementation**:
```python
class SessionIndex:
    """
    In-memory index for fast session listing.
    Backed by chats/.index.json for persistence.
    """

    def __init__(self, base_path: Path = Path("chats")):
        self.index_path = base_path / ".index.json"
        self.index = self._load_index()

    def add_session(self, workspace: SessionWorkspace):
        """Add session to index"""
        self.index["sessions"][workspace.session_id] = {
            "id": workspace.session_id,
            "display_name": workspace.display_name,
            "created_at": workspace.metadata["created_at"],
            "last_activity": workspace.metadata["last_activity"],
            "file_count": len(workspace.list_files()),
            "message_count": workspace.metadata.get("message_count", 0),
            "state": workspace.metadata.get("state", "CREATED")
        }
        self._save_index()

    def list_sessions(self,
                      limit: int = 50,
                      offset: int = 0,
                      sort_by: str = "last_activity",
                      filter_state: Optional[str] = None) -> list[dict]:
        """Fast listing without filesystem traversal"""
        sessions = list(self.index["sessions"].values())

        if filter_state:
            sessions = [s for s in sessions if s["state"] == filter_state]

        sessions.sort(key=lambda s: s.get(sort_by, ""), reverse=True)
        return sessions[offset:offset + limit]

    def update_activity(self, session_id: str):
        """Update last activity timestamp"""
        if session_id in self.index["sessions"]:
            self.index["sessions"][session_id]["last_activity"] = datetime.now().isoformat()
            self._save_index()
```

**Tests**: `bassi/core_v3/tests/test_session_index.py`
- Test index creation
- Test session addition
- Test fast listing (performance benchmark)
- Test sorting and filtering
- Test activity updates

**Acceptance Criteria**:
- ✅ Index loads/saves correctly
- ✅ Listing 1000 sessions takes < 100ms
- ✅ Filtering works correctly
- ✅ Activity updates are atomic

---

#### 1.3: Integrate with web_server_v3.py
**File**: `bassi/core_v3/web_server_v3.py` (modify)

**Changes**:
```python
class BassiWebServerV3:
    def __init__(self):
        self.sessions: dict[str, AgentSession] = {}
        self.workspaces: dict[str, SessionWorkspace] = {}  # NEW
        self.session_index = SessionIndex()  # NEW

    async def handle_websocket(self, websocket: WebSocket):
        session_id = self._get_or_create_session_id(websocket)

        # Create workspace for session
        workspace = SessionWorkspace(session_id)
        self.workspaces[session_id] = workspace
        self.session_index.add_session(workspace)

        # Create agent with workspace path
        config = SessionConfig(
            cwd=str(workspace.physical_path / "DATA_FROM_USER")
        )
        agent_session = AgentSession(session_id=session_id, config=config)
        self.sessions[session_id] = agent_session
```

**New Endpoints**:
```python
@app.post("/api/upload")
async def upload_file(file: UploadFile, session_id: str = Form(...)):
    """Upload file to session workspace"""
    workspace = server.workspaces.get(session_id)
    if not workspace:
        raise HTTPException(404, "Session not found")

    path = await workspace.upload_file(file)
    server.session_index.update_activity(session_id)

    return {
        "filename": path.name,
        "size": path.stat().st_size,
        "path": str(path)
    }

@app.get("/api/sessions/{session_id}/files")
async def list_session_files(session_id: str):
    """List all files in session"""
    workspace = server.workspaces.get(session_id)
    if not workspace:
        raise HTTPException(404, "Session not found")

    return {"files": [f.to_dict() for f in workspace.list_files()]}
```

**Tests**: `bassi/core_v3/tests/test_web_server_v3.py` (extend)
- Test session creation with workspace
- Test file upload endpoint
- Test file list endpoint
- Test WebSocket with workspace integration

**Acceptance Criteria**:
- ✅ WebSocket creates workspace on connect
- ✅ Upload saves to correct session folder
- ✅ File list returns all session files
- ✅ Session index updates on activity

---

### Frontend Work (Day 2-3)

#### 1.4: Session Tracking in app.js
**File**: `bassi/static/app.js` (modify)

**Changes**:
```javascript
class BassiClient {
    constructor() {
        // Session management
        this.sessionId = this.loadOrCreateSession()
        this.workspace = null

        // File state
        this.sessionFiles = []      // All files in workspace
        this.pendingFiles = []      // Files to send with next message

        // UI state
        this.fileAreaExpanded = false
    }

    loadOrCreateSession() {
        const stored = localStorage.getItem('bassi_active_session')
        if (stored) {
            const session = JSON.parse(stored)
            // Check if session is recent (< 24h)
            if (Date.now() - session.lastActivity < 24 * 60 * 60 * 1000) {
                return session.id
            }
        }

        // Create new session
        const newSessionId = this.generateSessionId()
        this.saveSession(newSessionId)
        return newSessionId
    }

    saveSession(sessionId) {
        localStorage.setItem('bassi_active_session', JSON.stringify({
            id: sessionId,
            lastActivity: Date.now()
        }))
    }

    async loadSessionFiles() {
        const response = await fetch(`/api/sessions/${this.sessionId}/files`)
        const data = await response.json()
        this.sessionFiles = data.files
        this.renderFileList()
    }
}
```

**Tests**: Manual browser testing + E2E tests
- Test session creation
- Test session persistence across refresh
- Test file list loading
- Test localStorage handling

**Acceptance Criteria**:
- ✅ Session survives browser refresh
- ✅ Files reload on page load
- ✅ Session expires after 24h inactivity

---

#### 1.5: Expandable File Upload Area
**File**: `bassi/static/app.js` (add component)

**Implementation**:
```javascript
class FileUploadArea {
    constructor(container, client) {
        this.container = container
        this.client = client
        this.expanded = false
        this.render()
    }

    render() {
        const fileCount = this.client.sessionFiles.length

        this.container.innerHTML = `
            <div class="file-upload-area ${this.expanded ? 'expanded' : 'collapsed'}">
                <div class="file-area-header" onclick="fileArea.toggle()">
                    <span class="file-count">📎 ${fileCount} file${fileCount !== 1 ? 's' : ''} in session</span>
                    <span class="toggle-icon">${this.expanded ? '▲' : '▼'}</span>
                </div>
                ${this.expanded ? this.renderFileList() : ''}
                ${this.expanded ? this.renderDropZone() : ''}
            </div>
        `
    }

    renderFileList() {
        return `
            <div class="file-list">
                ${this.client.sessionFiles.map(file => `
                    <div class="file-preview" data-filename="${file.name}">
                        <div class="file-icon">${this.getFileIcon(file)}</div>
                        <div class="file-info">
                            <div class="file-name">${file.name}</div>
                            <div class="file-meta">${this.formatSize(file.size)} · ${this.formatTime(file.uploaded_at)}</div>
                        </div>
                        <button class="file-remove" onclick="fileArea.removeFile('${file.name}')">×</button>
                    </div>
                `).join('')}
            </div>
        `
    }

    renderDropZone() {
        return `
            <div class="drop-zone"
                 ondragover="fileArea.handleDragOver(event)"
                 ondrop="fileArea.handleDrop(event)">
                Drop files here or <span class="upload-link" onclick="fileArea.clickUpload()">click to upload</span>
            </div>
        `
    }

    toggle() {
        this.expanded = !this.expanded
        this.render()
    }

    async handleDrop(event) {
        event.preventDefault()
        const files = Array.from(event.dataTransfer.files)

        // Auto-expand on drop
        if (!this.expanded) {
            this.expanded = true
        }

        // Upload files
        for (const file of files) {
            await this.client.uploadFile(file)
        }

        // Reload file list
        await this.client.loadSessionFiles()
        this.render()
    }
}
```

**CSS**: `bassi/static/style.css` (add)
```css
.file-upload-area {
    background: #f5f5f5;
    border-radius: 8px;
    margin-bottom: 16px;
    transition: all 0.3s ease;
}

.file-upload-area.collapsed .file-area-header {
    padding: 12px 16px;
    cursor: pointer;
}

.file-upload-area.collapsed:hover {
    background: #ebebeb;
}

.file-upload-area.expanded {
    border: 1px solid #ddd;
}

.file-area-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 500;
}

.file-list {
    padding: 8px;
    max-height: 300px;
    overflow-y: auto;
}

.file-preview {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    background: white;
    border-radius: 6px;
    margin-bottom: 8px;
}

.file-preview:hover {
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
}

.file-meta {
    font-size: 12px;
    color: #666;
}

.file-remove {
    width: 24px;
    height: 24px;
    border: none;
    background: #ff4444;
    color: white;
    border-radius: 50%;
    cursor: pointer;
    font-size: 18px;
    line-height: 1;
}

.file-remove:hover {
    background: #cc0000;
}

.drop-zone {
    margin: 8px;
    padding: 32px;
    border: 2px dashed #ccc;
    border-radius: 6px;
    text-align: center;
    color: #666;
}

.drop-zone.drag-over {
    border-color: #4CAF50;
    background: #f0fff0;
}

.upload-link {
    color: #1976d2;
    text-decoration: underline;
    cursor: pointer;
}
```

**Acceptance Criteria**:
- ✅ Collapsed by default
- ✅ Shows file count always
- ✅ Expands on toggle click
- ✅ Expands automatically on file drop
- ✅ Shows all session files
- ✅ Files can be removed
- ✅ Drop zone is visible when expanded

---

### Phase 1 Deliverable

**What Works After Phase 1**:
- ✅ Each session has its own workspace folder
- ✅ Files upload to `chats/{session_id}/DATA_FROM_USER/`
- ✅ Files persist and don't disappear after sending
- ✅ Expandable file area shows all session files
- ✅ Session survives browser refresh
- ✅ File deduplication prevents duplicates

**Demo Script**:
1. Open browser → new session created
2. Drop 2 files → uploaded to workspace
3. File area expands, shows both files
4. Send message with files → files still visible
5. Refresh browser → files still there
6. Check filesystem → `chats/{session_id}/DATA_FROM_USER/` contains files

---

## Phase 2: Session Management UI (Days 4-6)

**Goal**: Browsable session history with search and filtering

### Backend Work (Day 4)

#### 2.1: Session Management Endpoints
**File**: `bassi/core_v3/web_server_v3.py` (extend)

**New Endpoints**:
```python
@app.get("/api/sessions")
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "last_activity",
    filter_state: Optional[str] = None
):
    """List all sessions with pagination"""
    sessions = server.session_index.list_sessions(
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        filter_state=filter_state
    )

    return {
        "sessions": sessions,
        "total": len(server.session_index.index["sessions"]),
        "limit": limit,
        "offset": offset
    }

@app.get("/api/sessions/{session_id}")
async def get_session_details(session_id: str):
    """Get detailed session information"""
    workspace = SessionWorkspace(session_id)

    return {
        "id": session_id,
        "display_name": workspace.display_name,
        "created_at": workspace.metadata["created_at"],
        "last_activity": workspace.metadata["last_activity"],
        "state": workspace.metadata.get("state", "CREATED"),
        "files": [f.to_dict() for f in workspace.list_files()],
        "message_count": workspace.metadata.get("message_count", 0)
    }

@app.post("/api/sessions")
async def create_session(body: dict = None):
    """Create new session"""
    session_id = str(uuid.uuid4())
    workspace = SessionWorkspace(session_id)

    if body and "display_name" in body:
        workspace.update_display_name(body["display_name"])

    server.session_index.add_session(workspace)

    return {
        "id": session_id,
        "display_name": workspace.display_name
    }

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete session and its workspace"""
    workspace = SessionWorkspace(session_id)

    # Remove from index
    if session_id in server.session_index.index["sessions"]:
        del server.session_index.index["sessions"][session_id]
        server.session_index._save_index()

    # Remove workspace directory
    if workspace.physical_path.exists():
        shutil.rmtree(workspace.physical_path)

    return {"deleted": session_id}
```

**Tests**: `bassi/core_v3/tests/test_web_server_v3.py` (extend)
- Test session listing with pagination
- Test session details retrieval
- Test session creation
- Test session deletion

**Acceptance Criteria**:
- ✅ List endpoint returns paginated results
- ✅ List supports sorting and filtering
- ✅ Details endpoint returns complete info
- ✅ Create endpoint generates valid session
- ✅ Delete endpoint removes session and files

---

### Frontend Work (Day 5-6)

#### 2.2: Session Sidebar Component
**File**: `bassi/static/components/session-sidebar.js` (new)

**Implementation**:
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
                    <button class="new-session-btn" onclick="sidebar.createNewSession()">⊕</button>
                </div>

                <div class="search-bar">
                    <input type="text"
                           placeholder="🔍 Search sessions..."
                           oninput="sidebar.handleSearch(event)"
                           value="${this.searchTerm}">
                </div>

                <div class="filter-tabs">
                    <button class="${this.filter === 'all' ? 'active' : ''}"
                            onclick="sidebar.setFilter('all')">All</button>
                    <button class="${this.filter === 'active' ? 'active' : ''}"
                            onclick="sidebar.setFilter('active')">Active</button>
                    <button class="${this.filter === 'archived' ? 'active' : ''}"
                            onclick="sidebar.setFilter('archived')">Archived</button>
                </div>

                <div class="session-list">
                    ${Object.entries(grouped).map(([group, sessions]) => `
                        <div class="session-group">
                            <div class="group-header">📅 ${group}</div>
                            ${sessions.map(session => this.renderSession(session)).join('')}
                        </div>
                    `).join('')}
                </div>

                <div class="sidebar-footer">
                    <div class="current-session-info">
                        💾 Session: ${this.client.sessionId.slice(0, 8)}
                        <br>
                        🔄 Last activity: ${this.formatTime(Date.now())}
                    </div>
                </div>
            </div>
        `
    }

    renderSession(session) {
        const isActive = session.id === this.client.sessionId

        return `
            <div class="session-item ${isActive ? 'active' : ''}"
                 onclick="sidebar.selectSession('${session.id}')">
                <div class="session-header">
                    ${isActive ? '●' : ''} ${session.display_name}
                    <span class="session-time">[${this.formatTime(session.last_activity)}]</span>
                </div>
                <div class="session-meta">
                    📎 ${session.file_count} files • ${session.message_count} messages
                </div>
                <div class="session-actions">
                    <button onclick="sidebar.resumeSession('${session.id}'); event.stopPropagation()">Resume</button>
                    <button onclick="sidebar.exportSession('${session.id}'); event.stopPropagation()">Export</button>
                    <button onclick="sidebar.deleteSession('${session.id}'); event.stopPropagation()">Delete</button>
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

    async createNewSession() {
        const response = await fetch('/api/sessions', { method: 'POST' })
        const session = await response.json()

        // Switch to new session
        this.client.sessionId = session.id
        this.client.saveSession(session.id)

        // Clear chat and reload
        location.reload()
    }

    async resumeSession(sessionId) {
        // Switch to session
        this.client.sessionId = sessionId
        this.client.saveSession(sessionId)

        // Reload page with new session
        location.reload()
    }

    async deleteSession(sessionId) {
        if (!confirm('Delete this session? This cannot be undone.')) {
            return
        }

        await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' })

        // Reload session list
        await this.load()
    }
}
```

**CSS**: `bassi/static/style.css` (extend)
```css
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
    display: flex;
    justify-content: space-between;
    font-weight: 500;
    margin-bottom: 4px;
}

.session-time {
    font-size: 12px;
    color: #666;
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

.sidebar-footer {
    padding: 12px;
    border-top: 1px solid #dee2e6;
    font-size: 12px;
    color: #666;
}
```

**Acceptance Criteria**:
- ✅ Sidebar shows all sessions grouped by date
- ✅ Search filters sessions by name
- ✅ Filter tabs work (All/Active/Archived)
- ✅ Current session is highlighted
- ✅ Resume button switches to session
- ✅ Delete button removes session
- ✅ New session button creates fresh session

---

### Phase 2 Deliverable

**What Works After Phase 2**:
- ✅ Sidebar shows all past sessions
- ✅ Sessions grouped by date (Today/Yesterday/This Week/Older)
- ✅ Search and filter functionality
- ✅ Resume any past session
- ✅ Delete unwanted sessions
- ✅ Create new session anytime

**Demo Script**:
1. Open browser → sidebar shows past sessions
2. Search for "pdf" → filters to matching sessions
3. Click "Yesterday" session → loads that session
4. Files and messages restored
5. Click "New Session" → starts fresh chat
6. Delete old session → removed from list

---

## Phase 3: Session Naming & Resume (Days 7-9)

**Goal**: LLM-generated names and full session resumption

### Backend Work (Day 7-8)

#### 3.1: LLM Name Generation
**File**: `bassi/core_v3/session_naming.py` (new)

**Implementation**:
```python
class SessionNamingService:
    """
    Generates human-readable session names using LLM.
    """

    def __init__(self, anthropic_client):
        self.client = anthropic_client

    async def generate_name(self,
                           first_user_msg: str,
                           first_assistant_msg: str) -> str:
        """
        Generate session name from first exchange.

        Returns kebab-case name (e.g., "analyze-pdf-documents")
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

        return name[:50]  # Max 50 chars
```

**Tests**: `bassi/core_v3/tests/test_session_naming.py`
- Test name generation with various inputs
- Test name cleaning/validation
- Test fallback for errors
- Mock LLM responses

**Acceptance Criteria**:
- ✅ Generates valid kebab-case names
- ✅ Names are descriptive and relevant
- ✅ Names are max 50 characters
- ✅ Falls back to default on error

---

#### 3.2: Session State Machine
**File**: `bassi/core_v3/session_workspace.py` (extend)

**Add State Management**:
```python
class SessionState(Enum):
    CREATED = "created"           # Just created
    AUTO_NAMED = "auto_named"     # LLM generated name
    FINALIZED = "finalized"       # User explicitly ended
    ARCHIVED = "archived"         # Auto-archived after 24h

class SessionWorkspace:
    @property
    def state(self) -> SessionState:
        return SessionState(self.metadata.get("state", "created"))

    def transition_to_auto_named(self, generated_name: str):
        """Transition from CREATED → AUTO_NAMED"""
        if self.state != SessionState.CREATED:
            raise ValueError(f"Cannot auto-name from state {self.state}")

        self.update_display_name(generated_name)
        self.metadata["state"] = SessionState.AUTO_NAMED.value
        self.metadata["auto_named_at"] = datetime.now().isoformat()
        self._save_metadata()

    def finalize(self, final_name: Optional[str] = None):
        """Transition to FINALIZED (explicit end)"""
        if self.state == SessionState.FINALIZED:
            return  # Already finalized

        if final_name:
            self.update_display_name(final_name)

        self.metadata["state"] = SessionState.FINALIZED.value
        self.metadata["finalized_at"] = datetime.now().isoformat()
        self._save_metadata()

    def archive(self):
        """Transition to ARCHIVED (auto-cleanup)"""
        self.metadata["state"] = SessionState.ARCHIVED.value
        self.metadata["archived_at"] = datetime.now().isoformat()
        self._save_metadata()
```

**Tests**: `bassi/core_v3/tests/test_session_workspace.py` (extend)
- Test state transitions
- Test invalid transitions raise errors
- Test metadata updates

---

#### 3.3: Auto-Naming Integration
**File**: `bassi/core_v3/web_server_v3.py` (extend)

**Add Auto-Naming Logic**:
```python
class BassiWebServerV3:
    def __init__(self):
        self.naming_service = SessionNamingService(anthropic_client)

    async def _handle_first_response(self,
                                     session_id: str,
                                     user_msg: str,
                                     assistant_msg: str):
        """Auto-generate name after first exchange"""
        workspace = self.workspaces.get(session_id)

        # Only name if still in CREATED state
        if workspace.state != SessionState.CREATED:
            return

        try:
            # Generate name asynchronously
            name = await self.naming_service.generate_name(user_msg, assistant_msg)
            workspace.transition_to_auto_named(name)
            self.session_index.add_session(workspace)

            # Notify client
            await self._send_event(session_id, {
                "type": "session_named",
                "name": name
            })
        except Exception as e:
            logger.error(f"Failed to auto-name session: {e}")
            # Non-critical, continue without name
```

**New Endpoint**:
```python
@app.post("/api/sessions/{session_id}/finalize")
async def finalize_session(session_id: str, body: dict = None):
    """Explicitly end and finalize session"""
    workspace = server.workspaces.get(session_id)
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

**Acceptance Criteria**:
- ✅ Session auto-names after first response
- ✅ Name appears in sidebar immediately
- ✅ Finalize endpoint transitions state
- ✅ Naming errors don't break session

---

#### 3.4: Session Resume
**File**: `bassi/core_v3/web_server_v3.py` (extend)

**Add Resume Endpoint**:
```python
@app.post("/api/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume session with full context restoration"""
    workspace = SessionWorkspace(session_id)

    # Load conversation history
    history = workspace.load_history()

    # Load SDK context if available
    sdk_context = None
    context_path = workspace.physical_path / "context.json"
    if context_path.exists():
        with open(context_path) as f:
            sdk_context = json.load(f)

    return {
        "id": session_id,
        "display_name": workspace.display_name,
        "history": history,
        "context": sdk_context,
        "files": [f.to_dict() for f in workspace.list_files()]
    }
```

**Frontend Integration**: `bassi/static/app.js` (extend)
```javascript
async resumeSession(sessionId) {
    // Get session details
    const response = await fetch(`/api/sessions/${sessionId}/resume`, {
        method: 'POST'
    })
    const session = await response.json()

    // Switch session
    this.sessionId = sessionId
    this.saveSession(sessionId)

    // Restore UI
    this.sessionFiles = session.files
    this.renderMessages(session.history)
    this.renderFileList()

    // Reconnect WebSocket with new session
    await this.reconnectWebSocket()
}
```

**Acceptance Criteria**:
- ✅ Resume loads conversation history
- ✅ Resume restores file list
- ✅ Resume preserves SDK context
- ✅ UI updates correctly on resume

---

### Phase 3 Deliverable

**What Works After Phase 3**:
- ✅ Sessions auto-name after first response
- ✅ Names are descriptive and human-readable
- ✅ Sessions can be explicitly finalized
- ✅ Resume restores full conversation context
- ✅ Resume reloads all files
- ✅ Session state machine prevents invalid transitions

**Demo Script**:
1. Start new chat → session named "untitled"
2. Send first message → wait for response
3. Session auto-renames to "analyze-sales-data"
4. Continue conversation → name stays
5. Click "End Session" → state → FINALIZED
6. Start new chat → switch away
7. Resume first session → conversation restored
8. All files still there

---

## Phase 4: Agent Awareness (Days 10-12)

**Goal**: Agent understands and uses workspace structure

### Backend Work (Day 10-11)

#### 4.1: Enhanced System Prompt
**File**: `bassi/core_v3/agent_session.py` (modify)

**Add Workspace Context**:
```python
class AgentSession:
    def _build_system_prompt(self, workspace: SessionWorkspace) -> str:
        """Build system prompt with workspace awareness"""

        base_prompt = """You are Claude, an AI assistant with access to a session workspace.

## Your Current Workspace

**Path**: {workspace_path}
**Session**: {session_name}
**Files Available**: {file_count}

## Workspace Structure

Your session has an organized directory structure:

1. **DATA_FROM_USER/**: Files uploaded by the user
   - Current files: {user_files}
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

**Current working directory**: {cwd}
"""

        user_files = [f.name for f in workspace.list_files()]

        return base_prompt.format(
            workspace_path=workspace.physical_path,
            session_name=workspace.display_name,
            file_count=len(user_files),
            user_files=", ".join(user_files) if user_files else "none",
            cwd=workspace.physical_path / "DATA_FROM_USER"
        )
```

**Acceptance Criteria**:
- ✅ Agent receives workspace context
- ✅ Agent knows available files
- ✅ Agent understands folder purposes
- ✅ Agent uses correct folders for outputs

---

#### 4.2: Tool Output Routing
**File**: `bassi/core_v3/agent_session.py` (extend)

**Add Output Classification**:
```python
class AgentSession:
    async def _route_output(self,
                           content: str,
                           filename: str,
                           workspace: SessionWorkspace) -> Path:
        """Route agent output to appropriate folder"""

        ext = Path(filename).suffix.lower()

        # Python scripts
        if ext == '.py':
            return workspace.physical_path / "SCRIPTS_FROM_AGENT" / filename

        # Final outputs (markdown, reports, cleaned data)
        if ext in ['.md', '.pdf', '.docx', '.xlsx']:
            return workspace.physical_path / "RESULTS_FROM_AGENT" / filename

        # Intermediate data (JSON, HTML, temp CSV)
        if ext in ['.json', '.html', '.xml']:
            return workspace.physical_path / "DATA_FROM_AGENT" / filename

        # Default to results
        return workspace.physical_path / "RESULTS_FROM_AGENT" / filename
```

**Acceptance Criteria**:
- ✅ Python scripts go to SCRIPTS_FROM_AGENT/
- ✅ Final reports go to RESULTS_FROM_AGENT/
- ✅ Intermediate data goes to DATA_FROM_AGENT/
- ✅ Classification is automatic

---

#### 4.3: Workspace Search
**File**: `bassi/core_v3/session_workspace.py` (extend)

**Add Search Functionality**:
```python
class SessionWorkspace:
    def search_files(self, query: str) -> list[SearchResult]:
        """Search across all workspace files"""
        results = []

        # Search all folders
        for folder in ["DATA_FROM_USER", "RESULTS_FROM_AGENT",
                       "SCRIPTS_FROM_AGENT", "DATA_FROM_AGENT"]:
            folder_path = self.physical_path / folder

            if not folder_path.exists():
                continue

            for file_path in folder_path.rglob("*"):
                if not file_path.is_file():
                    continue

                # Search filename
                if query.lower() in file_path.name.lower():
                    results.append(SearchResult(
                        path=file_path,
                        folder=folder,
                        match_type="filename"
                    ))
                    continue

                # Search content (text files only)
                if file_path.suffix in ['.txt', '.md', '.py', '.json', '.csv']:
                    try:
                        content = file_path.read_text()
                        if query.lower() in content.lower():
                            results.append(SearchResult(
                                path=file_path,
                                folder=folder,
                                match_type="content",
                                snippet=self._extract_snippet(content, query)
                            ))
                    except:
                        pass  # Binary or unreadable file

        return results
```

**New Endpoint**:
```python
@app.get("/api/sessions/{session_id}/search")
async def search_workspace(session_id: str, q: str):
    """Search all files in session workspace"""
    workspace = SessionWorkspace(session_id)
    results = workspace.search_files(q)

    return {
        "query": q,
        "results": [r.to_dict() for r in results]
    }
```

**Acceptance Criteria**:
- ✅ Search finds files by name
- ✅ Search finds content in text files
- ✅ Search returns snippets with matches
- ✅ Search covers all workspace folders

---

### Frontend Work (Day 12)

#### 4.4: Workspace Browser UI
**File**: `bassi/static/components/workspace-browser.js` (new)

**Implementation**:
```javascript
class WorkspaceBrowser {
    constructor(container, client) {
        this.container = container
        this.client = client
    }

    async render() {
        const response = await fetch(`/api/sessions/${this.client.sessionId}`)
        const session = await response.json()

        const folderStructure = {
            'DATA_FROM_USER': session.files.filter(f => f.folder === 'DATA_FROM_USER'),
            'RESULTS_FROM_AGENT': session.files.filter(f => f.folder === 'RESULTS_FROM_AGENT'),
            'SCRIPTS_FROM_AGENT': session.files.filter(f => f.folder === 'SCRIPTS_FROM_AGENT'),
            'DATA_FROM_AGENT': session.files.filter(f => f.folder === 'DATA_FROM_AGENT')
        }

        this.container.innerHTML = `
            <div class="workspace-browser">
                <div class="browser-header">
                    <h3>📁 Workspace Files</h3>
                    <input type="text"
                           placeholder="Search..."
                           oninput="workspaceBrowser.handleSearch(event)">
                </div>

                ${Object.entries(folderStructure).map(([folder, files]) => `
                    <div class="folder-section">
                        <div class="folder-header" onclick="workspaceBrowser.toggleFolder('${folder}')">
                            <span class="folder-icon">📂</span>
                            <span class="folder-name">${folder}</span>
                            <span class="file-count">(${files.length})</span>
                        </div>
                        <div class="folder-contents" data-folder="${folder}">
                            ${files.map(file => this.renderFile(file)).join('')}
                        </div>
                    </div>
                `).join('')}
            </div>
        `
    }

    renderFile(file) {
        return `
            <div class="file-item" onclick="workspaceBrowser.openFile('${file.path}')">
                <span class="file-icon">${this.getFileIcon(file)}</span>
                <span class="file-name">${file.name}</span>
                <span class="file-size">${this.formatSize(file.size)}</span>
            </div>
        `
    }
}
```

**Acceptance Criteria**:
- ✅ Shows all workspace folders
- ✅ Groups files by folder
- ✅ Folders can be expanded/collapsed
- ✅ Files can be opened/downloaded
- ✅ Search filters across all folders

---

### Phase 4 Deliverable

**What Works After Phase 4**:
- ✅ Agent knows workspace structure
- ✅ Agent saves outputs to correct folders
- ✅ Scripts go to SCRIPTS_FROM_AGENT/
- ✅ Reports go to RESULTS_FROM_AGENT/
- ✅ Temp data goes to DATA_FROM_AGENT/
- ✅ Workspace browser shows all files
- ✅ Search finds files across workspace

**Demo Script**:
1. Drop PDF → saved to DATA_FROM_USER/
2. Ask agent to analyze → creates analysis_report.md
3. Check workspace browser → report in RESULTS_FROM_AGENT/
4. Ask agent to write script → creates processor.py
5. Check workspace browser → script in SCRIPTS_FROM_AGENT/
6. Search for "analysis" → finds report and mentions in chat
7. All outputs organized automatically

---

## Testing Strategy

### Unit Tests
- **Core Components**: 50+ tests across all modules
  - `test_session_workspace.py`: 15 tests
  - `test_session_index.py`: 10 tests
  - `test_session_naming.py`: 8 tests
  - `test_message_converter.py`: 12 tests (existing)
  - `test_tools.py`: 10 tests (existing)

### Integration Tests
- **API Endpoints**: Test all REST endpoints
- **WebSocket Flow**: Test full message lifecycle with workspaces
- **File Operations**: Test upload, list, search, delete
- **Session Lifecycle**: Test create, auto-name, resume, finalize

### E2E Tests
- **Manual Testing**: Browser testing with real files
- **Automated**: Playwright tests for critical flows

### Performance Tests
- **Session Listing**: Benchmark with 1000 sessions (target: <100ms)
- **File Upload**: Test 100MB file streaming
- **Search**: Benchmark search across 100 files (target: <500ms)

---

## Deployment Checklist

### Pre-Deployment
- [ ] All unit tests passing (50+)
- [ ] All integration tests passing
- [ ] Manual testing complete
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Migration script tested

### Deployment Steps
1. [ ] Backup existing `_DATA_FROM_USER/` directory
2. [ ] Deploy backend changes
3. [ ] Deploy frontend changes
4. [ ] Run migration script for existing files
5. [ ] Verify hot reload still works
6. [ ] Test with real user session

### Post-Deployment
- [ ] Monitor server logs for errors
- [ ] Check session creation works
- [ ] Verify file uploads work
- [ ] Test session resume
- [ ] Validate auto-naming
- [ ] Confirm search works

---

## Rollback Plan

If critical issues arise:

1. **Feature Flag**: Set `USE_SESSION_WORKSPACES=false` in env
2. **Revert**: Git revert to previous commit
3. **Restore Data**: Restore `_DATA_FROM_USER/` from backup
4. **Restart Server**: Old behavior restored

---

## Success Metrics

### Phase 1 (Days 1-3)
- [ ] Files persist after browser refresh
- [ ] File area shows all session files
- [ ] No files "disappear" after sending

### Phase 2 (Days 4-6)
- [ ] Can browse past 10+ sessions
- [ ] Search finds sessions by name
- [ ] Resume switches to old session

### Phase 3 (Days 7-9)
- [ ] 90%+ of sessions get meaningful auto-names
- [ ] Resume restores conversation correctly
- [ ] Session state transitions work

### Phase 4 (Days 10-12)
- [ ] Agent saves outputs to correct folders
- [ ] Workspace search finds files
- [ ] All folders visible in UI

---

## Timeline Summary

| Phase | Days | Deliverable |
|-------|------|-------------|
| **Phase 1** | 1-3 | Session-specific file storage |
| **Phase 2** | 4-6 | Session history sidebar |
| **Phase 3** | 7-9 | Auto-naming and resume |
| **Phase 4** | 10-12 | Agent workspace awareness |
| **Total** | **12 days** | **Full implementation** |

---

## Next Steps

**Ready to start?**

I'll now create the detailed task breakdown, then ask for your approval to begin Phase 1 implementation.
