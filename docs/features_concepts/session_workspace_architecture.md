# Session Workspace Architecture - Visual Guide

## Current vs. Proposed Architecture

### CURRENT: Global File Storage ❌

```
bassi/
  _DATA_FROM_USER/          ← All files mixed together
    screenshot_001.png      ← From session A
    report.pdf              ← From session B
    data.csv                ← From session C
    (files "disappear" after sending)

  Agent SDK
    session-abc-123         ← Session A (no file link)
    session-def-456         ← Session B (no file link)
    session-ghi-789         ← Session C (no file link)
```

**Problems:**
- Can't tell which file belongs to which session
- Files "vanish" from UI after sending
- No way to browse past sessions
- Can't resume with file context

---

### PROPOSED: Session Workspaces ✅

```
bassi/
  chats/
    2025-11-07T00-30-15--analyze-reports--abc123/
      session.json                    ← Metadata
      history.md                      ← Conversation log
      context.json                    ← Agent SDK state

      DATA_FROM_USER/                 ← Input files
        report.pdf
        screenshot_001.png

      RESULTS_FROM_AGENT/             ← Final outputs
        analysis_report.md
        summary.txt

      SCRIPTS_FROM_AGENT/             ← Python scripts
        data_processor.py
        web_scraper.py

      DATA_FROM_AGENT/                ← Intermediate data
        web_fetch_result.html
        api_response.json

    2025-11-06T15-22-08--create-slides--def456/
      session.json
      history.md
      DATA_FROM_USER/
        logo.png
        data.csv
      RESULTS_FROM_AGENT/
        presentation.md
      ...

  Agent SDK
    ↕ (synced with workspaces)
    session abc123 ←→ chats/2025-11-07T00-30-15--analyze-reports--abc123/
    session def456 ←→ chats/2025-11-06T15-22-08--create-slides--def456/
```

**Benefits:**
- ✅ Clear session boundaries
- ✅ Files persist forever
- ✅ Browse past work
- ✅ Resume with full context
- ✅ Agent knows structure

---

## Data Flow Diagrams

### Upload Flow (Current)

```
User drops file
  ↓
Upload to _DATA_FROM_USER/screenshot_X.png
  ↓
Show in preview
  ↓
User sends message
  ↓
File converted to base64 → sent to Claude
  ↓
Preview cleared ❌
  ↓
File still in _DATA_FROM_USER but "lost" from UI
```

### Upload Flow (Proposed)

```
User drops file
  ↓
Upload to chats/{session}/DATA_FROM_USER/screenshot.png
  ↓
Add to session file list (persistent)
  ↓
Show in expandable file area
  ↓
User sends message
  ↓
File converted to base64 → sent to Claude
  ↓
File STAYS in list ✅ (can re-send anytime)
  ↓
Logged in history.md as attachment
```

---

## Architecture Decision: Three Options

### Option A: SDK-First

```
┌─────────────────────────────────┐
│   Claude Agent SDK              │
│   (owns session state)          │
│                                 │
│   session_id: abc-123           │
│   messages: [...]               │
│   context: {...}                │
└────────────┬────────────────────┘
             │
             ↓ creates workspace
┌─────────────────────────────────┐
│   Workspace (secondary)         │
│                                 │
│   chats/abc-123/                │
│     DATA_FROM_USER/             │
│     RESULTS_FROM_AGENT/         │
└─────────────────────────────────┘
```

**When SDK creates session → create workspace**
**SDK session ID = workspace folder name**

---

### Option B: Workspace-First

```
┌─────────────────────────────────┐
│   Workspace (primary)           │
│                                 │
│   chats/analyze-reports-abc/    │
│     session.json                │
│     DATA_FROM_USER/             │
│     RESULTS_FROM_AGENT/         │
└────────────┬────────────────────┘
             │
             ↓ passed to SDK
┌─────────────────────────────────┐
│   Claude Agent SDK              │
│   (uses workspace session_id)   │
│                                 │
│   session_id: abc (from folder) │
│   cwd: chats/analyze-reports/   │
└─────────────────────────────────┘
```

**Create workspace → pass session_id to SDK**
**Workspace structure is authoritative**

---

### Option C: Hybrid (RECOMMENDED)

```
┌─────────────────────────────────┐
│   Claude Agent SDK              │
│   (authoritative for messages)  │
│                                 │
│   session_id: abc-123           │
│   messages: [...]               │
└────────────┬────────────────────┘
             │
             ↕ bidirectional sync
┌─────────────────────────────────┐
│   SessionWorkspace              │
│   (authoritative for files)     │
│                                 │
│   session_id: abc-123           │
│   path: chats/analyze-abc/      │
│   files: [...]                  │
└─────────────────────────────────┘
```

**SDK and Workspace are equal partners:**
- SDK: Conversation continuity & context
- Workspace: File organization & persistence
- Sync: After each message exchange

---

## Component Architecture

### New Components

