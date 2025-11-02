# Option 3 Implementation Plan: Append-Only with Smart IDs

## PHASE 1: ULTRATHINK - Core Architecture Design

### 1.1 Fundamental Principles

**Keep It Stupid Simple (KISS):**
- Server tracks current block IDs
- Client is dumb: append or update by ID
- No complex state machines
- No event buffering or reordering

**Single Source of Truth:**
- Server controls the sequence
- Client trusts the order messages arrive
- IDs ensure reliable updates

### 1.2 Message Flow Analysis

**Example: "list 5 files"**

```
Agent produces:
1. Text: "I'll list 5 files..."
2. Tool Start: bash execute
3. Tool End: [output data]
4. Text: "Here are the files..."
5. Complete: usage stats

Server sends:
1. {type: "text_delta", id: "msg-5-text-0", text: "I'll", create: true}
2. {type: "text_delta", id: "msg-5-text-0", text: " list"}
3. {type: "text_delta", id: "msg-5-text-0", text: " 5 files..."}
4. {type: "tool_start", id: "msg-5-tool-0", name: "bash", input: {...}}
5. {type: "tool_end", id: "msg-5-tool-0", output: {...}, success: true}
6. {type: "text_delta", id: "msg-5-text-1", text: "Here are...", create: true}
7. {type: "message_complete", usage: {...}}

Client does:
1. Create text block "msg-5-text-0", append "I'll"
2. Append " list" to "msg-5-text-0"
3. Append " 5 files..." to "msg-5-text-0"
4. Create tool panel "msg-5-tool-0", show "Running..."
5. Update tool panel "msg-5-tool-0" with output
6. Create text block "msg-5-text-1", append "Here are..."
7. Render markdown, add usage stats
```

### 1.3 Message Protocol Design

**Three core message types:**

```typescript
// 1. Text delta (streaming)
interface TextDelta {
    type: "text_delta"
    id: string           // e.g. "msg-5-text-0"
    text: string         // Text to append
    create?: boolean     // If true, create new block first
}

// 2. Tool lifecycle
interface ToolStart {
    type: "tool_start"
    id: string           // e.g. "msg-5-tool-0"
    tool_name: string
    input: object
}

interface ToolEnd {
    type: "tool_end"
    id: string           // Same ID as tool_start
    output: any          // Raw output from tool
    success: boolean
}

// 3. Message complete
interface MessageComplete {
    type: "message_complete"
    usage: {
        duration_ms: number
        cost_usd: number
        input_tokens: number
        output_tokens: number
    }
}
```

**Why this is simple:**
- Only 4 message types total
- Each has a single purpose
- No complex nesting
- Easy to validate

### 1.4 ID Generation Strategy

**Format:** `msg-{message_num}-{type}-{sequence}`

**Examples:**
- `msg-5-text-0` - First text block in message 5
- `msg-5-tool-0` - First tool in message 5
- `msg-5-text-1` - Second text block (after tool)

**Server state (per WebSocket session):**
```python
class SessionState:
    message_counter: int = 0      # Increments on new assistant message
    text_block_counter: int = 0   # Within current message
    tool_counter: int = 0         # Within current message
    current_text_block_id: str | None = None
```

**Rules:**
1. New message → reset counters, increment message_counter
2. First text delta → create new text block ID
3. Tool start → finalize current text block (set to None)
4. New text after tool → create new text block ID
5. Tool end → update existing tool block

### 1.5 Client Architecture

**State (minimal):**
```javascript
class BassiWebClient {
    blocks = new Map()        // id -> DOM element
    currentMessage = null     // Current message container
    totalCost = 0            // Cumulative cost
}
```

