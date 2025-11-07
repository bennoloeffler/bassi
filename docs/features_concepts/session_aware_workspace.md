# Session-Aware Workspace Management

**Status**: Draft Concept
**Version**: 1.0
**Date**: 2025-11-07

## Problem Statement

Current implementation has several limitations:
1. ❌ Uploaded files are global, not session-specific
2. ❌ Files "disappear" when sent (actually merged into message)
3. ❌ No visibility into past sessions
4. ❌ No way to resume previous work context
5. ❌ Agent cannot search across session artifacts
6. ❌ Session naming is UUID-based (not user-friendly)

## Vision

Each chat session should be a **self-contained workspace** with:
- ✅ Persistent file storage
- ✅ Complete conversation history
- ✅ Agent-generated outputs organized by type
- ✅ Searchable and resumable
- ✅ Human-readable naming
- ✅ UI for browsing past sessions

## Proposed Directory Structure

```
chats/
  2025-11-07T00-30-15--analyze-pdf-documents--e4b2c8/
    session.json              # Session metadata
    history.md                # Human-readable conversation log
    context.json              # Agent SDK context (for resume)

    DATA_FROM_USER/           # All user uploads
      screenshot_001.png
      report.pdf
      data.csv

    RESULTS_FROM_AGENT/       # Final outputs
      analysis_report.md
      cleaned_data.csv
      visualization.png

    SCRIPTS_FROM_AGENT/       # Executable scripts
      data_processor.py
      web_scraper.py

    DATA_FROM_AGENT/          # Intermediate/working data
      web_fetch_response.html
      mcp_query_results.json
      temp_calculations.json

  2025-11-06T15-22-08--create-presentation--a7f3d1/
    ... (same structure)
```

## Architecture Options

### Option A: Agent SDK Session ID as Primary Key

**Approach**: Use SDK's session management, enhance with workspace folders

**Pros**:
- ✅ Leverages existing SDK session infrastructure
- ✅ SDK handles context continuity automatically
- ✅ Minimal changes to agent_session.py
- ✅ Resume works out of the box

**Cons**:
- ⚠️ Session ID is SDK-controlled (UUIDs)
- ⚠️ Need to map SDK session_id → workspace folder
- ⚠️ SDK context storage separate from workspace

**Implementation**:
```python
session_id = "abc123-sdk-id"
workspace = f"chats/{timestamp}--{name}--{session_id[:6]}"
```

### Option B: Workspace-First Approach

**Approach**: Create workspace first, then pass as context to SDK

**Pros**:
- ✅ Workspace is primary organizational unit
- ✅ Folder name is human-readable
- ✅ All data naturally grouped
- ✅ Easy to backup/archive/share sessions

**Cons**:
- ⚠️ Need to sync workspace state with SDK
- ⚠️ More complex mapping logic
- ⚠️ Resume requires workspace → SDK session mapping

**Implementation**:
```python
workspace = f"chats/{timestamp}--{name}"
session_id = workspace_to_session_id(workspace)
sdk.query(prompt, session_id=session_id, cwd=workspace)
```

### Option C: Hybrid - SDK Session + Workspace Metadata

**Approach**: SDK owns session, workspace stores artifacts + metadata

**Pros**:
- ✅ Best of both worlds
- ✅ SDK handles continuity, workspace handles organization
- ✅ Workspace can be rebuilt from SDK if needed
- ✅ Flexible - can switch storage strategies

**Cons**:
- ⚠️ Two sources of truth (SDK context + workspace)
- ⚠️ Need sync mechanism
- ⚠️ Slightly more complex

**Implementation**:
```python
# SDK session is primary
session_id = sdk.create_session()

# Workspace is secondary (for organization)
workspace = SessionWorkspace(
    session_id=session_id,
    name=llm_generated_name,
    base_path=Path("chats")
)
```

## Recommended: Option C (Hybrid)