```
bassi/core_v3/
  session_workspace.py        ← New: Workspace manager
  workspace_sync.py           ← New: SDK ↔ Workspace sync
  web_server_v3.py            ← Modified: Session-aware
  agent_session.py            ← Modified: Uses workspace

bassi/static/
  components/
    session-list.js           ← New: Sidebar UI
    file-area.js              ← New: File upload area
  app.js                      ← Modified: Session tracking
```

### SessionWorkspace Class

```python
class SessionWorkspace:
    """
    Manages a single session's workspace.

    Responsibilities:
    - Create directory structure
    - Store uploaded files
    - Track file metadata
    - Save conversation history
    - Export SDK context
    - Generate session name
    """

    def __init__(
        self,
        session_id: str,
        base_path: Path = Path("chats")
    ):
        self.session_id = session_id
        self.path = self._create_workspace()

    def upload_file(self, file: UploadFile) -> Path:
        """Save file to DATA_FROM_USER/"""

    def save_message(self, message: Message):
        """Append to history.md"""

    def list_files(self) -> list[FileInfo]:
        """Get all DATA_FROM_USER files"""

    def save_context(self, context: dict):
        """Export SDK context to context.json"""

    def load_context(self) -> dict:
        """Load SDK context for resume"""

    @classmethod
    def list_all(cls) -> list['SessionWorkspace']:
        """List all sessions"""

    def generate_name(self, llm_client) -> str:
        """Generate human-readable name"""
```

---

## UI Component Hierarchy

```
<BassiApp>
  │
  ├── <SessionSidebar>
  │     ├── <SessionList>
  │     │     ├── <SessionItem> (Today)
  │     │     ├── <SessionItem> (Yesterday)
  │     │     └── ...
  │     └── <NewSessionButton>
  │
  ├── <MainChat>
  │     ├── <FileUploadArea>    ← NEW: Expandable
  │     │     ├── <FilePreview> (report.pdf)
  │     │     ├── <FilePreview> (screenshot.png)
  │     │     └── <DropZone>
  │     │
  │     ├── <MessageList>
  │     │     ├── <UserMessage>
  │     │     ├── <AssistantMessage>
  │     │     └── ...
  │     │
  │     └── <InputArea>
  │
  └── <SessionDetailModal>    ← Opens on session click
        ├── <SessionInfo>
        ├── <FileList>
        ├── <MessageHistory>
        └── <Actions> (Resume, Export, Delete)
```

---

## API Endpoints (New/Modified)

### Session Management

```
GET  /api/sessions
     → List all sessions
     {
       "sessions": [
         {
           "id": "abc-123",
           "name": "analyze-reports",
           "created_at": "2025-11-07T00:30:15",
           "file_count": 2,
           "message_count": 5
         }
       ]
     }

GET  /api/sessions/{session_id}
     → Get session details

POST /api/sessions
     → Create new session
     { "name": "optional-name" }

POST /api/sessions/{session_id}/resume
     → Resume session (restore context)

DELETE /api/sessions/{session_id}
       → Delete session
```

### File Management

```
POST /api/sessions/{session_id}/files
     → Upload file to session
     Form data: file, session_id

GET  /api/sessions/{session_id}/files
     → List all files in session

DELETE /api/sessions/{session_id}/files/{filename}
       → Remove file from session
```

### Context Management

```
GET  /api/sessions/{session_id}/context
     → Get SDK context for resume

POST /api/sessions/{session_id}/context
     → Save SDK context
     { "context": {...} }
```

---

## State Management

### WebSocket Connection State

```javascript
class BassiClient {
    constructor() {
        // Session tracking
        this.sessionId = this.loadOrCreateSession()
        this.workspace = null

        // File state
        this.sessionFiles = []      // All files in workspace
        this.pendingFiles = []      // Files to send with next message

        // UI state
        this.fileAreaExpanded = false
        this.currentView = 'chat'   // 'chat' | 'sessions' | 'detail'
    }

    async loadOrCreateSession() {
        // Check localStorage for active session
        let sessionId = localStorage.getItem('activeSession')

        if (!sessionId) {
            // Create new session
            const response = await fetch('/api/sessions', {
                method: 'POST'
            })
            sessionId = (await response.json()).id
            localStorage.setItem('activeSession', sessionId)
        }

        // Load workspace metadata
        this.workspace = await this.fetchSessionInfo(sessionId)

        // Load all files in session
        this.sessionFiles = await this.fetchSessionFiles(sessionId)

        return sessionId
    }
}
```

---

## Migration Path

### Step 1: Parallel Operation (Week 1)
```
bassi/
  _DATA_FROM_USER/          ← OLD (still works)
  chats/                    ← NEW (for new sessions)
```
- New sessions use workspaces
- Old behavior still works
- Gradual transition

### Step 2: Migration Script (Week 2)
```python
def migrate_old_files():
    """Move files from global to session workspaces"""

    # Create "imported" session for orphaned files
    legacy = SessionWorkspace("imported-files")

    for file in Path("_DATA_FROM_USER").glob("*"):
        # Move to legacy session
        dest = legacy.path / "DATA_FROM_USER" / file.name
        shutil.move(file, dest)

        legacy.add_file_metadata({
            "name": file.name,
            "imported_from": str(file),
            "imported_at": datetime.now()
        })
```