**Core logic (pseudo-code):**
```javascript
onMessage(msg) {
    switch (msg.type) {
        case "text_delta":
            handleTextDelta(msg)
            break
        case "tool_start":
            handleToolStart(msg)
            break
        case "tool_end":
            handleToolEnd(msg)
            break
        case "message_complete":
            handleComplete(msg)
            break
    }
}

handleTextDelta(msg) {
    let block = blocks.get(msg.id)
    if (!block) {
        block = createElement('div', 'text-block')
        block.id = msg.id
        currentMessage.appendChild(block)
        blocks.set(msg.id, block)
    }
    block.textContent += msg.text
}

handleToolStart(msg) {
    const tool = createToolPanel(msg.id, msg.tool_name, msg.input)
    currentMessage.appendChild(tool)
    blocks.set(msg.id, tool)
}

handleToolEnd(msg) {
    const tool = blocks.get(msg.id)
    if (!tool) {
        console.error('Tool not found:', msg.id)
        return
    }
    updateToolOutput(tool, msg.output, msg.success)
}

handleComplete(msg) {
    // Render all text blocks as markdown
    document.querySelectorAll('.text-block').forEach(renderMarkdown)

    // Add usage stats
    addUsageStats(msg.usage)

    // Cleanup
    currentMessage = null
    blocks.clear()
}
```

**Estimated LOC:** ~150 lines (vs 800+ currently)

### 1.6 Server Changes

**Current flow (web_server.py):**
```python
async for event in agent.chat(content):
    ws_message = _agent_event_to_ws_message(event)
    await websocket.send_json(ws_message)
```

**New flow:**
```python
state = SessionState()

async for event in agent.chat(content):
    messages = convert_event_to_messages(event, state)
    for msg in messages:
        await websocket.send_json(msg)
```

**Key function:**
```python
def convert_event_to_messages(event, state):
    """Convert agent event to one or more WebSocket messages"""

    if event.type == EventType.CONTENT_DELTA:
        # Create new text block if needed
        if not state.current_text_block_id:
            state.text_block_counter += 1
            state.current_text_block_id = f"msg-{state.message_counter}-text-{state.text_block_counter}"
            return [{
                "type": "text_delta",
                "id": state.current_text_block_id,
                "text": event.text,
                "create": True
            }]
        else:
            return [{
                "type": "text_delta",
                "id": state.current_text_block_id,
                "text": event.text
            }]

    elif event.type == EventType.TOOL_CALL_START:
        # Finalize current text block
        state.current_text_block_id = None

        # Create tool
        state.tool_counter += 1
        tool_id = f"msg-{state.message_counter}-tool-{state.tool_counter}"

        return [{
            "type": "tool_start",
            "id": tool_id,
            "tool_name": event.tool_name,
            "input": event.input_data
        }]

    elif event.type == EventType.TOOL_CALL_END:
        # Find tool ID (need to track tool name -> ID mapping)
        tool_id = state.get_tool_id(event.tool_name)

        return [{
            "type": "tool_end",
            "id": tool_id,
            "output": event.output_data,
            "success": event.success
        }]

    elif event.type == EventType.MESSAGE_COMPLETE:
        return [{
            "type": "message_complete",
            "usage": {
                "duration_ms": event.duration_ms,
                "cost_usd": event.cost_usd,
                "input_tokens": event.input_tokens,
                "output_tokens": event.output_tokens
            }
        }]

    return []
```

### 1.7 Error Handling Strategy

**Defensive programming:**

1. **Client can't find block to update**
   ```javascript
   if (!blocks.get(id)) {
       console.warn('Block not found, creating:', id)
       // Create it anyway - be forgiving
   }
   ```

2. **Server loses state**
   - Each WebSocket connection gets fresh SessionState
   - On reconnect, client refreshes page (simple)

3. **Malformed messages**
   ```javascript
   try {
       const data = JSON.parse(event.data)
       handleMessage(data)
   } catch (e) {
       console.error('Bad message:', e)
       // Continue - don't crash
   }
   ```

4. **Tool output never arrives**
   - Client shows "Running..." indefinitely
   - User can see something is wrong
   - Better than silent failure

### 1.8 Testing Strategy

**Unit tests (server):**
```python
def test_text_delta_creates_new_block():
    state = SessionState()
    event = ContentDeltaEvent(text="hello")
    messages = convert_event_to_messages(event, state)

    assert len(messages) == 1
    assert messages[0]["type"] == "text_delta"
    assert messages[0]["create"] == True
    assert "msg-0-text-0" in messages[0]["id"]

def test_tool_finalizes_text_block():
    state = SessionState()
    state.current_text_block_id = "msg-0-text-0"

    event = ToolCallStartEvent(tool_name="bash", input={})
    messages = convert_event_to_messages(event, state)

    assert state.current_text_block_id is None
    assert messages[0]["type"] == "tool_start"
```

