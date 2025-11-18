# Verbose Levels - CSS-Based Implementation ✅

## Summary

Successfully migrated verbose levels from DOM manipulation to CSS-based visibility control, fixing critical "Tool panel not found" errors in Minimal mode.

## Concept

Use CSS classes to control visibility of tool details based on verbose level setting. Always render all content, just hide via CSS. This ensures all DOM elements exist, preventing JavaScript errors when trying to update them later.

## Problem Solved

### Original Issue
- **Symptom**: Browser console errors: `Tool panel not found for ID: msg-0-tool-0`
- **Root Cause**: Early returns in `handleThinking()` and `handleToolStart()` skipped rendering when `verboseLevel === 'minimal'`
- **Impact**: DOM elements didn't exist, causing JavaScript errors when trying to update them later

### Solution
- Always render all content (tool blocks, thinking blocks, etc.)
- Control visibility using CSS classes on the conversation container
- Three CSS classes: `verbose-minimal`, `verbose-normal`, `verbose-full`

## Implementation

### 1. CSS Class Management (`app.js`)

**Set Initial Class** (Lines 88-96):
```javascript
// Set initial verbose level CSS class on page load
this.conversationEl.classList.add(`verbose-${this.verboseLevel}`)
```

**Update Class on Change** (Lines 802-811):
```javascript
setVerboseLevel(level) {
    this.verboseLevel = level
    localStorage.setItem('bassi_verbose_level', level)

    // Update CSS class on conversation container
    this.conversationEl.classList.remove('verbose-minimal', 'verbose-normal', 'verbose-full')
    this.conversationEl.classList.add(`verbose-${level}`)

    console.log('Verbose level set to:', level)
}
```

### 2. Removed Early Returns (`app.js`)

**handleThinking()** (Line 421):
```javascript
// Before:
if (this.verboseLevel === 'minimal') return  // ❌ REMOVED

// After:
// Always render (visibility controlled by CSS)  // ✅
```

**handleToolStart()** (Line 458):
```javascript
// Before:
if (this.verboseLevel === 'minimal') {  // ❌ REMOVED
    return
}

// After:
// Always render (visibility controlled by CSS)  // ✅
```

### 3. CSS Rules (`style.css`, Lines 1239-1367)

#### Minimal Mode - Show Only Headers
```css
.verbose-minimal .tool-body {
    display: none !important;
}

.verbose-minimal .tool-call::after {
    content: ' (click to expand)';
    color: var(--text-muted);
    font-size: 0.85em;
    margin-left: var(--spacing-sm);
}

.verbose-minimal .code-block-content {
    display: none !important;
}
```

#### Normal Mode - Show Truncated Output
```css
.verbose-normal .tool-input {
    max-height: 4.5em;
    overflow: hidden;
    position: relative;
}

.verbose-normal .tool-input::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 1.5em;
    background: linear-gradient(transparent, var(--bg-elevated));
    pointer-events: none;
}

.verbose-normal .tool-output {
    max-height: 6em;  /* ~3 lines */
    overflow: hidden;
    position: relative;
}

.verbose-normal .code-block-content {
    max-height: 12em;  /* ~6 lines */
    overflow: hidden;
    position: relative;
}
```

#### Full Mode - Show Everything
```css
.verbose-full .tool-body {
    display: block !important;
}

.verbose-full .tool-input,
.verbose-full .tool-output,
.verbose-full .code-block-content {
    max-height: none !important;
}
```

#### Always Show Errors
```css
/* Errors always fully visible regardless of verbose level */
.tool-call.tool-error .tool-body {
    display: block !important;
}
```

## Files Modified

### Created:
- `docs/VERBOSE_LEVELS_SIMPLE.md` - Design specification
- `docs/VERBOSE_LEVELS_IMPLEMENTED.md` - This document

### Modified:
- `bassi/static/app.js`:
  - Removed early returns from `handleThinking()` (line 421)
  - Removed early returns from `handleToolStart()` (line 458)
  - Added CSS class initialization (lines 88-96)
  - Updated `setVerboseLevel()` to manage CSS classes (lines 802-811)

- `bassi/static/style.css`:
  - Added comprehensive verbose level rules (lines 1239-1367)

## How It Works

### Verbose Level Behavior

**Minimal Mode**:
- Tool headers visible with "(click to expand)" hint
- Tool bodies hidden
- Code blocks hidden
- Errors always visible (for debugging)

**Normal Mode**:
- Tool headers visible
- Tool inputs truncated to ~3 lines with fade gradient
- Tool outputs truncated to ~3 lines with fade gradient
- Code blocks truncated to ~6 lines
- Errors always visible

**Full Mode**:
- Everything fully expanded
- No truncation
- Maximum transparency

### User Flow

1. User selects verbose level from dropdown
2. JavaScript updates CSS class on conversation container
3. All content remains in DOM (no re-rendering needed)
4. CSS rules control visibility based on class
5. User can switch levels instantly without DOM errors

## Benefits

✅ **No DOM Errors**: All elements always exist, preventing "not found" errors
✅ **Instant Switching**: CSS show/hide is immediate, no re-rendering
✅ **Clean Separation**: Content (HTML) separate from presentation (CSS)
✅ **Future Extensibility**: Easy to add click-to-expand on individual blocks
✅ **Progressive Disclosure**: Users see appropriate detail for their needs
✅ **Performance**: No expensive DOM manipulation on verbose level changes

## Testing

The implementation has been tested with the following scenarios:

1. **Page Load**: Correct verbose level class applied on initial load
2. **Level Switching**: Class updates correctly when user changes dropdown
3. **Minimal Mode**: No "Tool panel not found" errors
4. **Normal Mode**: Tool outputs truncated appropriately
5. **Full Mode**: All content visible
6. **Error Handling**: Errors remain visible in all modes
7. **Persistence**: Preference saved to localStorage

## Status

**✅ COMPLETE AND PRODUCTION READY**

The CSS-based verbose levels are fully implemented, tested, and ready for use in Bassi V3.

## Future Enhancements (Optional)

- Click-to-expand individual tool blocks (override verbose setting)
- Keyboard shortcuts for quick verbose level switching
- Per-tool-type verbose preferences (e.g., always expand errors)
- Smooth transitions/animations when switching levels
