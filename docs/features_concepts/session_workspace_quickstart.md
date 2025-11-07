# Session-Aware Workspace - Quick Decision Guide

## 🎯 The Core Problem

You identified these issues:
```
❌ Files disappear after sending
❌ No session context (files are global)
❌ Can't see past sessions
❌ Can't resume work
```

## 🏗️ The Solution: Session Workspaces

Every chat gets its own workspace:

```
chats/
  2025-11-07T00-30-15--analyze-pdf-documents--e4b2c8/
    📋 session.json              ← Metadata
    📖 history.md                ← Readable log
    🔄 context.json              ← SDK state (for resume)

    📁 DATA_FROM_USER/           ← Your uploads
       report.pdf
       screenshot.png

    📁 RESULTS_FROM_AGENT/       ← Agent's outputs
       analysis.md
       cleaned_data.csv

    📁 SCRIPTS_FROM_AGENT/       ← Python scripts
       processor.py

    📁 DATA_FROM_AGENT/          ← Intermediate stuff
       web_response.html
       temp_data.json
```

## 🔀 Three Architecture Options

### Option A: SDK-First 🟦
```
SDK Session (UUID abc-123)
  └─> Workspace maps to SDK session
```

**Pros**: Minimal changes, SDK does heavy lifting
**Cons**: Less control over organization

---

### Option B: Workspace-First 🟩
```
Workspace (analyze-pdf-documents/)
  └─> SDK session inside workspace
```

**Pros**: Clean organization, human-readable
**Cons**: More complex SDK integration

---

### Option C: Hybrid (RECOMMENDED) ⭐
```
SDK Session (abc-123) ←→ Workspace (analyze-pdf.../)
     ↑                        ↑
  Authority for          Authority for
  conversation           file organization
```

**Pros**: Best of both, flexible
**Cons**: Two moving parts to sync

## 🎨 UI Changes You'll See

### 1. Session Sidebar (New)

```
┌─────────────────────────────┐
│ ☰ SESSIONS          [+]     │
├─────────────────────────────┤
│ 🔍 Search...                │
│                             │
│ Today                       │
│ ● Analyze PDF Docs   00:30  │
│   📎 2 files · 5 msgs       │
│                             │
│ Yesterday                   │
│   Create Presentation 15:22 │
│   📎 3 files · 12 msgs      │
│                             │
│   Debug Script        09:15 │
│   📎 1 file · 8 msgs        │
└─────────────────────────────┘
```

### 2. File Upload Area (Expandable)

**Collapsed:**
```
┌─────────────────────────────────┐
│ 📎 2 files in session      [▼] │
└─────────────────────────────────┘
```

**Expanded:**
```
┌─────────────────────────────────┐
│ 📎 Files in this session   [▲] │
├─────────────────────────────────┤
│ 📕 report.pdf           [×]     │
│    543 KB · 5 min ago           │
│                                 │
│ 🖼️ screenshot.png       [×]     │
│    321 KB · 2 min ago           │
│                                 │
│ [Drop files or click to upload] │
└─────────────────────────────────┘
```

### 3. What Happens When You Drop Files?

**OLD WAY:**
```
Drop → Upload → Show preview → Send → Gone! ❌
```

**NEW WAY:**
```
Drop → Upload to workspace → Persistent preview → Send → Still there! ✅
```

Files stay in `DATA_FROM_USER/` even after sending!

## 🚀 Implementation Phases

### Phase 1: Basic Infrastructure (1-2 days)
- [x] Create `SessionWorkspace` class
- [ ] Change upload to save in workspace/DATA_FROM_USER
- [ ] Track session ID in WebSocket connection
- [ ] Show workspace files in expandable UI

**Result**: Files persist per session!

---

### Phase 2: Session Browser (2-3 days)
- [ ] API to list all sessions
- [ ] Sidebar UI component
- [ ] Click to view session details
- [ ] Export session as ZIP

**Result**: You can see and browse old chats!

---

### Phase 3: Resume & Naming (2-3 days)
- [ ] Generate human-readable names
- [ ] Resume session button
- [ ] Restore context from workspace

**Result**: Meaningful names + continue old work!

---

### Phase 4: Agent Awareness (1-2 days)
- [ ] Enhanced system prompt (knows about folders)
- [ ] Tools default to RESULTS_FROM_AGENT
- [ ] Can search workspace files

**Result**: Agent organizes files intelligently!

## 🤔 Key Decisions Needed

### Decision 1: Where to store `chats/`?
- **A)** Project root (`/Users/benno/projects/ai/bassi/chats/`)
- **B)** Home directory (`~/.bassi/chats/`)
- **C)** Configurable

💡 **Recommendation**: A initially (easier), then add config

