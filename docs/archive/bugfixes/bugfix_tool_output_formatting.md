# Bug Fix: Tool Output JSON Formatting

**Date**: 2025-10-31
**Status**: ✅ FIXED
**Severity**: MEDIUM (readability issue)

---

## Problem

Tool output containing JSON was displayed as a single line without newlines, making it unreadable:

```
[{"type":"text","text":"Exit Code: 0\nSuccess: True\n\nSTDOUT:\nfile1.txt\nfile2.txt\n..."}]
```

**Expected**: Tool output should preserve newlines and be easily readable.

---

## Root Cause

The tool output from the Claude Agent SDK comes in this format:
```json
[
  {
    "type": "text",
    "text": "Exit Code: 0\nSuccess: True\n\nSTDOUT:\n..."
  }
]
```

The `formatToolOutput()` method was not:
1. Parsing this JSON structure
2. Extracting the inner `text` field
3. Preserving newlines in the output

Additionally, the CSS for `.tool-output pre` was missing `white-space: pre-wrap` to preserve newlines.

---

## Solution

### Frontend JavaScript Fix (app.js:692-718)

```javascript
formatToolOutput(output) {
    // Handle object output
    if (typeof output === 'object' && output !== null) {
        return JSON.stringify(output, null, 2);
    }

    // Try to parse as JSON if it's a string
    if (typeof output === 'string') {
        try {
            const parsed = JSON.parse(output);

            // Check if it's an array with text content (common SDK format)
            if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].type === 'text') {
                // Extract the text content and preserve newlines
                return parsed[0].text;  // ✓ Extract inner text!
            }

            // Otherwise format as pretty JSON
            return JSON.stringify(parsed, null, 2);
        } catch (e) {
            // Not JSON, return as-is (preserves newlines)
            return output;
        }
    }

    return String(output);
}
```

**Logic Flow**:
1. If output is already an object → format as JSON
2. If output is a string:
   - Try to parse as JSON
   - Check if it matches SDK format: `[{"type": "text", "text": "..."}]`
   - If yes: Extract the `text` field (which contains the actual output with `\n` newlines)
   - If no: Format as pretty JSON
   - If parse fails: Return as-is (plain text)
3. Fallback: Convert to string

### CSS Fix (style.css:400-401)

```css
.tool-input pre, .tool-output pre {
    background: var(--code-bg);
    padding: var(--spacing-md);
    border-radius: 4px;
    overflow-x: auto;
    font-family: var(--font-mono);
    font-size: 0.875rem;
    line-height: 1.5;
    white-space: pre-wrap;  /* ✓ Preserve newlines and wrap long lines */
    word-wrap: break-word;  /* ✓ Break long words if needed */
}
```

**Why These CSS Properties**:
- `white-space: pre-wrap` → Preserves `\n` newlines and wraps long lines
- `word-wrap: break-word` → Breaks long words to prevent horizontal overflow

---

## Files Modified

1. **`bassi/static/app.js`**
   - Enhanced `formatToolOutput()` method to parse SDK JSON format
   - Extract inner `text` field from `[{"type": "text", "text": "..."}]` structure
   - Preserve newlines in output

2. **`bassi/static/style.css`**
   - Added `white-space: pre-wrap` to `.tool-output pre`
   - Added `word-wrap: break-word` to prevent horizontal overflow

---

## Testing

### Before Fix
```
[{"type":"text","text":"Exit Code: 0\nSuccess: True\n\nSTDOUT:\nfile1.txt\nfile2.txt"}]
```
- Single line
- `\n` displayed as literal text
- Unreadable

### After Fix
```
Exit Code: 0
Success: True

STDOUT:
file1.txt
file2.txt
```
- Multiple lines
- Newlines rendered correctly
- Highly readable

---

## Success Criteria

- ✅ Tool output extracts text from SDK JSON format
- ✅ Newlines are preserved and displayed correctly
- ✅ Long lines wrap instead of causing horizontal scroll
- ✅ JSON output (non-SDK format) is still formatted prettily
- ✅ Plain text output works as before
- ✅ Tool panels remain collapsible and functional

---

**Status**: ✅ RESOLVED
**Verified**: 2025-10-31
**Ready for**: Production use
