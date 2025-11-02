# Bugfix: Async Tool Results - Split Panel Architecture

## Problem Identified by User

**Root Cause Discovery:** The user noticed that tool results were staying "Running..." because of an **async timing issue**.

The CLI shows:
```
╭── Tool Use ──╮  (shows immediately)
│ INPUT        │
╰──────────────╯
    ↓ [ASYNC WAIT]
╭── Tool Result ──╮  (shows when complete)
│ OUTPUT          │
╰─────────────────╯
```

But the web UI was trying to keep them together:
```
╭── Tool Panel ──╮ (created immediately)
│ INPUT          │
│ OUTPUT: Running... │ (tries to update this later - FAILS)
╰────────────────╯
```

**Why it failed:**
1. Create panel with "Running..." placeholder
2. Wait for async tool_call_end event
3. Try to find the panel by `data-tool` attribute
4. Update might fail if DOM changed or timing is off
5. Result: "Running..." stays forever

## Solution: Two Separate Panels

Split tool display into TWO independent panels that appear sequentially:

1. **Tool Call Panel** (`tool-call-panel`)
   - Created immediately on `tool_call_start`
   - Shows tool name + input
   - Stays visible, never updates

2. **Tool Result Panel** (`tool-result-panel`)
   - Created later on `tool_call_end`
   - Shows success/error + output
   - Appears right after the call panel (or later if async)

This matches the CLI behavior exactly!

## Sequential Flow Example

```
Text block 1
    ↓
Tool Call Panel (mcp__bash__execute)
  INPUT: { command: "ls -la" }
    ↓ [async wait]
Tool Result Panel (mcp__bash__execute)
  ✅ Success
  OUTPUT: total 42...
    ↓
Text block 2
    ↓
Tool Call Panel (mcp__ms365__verify-login)
  INPUT: {}
    ↓ [async wait]
Tool Result Panel (mcp__ms365__verify-login)
  ✅ Success
  OUTPUT: {"success": true, ...}
    ↓
Text block 3
```

## Code Changes

### app.js

#### 1. New Panel Creation Methods

**createToolCallPanel()** - Input only
```javascript
createToolCallPanel(toolName, input, expanded) {
    // Shows tool name + input ONLY
    // No output container, no "Running..." placeholder
}
```

**createToolResultPanel()** - Output only
```javascript
createToolResultPanel(toolName, output, success, expanded) {
    // Shows status (✅/❌) + formatted output ONLY
    // Created separately when result arrives
}
```

#### 2. handleToolCallStart()
```javascript
// Create call panel (input only)
const toolCallPanel = this.createToolCallPanel(
    data.tool_name,
    data.input,
    expanded
);

// Append to content
contentEl.appendChild(toolCallPanel);
```

#### 3. handleToolCallEnd()
```javascript
// Create NEW result panel (don't search for call panel)
const resultPanel = this.createToolResultPanel(
    data.tool_name,
    data.output,
    data.success,
    expanded
);

// Append to content (will appear after call panel)
contentEl.appendChild(resultPanel);
```

### style.css

#### New Panel Styles

```css
/* Tool Call Panel - INPUT only */
.tool-call-panel {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 6px;
    margin: var(--spacing-md) 0;
}

/* Tool Result Panel - OUTPUT only */
.tool-result-panel {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 6px;
    margin: var(--spacing-md) 0;
}

/* Result header */
.result-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm) var(--spacing-md);
    cursor: pointer;
}

.result-header .status-text.success { color: var(--accent-green); }
.result-header .status-text.error { color: var(--accent-red); }

.result-body {
    padding: var(--spacing-md);
    display: none;
}

.tool-result-panel.expanded .result-body {
    display: block;
}
```

## Benefits

1. **✅ No more "Running..." stuck state**
   - Results always display when they arrive
   - No DOM searching/updating required

2. **✅ Matches CLI behavior exactly**
   - Call and result are separate
   - Sequential order preserved

3. **✅ Handles async timing naturally**
   - Panels created when events arrive
   - No assumptions about timing

4. **✅ Simpler logic**
   - No finding/updating existing elements
   - Just append new panels

5. **✅ Better visual separation**
   - Clear distinction between input and output
   - Easier to scan and understand

## Testing

1. **Hard refresh**: `Cmd+Shift+R`
2. **Open console**: F12
3. **Send message**: "list 3 files"
4. **Observe**:
   - Tool call panel appears immediately
   - "Running..." never shows
   - Result panel appears when complete
   - Results always display properly

## Console Logs

New logs show the split architecture:
```
🔧 handleToolCallStart: {tool_name: "mcp__bash__execute", ...}
🏁 Finalizing text block before tool call
   → SUMMARY mode: creating collapsed tool CALL panel
🔨 Created tool call panel for mcp__bash__execute (INPUT ONLY)
   ✅ Summary tool call panel appended
📍 Current DOM order: ["text-1", "call-mcp__bash__execute"]

━━━━━━━━━━━ TOOL CALL END ━━━━━━━━━━━
🏁 handleToolCallEnd: {tool_name: "mcp__bash__execute", success: true, ...}
🔨 Created tool result panel for mcp__bash__execute (OUTPUT ONLY)
✅ Tool result panel appended to content
📍 DOM order after result: ["text-1", "call-mcp__bash__execute", "result-mcp__bash__execute", "text-2"]
```

## Migration Notes

- Old `createToolCallElement()` is replaced by two methods
- Old `.tool-call` CSS still exists for backward compat
- New panels use `.tool-call-panel` and `.tool-result-panel`
- DOM order helper updated to recognize new panel types

## Files Changed

1. `/Users/benno/projects/ai/bassi/bassi/static/app.js`
   - Split createToolCallElement into two methods
   - Updated handleToolCallStart
   - Rewrote handleToolCallEnd
   - Updated getContentOrder helper

2. `/Users/benno/projects/ai/bassi/bassi/static/style.css`
   - Added .tool-call-panel styles
   - Added .tool-result-panel styles
   - Added .result-header styles

## Credit

**Issue identified by:** User (brilliant insight about async timing!)
**Solution:** Split panels architecture matching CLI behavior