**Rationale**:
- SDK is authoritative for conversation state
- Workspace is authoritative for file organization
- Clean separation of concerns
- Future-proof (can change storage backend)

---

## Session Naming Strategy

### Phase 1: Timestamp + UUID (Immediate)
```
2025-11-07T00-30-15--e4b2c8/
```
- Simple, deterministic
- No LLM call needed
- Always works

### Phase 2: LLM-Generated Names (Enhanced)
```
2025-11-07T00-30-15--analyze-pdf-documents--e4b2c8/
```

**Approach**:
1. User starts chat
2. After first assistant response, analyze conversation
3. Generate short name (3-5 words, kebab-case)
4. Rename folder: `{timestamp}--{name}--{session_id}`

**LLM Prompt for Naming**:
```
Given this conversation, generate a short descriptive name (3-5 words, lowercase-with-hyphens):

User: [first message]
Assistant: [first response]

Requirements:
- 3-5 words maximum
- Lowercase with hyphens (kebab-case)
- Descriptive of the task/topic
- No special characters except hyphens

Examples:
- "analyze-pdf-documents"
- "create-sales-presentation"
- "debug-python-script"
- "research-competitors"

Name:
```

### Phase 3: User-Editable Names (Future)
- Allow user to rename sessions in UI
- Update folder name atomically
- Maintain session_id consistency

---

## UI Design

### Session Browser Sidebar

```
┌─────────────────────────────────────────────┐
│ BASSI                          [≡] [+]      │
├─────────────────────────────────────────────┤
│                                             │
│ 🔍 Search sessions...                       │
│                                             │
│ Today                                       │
│ ● Analyze PDF Documents        [00:30]     │
│   2 files · 5 messages                     │
│                                             │
│ Yesterday                                   │
│   Create Sales Presentation    [15:22]     │
│   3 files · 12 messages                    │
│                                             │
│   Debug Python Script          [09:15]     │
│   1 file · 8 messages                      │
│                                             │
│ This Week                                   │
│   Research Competitors         [Mon 14:30] │
│   ...                                       │
│                                             │
└─────────────────────────────────────────────┘
```

### File Upload Area (Expandable)

**Collapsed State** (default):
```
┌─────────────────────────────────────────────┐
│ 📎 2 files attached                    [▼]  │
└─────────────────────────────────────────────┘
```

**Expanded State**:
```
┌─────────────────────────────────────────────┐
│ 📎 Files in this session              [▲]  │
├─────────────────────────────────────────────┤
│ 📄 report.pdf                  [×]          │
│    543 KB · Uploaded 5 min ago             │
│                                             │
│ 🖼️ screenshot_001.png          [×]          │
│    321 KB · Uploaded 2 min ago             │
│                                             │
│ [Drop files here or click to upload]       │
└─────────────────────────────────────────────┘
```

### Session Detail View

When clicking a session:
```
┌─────────────────────────────────────────────┐
│ ◀ Back to Sessions                          │
│                                             │
│ Analyze PDF Documents                       │
│ Started: Nov 7, 2025 at 00:30             │
│ Session ID: e4b2c8                         │
│                                             │
│ [Resume Session] [Export] [Delete]         │
│                                             │
│ Files (2)                                   │
│ • report.pdf (543 KB)                      │
│ • data.csv (61 KB)                         │
│                                             │
│ Conversation (5 messages)                   │
│ User: Please analyze this PDF...           │
│ Assistant: I'll analyze the document...    │
│ ...                                         │
│                                             │
│ Generated Content (3 items)                 │
│ • analysis_report.md                       │
│ • data_processor.py                        │
│ • cleaned_data.csv                         │
└─────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)

**Backend Changes**:

1. **Create SessionWorkspace class** (`bassi/core_v3/session_workspace.py`):
```python
class SessionWorkspace:
    """
    Manages session-specific file storage and organization.

    Features:
    - Creates/manages workspace directory structure
    - Tracks uploaded files
    - Stores conversation history
    - Organizes agent outputs
    """

    def __init__(self, session_id: str, base_path: Path = Path("chats")):
        self.session_id = session_id
        self.timestamp = datetime.now().isoformat()
        self.name = self._generate_initial_name()
        self.path = self._create_workspace()

    def upload_file(self, file: UploadFile) -> Path:
        """Upload file to DATA_FROM_USER/"""

    def save_script(self, script: str, name: str) -> Path:
        """Save agent script to SCRIPTS_FROM_AGENT/"""

    def save_result(self, content: bytes, name: str) -> Path:
        """Save agent result to RESULTS_FROM_AGENT/"""

    def list_files(self) -> list[FileInfo]:
        """List all files in DATA_FROM_USER/"""

    def save_message(self, message: Message):
        """Append message to history.md"""
