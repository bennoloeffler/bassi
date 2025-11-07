# Session Workspace - Task Breakdown

**Status**: Ready for Implementation
**Version**: 1.0
**Date**: 2025-11-07
**Total Estimated Time**: 10-12 days

---

## Phase 1: Core Infrastructure (Days 1-3)

### Day 1: Backend Core

#### Task 1.1: Create SessionWorkspace Class [4h]
**File**: `bassi/core_v3/session_workspace.py` (new)

- [x] Create SessionWorkspace class skeleton
- [ ] Implement `__init__` with session_id and base_path
- [ ] Implement `_create_directory_structure()` method
- [ ] Implement `_load_or_create_metadata()` method
- [ ] Implement `upload_file()` with AsyncIO lock
- [ ] Add hash-based deduplication (SHA256)
- [ ] Add streaming file upload (64KB chunks)
- [ ] Implement `list_files()` method
- [ ] Implement `save_message()` to history.md
- [ ] Add `display_name` property
- [ ] Add `update_display_name()` method
- [ ] Add `_save_metadata()` helper

**Dependencies**: None
**Deliverable**: Working SessionWorkspace class
**Tests**: 15 unit tests

---

#### Task 1.2: Create SessionIndex Manager [2h]
**File**: `bassi/core_v3/session_index.py` (new)

- [ ] Create SessionIndex class skeleton
- [ ] Implement index JSON loading/saving
- [ ] Implement `add_session()` method
- [ ] Implement `list_sessions()` with pagination
- [ ] Add sorting (by date, name, file_count, etc.)
- [ ] Add filtering (by state)
- [ ] Implement `update_activity()` method
- [ ] Add `remove_session()` method

**Dependencies**: Task 1.1 (needs SessionWorkspace)
**Deliverable**: Fast session listing
**Tests**: 10 unit tests

---

#### Task 1.3: Write Unit Tests [2h]
**File**: `bassi/core_v3/tests/test_session_workspace.py` (new)
**File**: `bassi/core_v3/tests/test_session_index.py` (new)

**SessionWorkspace Tests** (15 tests):
- [ ] Test workspace creation
- [ ] Test directory structure creation
- [ ] Test metadata loading
- [ ] Test file upload (single file)
- [ ] Test file upload (multiple files)
- [ ] Test file upload with duplicate (hash match)
- [ ] Test streaming upload (100MB file)
- [ ] Test file listing
- [ ] Test message saving
- [ ] Test display name get
- [ ] Test display name update
- [ ] Test metadata persistence
- [ ] Test invalid session_id handling
- [ ] Test concurrent uploads (race condition)
- [ ] Test workspace cleanup

**SessionIndex Tests** (10 tests):
- [ ] Test index creation
- [ ] Test index loading
- [ ] Test session addition
- [ ] Test session listing
- [ ] Test pagination
- [ ] Test sorting by date
- [ ] Test sorting by name
- [ ] Test filtering by state
- [ ] Test activity updates
- [ ] Test listing performance (1000 sessions benchmark)

**Dependencies**: Tasks 1.1, 1.2
**Deliverable**: 25 passing tests

---

### Day 2: Backend Integration

#### Task 1.4: Integrate with web_server_v3.py [3h]
**File**: `bassi/core_v3/web_server_v3.py` (modify)

- [ ] Import SessionWorkspace and SessionIndex
- [ ] Add `self.workspaces: dict[str, SessionWorkspace]` to `__init__`
- [ ] Add `self.session_index = SessionIndex()` to `__init__`
- [ ] Modify `handle_websocket()` to create workspace on connect
- [ ] Pass workspace path to AgentSession config
- [ ] Update `_get_or_create_session_id()` to use workspace

**Dependencies**: Tasks 1.1, 1.2
**Deliverable**: WebSocket creates workspaces

---

#### Task 1.5: Create Upload Endpoint [2h]
**File**: `bassi/core_v3/web_server_v3.py` (extend)

- [ ] Create `@app.post("/api/upload")` endpoint
- [ ] Accept `file: UploadFile` and `session_id: str`
- [ ] Get workspace from `self.workspaces`
- [ ] Call `workspace.upload_file(file)`
- [ ] Update session activity in index
- [ ] Return file metadata (name, size, path)
- [ ] Add error handling (file too large, session not found)

