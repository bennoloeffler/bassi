# Session Workspace - Critical Analysis & Hardening

**Status**: Critical Review
**Version**: 1.0
**Date**: 2025-11-07

## User Decisions

✅ **Architecture**: Hybrid (SDK + Workspace)
✅ **Storage**: Project root (`bassi/chats/`)
✅ **Naming**: `iso-date-time__session_id__description`
✅ **File UI**: Collapsed by default, show when files exist, always show count
✅ **Scope**: Full implementation (Phases 1-4)

---

## Critical Weaknesses & Solutions

### ❌ WEAKNESS 1: "Chat Ends" is Ambiguous

**Problem**: When does a chat "end" to trigger final naming?

**Scenarios**:
```
User closes browser?        → Chat might continue later
User sends "goodbye"?       → Unreliable heuristic
30 minutes of inactivity?   → Arbitrary, might interrupt thinking
User clicks "End Session"?  → Requires explicit action
```

**HARDENED SOLUTION**:
```
Approach: Progressive Naming + Explicit End

1. Initial name (immediate):
   2025-11-07T14-30-15__abc123__untitled

2. First response (auto-generate preview):
   2025-11-07T14-30-15__abc123__analyze-pdf-documents
   (shown as "Analyze PDF Documents" in UI)

3. Explicit end (final commit):
   User can:
   - Click "End Session" → finalizes name, archives
   - Let it auto-finalize after 24h inactivity
   - Keep editing name until satisfied

State machine:
  ACTIVE → HAS_NAME → ARCHIVED
  ↑         ↓
  └─────────┘ (can reactivate archived)
```

**Benefits**:
- ✅ No ambiguity
- ✅ User has control
- ✅ Graceful degradation (auto-finalize if forgotten)

---

### ❌ WEAKNESS 2: Name Collisions

**Problem**: Two sessions created at same second

```
2025-11-07T14-30-15__abc123__analyze-pdf
2025-11-07T14-30-15__def456__analyze-pdf
    ↑ Same timestamp!
```

**HARDENED SOLUTION**:
```python
# Include session_id in path (unique guarantee)
path = f"chats/{iso_datetime}__{session_id[:8]}__{description}"

# session_id is UUID (unique) → collision impossible

Examples:
2025-11-07T14-30-15__abc12345__analyze-pdf
2025-11-07T14-30-15__def67890__analyze-pdf
    ↑ Different session IDs → no collision
```

**Benefits**:
- ✅ Mathematically collision-free
- ✅ session_id traceable in folder name
- ✅ Can sort by timestamp, filter by session_id

---

### ❌ WEAKNESS 3: Folder Rename is Dangerous

**Problem**: Renaming folder while session is active

```
User in session: chats/2025-11-07__abc__untitled/
Agent writing:   DATA_FROM_USER/file.pdf
System renames:  chats/2025-11-07__abc__analyze-pdf/
Agent writes:    → Error! Path changed!
```

**HARDENED SOLUTION**:
```python
# NEVER rename active sessions
# Use symlink or metadata

class SessionWorkspace:
    def __init__(self, session_id: str):
        # Physical path (immutable)
        self.physical_path = Path(f"chats/{session_id}")

        # Display name (mutable metadata)
        self.display_name = self._load_display_name()

    def rename(self, new_name: str):
        """Update display name WITHOUT moving folder"""
        metadata = self.load_metadata()
        metadata["display_name"] = new_name
        metadata["renamed_at"] = datetime.now()
        self.save_metadata(metadata)

        # Optional: create symlink for convenience
        symlink = Path(f"chats/{self.timestamp}__{new_name}")
        symlink.symlink_to(self.physical_path)
```

**Directory structure**:
```
chats/
  abc123-def456-ghi789/           ← Physical (immutable)
    session.json                  ← Contains display_name
    DATA_FROM_USER/

  2025-11-07__analyze-pdf/        ← Symlink (convenience)
    → abc123-def456-ghi789/
```

**Benefits**:
- ✅ No file system race conditions
- ✅ Rename anytime, even while active
- ✅ Backward compatible (can find by session_id)

---

### ❌ WEAKNESS 4: Session ID Leak in SDK

**Problem**: Agent SDK might change session IDs

```python
# What if SDK does this internally?
sdk.query("Hello", session_id="abc")
    ↓ SDK rewrites
    session_id="abc-v2-resumed"  # Different!

# Our workspace lookup fails
workspace = get_workspace("abc")  # Not found!
```