```

2. **Integrate with web_server_v3.py**:
```python
class BassiWebServerV3:
    def __init__(self):
        self.workspaces: dict[str, SessionWorkspace] = {}

    async def handle_websocket(self, websocket: WebSocket):
        session_id = self._get_or_create_session_id(websocket)
        workspace = SessionWorkspace(session_id)
        self.workspaces[session_id] = workspace

        # Pass workspace to agent
        config = SessionConfig(cwd=workspace.path / "DATA_FROM_USER")
```

3. **Update upload endpoint**:
```python
@app.post("/api/upload")
async def upload_file(
    file: UploadFile,
    session_id: str = Form(...)
):
    workspace = get_workspace(session_id)
    path = workspace.upload_file(file)
    return {"path": str(path), "workspace": str(workspace.path)}
```

**Frontend Changes**:

1. **Track session ID in app.js**:
```javascript
class BassiClient {
    constructor() {
        this.sessionId = this.loadOrCreateSessionId()
        this.workspace = null
    }

    loadOrCreateSessionId() {
        return localStorage.getItem('currentSessionId') || uuidv4()
    }
}
```

2. **Update file upload**:
```javascript
async uploadFile(file) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('session_id', this.sessionId)

    const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData
    })
}
```

### Phase 2: Session Management UI (Week 2)

1. **Session list API**:
```python
@app.get("/api/sessions")
async def list_sessions():
    sessions = SessionWorkspace.list_all()
    return [s.to_dict() for s in sessions]