**Dependencies**: Task 1.4
**Deliverable**: Working upload endpoint

---

#### Task 1.6: Create File List Endpoint [1h]
**File**: `bassi/core_v3/web_server_v3.py` (extend)

- [ ] Create `@app.get("/api/sessions/{session_id}/files")` endpoint
- [ ] Get workspace from session_id
- [ ] Call `workspace.list_files()`
- [ ] Return file list as JSON
- [ ] Add error handling (session not found)

**Dependencies**: Task 1.4
**Deliverable**: Working file list endpoint

---

#### Task 1.7: Write Integration Tests [2h]
**File**: `bassi/core_v3/tests/test_web_server_v3.py` (extend)

- [ ] Test WebSocket creates workspace
- [ ] Test upload endpoint with valid file
- [ ] Test upload endpoint with large file (100MB)
- [ ] Test upload endpoint with invalid session
- [ ] Test file list endpoint
- [ ] Test file list empty session
- [ ] Test concurrent uploads to same session

**Dependencies**: Tasks 1.4, 1.5, 1.6
**Deliverable**: 7 passing integration tests

---

### Day 3: Frontend Implementation

#### Task 1.8: Add Session Tracking to app.js [2h]
**File**: `bassi/static/app.js` (modify)

- [ ] Add `this.sessionId` to BassiClient constructor
- [ ] Implement `loadOrCreateSession()` method
- [ ] Use localStorage to persist session ID
- [ ] Implement `saveSession()` method
- [ ] Add session expiration check (24h)
- [ ] Implement `loadSessionFiles()` method
- [ ] Call `loadSessionFiles()` on page load

**Dependencies**: Tasks 1.5, 1.6
**Deliverable**: Session persists across refresh

---

#### Task 1.9: Create FileUploadArea Component [3h]
**File**: `bassi/static/app.js` (add component)

- [ ] Create `FileUploadArea` class
- [ ] Implement `render()` method with collapsed/expanded states
- [ ] Implement `renderFileList()` showing all session files
- [ ] Implement `renderDropZone()` with drag & drop
- [ ] Implement `toggle()` method
- [ ] Implement `handleDrop()` with auto-expand
- [ ] Implement `removeFile()` method
- [ ] Add file upload progress indicator
- [ ] Update upload to use `/api/upload` with session_id

**Dependencies**: Task 1.8
**Deliverable**: Working expandable file area

---

#### Task 1.10: Add CSS Styling [1h]
**File**: `bassi/static/style.css` (extend)

- [ ] Add `.file-upload-area` styles
- [ ] Add `.file-upload-area.collapsed` styles
- [ ] Add `.file-upload-area.expanded` styles
- [ ] Add `.file-area-header` styles
- [ ] Add `.file-list` styles
- [ ] Add `.file-preview` styles
- [ ] Add `.file-icon`, `.file-info`, `.file-meta` styles
- [ ] Add `.file-remove` button styles
- [ ] Add `.drop-zone` styles
- [ ] Add `.drop-zone.drag-over` styles
- [ ] Add transition animations

**Dependencies**: Task 1.9
**Deliverable**: Polished file area UI

---

#### Task 1.11: Manual Testing & Fixes [2h]

**Test Scenarios**:
- [ ] Drop single file → uploads correctly
- [ ] Drop multiple files → all upload
- [ ] File area expands automatically
- [ ] File list shows all files with correct metadata
- [ ] Remove file → removed from UI
- [ ] Refresh page → files still visible
- [ ] Toggle file area → collapses/expands smoothly
- [ ] Send message with files → files persist
- [ ] Check filesystem → files in correct folder
- [ ] Test with 100MB file → streams correctly

**Dependencies**: All Phase 1 tasks
**Deliverable**: Bug-free Phase 1

---

### Phase 1 Checkpoint [30min]

- [ ] Run `./check.sh` (all tests passing)
- [ ] Demo to stakeholder
- [ ] Create Phase 1 completion report
- [ ] Get approval for Phase 2

---

## Phase 2: Session Management UI (Days 4-6)