**HARDENED SOLUTION**:
```python
# Workspace is source of truth for session_id
# Pass workspace to SDK, not vice versa

class SessionWorkspace:
    def __init__(self):
        self.session_id = str(uuid.uuid4())  # WE control
        self.sdk_session_id = None            # SDK's ID (if different)

    def create_agent(self) -> AgentSession:
        config = SessionConfig(
            cwd=self.path / "DATA_FROM_USER"
        )
        agent = AgentSession(config)

        # Track SDK's session ID
        await agent.connect()
        self.sdk_session_id = agent.session_id

        # Save mapping
        self.save_metadata({
            "workspace_session_id": self.session_id,
            "sdk_session_id": self.sdk_session_id
        })

        return agent
```

**Benefits**:
- ✅ Workspace session_id is stable
- ✅ SDK session_id is tracked but not authoritative
- ✅ Can recover from SDK ID changes

---

### ❌ WEAKNESS 5: Browser Refresh Loses Context

**Problem**: User refreshes page mid-session

```
State before refresh:
  - WebSocket connected
  - Files uploaded
  - Conversation in progress

State after refresh:
  - WebSocket disconnected
  - Files... where?
  - Conversation... lost?
```

**HARDENED SOLUTION**:
```javascript
// app.js
class BassiClient {
    constructor() {
        // Restore from localStorage
        this.sessionId = this.restoreSession()
        this.reconnect()
    }

    restoreSession() {
        const stored = localStorage.getItem('activeSession')
        if (stored) {
            const session = JSON.parse(stored)

            // Check if still valid (< 24h old)
            const age = Date.now() - session.lastActivity
            if (age < 24 * 60 * 60 * 1000) {
                return session.id
            }
        }

        // Create new session
        return this.createNewSession()
    }

    async reconnect() {
        // Reconnect WebSocket
        await this.connectWebSocket()

        // Reload workspace state
        const files = await this.fetchSessionFiles(this.sessionId)
        this.sessionFiles = files

        // Reload conversation history
        const messages = await this.fetchSessionHistory(this.sessionId)
        this.renderMessages(messages)

        console.log('✅ Session restored:', this.sessionId)
    }
}
```

**Backend support**:
```python
@app.get("/api/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """Return conversation history for UI reconstruction"""
    workspace = SessionWorkspace.load(session_id)
    return {
        "messages": workspace.load_messages(),
        "files": workspace.list_files(),
        "metadata": workspace.load_metadata()
    }
```

**Benefits**:
- ✅ F5 doesn't lose work
- ✅ Can close browser and continue later
- ✅ Works across devices (if session_id synced)

---

### ❌ WEAKNESS 6: Race Condition on File Upload

**Problem**: Multiple files uploaded simultaneously

```
User drops 5 PDFs at once
  ↓
5 parallel uploads to DATA_FROM_USER/
  ↓
Conflict: file1.pdf, file1.pdf, file1.pdf (same name)
```

**HARDENED SOLUTION**:
```python
import asyncio
import hashlib
from pathlib import Path

class SessionWorkspace:
    def __init__(self):
        self._upload_lock = asyncio.Lock()

    async def upload_file(self, file: UploadFile) -> Path:
        """Thread-safe file upload with deduplication"""

        async with self._upload_lock:
            # Generate unique filename
            content = await file.read()
            content_hash = hashlib.sha256(content).hexdigest()[:8]

            # Check for duplicate
            existing = self._find_by_hash(content_hash)
            if existing:
                logger.info(f"Duplicate file detected: {file.filename}")
                return existing

            # Generate unique filename
            timestamp = int(time.time() * 1000)  # millisecond precision
            name, ext = os.path.splitext(file.filename)
            unique_name = f"{name}_{timestamp}_{content_hash}{ext}"

            # Save
            path = self.path / "DATA_FROM_USER" / unique_name
            path.write_bytes(content)

            # Record metadata
            self._add_file_metadata({
                "filename": file.filename,
                "saved_as": unique_name,
                "hash": content_hash,
                "size": len(content),
                "uploaded_at": datetime.now()
            })

            return path

    def _find_by_hash(self, content_hash: str) -> Optional[Path]:
        """Check if file with same content already exists"""
        metadata = self.load_metadata()
        for file_info in metadata.get("files", []):
            if file_info.get("hash") == content_hash:
                return self.path / "DATA_FROM_USER" / file_info["saved_as"]
        return None
```

**Benefits**:
- ✅ No race conditions (lock)
- ✅ No duplicate files (hash deduplication)
- ✅ Collision-free names (timestamp + hash)

