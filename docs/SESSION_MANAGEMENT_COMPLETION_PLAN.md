# Session Management - Completion Plan

**Date**: 2025-11-08
**Status**: ⚠️ **PARTIALLY IMPLEMENTED** (Backend ✅ Implemented, Frontend ❌ Missing)
**Last Updated**: 2025-11-16
**Goal**: Complete session management feature with file browser UI

---

## Current State Analysis

### ✅ What's Implemented (Backend - Phase 1 Complete)

**Core Infrastructure** (`bassi/core_v3/`):
- ✅ `SessionWorkspace` class (session_workspace.py:1-300+)
  - Creates directory structure (DATA_FROM_USER, RESULTS_FROM_AGENT, etc.)
  - Hash-based file deduplication
  - Streaming upload (O(1) memory)
  - Metadata management (session.json)
  - Display name support
- ✅ `SessionIndex` class (session_index.py)
  - Fast session listing without filesystem traversal
  - Pagination, sorting, filtering support
- ✅ Web server integration (web_server_v3.py)
  - `POST /api/upload` - File upload with session_id (line 276-332)
  - `GET /api/sessions/{session_id}/files` - List session files (line 336-377)
  - WebSocket creates workspace on connect (line 399-408)
  - Active workspaces tracked in `self.workspaces` dict

**What Works**:
- Files upload to `chats/{session_id}/DATA_FROM_USER/`
- Files persist on disk across server restarts
- Duplicate detection prevents re-uploads
- Session metadata tracked

### ❌ What's Missing (Frontend - No UI)

**Phase 1 Frontend (File Browser)**:
- ❌ No localStorage session persistence (sessionId lost on refresh)
- ❌ No expandable file upload area component
- ❌ No file list display showing all session files
- ❌ No call to `/api/sessions/{session_id}/files` on page load
- ❌ Files disappear from UI after being sent in message

**Phase 2 (Session Management)**:
- ❌ No session sidebar showing past sessions
- ❌ No session list endpoints (`GET /api/sessions`, `POST /api/sessions`, etc.)
- ❌ No session search/filter UI
- ❌ No session switcher
- ❌ No session delete functionality

**Phase 3 (Naming & Resume)**:
- ❌ No LLM auto-naming service
- ❌ No session state machine (CREATED → AUTO_NAMED → FINALIZED)
- ❌ No session resume endpoint
- ❌ No conversation history loading

**Phase 4 (Agent Awareness)**:
- ❌ No workspace-aware system prompt
- ❌ No output routing to correct folders
- ❌ No workspace search functionality
- ❌ No workspace browser UI component

---

## Root Cause: Frontend Not Connected to Backend

**Problem**: The image shows no session management UI because:
1. Frontend never calls `/api/sessions/{session_id}/files` to load files
2. No UI component to display session files
3. SessionId not persisted in localStorage
4. No session history/sidebar implemented

**User Impact**:
- Files upload successfully but "disappear" from UI
- No way to see past sessions
- No way to browse uploaded files
- Session lost on browser refresh

---

## Completion Plan

### Option A: Minimal Fix (1-2 days)
**Goal**: Make current session files visible

**Tasks**:
1. **Session Persistence** [2h]
   - Save `sessionId` to localStorage on connect
   - Load sessionId on page load
   - Restore session if still active

2. **File List Display** [3h]
   - Create `FileListArea` component (collapsed by default)
   - Fetch files from `/api/sessions/{session_id}/files` on load
   - Show count: "📎 2 files in session" with expand/collapse
   - Display file list when expanded (name, size, upload time)

3. **File Persistence in UI** [2h]
   - Keep files visible after sending in message
   - Refresh file list after upload
   - Show "File already uploaded" for duplicates

**Deliverable**: Users can see their uploaded files persistently

---

### Option B: Full Session Management (8-10 days)
**Goal**: Complete all 4 phases from implementation plan

**Phase 1: File Browser** (Days 1-3) - Same as Option A plus:
4. **Expandable File Area UI** [3h]
   - Full component with drag-and-drop
   - File removal capability
   - Visual polish

**Phase 2: Session History** (Days 4-6):
5. **Session List Endpoints** [4h]
   - `GET /api/sessions` (pagination, sorting, filtering)
   - `GET /api/sessions/{id}` (detail view)
   - `POST /api/sessions` (create new)
   - `DELETE /api/sessions/{id}` (delete)

6. **Session Sidebar Component** [6h]
   - Left sidebar showing past sessions
   - Grouped by date (Today/Yesterday/This Week/Older)
   - Search and filter functionality
   - Session switcher

**Phase 3: Auto-Naming & Resume** (Days 7-9):
7. **Session Naming Service** [4h]
   - LLM-based name generation
   - State machine (CREATED → AUTO_NAMED → FINALIZED)
   - Auto-name after first response