### Day 4: Backend Session Management

#### Task 2.1: Create Session List Endpoint [2h]
**File**: `bassi/core_v3/web_server_v3.py` (extend)

- [ ] Create `@app.get("/api/sessions")` endpoint
- [ ] Accept query params: `limit`, `offset`, `sort_by`, `filter_state`
- [ ] Call `session_index.list_sessions()`
- [ ] Return paginated session list
- [ ] Include total count
- [ ] Add error handling

**Dependencies**: Task 1.2 (SessionIndex)
**Deliverable**: Working session list endpoint

---

#### Task 2.2: Create Session Detail Endpoint [1h]
**File**: `bassi/core_v3/web_server_v3.py` (extend)

- [ ] Create `@app.get("/api/sessions/{session_id}")` endpoint
- [ ] Load SessionWorkspace
- [ ] Return full session metadata
- [ ] Include file list
- [ ] Include message count
- [ ] Add error handling (session not found)

**Dependencies**: Task 1.1 (SessionWorkspace)
**Deliverable**: Working session detail endpoint

---

#### Task 2.3: Create Session Create Endpoint [1h]
**File**: `bassi/core_v3/web_server_v3.py` (extend)

- [ ] Create `@app.post("/api/sessions")` endpoint
- [ ] Generate new session_id (UUID)
- [ ] Create SessionWorkspace
- [ ] Accept optional `display_name` in body
- [ ] Add to session index
- [ ] Return session metadata

**Dependencies**: Tasks 1.1, 1.2
**Deliverable**: Working session creation

---

#### Task 2.4: Create Session Delete Endpoint [1h]
**File**: `bassi/core_v3/web_server_v3.py` (extend)

- [ ] Create `@app.delete("/api/sessions/{session_id}")` endpoint
- [ ] Remove from session index
- [ ] Delete workspace directory
- [ ] Add error handling (session not found, active session)
- [ ] Add safety check (confirm not active)

**Dependencies**: Tasks 1.1, 1.2
**Deliverable**: Working session deletion

---

#### Task 2.5: Write Endpoint Tests [2h]
**File**: `bassi/core_v3/tests/test_web_server_v3.py` (extend)

- [ ] Test session list endpoint
- [ ] Test pagination (offset, limit)
- [ ] Test sorting (by date, name)
- [ ] Test filtering (by state)
- [ ] Test session detail endpoint
- [ ] Test session create endpoint
- [ ] Test session delete endpoint
- [ ] Test delete active session (should fail)

**Dependencies**: Tasks 2.1-2.4
**Deliverable**: 8 passing tests

---

### Day 5: Frontend Session Sidebar

#### Task 2.6: Create SessionSidebar Component [4h]
**File**: `bassi/static/components/session-sidebar.js` (new)

- [ ] Create `SessionSidebar` class
- [ ] Implement `load()` method (fetch sessions from API)
- [ ] Implement `render()` method
- [ ] Implement `groupByDate()` method (Today/Yesterday/Week/Older)
- [ ] Implement `renderSession()` method
- [ ] Add search input with `handleSearch()`
- [ ] Add filter tabs (All/Active/Archived)
- [ ] Implement `createNewSession()` method
- [ ] Implement `resumeSession()` method
- [ ] Implement `deleteSession()` method with confirmation
- [ ] Add loading states
- [ ] Add empty states

**Dependencies**: Tasks 2.1-2.4 (API endpoints)
**Deliverable**: Working session sidebar

---

#### Task 2.7: Add Sidebar CSS [2h]
**File**: `bassi/static/style.css` (extend)

- [ ] Add `.session-sidebar` layout (300px, flex column)
- [ ] Add `.sidebar-header` styles
- [ ] Add `.new-session-btn` styles
- [ ] Add `.search-bar` styles
- [ ] Add `.filter-tabs` styles
- [ ] Add `.session-list` scrollable area
- [ ] Add `.session-group` styles
- [ ] Add `.session-item` styles (normal, hover, active)
- [ ] Add `.session-actions` hover reveal
- [ ] Add `.sidebar-footer` styles
- [ ] Add responsive breakpoints

