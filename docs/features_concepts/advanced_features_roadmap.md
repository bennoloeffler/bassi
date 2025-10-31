# Advanced Web UI Features - Implementation Roadmap

**Status**: Planning Phase
**Version**: 1.0
**Last Updated**: 2025-01-31

---

## Executive Summary

This roadmap outlines five advanced features to enhance bassi's web UI, bringing it to feature parity with Claude Code. Features are prioritized by value, complexity, and dependencies.

**Total Estimated Time**: 11-17 days
**Implementation Phases**: 4 phases

---

## Features Overview

### Feature 1: Agent Interruption
**Priority**: HIGHEST ⭐⭐⭐
**Complexity**: LOW
**Phase**: 1.1 (First to implement)
**Time Estimate**: 1-2 days

Stop button to interrupt agent during execution. Backend already implements `agent.interrupt()` - just need UI + WebSocket integration.

**Value**: Essential UX - users must be able to stop runaway agents.

---

### Feature 2: Verbose Mode Levels
**Priority**: HIGH ⭐⭐⭐
**Complexity**: LOW-MEDIUM
**Phase**: 1.2 (Second)
**Time Estimate**: 1-2 days

Three-level verbosity control:
- **Minimal**: Just hints ("🔧 Using tool...")
- **Summary**: Tool name + collapsed details
- **Full**: Complete input/output expanded

**Value**: Improves readability and reduces noise.

---

### Feature 3: Thinking Mode Toggle
**Priority**: MEDIUM ⭐⭐
**Complexity**: MEDIUM
**Phase**: 2
**Time Estimate**: 2-3 days

Toggle extended thinking mode where Claude shows reasoning process. Requires API parameter changes and special UI rendering for thinking blocks.

**Value**: Power users want deep reasoning visibility.

---

### Feature 4: Drag & Drop Documents
**Priority**: HIGH ⭐⭐⭐
**Complexity**: MEDIUM-HIGH
**Phase**: 3
**Time Estimate**: 3-5 days

Drag files from Finder/Explorer into chat. Support multiple file types (images, PDFs, text files, documents). Foundational for file handling infrastructure.

**Value**: Very common workflow - essential for productivity.

---

### Feature 5: Clipboard Image Paste (Ctrl+V)
**Priority**: MEDIUM-HIGH ⭐⭐
**Complexity**: HIGH
**Phase**: 4
**Time Estimate**: 3-5 days

Paste images from clipboard directly into chat. Requires vision API integration and file handling. Builds on infrastructure from Feature 4.

**Value**: Convenient for screenshots and visual questions.

---

## Implementation Phases

### Phase 1: Quick Wins (2-4 days)
**Goal**: Deliver high-value, low-complexity features

#### 1.1 Agent Interruption (1-2 days)
- Add Stop button to UI
- WebSocket interrupt message
- Backend interrupt handling (reuse existing)
- UI feedback for interrupted state

#### 1.2 Verbose Mode Levels (1-2 days)
- UI dropdown/toggle for 3 levels
- Event filtering logic
- localStorage persistence
- Update existing tool call rendering

**Deliverables**:
- Users can stop agents mid-execution
- Users can control tool call verbosity
- Improved UX for both CLI and web

---

### Phase 2: Thinking Mode (2-3 days)
**Goal**: Add extended thinking capability

#### 2.1 Thinking Mode Toggle
- UI toggle button in header
- Backend model parameter change
- Special rendering for thinking blocks
- localStorage preference
- Cost warning (thinking = 2-3x tokens)

**Deliverables**:
- Users can enable/disable thinking mode
- Thinking blocks rendered with distinct styling
- Clear indication of thinking mode status

---

### Phase 3: File Infrastructure (3-5 days)
**Goal**: Build foundation for file handling

#### 3.1 Drag & Drop Documents
- Frontend drag/drop event handling
- File upload endpoint (HTTP or WebSocket)
- File type detection & validation
- Preview UI components
- Agent integration (attach files to messages)
- Support: images, PDFs, text files

**Deliverables**:
- Users can drag files into chat
- Files processed and sent to agent
- Preview before sending
- Progress indicators
- Shared file handling infrastructure

---

### Phase 4: Vision Support (3-5 days)
**Goal**: Add vision capabilities

#### 4.1 Clipboard Image Paste
- Paste event handling (Ctrl+V)
- Image extraction from clipboard
- Image preview UI
- Vision API integration
- Image display in history
- Size limits & validation

