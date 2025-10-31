# Web UI Feature Specification

**Feature**: Web-based chat interface for bassi
**Status**: Planning
**Version**: 1.0

## Overview

A standalone web interface that provides full chat functionality without requiring the CLI. Users can run bassi purely as a web application, interact via browser, and see beautifully formatted responses with streaming markdown and pretty-printed tool calls.

## Goals

1. **Standalone Operation**: Web UI is the primary interface, CLI is optional
2. **Real-time Streaming**: Stream markdown content as it arrives from Claude
3. **Beautiful Rendering**: Properly formatted markdown with syntax highlighting
4. **Tool Visibility**: Pretty-printed, colored JSON for tool calls
5. **Modern UX**: Clean, responsive, terminal-inspired design

## Non-Goals

- Mobile app (web-responsive is enough)
- Multi-user authentication (single-user localhost for v1.0)
- Conversation management UI (single session for v1.0)
- File uploads (can add later)

---

## User Stories

### US-1: Start Web UI
**As a** user
**I want to** run bassi as a web application
**So that** I can use it in my browser instead of terminal

**Acceptance Criteria:**
- Running `./run-agent.sh --web` starts only the web server
- Running `./run-agent.sh` starts CLI (web optional via config)
- Browser opens automatically to http://localhost:8765
- Web UI displays connection status

---

### US-2: Chat in Browser
**As a** user
**I want to** type messages in the web UI
**So that** I can interact with bassi without a terminal

**Acceptance Criteria:**
- Input field at bottom of page
- Send button and Enter key both work
- Message appears in conversation immediately
- Input clears after sending

---

### US-3: See Streaming Markdown
**As a** user
**I want to** see responses stream in real-time with proper formatting
**So that** I get immediate feedback like in ChatGPT

**Acceptance Criteria:**
- Text appears character-by-character as it streams
- Markdown renders correctly during streaming (no flashing)
- Code blocks have syntax highlighting
- Lists, headers, bold, italic render correctly
- Incomplete markdown renders gracefully

---

### US-4: View Tool Calls
**As a** user
**I want to** see tool executions with pretty-printed JSON
**So that** I understand what bassi is doing

**Acceptance Criteria:**
- Tool calls appear in colored panels
- JSON is pretty-printed with indentation
- Syntax highlighting: keys, strings, numbers, booleans
- Collapsed by default, expandable on click
- Shows tool name, input, and output

---

### US-5: Track Usage
**As a** user
**I want to** see token usage and costs
**So that** I can monitor my API spending

**Acceptance Criteria:**
- Usage stats shown after each response
- Shows: tokens, time, cost, cumulative cost
- Warning when approaching context limit
- Compaction events clearly indicated

---

## Architecture

### Component Overview

```
┌──────────────────────────────────────┐
│     Browser (Web UI)                  │
│  - Chat interface                     │
│  - Message input                      │
│  - Streaming markdown display         │
│  - Tool call panels                   │
└────────────┬─────────────────────────┘
             │ WebSocket
             │
┌────────────▼─────────────────────────┐
│   FastAPI Web Server                  │
│  - HTTP: serve static files           │
│  - WebSocket: bidirectional messaging │
│  - /api/chat: send message endpoint   │
│  - /api/status: health check          │
└────────────┬─────────────────────────┘
             │
┌────────────▼─────────────────────────┐
│      BassiAgent                       │
│  - Streaming responses                │
│  - Context management                 │
│  - MCP tool execution                 │
└───────────────────────────────────────┘
```

### Message Flow

```
1. User types in browser
2. JavaScript sends WebSocket message: {"type": "user_message", "content": "..."}
3. FastAPI receives, calls agent.chat(message)
4. Agent streams response:
   - content_delta: {"type": "content_delta", "text": "..."}
   - tool_call: {"type": "tool_call", "name": "...", "input": {...}}
   - tool_result: {"type": "tool_result", "output": "..."}
   - message_complete: {"type": "message_complete", "usage": {...}}
5. Browser receives events via WebSocket
6. JavaScript updates UI in real-time
```

---

## Technical Design

### Backend: FastAPI Server

**File**: `bassi/web_server.py`

**Endpoints:**
- `GET /` - Serve index.html
- `GET /static/*` - Serve CSS, JS
- `WS /ws` - WebSocket connection
- `GET /health` - Health check

**WebSocket Protocol:**

**Client → Server:**
```json
{
  "type": "user_message",
  "content": "What's the weather?"
}
```