**Dependencies**: Task 2.6
**Deliverable**: Polished sidebar UI

---

#### Task 2.8: Integrate Sidebar with Main App [2h]
**File**: `bassi/static/index.html` (modify)
**File**: `bassi/static/app.js` (modify)

- [ ] Add sidebar container to HTML
- [ ] Update layout to be 2-column (sidebar + main)
- [ ] Initialize SessionSidebar on page load
- [ ] Connect sidebar events to BassiClient
- [ ] Update session tracking (localStorage + sidebar sync)
- [ ] Add toggle button for mobile
- [ ] Test layout on different screen sizes

**Dependencies**: Task 2.6, 2.7
**Deliverable**: Integrated sidebar

---

### Day 6: Testing & Polish

#### Task 2.9: Manual Testing [2h]

**Test Scenarios**:
- [ ] Sidebar loads with past sessions
- [ ] Sessions grouped by date correctly
- [ ] Search filters sessions
- [ ] Filter tabs work (All/Active/Archived)
- [ ] Create new session → added to list
- [ ] Resume session → switches correctly
- [ ] Delete session → removed from list
- [ ] Delete confirmation shows
- [ ] Current session highlighted
- [ ] Session actions show on hover
- [ ] Responsive layout works

**Dependencies**: All Phase 2 tasks
**Deliverable**: Bug-free sidebar

---

#### Task 2.10: Performance Testing [2h]

**Benchmarks**:
- [ ] Create 100 test sessions
- [ ] Measure list load time (target: <100ms)
- [ ] Measure search performance (target: <50ms)
- [ ] Measure filter performance (target: <50ms)
- [ ] Test pagination with 1000 sessions
- [ ] Profile memory usage
- [ ] Optimize if needed

**Dependencies**: All Phase 2 tasks
**Deliverable**: Performance benchmarks met

---

#### Task 2.11: Write E2E Tests [2h]
**File**: `bassi/core_v3/tests/test_session_ui.py` (new, optional)

- [ ] Test sidebar loads
- [ ] Test session creation flow
- [ ] Test session resume flow
- [ ] Test session deletion flow
- [ ] Test search
- [ ] Test filtering

**Dependencies**: All Phase 2 tasks
**Deliverable**: 6 E2E tests (optional)

---

### Phase 2 Checkpoint [30min]

- [ ] Run `./check.sh` (all tests passing)
- [ ] Demo to stakeholder (show session history)
- [ ] Create Phase 2 completion report
- [ ] Get approval for Phase 3

---

## Phase 3: Session Naming & Resume (Days 7-9)

### Day 7: Session Naming

#### Task 3.1: Create SessionNamingService [3h]
**File**: `bassi/core_v3/session_naming.py` (new)

- [ ] Create `SessionNamingService` class
- [ ] Implement `generate_name()` method
- [ ] Build LLM prompt for name generation
- [ ] Call Anthropic API (claude-sonnet-4-5)
- [ ] Parse and clean response (kebab-case)
- [ ] Add validation (max 50 chars, valid characters)
- [ ] Add fallback for errors
- [ ] Add caching to avoid duplicate calls

**Dependencies**: None
**Deliverable**: Working naming service

---

#### Task 3.2: Write Naming Tests [2h]
**File**: `bassi/core_v3/tests/test_session_naming.py` (new)

- [ ] Test name generation with mock LLM
- [ ] Test name cleaning (remove invalid chars)
- [ ] Test name validation (length, format)
- [ ] Test fallback on error
- [ ] Test caching
- [ ] Test various input types
- [ ] Test edge cases (empty messages, long messages)

**Dependencies**: Task 3.1
**Deliverable**: 8 passing tests

---

#### Task 3.3: Add Session State Machine [2h]
**File**: `bassi/core_v3/session_workspace.py` (extend)

- [ ] Create `SessionState` enum (CREATED, AUTO_NAMED, FINALIZED, ARCHIVED)
- [ ] Add `state` property to SessionWorkspace
- [ ] Implement `transition_to_auto_named()` method
- [ ] Implement `finalize()` method
- [ ] Implement `archive()` method
- [ ] Add validation (prevent invalid transitions)
- [ ] Update metadata on state changes

