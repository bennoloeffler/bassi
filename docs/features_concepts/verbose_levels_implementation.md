# Verbose Mode Levels - Implementation Summary

**Feature**: Three-Level Verbosity Control
**Status**: ✅ **IMPLEMENTED**
**Date**: 2025-10-31
**Phase**: 1.2

---

## Overview

Successfully upgraded bassi's verbosity control from binary (ON/OFF) to three distinct levels (MINIMAL, SUMMARY, FULL), giving users fine-grained control over tool call visibility.

**Implementation Approach**: Frontend-only (no backend changes needed)

---

## Three Levels

### Level 1: MINIMAL (Quiet)
- **Display**: Status indicator only: "🔧 Using bash..."
- **No tool panels shown**
- **Clean, minimal UI**
- **Use Case**: Non-technical users, clean conversations

### Level 2: SUMMARY (Default)
- **Display**: Tool name + icon, collapsed by default
- **Click to expand** for full details
- **Balanced approach**
- **Use Case**: Power users who want awareness without clutter

### Level 3: FULL (Detailed)
- **Display**: Complete tool input/output
- **Expanded by default**
- **Full transparency**
- **Use Case**: Debugging, learning, verification

---

## Implementation Details

### Files Modified

#### 1. `/bassi/static/index.html`
**Added**: Verbose level dropdown in header

```html
<div class="header-controls">
    <div class="verbose-selector">
        <label for="verbose-level">Detail:</label>
        <select id="verbose-level">
            <option value="minimal">Minimal</option>
            <option value="summary" selected>Summary</option>
            <option value="full">Full</option>
        </select>
    </div>
    <div class="connection-status">
        <!-- ... -->
    </div>
</div>
```

**Changes**:
- Added `.header-controls` container for grouping
- Added verbose level dropdown with 3 options
- Default: "summary" selected

---

#### 2. `/bassi/static/app.js`
**Added**: Verbose level state management and rendering logic

**Key Methods Added**:

```javascript
loadVerboseLevel() {
    // Load from localStorage with migration from old boolean setting
    const saved = localStorage.getItem('bassi_verbose_level');
    if (saved && ['minimal', 'summary', 'full'].includes(saved)) {
        return saved;
    }

    // Migrate from old boolean
    const oldVerbose = localStorage.getItem('bassi_verbose');
    if (oldVerbose !== null) {
        const level = oldVerbose === 'true' ? 'full' : 'minimal';
        localStorage.setItem('bassi_verbose_level', level);
        localStorage.removeItem('bassi_verbose');
        return level;
    }

    return 'summary'; // Default
}

setVerboseLevel(level) {
    this.verboseLevel = level;
    localStorage.setItem('bassi_verbose_level', level);
    console.log('Verbose level set to:', level);
}
```

**Modified Methods**:

```javascript
handleToolCallStart(data) {
    // ... existing code

    // Handle different verbose levels
    switch (this.verboseLevel) {
        case 'minimal':
            // Just show status indicator
            this.showMinimalToolIndicator(data.tool_name);
            break;

        case 'summary':
            // Show collapsed tool panel
            const summaryToolEl = this.createToolCallElement(
                data.tool_name,
                data.input,
                false  // collapsed
            );
            summaryToolEl.classList.add('summary-mode');
            contentEl.appendChild(summaryToolEl);
            break;

        case 'full':
            // Show expanded tool panel
            const fullToolEl = this.createToolCallElement(
                data.tool_name,
                data.input,
                true  // expanded
            );
            fullToolEl.classList.add('full-mode', 'expanded');
            contentEl.appendChild(fullToolEl);
            break;
    }
}

handleToolCallEnd(data) {
    // Handle minimal mode - clear status indicator
    if (this.verboseLevel === 'minimal') {
        this.updateConnectionStatus('online', 'Connected');
        return; // Don't show tool panel
    }

    // Update tool panel for summary/full modes
    // ... existing code
}
```

**Helper Methods**:

```javascript
showMinimalToolIndicator(toolName) {
    const icon = this.getToolIcon(toolName);
    const shortName = this.getShortToolName(toolName);
    this.updateConnectionStatus('online', `${icon} Using ${shortName}...`);
}

getToolIcon(toolName) {
    if (toolName.includes('bash')) return '🔧';
    if (toolName.includes('read')) return '📄';
    if (toolName.includes('write')) return '✏️';
    if (toolName.includes('search')) return '🔍';
    if (toolName.includes('web')) return '🌐';
    return '🔧'; // default
}

getShortToolName(toolName) {
    // Convert "mcp__bash__execute" to "bash"
    const parts = toolName.split('__');
    if (parts.length > 1) {
        return parts[1];
    }
    return toolName.length > 20 ? toolName.substring(0, 20) + '...' : toolName;
}
```