**Integration tests:**
```python
async def test_full_message_flow():
    """Test: text -> tool -> text -> complete"""
    events = [
        ContentDeltaEvent(text="I'll run"),
        ToolCallStartEvent(tool_name="bash", input={"cmd": "ls"}),
        ToolCallEndEvent(tool_name="bash", output="file.txt", success=True),
        ContentDeltaEvent(text="Here is the file"),
        MessageCompleteEvent(duration_ms=1000, cost_usd=0.001)
    ]

    messages = []
    state = SessionState()
    for event in events:
        messages.extend(convert_event_to_messages(event, state))

    assert messages[0]["type"] == "text_delta"
    assert messages[0]["create"] == True
    assert messages[1]["type"] == "tool_start"
    assert messages[2]["type"] == "tool_end"
    assert messages[3]["type"] == "text_delta"
    assert messages[3]["create"] == True  # New text block after tool
    assert messages[4]["type"] == "message_complete"
```

**Manual testing checklist:**
- [ ] Single text message displays
- [ ] Text + tool + text displays in order
- [ ] Multiple tools display correctly
- [ ] Tool outputs update (not stuck on "Running...")
- [ ] Markdown renders on complete
- [ ] Usage stats show correct values
- [ ] Collapsible tool panels work
- [ ] Reconnect works (refresh page)

---

## PHASE 2: CRITICISM & IMPROVEMENTS

### 2.1 Potential Issues with Current Plan

**Issue 1: Tool ID Mapping**
- Problem: Tool end event has tool_name, but we need tool_id
- Solution: Track `tool_name_to_id` mapping in SessionState

**Issue 2: Multiple tools with same name**
- Problem: If user runs bash twice, names collide
- Solution: Track each tool instance separately
  ```python
  tool_instances = {}  # tool_name -> list of IDs
  def get_latest_tool_id(name):
      return tool_instances[name][-1]
  ```

**Issue 3: Markdown rendering timing**
- Problem: Rendering markdown on every text delta is expensive
- Solution: Only render on message_complete (current plan ✓)

**Issue 4: Lost WebSocket messages**
- Problem: UDP-like, no guaranteed delivery
- Solution: Accept it - if message lost, user refreshes (simple)
- Alternative: Add sequence numbers + client requests missing (complex)

**Issue 5: Very long text blocks**
- Problem: Single huge text block could freeze browser
- Solution: Throttle DOM updates (requestAnimationFrame) ✓

**Issue 6: XSS risk in tool output**
- Problem: If output contains HTML, could inject script
- Solution: Use `textContent` not `innerHTML` for output ✓

### 2.2 Improvements to Make

**Improvement 1: Add verbose level filtering**
```javascript
handleToolStart(msg) {
    if (verboseLevel === 'minimal') {
        // Don't create panel, just show status
        updateStatus('Using ' + msg.tool_name)
        return
    }
    // ... create panel
}
```

**Improvement 2: Better tool output formatting**
```javascript
function formatToolOutput(output) {
    // Extract text from SDK format
    if (Array.isArray(output) && output[0]?.type === 'text') {
        return output[0].text
    }
    return JSON.stringify(output, null, 2)
}
```

**Improvement 3: Add loading states**
```javascript
handleToolStart(msg) {
    const tool = createToolPanel(msg)
    tool.classList.add('loading')  // Spinner CSS
    blocks.set(msg.id, tool)
}

handleToolEnd(msg) {
    tool.classList.remove('loading')
    tool.classList.add('completed')
}
```

**Improvement 4: Graceful degradation**
```javascript
// If marked.js fails to load
const renderMarkdown = typeof marked !== 'undefined'
    ? (text) => marked.parse(text)
    : (text) => text  // Fallback to plain text
```

### 2.3 Revised Architecture

**Changes from original plan:**

1. ✅ Add `tool_name_to_id` mapping in SessionState
2. ✅ Use `textContent` for safety
3. ✅ Throttle updates with requestAnimationFrame
4. ✅ Add verbose level support
5. ✅ Better tool output formatting
6. ✅ Loading states for tools

**Final message protocol (unchanged):**
- text_delta
- tool_start
- tool_end
- message_complete