**Dependencies**: Task 1.1
**Deliverable**: State machine implemented

---

#### Task 3.4: Write State Machine Tests [1h]
**File**: `bassi/core_v3/tests/test_session_workspace.py` (extend)

- [ ] Test CREATED → AUTO_NAMED transition
- [ ] Test AUTO_NAMED → FINALIZED transition
- [ ] Test FINALIZED → ARCHIVED transition
- [ ] Test invalid transitions raise errors
- [ ] Test metadata updates
- [ ] Test state persistence

**Dependencies**: Task 3.3
**Deliverable**: 6 passing tests

---

### Day 8: Auto-Naming Integration

#### Task 3.5: Integrate Naming with WebSocket [3h]
**File**: `bassi/core_v3/web_server_v3.py` (extend)

- [ ] Import SessionNamingService
- [ ] Initialize naming service in `__init__`
- [ ] Add `_handle_first_response()` method
- [ ] Hook into message flow (detect first response)
- [ ] Call naming service asynchronously
- [ ] Update workspace state to AUTO_NAMED
- [ ] Send `session_named` event to client
- [ ] Handle errors gracefully

**Dependencies**: Tasks 3.1, 3.3
**Deliverable**: Auto-naming works on first response

---

#### Task 3.6: Create Finalize Endpoint [1h]
**File**: `bassi/core_v3/web_server_v3.py` (extend)

- [ ] Create `@app.post("/api/sessions/{session_id}/finalize")` endpoint
- [ ] Accept optional `name` in request body
- [ ] Get workspace
- [ ] Call `workspace.finalize()`
- [ ] Update session index
- [ ] Return updated session metadata

**Dependencies**: Task 3.3
**Deliverable**: Working finalize endpoint

---

#### Task 3.7: Add Frontend Naming Display [2h]
**File**: `bassi/static/app.js` (extend)

- [ ] Listen for `session_named` WebSocket event
- [ ] Update sidebar with new name
- [ ] Show notification ("Session named: ...")
- [ ] Add "End Session" button
- [ ] Connect to finalize endpoint
- [ ] Update UI on finalize

**Dependencies**: Tasks 3.5, 3.6
**Deliverable**: Name updates visible in UI

---

#### Task 3.8: Manual Naming Testing [2h]

**Test Scenarios**:
- [ ] Start new chat → session created
- [ ] Send first message → wait for response
- [ ] Session auto-names (within 2 seconds)
- [ ] Name appears in sidebar
- [ ] Name is relevant to conversation
- [ ] Click "End Session" → state changes to FINALIZED
- [ ] Test error handling (naming fails)
- [ ] Test with various conversation types

**Dependencies**: All Phase 3 naming tasks
**Deliverable**: Bug-free auto-naming

---

### Day 9: Session Resume

#### Task 3.9: Add History Loading [2h]
**File**: `bassi/core_v3/session_workspace.py` (extend)

- [ ] Implement `load_history()` method
- [ ] Parse history.md file
- [ ] Convert to message objects
- [ ] Handle missing or corrupted history
- [ ] Add pagination (optional)

**Dependencies**: Task 1.1
**Deliverable**: History loading works

---

#### Task 3.10: Create Resume Endpoint [2h]
**File**: `bassi/core_v3/web_server_v3.py` (extend)

- [ ] Create `@app.post("/api/sessions/{session_id}/resume")` endpoint
- [ ] Load SessionWorkspace
- [ ] Load conversation history
- [ ] Load SDK context (if exists)
- [ ] Load file list
- [ ] Return complete session state

**Dependencies**: Task 3.9
**Deliverable**: Working resume endpoint

---

#### Task 3.11: Add Frontend Resume [3h]
**File**: `bassi/static/app.js` (extend)

- [ ] Implement `resumeSession()` method
- [ ] Fetch session details from resume endpoint
- [ ] Clear current chat UI
- [ ] Render historical messages
- [ ] Render file list
- [ ] Update session ID
- [ ] Reconnect WebSocket with new session
- [ ] Update localStorage
- [ ] Show loading states

**Dependencies**: Task 3.10
**Deliverable**: Resume switches session and restores UI

---