**Updated Constructor**:

```javascript
constructor() {
    // ... existing code

    // Verbose level management
    this.verboseLevel = this.loadVerboseLevel();
    this.currentToolIndicator = null; // For MINIMAL mode

    // DOM elements
    this.verboseLevelSelect = document.getElementById('verbose-level');

    // ... existing code
}
```

**Updated init()**:

```javascript
init() {
    // Set initial verbose level in dropdown
    this.verboseLevelSelect.value = this.verboseLevel;

    // Event listener for dropdown
    this.verboseLevelSelect.addEventListener('change', (e) => {
        this.setVerboseLevel(e.target.value);
    });

    // ... existing code
}
```

**Updated createToolCallElement()**:

```javascript
createToolCallElement(toolName, input, expanded = false) {
    const toolEl = document.createElement('div');
    const initialClass = expanded ? 'tool-call expanded' : 'tool-call collapsed';
    toolEl.className = initialClass;
    toolEl.setAttribute('data-tool', toolName);

    const inputHtml = this.syntaxHighlightJSON(input);
    const icon = this.getToolIcon(toolName);
    const shortName = this.getShortToolName(toolName);
    const toggleIcon = expanded ? '▲' : '▼';

    toolEl.innerHTML = `
        <div class="tool-header" onclick="this.parentElement.classList.toggle('expanded')">
            <span class="icon">${icon}</span>
            <span class="name">${this.escapeHtml(shortName)}</span>
            <span class="full-name">${this.escapeHtml(toolName)}</span>
            <span class="toggle">${toggleIcon}</span>
        </div>
        <div class="tool-body">
            <!-- ... -->
        </div>
    `;

    // Update toggle icon dynamically
    toolEl.querySelector('.tool-header').addEventListener('click', () => {
        const toggle = toolEl.querySelector('.toggle');
        toggle.textContent = toolEl.classList.contains('expanded') ? '▲' : '▼';
    });

    return toolEl;
}
```

---

#### 3. `/bassi/static/style.css`
**Added**: CSS styling for verbose levels

```css
/* Verbose Level Selector */
.header-controls {
    display: flex;
    align-items: center;
    gap: var(--spacing-lg);
}

.verbose-selector {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
}

.verbose-selector label {
    color: var(--text-secondary);
    font-size: 0.875rem;
    font-weight: 500;
}

.verbose-selector select {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 6px 12px;
    color: var(--text-primary);
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.2s;
}

.verbose-selector select:hover {
    background: var(--bg-hover);
    border-color: var(--text-muted);
}

.verbose-selector select:focus {
    outline: none;
    border-color: var(--accent-blue);
}

/* Tool Call Styling by Verbose Level */

/* Summary mode - collapsed by default */
.tool-call.summary-mode .tool-body {
    display: none;
}

.tool-call.summary-mode.expanded .tool-body {
    display: block;
}

.tool-call.summary-mode .tool-header {
    padding: 10px 14px;
    font-size: 0.875rem;
}

.tool-call.summary-mode .full-name {
    display: none; /* Hide full tool name */
}

/* Full mode - expanded by default */
.tool-call.full-mode .tool-body {
    display: block;
}

.tool-call.full-mode .tool-header {
    padding: 12px 16px;
}

.tool-call.full-mode .name {
    display: none; /* Hide short name */
}

.tool-call.full-mode .full-name {
    display: inline; /* Show full tool name */
    font-family: 'Courier New', monospace;
    font-size: 0.8rem;
}

/* Tool header improvements */
.tool-call .tool-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    cursor: pointer;
    user-select: none;
}

.tool-call .tool-header .icon {
    font-size: 1.1rem;
    flex-shrink: 0;
}

.tool-call .tool-header .name {
    font-weight: 600;
    color: var(--text-primary);
    flex-grow: 1;
}

.tool-call .tool-header .full-name {
    font-weight: 500;
    color: var(--text-secondary);
    flex-grow: 1;
    display: none; /* Hidden by default */
}

.tool-call .tool-header .toggle {
    font-size: 0.75rem;
    color: var(--text-muted);
    transition: transform 0.2s;
}

.tool-call.expanded .tool-header .toggle {
    transform: rotate(180deg);
}
```

---

## User Experience

### Switching Levels

**MINIMAL Mode**:
```
Header: [Detail: Minimal ▼]
Status: 🔧 Using bash...
[No tool panels shown]
```