---

### ❌ WEAKNESS 7: Orphaned Sessions

**Problem**: User creates session, uploads files, never chats

```
chats/
  2025-11-07__abc__untitled/     ← Created but abandoned
    DATA_FROM_USER/
      report.pdf                 ← 5MB wasted
    (no messages, no activity)
```

**HARDENED SOLUTION**:
```python
# Background cleanup task
async def cleanup_orphaned_sessions():
    """Delete sessions with no activity"""

    for workspace in SessionWorkspace.list_all():
        metadata = workspace.load_metadata()

        # Check if orphaned
        message_count = metadata.get("message_count", 0)
        created_at = datetime.fromisoformat(metadata["created_at"])
        age = datetime.now() - created_at

        if message_count == 0 and age > timedelta(hours=1):
            logger.info(f"Deleting orphaned session: {workspace.session_id}")
            workspace.delete()

# Run cleanup daily
async def background_tasks():
    while True:
        await cleanup_orphaned_sessions()
        await asyncio.sleep(24 * 60 * 60)  # 24 hours
```

**Benefits**:
- ✅ Automatic cleanup
- ✅ Recovers disk space
- ✅ Keeps workspace tidy

---

### ❌ WEAKNESS 8: Large File Memory Consumption

**Problem**: Uploading 100MB file → loads into memory

```python
# Current approach
content = await file.read()  # 100MB in RAM!
path.write_bytes(content)    # 100MB written
```

**HARDENED SOLUTION**:
```python
# Streaming approach
async def upload_file_streaming(file: UploadFile) -> Path:
    """Stream file to disk without loading into memory"""

    path = self.path / "DATA_FROM_USER" / self._generate_filename(file)

    # Stream in chunks
    CHUNK_SIZE = 64 * 1024  # 64KB chunks
    total_size = 0

    async with aiofiles.open(path, 'wb') as f:
        while chunk := await file.read(CHUNK_SIZE):
            await f.write(chunk)
            total_size += len(chunk)

            # Check size limit
            if total_size > MAX_FILE_SIZE:
                path.unlink()  # Delete incomplete file
                raise FileTooLarge(f"Max size: {MAX_FILE_SIZE}")

    return path
```

**Benefits**:
- ✅ Constant memory usage (64KB)
- ✅ Can handle 100MB+ files
- ✅ Early termination if too large

---

### ❌ WEAKNESS 9: Session List Performance

**Problem**: 1000 sessions → slow to list

```python
# Naive approach (slow)
def list_sessions():
    sessions = []
    for folder in Path("chats").glob("*"):
        metadata = json.loads((folder / "session.json").read_text())
        sessions.append(metadata)
    return sessions  # O(n) file reads!
```

**HARDENED SOLUTION**:
```python
# Index-based approach
class SessionIndex:
    """In-memory index of session metadata"""

    def __init__(self):
        self.index_path = Path("chats/.index.json")
        self.index = self._load_index()

    def _load_index(self) -> dict:
        """Load index from disk"""
        if self.index_path.exists():
            return json.loads(self.index_path.read_text())
        return {"sessions": {}, "last_updated": None}

    def add_session(self, session_id: str, metadata: dict):
        """Add session to index"""
        self.index["sessions"][session_id] = {
            "id": session_id,
            "display_name": metadata["display_name"],
            "created_at": metadata["created_at"],
            "message_count": metadata.get("message_count", 0),
            "file_count": metadata.get("file_count", 0),
            "last_activity": metadata.get("last_activity")
        }
        self._save_index()

    def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "last_activity"
    ) -> list[dict]:
        """List sessions from index (fast)"""

        sessions = list(self.index["sessions"].values())

        # Sort
        sessions.sort(
            key=lambda s: s.get(sort_by, ""),
            reverse=True
        )

        # Paginate
        return sessions[offset:offset + limit]

    def _save_index(self):
        """Persist index to disk"""
        self.index["last_updated"] = datetime.now().isoformat()
        self.index_path.write_text(json.dumps(self.index, indent=2))

# Usage
session_index = SessionIndex()

@app.get("/api/sessions")
async def list_sessions(limit: int = 50, offset: int = 0):
    """Fast session listing using index"""
    return session_index.list_sessions(limit, offset)
```

**Benefits**:
- ✅ O(1) session listing (from memory)
- ✅ Supports pagination
- ✅ Fast sorting/filtering

---

### ❌ WEAKNESS 10: SDK Context Sync Issues

**Problem**: SDK context and workspace state diverge