#### Task 3.12: Resume Testing [2h]

**Test Scenarios**:
- [ ] Resume session with 10 messages
- [ ] Resume session with files
- [ ] Resume session without files
- [ ] Resume session with SDK context
- [ ] Resume then send new message
- [ ] Resume multiple times
- [ ] Resume from different browser tab
- [ ] Test WebSocket reconnection

**Dependencies**: All Phase 3 resume tasks
**Deliverable**: Bug-free resume

---

### Phase 3 Checkpoint [30min]

- [ ] Run `./check.sh` (all tests passing)
- [ ] Demo auto-naming and resume
- [ ] Create Phase 3 completion report
- [ ] Get approval for Phase 4

---

## Phase 4: Agent Awareness (Days 10-12)

### Day 10: System Prompt Enhancement

#### Task 4.1: Build Workspace-Aware Prompt [2h]
**File**: `bassi/core_v3/agent_session.py` (modify)

- [ ] Create `_build_system_prompt()` method
- [ ] Accept SessionWorkspace parameter
- [ ] Include workspace path in prompt
- [ ] Include current session name
- [ ] List all available files from DATA_FROM_USER/
- [ ] Explain folder structure (4 folders)
- [ ] Provide usage guidelines
- [ ] Include working directory

**Dependencies**: Task 1.1
**Deliverable**: Enhanced system prompt

---

#### Task 4.2: Integrate Prompt with Agent [1h]
**File**: `bassi/core_v3/agent_session.py` (modify)

- [ ] Pass workspace to session initialization
- [ ] Call `_build_system_prompt()` on startup
- [ ] Update system message in config
- [ ] Rebuild prompt on file changes (optional)

**Dependencies**: Task 4.1
**Deliverable**: Agent receives workspace context

---

#### Task 4.3: Test Agent Awareness [2h]

**Test Scenarios**:
- [ ] Agent mentions workspace in response
- [ ] Agent knows available files
- [ ] Agent references correct folders
- [ ] Agent suggests saving to appropriate folder
- [ ] Test with 0 files
- [ ] Test with 10 files

**Dependencies**: Tasks 4.1, 4.2
**Deliverable**: Agent is workspace-aware

---

### Day 11: Output Routing

#### Task 4.4: Implement Output Classification [3h]
**File**: `bassi/core_v3/agent_session.py` (extend)

- [ ] Create `_route_output()` method
- [ ] Classify by file extension
- [ ] Route .py → SCRIPTS_FROM_AGENT/
- [ ] Route .md, .pdf, .docx → RESULTS_FROM_AGENT/
- [ ] Route .json, .html → DATA_FROM_AGENT/
- [ ] Default → RESULTS_FROM_AGENT/
- [ ] Create target directories if needed

**Dependencies**: Task 1.1
**Deliverable**: Output routing works

---

#### Task 4.5: Hook Output Routing into Tool Flow [2h]
**File**: `bassi/core_v3/agent_session.py` (extend)

- [ ] Intercept Write tool calls
- [ ] Apply `_route_output()` to determine path
- [ ] Override file path before write
- [ ] Log routing decisions
- [ ] Handle errors (invalid paths, permissions)

**Dependencies**: Task 4.4
**Deliverable**: All agent outputs routed correctly

---

#### Task 4.6: Test Output Routing [2h]

**Test Scenarios**:
- [ ] Agent writes .py script → goes to SCRIPTS_FROM_AGENT/
- [ ] Agent writes .md report → goes to RESULTS_FROM_AGENT/
- [ ] Agent writes .json data → goes to DATA_FROM_AGENT/
- [ ] Test with 10 different file types
- [ ] Verify folders created automatically
- [ ] Check filesystem after writes

**Dependencies**: Tasks 4.4, 4.5
**Deliverable**: All outputs correctly organized

---

### Day 12: Workspace Search & Browser

#### Task 4.7: Implement Workspace Search [3h]
**File**: `bassi/core_v3/session_workspace.py` (extend)

- [ ] Create `search_files()` method
- [ ] Search by filename (case-insensitive)
- [ ] Search by content (text files only)
- [ ] Extract snippets for content matches
- [ ] Search across all 4 folders
- [ ] Return structured results with metadata

