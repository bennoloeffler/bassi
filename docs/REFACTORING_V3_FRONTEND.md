```markdown
# V3 Frontend Refactoring - Black Box Design

## Overview

The V3 frontend (`bassi/static/app.js`) is **3708 lines** with a single `BassiWebClient` class containing **99+ methods**. This document outlines the refactoring to Black Box Design principles.

## Goals

1. **Separation of Concerns**: Split data layer from UI layer
2. **Modularity**: Each file handles one responsibility
3. **Maintainability**: New developers can understand one module at a time
4. **Testability**: Modules can be tested independently
5. **Target Size**: Main file <200 lines (just initialization and wiring)

## Architecture

### Before (Monolithic)

```
app.js (3708 lines)
└── BassiWebClient class (99+ methods)
    ├── WebSocket connection and event handling
    ├── State management (session, capabilities, files, messages)
    ├── UI rendering (messages, tools, thinking blocks)
    ├── File management (upload, chips, drag-and-drop)
    ├── Autocomplete
    ├── Session sidebar
    ├── Settings modal
    └── Utility methods (formatFileSize, escapeHtml, etc.)
```

### After (Modular)

```
bassi/static/
├── app.js (~200 lines)                    # Initialization and wiring ONLY
├── core/
│   ├── websocket-client.js                # WebSocket connection management
│   └── event-dispatcher.js                # Route events to handlers
├── state/
│   ├── session-state.js                   # Session ID, capabilities, files
│   ├── message-state.js                   # Message blocks, buffers
│   └── ui-state.js                        # Verbose level, working state
├── handlers/
│   ├── message-handler.js                 # Handle incoming WS events
│   ├── text-handler.js                    # Handle text_delta events
│   ├── tool-handler.js                    # Handle tool_start/tool_end
│   └── system-handler.js                  # Handle system events
├── components/
│   ├── message-renderer.js                # Render messages with markdown
│   ├── file-chips.js                      # File chips UI
│   ├── file-list.js                       # File list panel
│   ├── autocomplete.js                    # Command autocomplete
│   ├── session-sidebar.js                 # Session management sidebar
│   └── settings-modal.js                  # Settings dialog
├── services/
│   ├── api-client.js                      # REST API calls
│   ├── upload-service.js                  # File upload logic
│   └── markdown-service.js                # Markdown rendering
└── utils/
    ├── dom-utils.js                       # DOM manipulation helpers
    └── format-utils.js                    # formatFileSize, escapeHtml, etc.
```

## Module Interfaces (Black Box Boundaries)

### Core Layer

**websocket-client.js**
```javascript
class WebSocketClient {
    connect(sessionId?: string): void
    disconnect(): void
    send(message: object): void
    on(eventType: string, handler: Function): void
    off(eventType: string, handler: Function): void
}
```

**event-dispatcher.js**
```javascript
class EventDispatcher {
    register(eventType: string, handler: Function): void
    dispatch(event: object): void
}
```

### State Layer (No Dependencies)

**session-state.js**
```javascript
class SessionState {
    get sessionId(): string
    set sessionId(id: string): void

    get capabilities(): object
    updateCapabilities(caps: object): void

    get files(): File[]
    addFile(file: File): void
    removeFile(filename: string): void
    clearFiles(): void
}
```

**message-state.js**
```javascript
class MessageState {
    get messages(): MessageBlock[]

    createMessage(role: 'user' | 'assistant'): MessageBlock
    updateTextBlock(id: string, text: string): void
    addToolBlock(name: string, input: object): ToolBlock

    // Buffer management for streaming
    getBuffer(key: string): string
    appendBuffer(key: string, text: string): void
    clearBuffer(key: string): void
}
```

**ui-state.js**
```javascript
class UIState {
    get verboseLevel(): number
    set verboseLevel(level: number): void

    get isAgentWorking(): boolean
    setAgentWorking(working: boolean): void

    get isInteractive(): boolean
    setInteractive(interactive: boolean): void
}
```

### Handler Layer

**message-handler.js**
```javascript
class MessageHandler {
    constructor(messageState, uiState, renderer)

    handleTextDelta(event: object): void
    handleThinkingStart(event: object): void
    handleToolStart(event: object): void
    // ... other event handlers
}
```

### Component Layer

**message-renderer.js**
```javascript
class MessageRenderer {
    constructor(container: HTMLElement, markdownService)

    renderUserMessage(content: string, files: File[]): void
    renderAssistantMessage(): MessageBlock
    updateTextBlock(id: string, text: string): void
    renderToolBlock(name: string, input: object): ToolBlock