**Server → Client:**
```json
// Streaming text
{
  "type": "content_delta",
  "text": "The weather"
}

// Tool call start
{
  "type": "tool_call_start",
  "tool_name": "mcp__web__search",
  "input": {"query": "weather Berlin"}
}

// Tool call end
{
  "type": "tool_call_end",
  "tool_name": "mcp__web__search",
  "output": "..."
}

// Message complete
{
  "type": "message_complete",
  "usage": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "cost_usd": 0.0123,
    "total_cost_usd": 1.45,
    "duration_ms": 3400
  }
}

// Status update
{
  "type": "status",
  "message": "⏳ Searching the web..."
}

// Error
{
  "type": "error",
  "message": "Failed to connect to API"
}
```

---

### Frontend: Vanilla JavaScript

**Files:**
- `bassi/static/index.html` - Main page
- `bassi/static/style.css` - Styling
- `bassi/static/app.js` - WebSocket client and rendering

**Key Technologies:**
- **WebSocket API**: Native browser WebSocket
- **Streaming Markdown**: Custom incremental renderer (see below)
- **JSON Highlighting**: Regex-based syntax highlighting
- **Code Highlighting**: Prism.js for code blocks

---

### Streaming Markdown Solution

**Problem**: Traditional markdown parsers (marked.js, markdown-it) don't handle streaming well - incomplete syntax causes flashing and broken rendering.

**Solution**: Incremental rendering with buffering

**Approach:**
1. **Buffer incoming text chunks**
2. **Parse complete elements only** (paragraphs, code blocks, headers)
3. **Render current paragraph incrementally** (handle bold, italic, links mid-stream)
4. **Queue incomplete elements** (half-closed code blocks, lists)

**Implementation Strategy:**