**Dependencies**: Task 1.1
**Deliverable**: Search finds files

---

#### Task 4.8: Create Search Endpoint [1h]
**File**: `bassi/core_v3/web_server_v3.py` (extend)

- [ ] Create `@app.get("/api/sessions/{session_id}/search")` endpoint
- [ ] Accept `q` query parameter
- [ ] Call `workspace.search_files()`
- [ ] Return search results as JSON

**Dependencies**: Task 4.7
**Deliverable**: Working search endpoint

---

#### Task 4.9: Create WorkspaceBrowser Component [3h]
**File**: `bassi/static/components/workspace-browser.js` (new)

- [ ] Create `WorkspaceBrowser` class
- [ ] Implement `render()` method
- [ ] Show all 4 folders with file counts
- [ ] Implement folder expand/collapse
- [ ] Implement `renderFile()` for each file
- [ ] Add search input
- [ ] Connect to search endpoint
- [ ] Add file download/open functionality

**Dependencies**: Task 4.8
**Deliverable**: Working workspace browser

---

#### Task 4.10: Add Browser CSS & Integration [2h]
**File**: `bassi/static/style.css` (extend)
**File**: `bassi/static/index.html` (modify)

- [ ] Add `.workspace-browser` styles
- [ ] Add `.folder-section` styles
- [ ] Add `.file-item` styles
- [ ] Add search input styles
- [ ] Add to main layout (collapsible panel)
- [ ] Test responsive layout

**Dependencies**: Task 4.9
**Deliverable**: Polished workspace browser

---

#### Task 4.11: Final Testing & Polish [2h]

**Test Scenarios**:
- [ ] Agent saves files to correct folders
- [ ] Workspace browser shows all files
- [ ] Search finds files by name
- [ ] Search finds files by content
- [ ] Folders expand/collapse smoothly
- [ ] Test with 50+ files
- [ ] Performance is acceptable

**Dependencies**: All Phase 4 tasks
**Deliverable**: Bug-free Phase 4

---

### Phase 4 Checkpoint [30min]

- [ ] Run `./check.sh` (all tests passing)
- [ ] Demo agent folder awareness
- [ ] Create Phase 4 completion report
- [ ] Project complete! 🎉

---

## Final QA & Documentation (Day 12 afternoon)

### Task 5.1: Comprehensive QA [2h]

**Full System Testing**:
- [ ] Test complete workflow (upload → chat → resume)
- [ ] Test with multiple file types
- [ ] Test with large files (100MB)
- [ ] Test with 100+ sessions
- [ ] Test concurrent users (simulate)
- [ ] Performance benchmarks
- [ ] Memory profiling
- [ ] Security review (path traversal, etc.)

---

### Task 5.2: Update Documentation [1h]

- [ ] Update `docs/vision.md` (mark session workspaces as complete)
- [ ] Update `docs/design.md` (add workspace section)
- [ ] Update `docs/requirements.md` (add workspace requirements)
- [ ] Create `docs/features_concepts/session_workspace_usage.md` (user guide)
- [ ] Update `CLAUDE.md` with workspace info
- [ ] Update README.md

---

### Task 5.3: Create Migration Script [1h]
**File**: `bassi/core_v3/migrate_old_files.py` (new)

- [ ] Create script to migrate `_DATA_FROM_USER/` files
- [ ] Create "imported-files" session for orphaned files
- [ ] Move all files to imported session
- [ ] Update metadata
- [ ] Log migration results
- [ ] Add dry-run mode

---

### Task 5.4: Deployment Preparation [1h]

- [ ] Create deployment checklist
- [ ] Test rollback procedure
- [ ] Document feature flag usage
- [ ] Create backup instructions
- [ ] Prepare monitoring/logging
- [ ] Write release notes

---

## Summary by Day