### Step 3: Deprecation (Week 3+)
```python
# Show warning for old behavior
if using_global_data_dir():
    logger.warning(
        "Global _DATA_FROM_USER is deprecated. "
        "Please migrate to session workspaces."
    )
```

---

## Testing Strategy

### Unit Tests
```python
# test_session_workspace.py
def test_create_workspace():
    ws = SessionWorkspace("test-123")
    assert ws.path.exists()
    assert (ws.path / "DATA_FROM_USER").exists()

def test_upload_file():
    ws = SessionWorkspace("test-123")
    file = create_test_file()
    path = ws.upload_file(file)
    assert path.exists()
    assert path.parent.name == "DATA_FROM_USER"

def test_list_files():
    ws = SessionWorkspace("test-123")
    ws.upload_file(create_test_file("a.txt"))
    ws.upload_file(create_test_file("b.txt"))
    assert len(ws.list_files()) == 2
```

### Integration Tests
```python
# test_session_integration.py
async def test_session_lifecycle():
    # Create session
    session_id = await create_session()

    # Upload files
    await upload_file(session_id, "test.pdf")

    # Send message
    await send_message(session_id, "Analyze this")

    # Verify file persists
    files = await list_session_files(session_id)
    assert len(files) == 1

    # Resume session
    await resume_session(session_id)

    # Verify context restored
    assert session.message_count > 0
```

---

## Performance Considerations

### File System Operations
```
Operation                    Target    Typical
────────────────────────────────────────────────
Create workspace              < 10ms    5ms
Upload file (1MB)            < 100ms   50ms
List session files           < 50ms    20ms
List all sessions (100)      < 100ms   80ms
Load session context         < 50ms    30ms
Generate session name        < 2s      1s
```

### Storage Estimates
```
Component                    Size
────────────────────────────────────
session.json                 1-5 KB
history.md                   50-500 KB
context.json                 10-100 KB
Average file                 100 KB - 5 MB
────────────────────────────────────
Per session:                 1-50 MB
100 sessions:                100MB - 5GB
```

### Caching Strategy
```python
# Cache session metadata in memory
session_cache = {}

def get_session(session_id: str) -> SessionWorkspace:
    if session_id not in session_cache:
        session_cache[session_id] = SessionWorkspace.load(session_id)
    return session_cache[session_id]

# Invalidate on update
def update_session(session_id: str):
    if session_id in session_cache:
        del session_cache[session_id]
```

---

## Security Considerations

### Path Traversal Prevention
```python
def safe_path(session_id: str, filename: str) -> Path:
    """Ensure path stays within workspace"""

    # Validate session_id (UUID or safe string)
    if not re.match(r'^[a-zA-Z0-9-]+$', session_id):
        raise ValueError("Invalid session ID")

    # Validate filename (no path components)
    if '/' in filename or '\\' in filename:
        raise ValueError("Invalid filename")

    # Build path
    base = Path("chats") / session_id / "DATA_FROM_USER"
    full = (base / filename).resolve()

    # Verify still under base
    if not str(full).startswith(str(base.resolve())):
        raise ValueError("Path traversal attempt")

    return full
```

### File Size Limits
```python
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_SESSION_SIZE = 1024 * 1024 * 1024  # 1 GB

def check_session_quota(session_id: str):
    """Verify session hasn't exceeded quota"""
    ws = SessionWorkspace.load(session_id)
    total_size = sum(f.stat().st_size for f in ws.path.rglob("*"))

    if total_size > MAX_SESSION_SIZE:
        raise QuotaExceeded(f"Session size: {total_size / 1e9:.1f} GB")
```

---

## Monitoring & Observability

### Metrics to Track
```python
# Prometheus-style metrics

# Session lifecycle
sessions_created_total
sessions_resumed_total
sessions_deleted_total

# File operations
files_uploaded_total
files_uploaded_bytes_total
files_deleted_total

# Storage
workspace_size_bytes{session_id}
workspace_file_count{session_id}

# Performance
workspace_operation_duration_seconds{operation}
session_list_duration_seconds
```

### Logging
```python
logger.info(
    "Session created",
    extra={
        "session_id": session_id,
        "workspace_path": str(workspace.path),
        "initial_files": 0
    }
)

logger.info(
    "File uploaded",
    extra={
        "session_id": session_id,
        "filename": file.filename,
        "size_bytes": file.size,
        "mime_type": file.content_type
    }
)
```

---

## Rollback Plan

If session workspaces cause issues:

```python
# Feature flag
USE_SESSION_WORKSPACES = os.getenv("BASSI_USE_WORKSPACES", "true") == "true"

if USE_SESSION_WORKSPACES:
    workspace = SessionWorkspace(session_id)
    upload_path = workspace.upload_file(file)
else:
    # Old behavior
    upload_path = Path("_DATA_FROM_USER") / file.filename
    file.save(upload_path)
```

Quick disable:
```bash
export BASSI_USE_WORKSPACES=false
./run-agent-web.sh
```