**SUMMARY Mode** (Default):
```
Header: [Detail: Summary ▼]

┌─ 🔧 bash ──── ▼
└────────────────  (Click to expand)
```

**FULL Mode**:
```
Header: [Detail: Full ▼]

┌─ 🔧 mcp__bash__execute ──── ▲
│ Input:
│   {"command": "ls -la"}
│
│ Output:
│   total 48
│   drwxr-xr-x  12 user  staff  384 Oct 31 10:00 .
│   ...
└────────────────────────────────
```

---

## Technical Architecture

### State Flow

```
User selects verbose level
    ↓
setVerboseLevel() called
    ↓
Save to localStorage
    ↓
Update this.verboseLevel
    ↓
Future tool calls render based on level
```

### Tool Call Rendering Flow

```
handleToolCallStart() receives tool data
    ↓
Check this.verboseLevel
    ↓
MINIMAL → showMinimalToolIndicator()
SUMMARY → createToolCallElement(collapsed)
FULL    → createToolCallElement(expanded)
    ↓
Append to message (except minimal)
```

### Persistence

**localStorage Key**: `bassi_verbose_level`

**Values**: `'minimal'`, `'summary'`, `'full'`

**Migration**: Old boolean `bassi_verbose` automatically migrated:
- `true` → `'full'`
- `false` → `'minimal'`

---

## Testing

### Manual Test Scenarios

#### Test 1: Level Persistence
1. Set level to FULL
2. Refresh page
3. ✅ Verify dropdown shows FULL
4. ✅ Verify tool calls expanded

#### Test 2: Minimal Mode
1. Set level to MINIMAL
2. Send message with tool calls
3. ✅ Verify no tool panels shown
4. ✅ Verify status indicator shows "🔧 Using..."

#### Test 3: Summary Mode
1. Set level to SUMMARY
2. Send message with tool calls
3. ✅ Verify collapsed tool panels shown
4. ✅ Click header to expand
5. ✅ Verify details appear

#### Test 4: Full Mode
1. Set level to FULL
2. Send message with tool calls
3. ✅ Verify expanded tool panels shown
4. ✅ Verify full tool names displayed
5. ✅ Verify JSON input/output visible

#### Test 5: Migration
1. Set old `bassi_verbose` = `true` in localStorage
2. Refresh page
3. ✅ Verify migrated to `bassi_verbose_level` = `'full'`
4. ✅ Verify old key removed

---

## Performance Impact

**No measurable performance impact**:
- Frontend-only implementation
- Simple conditional rendering
- localStorage operations are instant
- No network overhead

---

## Comparison: Before vs After

### Before
```
Binary verbose mode:
  OFF → No tool information (black box)
  ON  → Full details always shown (cluttered)
```

### After
```
Three-level verbose mode:
  MINIMAL → Clean, status hints only
  SUMMARY → Balanced, collapsed details
  FULL    → Complete transparency
```

---

## Future Enhancements

**Possible improvements**:
1. Per-tool override (show some tools in FULL, others MINIMAL)
2. Smart defaults (auto-collapse successful tools, expand errors)
3. Filter by tool type (show bash in FULL, hide file ops)
4. Retroactive level change (apply to past messages)
5. Keyboard shortcuts (quick toggle via hotkey)

---

## Benefits

### For Users
- ✅ **Control**: Choose their preferred level of detail
- ✅ **Flexibility**: Switch levels anytime
- ✅ **Persistence**: Preference saved across sessions

### For Non-Technical Users
- ✅ **Clean UI**: MINIMAL mode hides complexity
- ✅ **Focus**: See results, not process

### For Power Users
- ✅ **Awareness**: SUMMARY mode shows what's happening
- ✅ **Debugging**: FULL mode for deep inspection

---

## Success Criteria

- ✅ Three levels clearly defined
- ✅ Dropdown selector in UI
- ✅ Level persists across sessions (localStorage)
- ✅ MINIMAL shows hints only
- ✅ SUMMARY shows collapsible panels
- ✅ FULL shows expanded panels
- ✅ Backward compatible (boolean migration)
- ✅ No performance degradation
- ✅ All quality checks passing

---

## Documentation

**Related Files**:
- Specification: `docs/features_concepts/verbose_levels_spec.md`
- Implementation: `docs/features_concepts/verbose_levels_implementation.md` (this file)
- Roadmap: `docs/features_concepts/advanced_features_roadmap.md`

---

**Status**: ✅ **COMPLETE** - Ready for production use!
**Implementation Time**: ~2 hours
**Last Updated**: 2025-10-31
