# Complete Protocol Fix - Web UI Streaming & Display

## Issues Fixed

### 1. Content Display Order (CRITICAL)
**Problem:** Tool calls appeared before/after text instead of being interleaved naturally
**Root Cause:** Two separate containers (streamingTextContainer, toolPanelsContainer) violated sequential flow
**Solution:** Single sequential container with text-blocks and tool-panels interleaved

### 2. Tool Results Showing "Running..." (CRITICAL)
**Problem:** Tool outputs stayed as "Running..." instead of showing actual results
**Root Cause:** `handleToolCallEnd` wasn't being called or wasn't finding the tool panels
**Solution:** Enhanced logging + robust DOM querying in `handleToolCallEnd`

### 3. Tool Names Not Displayed Like CLI
**Problem:** Tool names were abbreviated or hidden, unlike the CLI which shows full names
**Solution:** Added "Tool:" label and full tool name display in header

## Changes Made

### File: `bassi/static/app.js`

#### 1. State Management (Lines 34-38)
```javascript
// NEW: Sequential content flow state
this.currentTextBlock = null;
this.textBlockBuffer = '';
this.textBlockCounter = 0;
```

#### 2. Enhanced Message Logging (Lines 180-189)
```javascript
onMessage(event) {
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('📨 WebSocket message received:', data.type);
    console.log('📦 Full data:', data);
    console.log('🏗️ Current state:', { ... });
```

#### 3. handleContentDelta - Sequential Text Blocks (Lines 329-394)
- Creates new text-block elements
- Appends them sequentially to .message-content
- Buffers content and updates in requestAnimationFrame

#### 4. handleToolCallStart - Finalize & Insert (Lines 396-488)
- **Finalizes** current text block (stops streaming)
- Appends tool panel to .message-content (sequential order)
- Resets state for next text block

Key logic:
```javascript
// Finalize text block before tool call
if (this.currentTextBlock) {
    this.currentTextBlock.classList.remove('streaming');
    this.currentTextBlock.classList.add('finalized');
}

// Reset for next content
this.currentTextBlock = null;
this.textBlockBuffer = '';

// Append tool panel sequentially
contentEl.appendChild(toolPanel);
```

#### 5. handleToolCallEnd - Robust Result Display (Lines 516-613)
- Enhanced logging shows entire DOM state
- Finds tool panel by `data-tool` attribute
- Updates output container with formatted results
- Adds success/error status indicators

Key additions:
```javascript
console.log('🔍 Current content children:', ...);
console.log('✅ Found tool call element');
console.log('✅ Found output container');
console.log('📄 Formatted output:', ...);
```

#### 6. handleMessageComplete - Markdown Rendering (Lines 615-674)
- Finalizes last text block
- Renders ALL text blocks as markdown (in place)
- Preserves sequential order
- Adds usage stats at end

#### 7. createToolCallElement - CLI-Style Display (Lines 764-805)
```javascript
<div class="tool-header">
    <span class="icon">🔧</span>
    <span class="tool-label">Tool:</span>
    <span class="full-name">mcp__bash__execute</span>
    <span class="toggle">▼</span>
</div>
<div class="tool-body">
    <div class="tool-input">
        <h4>INPUT:</h4>
        <pre>{ command: "ls ..." }</pre>
    </div>
    <div class="tool-output">
        <h4>OUTPUT:</h4>
        <pre class="running-indicator">Running...</pre>
    </div>
</div>
```

#### 8. Helper Method - Content Order Debugging (Lines 473-488)
```javascript
getContentOrder() {
    // Returns array like ["text-1", "tool-mcp__bash__execute", "text-2"]
}
```

### File: `bassi/static/style.css`

#### 1. Text Block Styles (Lines 168-189)
```css
.text-block {
    white-space: pre-wrap;
    margin-bottom: var(--spacing-md);
}

.text-block.streaming { /* Currently streaming */ }
.text-block.finalized { /* Stream complete, not yet markdown */ }
.text-block.markdown-rendered {
    white-space: normal; /* Markdown rendered */
}
```

#### 2. Tool Header - CLI-Like Display (Lines 751-797)
```css
.tool-header .tool-label {
    font-weight: 600;
    color: var(--text-secondary);
}

.tool-header .full-name {
    font-family: var(--font-mono);
    color: var(--accent-blue);
    flex-grow: 1;
}

.tool-output .status-text.success {
    color: var(--accent-green);
}

.tool-output .status-text.error {
    color: var(--accent-red);
}
```

## Sequential Flow Guarantee

### Event Sequence
```
1. content_delta → creates text-block-1, appends to content
2. content_delta → appends to text-block-1
3. tool_call_start → finalizes text-block-1, appends tool-panel-1
4. tool_call_end → updates tool-panel-1 output
5. content_delta → creates text-block-2, appends to content
6. content_delta → appends to text-block-2
7. message_complete → finalizes text-block-2, renders markdown
```

### Resulting DOM
```
.message-content
  ├── .text-block[data-block-id="1"] (finalized, markdown)
  ├── .tool-call[data-tool="mcp__bash__execute"] (completed)
  ├── .text-block[data-block-id="2"] (finalized, markdown)
  └── .usage-stats
```

## Console Logging Strategy

Every key operation logs:
- **Input:** What data arrived
- **State:** Current DOM/buffer state
- **Action:** What operation is being performed
- **Result:** Outcome of operation
- **DOM Order:** Current sequential layout

Example log sequence:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📨 WebSocket message received: tool_call_start
📦 Full data: {type: "tool_call_start", tool_name: "mcp__bash__execute", ...}
🏗️ Current state: {currentTextBlock: "exists", textBlockBuffer: "45 chars", ...}
🔧 handleToolCallStart: {tool_name: "mcp__bash__execute", ...}
🏁 Finalizing text block before tool call
✅ Text block finalized with 45 chars
🔄 Text block state reset for next content
   → SUMMARY mode: creating collapsed tool panel
   ✅ Summary tool panel appended to content
📍 Current DOM order: ["text-1", "tool-mcp__bash__execute"]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Testing

1. **Refresh browser** (hard refresh: Cmd+Shift+R)
2. **Open console** (F12 or Cmd+Option+I)
3. **Send test message:** "list 3 files and read one"
4. **Observe logs:**
   - Text blocks created sequentially
   - Tool panels inserted at correct position
   - Tool results update properly
   - Final markdown rendering preserves order

## Expected Result

Web UI now matches CLI behavior:
- ✅ Content appears in natural sequential order
- ✅ Tool names displayed prominently like CLI
- ✅ Tool results show actual output (not "Running...")
- ✅ Markdown renders correctly with preserved order
- ✅ Usage stats appear at the end

## Files Changed
1. `/Users/benno/projects/ai/bassi/bassi/static/app.js` - Complete rewrite of streaming handlers
2. `/Users/benno/projects/ai/bassi/bassi/static/style.css` - Added text-block styles and improved tool headers

## Documentation
- `/Users/benno/projects/ai/bassi/docs/bugfix_streaming_protocol_final.md` - Architecture overview
- `/Users/benno/projects/ai/bassi/docs/bugfix_complete_protocol_fix.md` - This file (implementation details)
