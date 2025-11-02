# Bugfix: Streaming Protocol and Content Display Order

## Issue Description
The web UI displays content in the wrong order. Tool calls appear before/after streaming text instead of being interleaved naturally as they occur.

## Root Cause
The DOM structure uses TWO separate containers:
1. `streamingTextContainer` - accumulates ALL streaming text
2. `toolPanelsContainer` - accumulates ALL tool panels

This violates the natural flow where Claude's output is interleaved:
```
Text → Tool → Result → Text → Tool → Result → Text
```

## Solution: Sequential Content Flow

### New Architecture
```
.message-content (sequential container)
  ├── .text-block-1 (streaming/finalized)
  ├── .tool-panel-1
  ├── .text-block-2 (streaming/finalized)
  ├── .tool-panel-2
  ├── .text-block-3 (streaming/finalized)
  └── .usage-stats
```

### State Machine

Track current content type:
- `currentTextBlock`: DOM element for current streaming text
- When text arrives: append to currentTextBlock
- When tool starts: finalize currentTextBlock, append tool panel, create new currentTextBlock
- When tool ends: update tool panel
- When message completes: finalize currentTextBlock, render markdown, add usage stats

### Event Flow

```
1. content_delta (text)
   → Create currentTextBlock if none
   → Append text to currentTextBlock

2. content_delta (more text)
   → Append to currentTextBlock

3. tool_call_start
   → Finalize currentTextBlock (stop streaming mode)
   → Create tool panel, append to message-content
   → currentTextBlock = null

4. tool_call_end
   → Update tool panel with results

5. content_delta (more text)
   → Create NEW currentTextBlock
   → Append text to currentTextBlock

6. message_complete
   → Finalize currentTextBlock
   → Render ALL text blocks as markdown
   → Add usage stats
```

### Implementation Plan

1. **Remove old container structure**
   - Delete streamingTextContainer/toolPanelsContainer logic
   - Use direct `.message-content` as sequential container

2. **Add state tracking**
   ```javascript
   this.currentTextBlock = null;
   this.textBlockBuffer = '';
   ```

3. **handleContentDelta()**
   ```javascript
   - If no currentTextBlock: create one, append to message-content
   - Append text to buffer
   - Update currentTextBlock.textContent
   ```

4. **handleToolCallStart()**
   ```javascript
   - Finalize currentTextBlock (convert to markdown if needed)
   - currentTextBlock = null
   - textBlockBuffer = ''
   - Create tool panel, append to message-content
   ```

5. **handleToolCallEnd()**
   ```javascript
   - Find tool panel, update with results
   ```

6. **handleMessageComplete()**
   ```javascript
   - Finalize currentTextBlock
   - Render all .text-block elements as markdown
   - Add usage stats
   ```

### Logging Strategy

Add logs at every step:
```javascript
console.log('📨 Event:', eventType, metadata);
console.log('🏗️ DOM state:', currentTextBlock, textBlockBuffer.length);
console.log('✅ Action:', action, result);
```

## Testing

1. Send message that triggers multiple tools
2. Verify order: text → tool → result → text → tool → result
3. Check markdown rendering preserves order
4. Verify usage stats appear at end

## Expected Result

Content flows naturally in order, matching the CLI version:
```
🤖 Assistant:

I'll help you...

╭─── Tool Use ───╮
│ ...            │
╰────────────────╯

╭─── ✅ Result ───╮
│ ...            │
╰────────────────╯

Based on the results...

╭─── Tool Use ───╮
│ ...            │
╰────────────────╯

╭─── ✅ Result ───╮
│ ...            │
╰────────────────╯

Here's the final answer...

⏱️ 5.2s | 💰 $0.0234
```