**Deliverables**:
- Users can paste images from clipboard
- Images sent to Claude Vision API
- Full multimodal conversation support

---

## Shared Infrastructure

These components are needed across multiple features:

### 1. WebSocket Protocol Extensions
Current message types:
- `user_message`, `content_delta`, `tool_call_start`, `tool_call_end`, `message_complete`, `status`, `error`

New message types needed:
- `interrupt` - Stop agent execution
- `config_change` - Update settings (thinking mode, verbose level)
- `file_upload` - Upload file data
- `thinking_block` - Extended thinking content

### 2. Configuration Management
- User preferences (thinking mode, verbose level)
- Session persistence (localStorage)
- Backend state synchronization

### 3. File Handling System
- Upload endpoint (HTTP multipart or WebSocket binary)
- File type detection (MIME types)
- Size validation (max 5MB for images, 10MB for docs)
- Temporary storage (/tmp)
- Automatic cleanup

### 4. UI Components Library
- Settings panel/modal
- File preview cards
- Progress indicators
- Drag/drop overlays
- Thinking block renderer
- Status badges

### 5. Error Handling
- File too large
- Unsupported format
- Upload failed
- Vision API errors
- Network issues
- Interrupt failures

---

## Technical Architecture

### Backend Changes

**Agent (bassi/agent.py)**:
- Add thinking mode parameter to `ClaudeAgentOptions`
- Add verbose level enum (MINIMAL, SUMMARY, FULL)
- File attachment support in `chat()` method
- Vision API integration for images

**Web Server (bassi/web_server.py)**:
- New WebSocket message handlers
- File upload endpoint (HTTP POST)
- Interrupt handler
- Config change handler

**New Files**:
- `bassi/file_handler.py` - File processing utilities
- `bassi/vision_handler.py` - Vision API integration

### Frontend Changes

**New UI Components** (bassi/static/):
- `components/StopButton.js` - Interrupt button
- `components/VerboseToggle.js` - Verbosity selector
- `components/ThinkingToggle.js` - Thinking mode toggle
- `components/FilePreview.js` - File preview cards
- `components/ImagePreview.js` - Image preview
- `components/DropZone.js` - Drag & drop overlay
- `components/ThinkingBlock.js` - Thinking content renderer

**Updated Files**:
- `bassi/static/app.js` - Add new event handlers
- `bassi/static/style.css` - New component styles
- `bassi/static/index.html` - Settings UI

### Database/Storage
- No database changes needed (localStorage for preferences)
- Temporary file storage in `/tmp` with auto-cleanup

---

## Security Considerations

### File Upload Security
1. **Size Limits**:
   - Images: 5MB (Claude API limit)
   - Documents: 10MB (reasonable for PDFs)
2. **File Type Validation**:
   - Whitelist: PNG, JPEG, WebP, PDF, TXT, MD, PY, JS, etc.
   - Reject executables, scripts (unless explicitly requested)
3. **Filename Sanitization**:
   - Remove path traversal attempts
   - Limit length
4. **Temporary Storage**:
   - Use secure temp directory
   - Auto-cleanup after processing
   - No persistent storage of user files

### Privacy
1. **Image Handling**:
   - Images sent to Claude API (external service)
   - Clear user consent required
   - No local caching of images (optional: encrypted cache)
2. **Document Content**:
   - Extracted text sent to Claude
   - Original files not stored
3. **Session Data**:
   - localStorage for preferences only
   - No sensitive data in localStorage

### WebSocket Security
1. **Rate Limiting**:
   - Max message size
   - Max upload frequency
2. **Authentication**:
   - Currently localhost only
   - For remote: need authentication layer
3. **Input Validation**:
   - Sanitize all user inputs
   - Validate message types

---

## Testing Strategy

### Unit Tests
- Agent interruption logic
- File type detection
- Image validation
- Verbose level filtering
- Thinking mode parameter

### Integration Tests
- WebSocket message flow
- File upload end-to-end
- Vision API calls
- Agent with attachments

### E2E Tests
- User clicks Stop → agent stops
- User drags file → file uploaded → agent responds
- User pastes image → image sent → vision response
- User toggles thinking → thinking blocks appear

### Manual Testing
- Cross-browser (Chrome, Firefox, Safari)
- Mobile responsiveness
- Large file uploads
- Error scenarios
- Network interruptions

---

## Documentation Deliverables

For each feature, create two documents:

### Specification Documents
Location: `docs/features_concepts/`