8. **Session Resume** [4h]
   - Load conversation history
   - Restore file list
   - Reconnect WebSocket with session context

**Phase 4: Agent Awareness** (Days 10-12):
9. **Workspace-Aware Prompts** [3h]
   - System prompt includes workspace info
   - Agent knows available files
   - Output routing to correct folders

10. **Workspace Browser** [5h]
    - UI showing all 4 folders
    - File search across workspace
    - Download/open capabilities

**Deliverable**: Full session management as designed

---

### Option C: Iterative Approach (Recommended)
**Goal**: Deliver value incrementally

**Sprint 1 (3 days)**: File Visibility
- Tasks 1-3 from Option A
- Basic file list display
- Session persistence
- **Demo**: "Files no longer disappear"

**Sprint 2 (3 days)**: Session History
- Tasks 5-6 from Option B
- Session sidebar
- Session switching
- **Demo**: "Browse past sessions"

**Sprint 3 (3 days)**: Auto-Naming
- Task 7 from Option B
- LLM naming service
- State machine
- **Demo**: "Sessions have meaningful names"

**Sprint 4 (3 days)**: Resume & Agent Awareness
- Tasks 8-9 from Option B
- Full resume capability
- Workspace-aware agent
- **Demo**: "Resume any session"

---

## Recommended Next Steps

### Immediate (Today):
1. **Decide on approach**: Option A (minimal) vs Option C (iterative)
2. **Prioritize pain points**: What frustrates users most?
3. **Set success criteria**: What does "done" look like?

### This Week (Option A - Minimal):
1. Implement session persistence (2h)
2. Implement file list display (3h)
3. Test with real files (1h)
4. Deploy and gather feedback

### This Month (Option C - Iterative):
- Sprint 1: File visibility (by Nov 15)
- Sprint 2: Session history (by Nov 22)
- Sprint 3: Auto-naming (by Nov 29)
- Sprint 4: Full feature (by Dec 6)

---

## Questions for Decision

1. **Scope**: Minimal fix (Option A) or full feature (Option B)?
2. **Timeline**: Can we dedicate 3-10 days to this?
3. **User Priority**: What do users need most urgently?
   - See uploaded files? (Phase 1)
   - Browse past sessions? (Phase 2)
   - Meaningful names? (Phase 3)
   - Agent workspace awareness? (Phase 4)

4. **Integration**: How does this fit with other roadmap items?
   - Are there more urgent features?
   - Can we do this incrementally?

---

## Technical Risks

### Low Risk:
- ✅ Backend is already implemented and tested
- ✅ API endpoints exist and work
- ✅ File storage is solid

### Medium Risk:
- ⚠️ Frontend state management complexity
- ⚠️ localStorage session persistence edge cases
- ⚠️ WebSocket reconnection with session state

### High Risk:
- 🔴 LLM naming service cost and latency
- 🔴 Session resume with large conversation history
- 🔴 UI/UX complexity for session management

---

## Success Metrics

**Phase 1 (Minimal)**:
- ✅ Files persist in UI after sending
- ✅ File count visible at all times
- ✅ Session survives browser refresh

**Phase 2 (Full)**:
- ✅ Can browse 10+ past sessions
- ✅ Sessions have meaningful names
- ✅ Resume works with full context
- ✅ Agent knows workspace structure

---

## Appendix: File Locations

### Backend (Implemented):
- `bassi/core_v3/session_workspace.py` - Workspace manager
- `bassi/core_v3/session_index.py` - Session index
- `bassi/core_v3/web_server_v3.py:276-408` - API endpoints
- `bassi/core_v3/upload_service.py` - File upload logic

### Frontend (To Implement):
- `bassi/static/app.js` - Add session persistence, file list
- `bassi/static/components/file-list.js` - New component (if needed)
- `bassi/static/components/session-sidebar.js` - New component (Phase 2)
- `bassi/static/style.css` - New styles for components

### Documentation:
- `docs/features_concepts/session_workspace_tasks.md` - Full task breakdown
- `docs/features_concepts/session_workspace_implementation_plan.md` - Architecture
- `docs/2025-11-08-refactoring-plan.md:114-131` - Phase 1.6 status

---

## Next Action

**Recommend**: Start with **Option A (Minimal)** to quickly address user pain point.

**Tasks**:
1. Add localStorage session persistence (bassi/static/app.js:1514)
2. Create file list component that calls `/api/sessions/{id}/files`
3. Display collapsed file area showing count
4. Expand on click to show full file list

**Time**: 1-2 days
**Impact**: High (files no longer "disappear")
**Risk**: Low (backend ready, simple frontend change)

**After completion**: Gather user feedback, then decide on Phase 2 (session history sidebar).