```javascript
class StreamingMarkdownRenderer {
  constructor(container) {
    this.container = container;
    this.buffer = '';
    this.currentBlock = null;
    this.inCodeBlock = false;
  }

  appendChunk(text) {
    this.buffer += text;
    this.renderIncremental();
  }

  renderIncremental() {
    // 1. Detect code blocks (``` markers)
    // 2. Detect paragraphs (double newline)
    // 3. Render inline formatting within current paragraph
    // 4. Handle lists, headers
    // 5. Update DOM without causing flashing
  }

  finalize() {
    // Render any remaining buffered content
  }
}
```

**Fallback**: If custom renderer is too complex, use simpler approach:
- Accumulate all chunks in hidden buffer
- Re-render full markdown every N chunks (debounced)
- Use `marked.js` for final rendering
- Less perfect but simpler

---

### JSON Pretty Printing

**Implementation**: Vanilla JavaScript with regex-based syntax highlighting

```javascript
function syntaxHighlightJSON(json) {
  // Pretty print
  const formatted = JSON.stringify(json, null, 2);

  // Escape HTML
  const escaped = formatted
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Apply syntax highlighting
  return escaped.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    (match) => {
      let cls = 'json-number';
      if (/^"/.test(match)) {
        cls = /:$/.test(match) ? 'json-key' : 'json-string';
      } else if (/true|false/.test(match)) {
        cls = 'json-boolean';
      } else if (/null/.test(match)) {
        cls = 'json-null';
      }
      return `<span class="${cls}">${match}</span>`;
    }
  );
}
```

**CSS:**
```css
.json-key { color: #9876aa; }      /* Purple for keys */
.json-string { color: #6a8759; }   /* Green for strings */
.json-number { color: #6897bb; }   /* Blue for numbers */
.json-boolean { color: #cc7832; }  /* Orange for booleans */
.json-null { color: #808080; }     /* Gray for null */
```

---

## UI Design

### Layout

```
┌────────────────────────────────────────────┐
│  bassi - Benno's Assistant      [●] Online │  ← Header
├────────────────────────────────────────────┤
│                                             │
│  👤 User: What's the weather in Berlin?    │
│                                             │
│  🤖 Assistant:                              │
│  The current weather in Berlin is...       │  ← Conversation
│                                             │  ← Area
│  [Tool Call: web_search] ▼                 │  ← (scrollable)
│    {                                        │
│      "query": "Berlin weather"             │
│    }                                        │
│                                             │
│  ⏱️ 2.3s | 💰 $0.012 | 💵 Total: $1.45    │
│                                             │
├────────────────────────────────────────────┤
│  Type your message...              [Send]  │  ← Input
└────────────────────────────────────────────┘
```

### Color Scheme (Terminal-Inspired)

```css
:root {
  --bg-primary: #1e1e1e;        /* Dark background */
  --bg-secondary: #252526;      /* Slightly lighter */
  --bg-elevated: #2d2d30;       /* Panels, cards */

  --text-primary: #d4d4d4;      /* Main text */
  --text-secondary: #858585;    /* Muted text */
  --text-bright: #ffffff;       /* Highlights */

  --accent-blue: #4fc3f7;       /* Links, buttons */
  --accent-green: #81c784;      /* Success, assistant */
  --accent-yellow: #ffd54f;     /* Warnings */
  --accent-red: #e57373;        /* Errors */
  --accent-purple: #ba68c8;     /* Tool calls */

  --code-bg: #1e1e1e;           /* Code blocks */
  --border: #3e3e42;            /* Borders, dividers */
}
```

### Components

**1. Message Bubble**
```html
<div class="message user-message">
  <div class="message-header">
    <span class="icon">👤</span>
    <span class="label">You</span>
    <span class="timestamp">14:23</span>
  </div>
  <div class="message-content">
    What's the weather in Berlin?
  </div>
</div>
```

**2. Assistant Message (Streaming)**
```html
<div class="message assistant-message">
  <div class="message-header">
    <span class="icon">🤖</span>
    <span class="label">Assistant</span>
    <span class="status">● streaming...</span>
  </div>
  <div class="message-content markdown">
    <!-- Streaming markdown content -->
  </div>
</div>
```

**3. Tool Call Panel**
```html
<div class="tool-call collapsed" data-tool="web_search">
  <div class="tool-header" onclick="toggleTool(this)">
    <span class="icon">🔧</span>
    <span class="name">mcp__web__search</span>
    <span class="toggle">▼</span>
  </div>
  <div class="tool-body">
    <div class="tool-input">
      <h4>Input:</h4>
      <pre class="json"><!-- Highlighted JSON --></pre>
    </div>
    <div class="tool-output">
      <h4>Output:</h4>
      <pre><!-- Raw output --></pre>
    </div>
  </div>
</div>
```

**4. Usage Stats**
```html
<div class="usage-stats">
  <span class="stat">⏱️ 2.3s</span>
  <span class="stat">💰 $0.012</span>
  <span class="stat">💵 Total: $1.45</span>
</div>
```

**5. Input Area**
```html
<div class="input-container">
  <textarea
    id="message-input"
    placeholder="Type your message..."
    rows="1"
  ></textarea>
  <button id="send-button" class="btn-primary">
    Send
  </button>
</div>
```

---

## Configuration

**Add to `~/.config/bassi/config.json`:**
```json
{
  "web_ui": {
    "enabled": true,
    "host": "localhost",
    "port": 8765,
    "auto_open_browser": true,
    "verbose": false
  }
}
```

**CLI flags:**
```bash
# Web-only mode
./run-agent.sh --web

# CLI with web UI
./run-agent.sh --web --cli

# Web UI on custom port
./run-agent.sh --web --port 9000
```

---

## File Structure

```
bassi/
├── web_server.py              # FastAPI application (new)
├── static/                    # Web UI assets (new)
│   ├── index.html             # Main page
│   ├── style.css              # Styling
│   ├── app.js                 # WebSocket client, rendering
│   └── libs/                  # Third-party libraries
│       └── prism.min.js       # Code highlighting
├── agent.py                   # Modified: emit events
└── main.py                    # Modified: web mode support

docs/features_concepts/
└── web_ui.md                  # This document

tests/
├── test_web_server.py         # Web server tests (new)
└── test_streaming_markdown.py # Markdown renderer tests (new)
```

---

## Implementation Plan

### Phase 1: Backend Foundation (2-3 hours)

**Task 1.1**: Create FastAPI server
- File: `bassi/web_server.py`
- Basic HTTP server for static files
- WebSocket endpoint `/ws`
- Health check endpoint `/health`

**Task 1.2**: Integrate with BassiAgent
- Modify `agent.py` to emit events
- Add event emitter for: content_delta, tool_call, usage
- Keep CLI compatibility

**Task 1.3**: Update main.py for web mode
- Add `--web` flag support
- Start web server in async task
- Keep CLI optional

---

### Phase 2: Frontend Core (3-4 hours)

**Task 2.1**: Create HTML structure
- File: `bassi/static/index.html`
- Semantic HTML5 layout
- Conversation container, input area
- Connection status indicator

**Task 2.2**: Implement WebSocket client
- File: `bassi/static/app.js`
- Connect to `/ws`
- Send user messages
- Receive and dispatch events

**Task 2.3**: Basic message rendering
- Display user messages
- Display assistant messages (plain text first)
- Auto-scroll to latest

---

### Phase 3: Streaming Markdown (4-5 hours)

**Task 3.1**: Research & prototype
- Test incremental rendering approaches
- Choose between custom renderer vs. marked.js buffering
- Prototype in standalone HTML file

**Task 3.2**: Implement streaming renderer
- Create `StreamingMarkdownRenderer` class
- Handle inline formatting (bold, italic, code)
- Handle block elements (headers, lists, code blocks)
- Prevent flashing/re-rendering

**Task 3.3**: Integrate Prism.js
- Add code block syntax highlighting
- Support multiple languages
- Terminal theme for code blocks

---

### Phase 4: Tool Call Display (2-3 hours)

**Task 4.1**: Implement JSON highlighting
- Create `syntaxHighlightJSON()` function
- Regex-based coloring
- Pretty-print with indentation

**Task 4.2**: Create tool call panels
- Collapsible UI component
- Show tool name, input, output
- Color-coded by status (running, complete, error)

---

### Phase 5: Polish & Features (2-3 hours)

**Task 5.1**: Styling & responsiveness
- File: `bassi/static/style.css`
- Terminal-inspired dark theme
- Responsive layout (desktop, tablet)
- Smooth animations

**Task 5.2**: Usage stats display
- Show after each response
- Cumulative cost tracking
- Warning indicators

**Task 5.3**: Connection handling
- Reconnection logic
- Connection status indicator
- Graceful error handling

---

### Phase 6: Testing & Documentation (2-3 hours)

**Task 6.1**: Backend tests
- WebSocket connection tests
- Message routing tests
- Error handling tests

**Task 6.2**: Frontend tests (manual)
- Test streaming behavior
- Test tool call display
- Test reconnection
- Browser compatibility (Chrome, Firefox, Safari)

**Task 6.3**: Documentation
- Update README.md
- Add usage examples
- Document configuration options

---

## Testing Strategy

### Backend Tests
```python
# tests/test_web_server.py

async def test_websocket_connection():
    """Test WebSocket connection establishment"""
    pass

async def test_message_routing():
    """Test user message → agent → response flow"""
    pass

async def test_streaming_events():
    """Test content_delta events stream correctly"""
    pass

async def test_tool_call_events():
    """Test tool call events emit correctly"""
    pass
```

### Manual Frontend Testing
- [ ] WebSocket connects on page load
- [ ] User can send messages
- [ ] Messages appear in conversation
- [ ] Markdown streams correctly (no flashing)
- [ ] Code blocks highlight properly
- [ ] Tool calls display in panels
- [ ] JSON is pretty-printed and colored
- [ ] Usage stats display correctly
- [ ] Reconnection works after network interruption
- [ ] Multiple browser windows work simultaneously

### Browser Compatibility
- [ ] Chrome/Edge (Chromium)
- [ ] Firefox
- [ ] Safari

---

## Risks & Mitigation

### Risk 1: Streaming Markdown Complexity
**Risk**: Custom markdown renderer is complex, may have bugs
**Mitigation**:
- Start with simpler buffered approach (re-render every N chunks)
- Use marked.js for correctness
- Iterate to incremental rendering if needed

### Risk 2: WebSocket Reconnection
**Risk**: Connection drops, state lost
**Mitigation**:
- Implement auto-reconnect with exponential backoff
- Show clear connection status
- Client-side message queuing during disconnect

### Risk 3: Performance with Long Conversations
**Risk**: DOM gets too large, browser slows down
**Mitigation**:
- Virtual scrolling (later)
- Message limit (show last 100 messages)
- Pagination or load-more button

---

## Success Criteria

1. ✅ Web UI runs standalone (no CLI required)
2. ✅ User can chat via browser input
3. ✅ Responses stream in real-time
4. ✅ Markdown renders correctly during streaming
5. ✅ Code blocks have syntax highlighting
6. ✅ Tool calls display in colored, pretty-printed panels
7. ✅ Usage stats show after each response
8. ✅ Connection status visible
9. ✅ Reconnection works after disconnect
10. ✅ Tests pass
11. ✅ Documentation complete

---

## Future Enhancements (v2.0+)

- **Multi-Session Management**: Switch between conversations
- **History Search**: Search past messages
- **Export**: Export conversation to markdown
- **Themes**: Light mode, custom color schemes
- **Voice Input**: Speech-to-text
- **File Uploads**: Upload images, PDFs for analysis
- **Mobile App**: Native mobile experience
- **Collaboration**: Share sessions with others
- **Authentication**: Secure remote access

---

**Status**: Ready for implementation
**Estimated Total Effort**: 15-20 hours
**Target Completion**: [TBD]