**Final client LOC estimate:** ~200 lines (with improvements)
**Final server changes:** ~150 lines

---

## PHASE 3: IMPLEMENTATION TASKS

### Task Sequence

```
Phase 3A: Preparation
├─ 3A.1: Create backup of current files
├─ 3A.2: Create new files (app_v2.js, web_server_v2.py)
└─ 3A.3: Setup test environment

Phase 3B: Server Implementation
├─ 3B.1: Create SessionState class
├─ 3B.2: Implement convert_event_to_messages()
├─ 3B.3: Update WebSocket handler
├─ 3B.4: Add logging for debugging
└─ 3B.5: Test with unit tests

Phase 3C: Client Implementation
├─ 3C.1: Create minimal BassiWebClient class
├─ 3C.2: Implement message handlers
├─ 3C.3: Implement tool panel creation
├─ 3C.4: Implement markdown rendering
├─ 3C.5: Add CSS for new structure
└─ 3C.6: Add verbose level support

Phase 3D: Integration & Testing
├─ 3D.1: Wire up new client/server
├─ 3D.2: Manual testing (checklist)
├─ 3D.3: Fix bugs found
├─ 3D.4: Performance testing
└─ 3D.5: Document the new architecture

Phase 3E: Cleanup
├─ 3E.1: Delete old complex code
├─ 3E.2: Update docs
└─ 3E.3: Commit with clear message
```

### Detailed Task Breakdown

**3A.1: Create backup**
```bash
cp bassi/static/app.js bassi/static/app_old.js
cp bassi/web_server.py bassi/web_server_old.py
```

**3B.1: Create SessionState class**
```python
# In web_server.py

@dataclass
class SessionState:
    """Track state for a single WebSocket session"""
    message_counter: int = 0
    text_block_counter: int = 0
    tool_counter: int = 0
    current_text_block_id: str | None = None
    tool_name_to_id: dict[str, str] = field(default_factory=dict)

    def new_message(self):
        """Reset for new assistant message"""
        self.message_counter += 1
        self.text_block_counter = 0
        self.tool_counter = 0
        self.current_text_block_id = None
        self.tool_name_to_id.clear()

    def create_text_block_id(self) -> str:
        self.text_block_counter += 1
        return f"msg-{self.message_counter}-text-{self.text_block_counter}"

    def create_tool_id(self, tool_name: str) -> str:
        self.tool_counter += 1
        tool_id = f"msg-{self.message_counter}-tool-{self.tool_counter}"
        self.tool_name_to_id[tool_name] = tool_id
        return tool_id
```

**3C.1: Create minimal client class**
```javascript
class BassiWebClient {
    constructor() {
        // WebSocket
        this.ws = null
        this.isConnected = false

        // State
        this.blocks = new Map()       // id -> DOM element
        this.currentMessage = null    // Current message container
        this.totalCost = 0           // Cumulative cost
        this.verboseLevel = this.loadVerboseLevel()

        // DOM elements
        this.conversationEl = document.getElementById('conversation')
        this.messageInput = document.getElementById('message-input')
        this.sendButton = document.getElementById('send-button')
        this.verboseLevelSelect = document.getElementById('verbose-level')

        this.init()
    }

    init() {
        // Setup event listeners
        this.sendButton.addEventListener('click', () => this.sendMessage())
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                this.sendMessage()
            }
        })

        this.verboseLevelSelect.value = this.verboseLevel
        this.verboseLevelSelect.addEventListener('change', (e) => {
            this.setVerboseLevel(e.target.value)
        })

        // Connect WebSocket
        this.connect()
    }

    // ... rest of implementation
}
```

---

## PHASE 4: IMPLEMENTATION

**Ready to implement:**
- Plan is solid
- Architecture is simple
- Tasks are clear
- Testing strategy defined

**Next steps:**
1. Execute Phase 3A (preparation)
2. Execute Phase 3B (server)
3. Execute Phase 3C (client)
4. Execute Phase 3D (testing)
5. Execute Phase 3E (cleanup)

**Success criteria:**
- [ ] All manual tests pass
- [ ] Code is <400 lines total (server + client)
- [ ] No "Running..." bugs
- [ ] Sequential order maintained
- [ ] Easy to understand and debug