    // Returns MessageBlock with DOM element and metadata
}
```

**file-chips.js**
```javascript
class FileChips {
    constructor(container: HTMLElement)

    addFile(file: File): void
    removeFile(filename: string): void
    clear(): void

    on(event: 'remove', handler: (filename) => void): void
}
```

**session-sidebar.js**
```javascript
class SessionSidebar {
    constructor(container: HTMLElement, apiClient)

    async loadSessions(): void
    async deleteSession(sessionId: string): void
    selectSession(sessionId: string): void

    on(event: 'select', handler: (sessionId) => void): void
}
```

### Service Layer

**api-client.js**
```javascript
class ApiClient {
    async listSessions(limit, offset): Promise<Session[]>
    async getSession(sessionId): Promise<SessionDetails>
    async deleteSession(sessionId): Promise<void>
    async uploadFile(sessionId, file): Promise<FileInfo>
    async getCapabilities(): Promise<Capabilities>
}
```

**upload-service.js**
```javascript
class UploadService {
    constructor(apiClient)

    async uploadFile(file: File, sessionId: string): Promise<FileInfo>
    async uploadMultiple(files: File[], sessionId: string): Promise<FileInfo[]>
}
```

**markdown-service.js**
```javascript
class MarkdownService {
    render(markdown: string): string
    renderInline(markdown: string): string
}
```

### Utility Layer

**dom-utils.js**
```javascript
export function createElement(tag, classes, attrs)
export function empty(element)
export function scrollToBottom(container)
export function showElement(element)
export function hideElement(element)
```

**format-utils.js**
```javascript
export function formatFileSize(bytes): string
export function escapeHtml(text): string
export function formatTimestamp(date): string
export function truncate(text, maxLength): string
```

## Extraction Strategy (Prioritized)

### Phase 1: Utilities (No Dependencies)

1. **format-utils.js** (Est. 50 lines)
   - Extract `formatFileSize`, `escapeHtml`, `formatTimestamp`, `truncate`
   - No dependencies
   - Easy to test

2. **dom-utils.js** (Est. 100 lines)
   - Extract `createElement`, `empty`, `scrollToBottom`, etc.
   - No dependencies
   - Easy to test

### Phase 2: State Layer (No UI Dependencies)

3. **session-state.js** (Est. 120 lines)
   - Extract session ID, capabilities, files state
   - No UI dependencies
   - Can use localStorage

4. **message-state.js** (Est. 150 lines)
   - Extract message blocks, buffers
   - No UI dependencies

5. **ui-state.js** (Est. 80 lines)
   - Extract verbose level, working state
   - No UI dependencies

### Phase 3: Services

6. **api-client.js** (Est. 150 lines)
   - Extract all `fetch()` calls
   - Uses only browser fetch API

7. **markdown-service.js** (Est. 30 lines)
   - Wrapper around marked.js
   - Simple interface

8. **upload-service.js** (Est. 100 lines)
   - Uses api-client
   - Handles file upload logic

### Phase 4: Core Layer

9. **websocket-client.js** (Est. 200 lines)
   - Extract WebSocket connection logic
   - Event emitter pattern
   - Depends on: nothing (browser WebSocket API)

10. **event-dispatcher.js** (Est. 80 lines)
    - Simple event routing
    - No dependencies

### Phase 5: Components

11. **message-renderer.js** (Est. 300 lines)
    - Render message blocks
    - Depends on: markdown-service, dom-utils, format-utils

12. **file-chips.js** (Est. 150 lines)
    - File chip UI
    - Depends on: dom-utils, format-utils

13. **autocomplete.js** (Est. 200 lines)
    - Command autocomplete
    - Depends on: dom-utils

14. **session-sidebar.js** (Est. 250 lines)
    - Session management UI
    - Depends on: api-client, dom-utils, format-utils

15. **settings-modal.js** (Est. 150 lines)
    - Settings dialog
    - Depends on: dom-utils

### Phase 6: Handlers

16. **message-handler.js** (Est. 400 lines)
    - Route WebSocket events
    - Depends on: message-state, ui-state, message-renderer

17. **text-handler.js** (Est. 150 lines)
    - Handle text_delta events
    - Depends on: message-state, message-renderer

18. **tool-handler.js** (Est. 200 lines)
    - Handle tool events
    - Depends on: message-state, message-renderer

### Phase 7: Main App Wiring

19. **app.js** (Est. 200 lines)
    - Initialize all modules
    - Wire dependencies
    - Set up event handlers
    - Start WebSocket connection

## Testing Strategy

### Unit Tests (Jest or Vitest)

```javascript
// Example: state/session-state.test.js
import { SessionState } from './session-state.js';