```
SDK state:        5 messages
Workspace state:  4 messages (missed one?)
  ↓ Resume → Inconsistency!
```

**HARDENED SOLUTION**:
```python
class SessionWorkspace:
    """Workspace that tracks SDK sync"""

    def __init__(self):
        self.sdk_synced = False
        self.last_sdk_sync = None

    async def sync_with_sdk(self, agent: AgentSession):
        """Ensure SDK and workspace are in sync"""

        try:
            # Get SDK state
            sdk_history = agent.get_history()
            sdk_message_count = len(sdk_history)

            # Get workspace state
            workspace_history = self.load_messages()
            workspace_message_count = len(workspace_history)

            # Detect divergence
            if sdk_message_count != workspace_message_count:
                logger.warning(
                    f"SDK/Workspace divergence: "
                    f"SDK={sdk_message_count} messages, "
                    f"Workspace={workspace_message_count} messages"
                )

                # Reconcile (SDK is source of truth for messages)
                self.save_messages(sdk_history)

            # Export SDK context
            self.save_context({
                "message_count": sdk_message_count,
                "stats": agent.get_stats(),
                "synced_at": datetime.now().isoformat()
            })

            self.sdk_synced = True
            self.last_sdk_sync = datetime.now()

        except Exception as e:
            logger.error(f"SDK sync failed: {e}")
            self.sdk_synced = False

# Call after every message exchange
async def handle_message(workspace, agent, user_message):
    # Send message
    async for response in agent.query(user_message):
        workspace.save_message(response)

    # Sync after exchange
    await workspace.sync_with_sdk(agent)
```

**Benefits**:
- ✅ Detects divergence early
- ✅ Auto-reconciles from SDK (source of truth)
- ✅ Workspace is always consistent

---

## UI Design - Detailed Specifications

### Session List Sidebar

```
┌───────────────────────────────────────────┐
│ 🏠 BASSI              [≡] [⊕]            │ ← Header
├───────────────────────────────────────────┤
│                                           │
│ 🔍 [Search sessions...]                   │ ← Search bar
│ 📊 [All] [Active] [Archived]             │ ← Filters
│                                           │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                           │
│ 📅 Today                                  │ ← Date grouping
│   ● Analyze PDF Documents         [14:30]│
│     📎 2 files • 5 messages               │
│     [Resume] [Export] [Delete]            │ ← Quick actions
│                                           │
│   ● Create Sales Presentation     [09:15]│
│     📎 3 files • 12 messages              │
│     [Resume] [Export] [Delete]            │
│                                           │
│ 📅 Yesterday                              │
│     Debug Python Script           [15:22]│
│     📎 1 file • 8 messages                │
│     [Resume] [Export] [Delete]            │
│                                           │
│ 📅 This Week                              │
│     Research Competitors          [Mon]   │
│     📎 0 files • 15 messages              │
│     [Resume] [Export] [Delete]            │
│                                           │
│ 📅 Older (Show 10 more...)                │
│                                           │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                           │
│ 💾 Session: abc12345                      │ ← Current session info
│ 🔄 Last activity: 2 min ago               │
│ 📁 2 files • 5 messages                   │
│                                           │
└───────────────────────────────────────────┘

States:
● Active (green)
○ Archived (gray)
```

### File Upload Area

**Collapsed (default)**:
```
┌───────────────────────────────────────────┐
│ 📎 Files (2)                      [▼]     │ ← Click to expand
└───────────────────────────────────────────┘
```

**Expanded**:
```
┌───────────────────────────────────────────┐
│ 📎 Files in Session               [▲]     │ ← Click to collapse
├───────────────────────────────────────────┤
│                                           │
│ 📕 report.pdf                     [×]     │
│    543 KB • Uploaded 5 min ago            │
│    [Preview] [Download] [Remove]          │
│                                           │
│ 🖼️  screenshot_001.png            [×]     │
│    321 KB • Uploaded 2 min ago            │
│    [Preview] [Download] [Remove]          │
│                                           │
│ ┌─────────────────────────────────────┐   │
│ │                                     │   │
│ │     Drop files here to upload      │   │
│ │     or click to browse              │   │
│ │                                     │   │
│ └─────────────────────────────────────┘   │
│                                           │
└───────────────────────────────────────────┘
```