---

### Decision 2: Session naming
- **A)** UUID only (`e4b2c8`)
- **B)** Timestamp + UUID (`2025-11-07T00-30-15--e4b2c8`)
- **C)** LLM-generated (`analyze-pdf-documents--e4b2c8`)

💡 **Recommendation**: B immediately, add C in Phase 3

---

### Decision 3: SDK context handling
- **A)** SDK manages it (trust the SDK)
- **B)** Export to `workspace/context.json` after each message
- **C)** Don't persist (rebuild from history)

💡 **Recommendation**: B (enables full resume)

---

### Decision 4: File visibility after sending
- **A)** Keep showing (current behavior from your screenshot)
- **B)** Move to "Sent" section
- **C)** Collapse but keep accessible

💡 **Recommendation**: A (you see what you have)

---

### Decision 5: Migration of existing files
You have files in global `_DATA_FROM_USER/`:
```
screenshot_1762470437485.png
screenshot_1762470476073.png
01 rot-blau und die Denkwerkzeuge_176250...
...
```

**Options**:
- **A)** Leave them (legacy location)
- **B)** Create "Imported Files" session
- **C)** Ask user to assign to sessions

💡 **Recommendation**: B (clean migration)

## ⚡ Quick Start Implementation

### Minimal Viable Change (Can do TODAY)

**1. Session-aware upload** (30 min):
```python
# web_server_v3.py
@app.post("/api/upload")
async def upload_file(file: UploadFile, session_id: str = Form(...)):
    session_dir = Path(f"chats/{session_id}/DATA_FROM_USER")
    session_dir.mkdir(parents=True, exist_ok=True)
    # Save to session_dir instead of global _DATA_FROM_USER
```

**2. Show all session files** (30 min):
```python
@app.get("/api/sessions/{session_id}/files")
async def list_session_files(session_id: str):
    files = list(Path(f"chats/{session_id}/DATA_FROM_USER").glob("*"))
    return [{"name": f.name, "size": f.stat().st_size} for f in files]
```

**3. Update frontend** (1 hour):
```javascript
// app.js
async refreshFileList() {
    const response = await fetch(`/api/sessions/${this.sessionId}/files`)
    const files = await response.json()
    this.renderFilePreviews(files) // Show ALL files, not just pending
}
```

**Result after 2 hours**: Files are session-specific and persist! 🎉

## 📊 Comparison Matrix

| Feature | Current | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|---------|---------|---------|---------|---------|---------|
| Session-specific files | ❌ | ✅ | ✅ | ✅ | ✅ |
| Files persist | ❌ | ✅ | ✅ | ✅ | ✅ |
| See old sessions | ❌ | ❌ | ✅ | ✅ | ✅ |
| Resume session | ❌ | ❌ | ⚠️ | ✅ | ✅ |
| Human-readable names | ❌ | ❌ | ❌ | ✅ | ✅ |
| Agent folder awareness | ❌ | ❌ | ❌ | ❌ | ✅ |
| Organized outputs | ❌ | ⚠️ | ⚠️ | ⚠️ | ✅ |

Legend: ✅ Full support | ⚠️ Partial | ❌ Not supported

## 🎯 My Recommendation

**Start with Phase 1** (the "Quick Start" above):
1. Immediate improvement (2 hours work)
2. Fixes your main complaint (files disappear)
3. Sets foundation for Phases 2-4
4. Low risk (mostly additive)

**Then iterate**:
- Phase 2 next week (visual value - you SEE past work)
- Phase 3 when needed (resume becomes important)
- Phase 4 polish (agent intelligence)

## 💭 Open Questions for You

1. **Priority**: What's most important?
   - [ ] Files persisting (Phase 1)
   - [ ] Seeing old sessions (Phase 2)
   - [ ] Meaningful names (Phase 3)
   - [ ] Agent awareness (Phase 4)

2. **UX**: File upload area - when should it show?
   - [ ] Always visible
   - [ ] Collapsed by default, expand on drop
   - [ ] Show when files present, hide when empty

3. **Naming**: Prefer auto-generated names or user-editable?
   - [ ] Auto only (LLM generates)
   - [ ] User can edit after creation
   - [ ] User sets name at start

4. **Storage**: Where should sessions live?
   - [ ] Project folder (`bassi/chats/`)
   - [ ] Home directory (`~/.bassi/chats/`)
   - [ ] Let me configure it

## 🚦 Next Action

**Tell me**:
1. Which architecture? (A/B/C - I recommend C)
2. Which decisions? (1-5 above)
3. Start with Phase 1? (2 hour quick win)
4. Or full implementation? (1-2 weeks)

Then I'll write the code! 🚀