1. `agent_interruption_spec.md` - Stop button specification
2. `verbose_levels_spec.md` - Verbosity levels specification
3. `thinking_mode_spec.md` - Thinking toggle specification
4. `drag_drop_spec.md` - Drag & drop specification
5. `image_paste_spec.md` - Clipboard paste specification

Each spec includes:
- User stories
- UI mockups
- Acceptance criteria
- Security considerations

### Implementation Plans
Location: `docs/features_concepts/`

1. `agent_interruption_implementation.md`
2. `verbose_levels_implementation.md`
3. `thinking_mode_implementation.md`
4. `drag_drop_implementation.md`
5. `image_paste_implementation.md`

Each plan includes:
- Architecture diagrams
- Code examples
- Task breakdown
- Time estimates
- Testing plan

---

## Success Metrics

### Phase 1 Success Criteria
- [ ] Users can interrupt agents with <1s latency
- [ ] Verbose levels working with proper rendering
- [ ] No regressions in existing functionality
- [ ] 100% of tests passing

### Phase 2 Success Criteria
- [ ] Thinking mode toggle works
- [ ] Thinking blocks render distinctly
- [ ] Cost warnings displayed
- [ ] Performance acceptable (responses may be 2-3x slower)

### Phase 3 Success Criteria
- [ ] File upload works for all supported types
- [ ] Preview UI is clear and helpful
- [ ] Error messages are actionable
- [ ] Files properly cleaned up after processing

### Phase 4 Success Criteria
- [ ] Image paste works (Ctrl+V)
- [ ] Vision API responses accurate
- [ ] Image display in conversation history
- [ ] Performance acceptable for image upload

### Overall Success Criteria
- [ ] All 5 features implemented and tested
- [ ] Documentation complete
- [ ] No critical bugs
- [ ] User feedback positive
- [ ] Feature parity with Claude Code

---

## Risks & Mitigation

### Risk 1: Vision API Complexity
**Impact**: HIGH
**Probability**: MEDIUM
**Mitigation**:
- Study Claude Vision API docs thoroughly
- Build simple prototype first
- Test with various image types

### Risk 2: File Upload Performance
**Impact**: MEDIUM
**Probability**: MEDIUM
**Mitigation**:
- Implement streaming uploads
- Client-side compression
- Progress indicators
- Size limits

### Risk 3: WebSocket Scalability
**Impact**: LOW (single user), HIGH (multi-user)
**Probability**: LOW (currently single user)
**Mitigation**:
- Load testing
- Connection pooling
- Rate limiting

### Risk 4: Browser Compatibility
**Impact**: MEDIUM
**Probability**: LOW
**Mitigation**:
- Cross-browser testing
- Polyfills for older browsers
- Graceful degradation

---

## Timeline

**Week 1**: Phase 1 (Interruption + Verbose)
**Week 2**: Phase 2 (Thinking Mode) + Phase 3 Start
**Week 3**: Phase 3 Complete (Drag & Drop)
**Week 4**: Phase 4 (Image Paste) + Testing

**Total**: ~4 weeks for complete implementation

**Fast Track** (focus on essentials):
- Week 1: Phase 1 only
- Week 2: Phase 3 only (skip thinking mode)
- Total: ~2 weeks for core features

---

## Next Steps

1. ✅ Complete analysis (DONE)
2. **Create specification documents** (5 docs)
3. **Create implementation plans** (5 docs)
4. **Review with team/user**
5. **Begin Phase 1 implementation**

---

## Appendix: Feature Comparison

| Feature | Claude Code | bassi CLI | bassi Web | After Roadmap |
|---------|-------------|-----------|-----------|---------------|
| Agent Interruption | ✅ | ✅ (Ctrl+C) | ❌ | ✅ |
| Verbose Control | ✅ (3 levels) | ⚠️ (on/off) | ⚠️ (on/off) | ✅ (3 levels) |
| Thinking Mode | ✅ | ❌ | ❌ | ✅ |
| Drag & Drop Files | ✅ | ❌ | ❌ | ✅ |
| Image Paste | ✅ | ❌ | ❌ | ✅ |
| Streaming Responses | ✅ | ✅ | ✅ | ✅ |
| Tool Call Display | ✅ | ✅ | ✅ | ✅ |
| Web Interface | ✅ | ❌ | ✅ | ✅ |

**Goal**: Achieve 100% feature parity with Claude Code web UI.

---

**Status**: Ready for specification phase
**Next**: Create individual feature specification documents