test('should add file to session', () => {
    const state = new SessionState();
    state.addFile({ name: 'test.txt', size: 100 });
    expect(state.files).toHaveLength(1);
});
```

### Integration Tests (Test wiring between modules)

```javascript
// Example: components/message-renderer.test.js
import { MessageRenderer } from './message-renderer.js';
import { MarkdownService } from '../services/markdown-service.js';

test('should render markdown message', () => {
    const container = document.createElement('div');
    const renderer = new MessageRenderer(container, new MarkdownService());

    renderer.renderUserMessage('Hello **world**', []);

    expect(container.innerHTML).toContain('<strong>world</strong>');
});
```

### E2E Tests (Playwright)

Keep existing E2E tests in `bassi/core_v3/tests/test_*_e2e.py`

## Migration Path

### Step 1: Extract Utilities

Start with `format-utils.js` and `dom-utils.js`:
```bash
# Create files
touch bassi/static/utils/{format-utils.js,dom-utils.js}

# Extract functions
# Update app.js imports
```

### Step 2: Extract State Layer

Create state modules:
```bash
mkdir -p bassi/static/state
touch bassi/static/state/{session-state.js,message-state.js,ui-state.js}
```

### Step 3: Extract Services

Create service modules:
```bash
mkdir -p bassi/static/services
touch bassi/static/services/{api-client.js,upload-service.js,markdown-service.js}
```

### Step 4: Extract Core

Create core modules:
```bash
mkdir -p bassi/static/core
touch bassi/static/core/{websocket-client.js,event-dispatcher.js}
```

### Step 5: Extract Components

Create component modules:
```bash
mkdir -p bassi/static/components
touch bassi/static/components/{message-renderer.js,file-chips.js,autocomplete.js,session-sidebar.js,settings-modal.js}
```

### Step 6: Extract Handlers

Create handler modules:
```bash
mkdir -p bassi/static/handlers
touch bassi/static/handlers/{message-handler.js,text-handler.js,tool-handler.js,system-handler.js}
```

### Step 7: Update index.html

Add module imports:
```html
<!-- Utils -->
<script type="module" src="/static/utils/format-utils.js"></script>
<script type="module" src="/static/utils/dom-utils.js"></script>

<!-- State -->
<script type="module" src="/static/state/session-state.js"></script>
<script type="module" src="/static/state/message-state.js"></script>
<script type="module" src="/static/state/ui-state.js"></script>

<!-- Services -->
<script type="module" src="/static/services/api-client.js"></script>
<script type="module" src="/static/services/upload-service.js"></script>
<script type="module" src="/static/services/markdown-service.js"></script>

<!-- Core -->
<script type="module" src="/static/core/websocket-client.js"></script>
<script type="module" src="/static/core/event-dispatcher.js"></script>

<!-- Components -->
<script type="module" src="/static/components/message-renderer.js"></script>
<script type="module" src="/static/components/file-chips.js"></script>
<script type="module" src="/static/components/autocomplete.js"></script>
<script type="module" src="/static/components/session-sidebar.js"></script>
<script type="module" src="/static/components/settings-modal.js"></script>

<!-- Handlers -->
<script type="module" src="/static/handlers/message-handler.js"></script>

<!-- Main App -->
<script type="module" src="/static/app.js"></script>
```

### Step 8: Verify Functionality

Test in browser:
1. WebSocket connection works
2. Message streaming works
3. File upload works
4. Session management works
5. Autocomplete works

### Step 9: Rename Files

Once verified:
```bash
mv bassi/static/app.js bassi/static/app_old.js
mv bassi/static/app_new.js bassi/static/app.js
```

## Benefits

1. **Modularity**: Each file has a single responsibility
2. **Testability**: Can test each module independently
3. **Maintainability**: Easy to locate and modify specific functionality
4. **Replaceability**: Can replace any module using only its interface
5. **Developer Experience**: New developers can understand one module at a time

## Estimated Timeline

- **Phase 1 (Utilities)**: 1-2 hours
- **Phase 2 (State)**: 2-3 hours
- **Phase 3 (Services)**: 2-3 hours
- **Phase 4 (Core)**: 3-4 hours
- **Phase 5 (Components)**: 6-8 hours
- **Phase 6 (Handlers)**: 4-5 hours
- **Phase 7 (Wiring)**: 2-3 hours
- **Total**: ~25-35 hours

## Related Documentation

- [CLAUDE_BBS.md](../CLAUDE_BBS.md) - Black Box Design principles
- [REFACTORING_V3_BACKEND.md](REFACTORING_V3_BACKEND.md) - Backend refactoring (completed)
```