| Day | Tasks | Hours | Deliverable |
|-----|-------|-------|-------------|
| **Day 1** | 1.1-1.3 | 8h | SessionWorkspace + SessionIndex + Tests |
| **Day 2** | 1.4-1.7 | 8h | Backend integration + Upload endpoint |
| **Day 3** | 1.8-1.11 | 8h | Frontend file area + Manual testing |
| **Day 4** | 2.1-2.5 | 7h | Session management endpoints |
| **Day 5** | 2.6-2.8 | 8h | Session sidebar component |
| **Day 6** | 2.9-2.11 | 6h | Testing & polish |
| **Day 7** | 3.1-3.4 | 8h | Session naming service + State machine |
| **Day 8** | 3.5-3.8 | 8h | Auto-naming integration |
| **Day 9** | 3.9-3.12 | 9h | Session resume |
| **Day 10** | 4.1-4.3 | 5h | System prompt enhancement |
| **Day 11** | 4.4-4.6 | 7h | Output routing |
| **Day 12** | 4.7-4.11 + 5.1-5.4 | 12h | Workspace browser + Final QA |
| **Total** | **82 tasks** | **94h** | **Full implementation** |

---

## Task Dependencies Visualization

```
Phase 1
├─ 1.1 SessionWorkspace ──┬──> 1.2 SessionIndex
│                         ├──> 1.4 web_server integration
│                         └──> 1.8 Frontend tracking
├─ 1.4 web_server ────────┬──> 1.5 Upload endpoint
│                         └──> 1.6 File list endpoint
└─ 1.8 Frontend ──────────┴──> 1.9 FileUploadArea

Phase 2
├─ 1.2 SessionIndex ──────┬──> 2.1 List endpoint
│                         ├──> 2.3 Create endpoint
│                         └──> 2.4 Delete endpoint
├─ 2.1-2.4 Endpoints ─────┴──> 2.6 SessionSidebar
└─ 2.6 SessionSidebar ────┴──> 2.7 CSS + 2.8 Integration

Phase 3
├─ 3.1 Naming service ────┬──> 3.5 Auto-naming integration
├─ 3.3 State machine ─────┤
│                         └──> 3.6 Finalize endpoint
└─ 3.9 History loading ───┴──> 3.10 Resume endpoint

Phase 4
├─ 1.1 SessionWorkspace ──┬──> 4.1 System prompt
│                         ├──> 4.4 Output routing
│                         └──> 4.7 Workspace search
└─ 4.7 Search ────────────┴──> 4.8 Search endpoint ──> 4.9 Browser UI
```

---

## Risk Assessment

### High Risk Tasks
- **1.1 SessionWorkspace**: Core functionality, many dependencies
  - Mitigation: Write tests first, incremental implementation
- **3.5 Auto-naming integration**: Async complexity, error handling
  - Mitigation: Fallback gracefully, non-critical feature
- **3.11 Resume**: State restoration complexity
  - Mitigation: Thorough testing, clear error messages

### Medium Risk Tasks
- **1.9 FileUploadArea**: UI complexity, many states
  - Mitigation: Build incrementally, test each state
- **2.6 SessionSidebar**: Complex component, many interactions
  - Mitigation: Break into smaller sub-components
- **4.4 Output routing**: Needs careful path handling
  - Mitigation: Extensive path validation, security review

### Low Risk Tasks
- All CSS tasks: Mostly visual, can iterate
- Test tasks: Additive, don't break existing code
- Documentation: Can be done in parallel

---

## Success Criteria Checklist

### Phase 1 ✅
- [ ] Files upload to session-specific folders
- [ ] Files persist across refresh
- [ ] File area shows all session files
- [ ] No "disappearing files" bug

### Phase 2 ✅
- [ ] Can see 10+ past sessions
- [ ] Sessions grouped by date
- [ ] Search works
- [ ] Resume switches sessions

### Phase 3 ✅
- [ ] Sessions auto-name with meaningful names
- [ ] Resume restores conversation
- [ ] State machine prevents invalid transitions

### Phase 4 ✅
- [ ] Agent knows workspace structure
- [ ] Outputs saved to correct folders
- [ ] Workspace search finds files
- [ ] Browser shows organized files

---

## Next Step

**Ready to begin Phase 1?**

Say "yes" and I'll start with Task 1.1: Create SessionWorkspace Class.

I'll implement each task, run tests, and report progress. We can adjust the plan as we discover issues or improvements.

**Estimated completion**: 10-12 days (~80 hours of work)