```

2. **Session sidebar component** (`bassi/static/components/session-list.js`)

3. **File list component** (expandable/collapsible)

### Phase 3: Session Resume & Naming (Week 3)

1. **Resume session**:
```python
@app.post("/api/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    workspace = SessionWorkspace.load(session_id)
    # Load SDK context from workspace.context.json
    # Restore conversation history
```

2. **Auto-generate session names**:
```python
async def generate_session_name(workspace: SessionWorkspace):
    # After first exchange, analyze and generate name
    first_user_msg = workspace.get_first_user_message()
    first_assistant_msg = workspace.get_first_assistant_message()

    name = await llm_generate_name(first_user_msg, first_assistant_msg)
    workspace.rename(name)
```

### Phase 4: Agent Awareness (Week 4)

1. **System prompt enhancement**:
```python
system_prompt = f"""
You are Claude, working in a session workspace.

Current workspace: {workspace.path}

Available directories:
- DATA_FROM_USER/: Files uploaded by user
- RESULTS_FROM_AGENT/: Your final outputs (save here)
- SCRIPTS_FROM_AGENT/: Python scripts you create
- DATA_FROM_AGENT/: Intermediate data/downloads

When you create files, use the appropriate directory.
You can search across all workspace files.
"""
```

2. **Tool enhancements**:
   - Read tool: Search DATA_FROM_USER first
   - Write tool: Save to RESULTS_FROM_AGENT by default
   - Bash tool: Scripts saved to SCRIPTS_FROM_AGENT

---

## Migration Strategy

### For Existing Files

```python
def migrate_existing_files():
    """Migrate files from global _DATA_FROM_USER to session workspaces"""

    # Option 1: Create "legacy" session
    legacy_workspace = SessionWorkspace("legacy-imports")
    for file in Path("_DATA_FROM_USER").glob("*"):
        shutil.move(file, legacy_workspace.path / "DATA_FROM_USER" / file.name)

    # Option 2: Let user assign files to sessions via UI
    # Show "unassigned files" and let user move to sessions
```

---

## Open Questions

### 1. Session Lifecycle
**Q**: When should a session be considered "ended"?

**Options**:
- A) After 24 hours of inactivity (auto-archive)
- B) Explicit "End Session" button
- C) Never (always resumable)

**Recommendation**: C - Always resumable, with UI filters (Active/Archived)

### 2. Session Resume Behavior
**Q**: When resuming, should files be "re-sent" to Claude?

**Options**:
- A) Yes - reconstruct full multimodal context
- B) No - just restore conversation history
- C) Ask user

**Recommendation**: B initially, with option to "re-attach files"

### 3. Storage Location
**Q**: Where should `chats/` directory live?

**Options**:
- A) Project root (alongside `_DATA_FROM_USER`)
- B) User home directory (`~/.bassi/chats/`)
- C) Configurable in settings

**Recommendation**: C (default to project root, allow config)

### 4. SDK Context Storage
**Q**: How to handle Agent SDK's internal session state?

**Options**:
- A) Let SDK manage, just track session_id
- B) Export SDK context to `workspace/context.json`
- C) Don't persist - rely on message history

**Recommendation**: B - Export after each message for full resume capability

### 5. Large File Handling
**Q**: What if DATA_FROM_AGENT grows huge (100MB+ downloads)?

**Options**:
- A) Set workspace size limits
- B) Auto-clean old DATA_FROM_AGENT on resume
- C) Let it grow (disk is cheap)

**Recommendation**: A + B - 1GB soft limit, auto-clean on resume

### 6. Session Search
**Q**: How to make sessions searchable?

**Options**:
- A) Full-text search in history.md (simple grep)
- B) SQLite index (file metadata + message snippets)
- C) LLM semantic search

**Recommendation**: A → B progression

---

## Success Metrics

- ✅ User can see all past sessions in sidebar
- ✅ User can resume any session with full context
- ✅ Files persist across page refreshes
- ✅ Agent can find and reference uploaded files
- ✅ Session names are human-readable
- ✅ Old sessions can be exported/archived
- ✅ Zero data loss on browser crash

---

## Technical Considerations

### Performance
- Session list API: < 100ms for 100 sessions
- File listing: < 50ms per session
- Resume: < 2s including context reconstruction

### Storage
- Expect ~10MB per session (with files)
- 100 sessions = ~1GB disk space
- Suggest cleanup after 90 days of inactivity

### Security
- Session workspace paths must be validated (no path traversal)
- File uploads still size-limited
- Session IDs must be unguessable (UUIDs)

---

## Next Steps

1. ✅ Create this concept document
2. ⏳ Review with stakeholders
3. ⏳ Prototype SessionWorkspace class
4. ⏳ Add session list endpoint + UI
5. ⏳ Integrate with file upload flow
6. ⏳ Implement session naming
7. ⏳ Add resume functionality
8. ⏳ Enhance agent system prompt
9. ⏳ Add session export/archive
10. ⏳ Write comprehensive tests

---

## Appendix: Alternative Architectures

### Flat Structure (Rejected)
```
chats/
  sessions.json              # All metadata
  e4b2c8-file1.pdf          # Files prefixed with session ID
  e4b2c8-file2.csv
  a7f3d1-file1.txt
```
**Why rejected**: Hard to navigate, no clear boundaries

### Database-Backed (Future)
```python
# SQLite for metadata, filesystem for files
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    name TEXT,
    created_at DATETIME,
    workspace_path TEXT
);

CREATE TABLE files (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    path TEXT,
    size INTEGER,
    uploaded_at DATETIME
);
```
**Future consideration**: When sessions > 1000