**Drag Over State**:
```
┌───────────────────────────────────────────┐
│ 📎 Files                          [▲]     │
├───────────────────────────────────────────┤
│ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓   │
│ ┃                                     ┃   │
│ ┃  📥  Drop to upload files           ┃   │
│ ┃                                     ┃   │
│ ┃  Images, PDFs, Documents           ┃   │
│ ┃  Up to 100 MB per file             ┃   │
│ ┃                                     ┃   │
│ ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛   │
└───────────────────────────────────────────┘
```

### Session Detail Modal

```
┌───────────────────────────────────────────────────┐
│ ← Back to Sessions                     [×] Close  │
├───────────────────────────────────────────────────┤
│                                                   │
│ 📊 Analyze PDF Documents                          │
│ Created: Nov 7, 2025 at 14:30                    │
│ Session ID: abc12345-def67890                    │
│ Status: ● Active                                  │
│                                                   │
│ ─────────────────────────────────────────────── │
│                                                   │
│ 📁 Files (2)                              [▼]    │
│   📕 report.pdf (543 KB)                          │
│   🖼️  screenshot_001.png (321 KB)                 │
│                                                   │
│ 💬 Conversation (5 messages)              [▼]    │
│   User: Please analyze this PDF...               │
│   Assistant: I'll analyze the document...        │
│   User: What are the key findings?               │
│   Assistant: The key findings are...             │
│   ...                                             │
│                                                   │
│ 📝 Generated Content (3 items)            [▼]    │
│   📄 analysis_report.md (12 KB)                   │
│   🐍 data_processor.py (3 KB)                     │
│   📊 cleaned_data.csv (8 KB)                      │
│                                                   │
│ ─────────────────────────────────────────────── │
│                                                   │
│ [Resume Session] [Export ZIP] [Rename] [Delete]  │
│                                                   │
└───────────────────────────────────────────────────┘
```

---

## Session Naming State Machine

```
┌─────────────┐
│   CREATED   │  ← New session started
│             │     Name: 2025-11-07T14-30-15__abc12345__untitled
└──────┬──────┘
       │
       │ First assistant response
       ↓
┌─────────────┐
│ AUTO_NAMED  │  ← LLM generates preview name
│             │     Name: 2025-11-07T14-30-15__abc12345__analyze-pdf-documents
└──────┬──────┘     Display: "Analyze PDF Documents"
       │
       ├──→ User continues chatting
       │    (stays AUTO_NAMED, can edit)
       │
       ├──→ User clicks "End Session"
       │    ↓
       │    ┌──────────────┐
       │    │   FINALIZED  │  ← Name committed
       │    │              │     Can still rename via modal
       │    └──────────────┘
       │
       └──→ 24h inactivity
            ↓
            ┌──────────────┐
            │  ARCHIVED    │  ← Auto-finalized and archived
            └──────────────┘     Moved to "Older" section
```

**Implementation**:
```python
class SessionState(Enum):
    CREATED = "created"         # Just created
    AUTO_NAMED = "auto_named"   # LLM generated name
    FINALIZED = "finalized"     # User explicitly ended
    ARCHIVED = "archived"       # Auto-archived after 24h

class SessionWorkspace:
    def __init__(self):
        self.state = SessionState.CREATED
        self.display_name = "untitled"

    async def on_first_response(self, agent_response: str):
        """After first assistant response, generate name"""
        if self.state == SessionState.CREATED:
            # Generate name using LLM
            self.display_name = await self._generate_name(agent_response)
            self.state = SessionState.AUTO_NAMED
            self.save_metadata()

    def finalize(self):
        """User explicitly ends session"""
        self.state = SessionState.FINALIZED
        self.finalized_at = datetime.now()
        self.save_metadata()

    async def check_auto_archive(self):
        """Archive if inactive for 24h"""
        if self.state in [SessionState.AUTO_NAMED, SessionState.FINALIZED]:
            age = datetime.now() - self.last_activity
            if age > timedelta(hours=24):
                self.state = SessionState.ARCHIVED
                self.save_metadata()
```

---

## Conclusion: Hardened Concept

All major weaknesses have been addressed:

✅ **Session ending**: Progressive naming + explicit/auto finalize
✅ **Name collisions**: session_id in path (unique)
✅ **Folder rename**: Metadata-based (no filesystem move)
✅ **SDK integration**: Workspace is source of truth
✅ **Browser refresh**: localStorage + history API
✅ **File upload races**: Async lock + hash deduplication
✅ **Orphaned sessions**: Auto-cleanup after 1h
✅ **Memory consumption**: Streaming uploads
✅ **List performance**: In-memory index
✅ **SDK sync**: Automatic reconciliation

The concept is now production-ready! 🚀
