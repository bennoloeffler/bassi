# Verbose Mode Levels - Feature Specification

**Feature**: Three-Level Verbosity Control
**Priority**: HIGH ⭐⭐⭐
**Phase**: 1.2
**Status**: Specification
**Version**: 1.0

---

## Overview

Upgrade verbosity from binary (ON/OFF) to three distinct levels, giving users fine-grained control over tool call visibility. Improves readability by reducing noise while maintaining transparency.

**Current State**: CLI and Web UI have boolean verbose mode
**Target State**: Three levels - MINIMAL, SUMMARY, FULL

---

## Problem Statement

Current verbose mode issues:
- **OFF**: Users have no idea what agent is doing (black box)
- **ON**: Too much detail, clutters conversation
- **No middle ground**: Can't see tool usage without full dumps

Users want to see that agent is working without overwhelming detail.

---

## User Stories

### US-1: Quiet Mode for Clean Conversations
**As a** user who values clean UI
**I want** minimal tool visibility (just hints)
**So that** conversations focus on results, not process

**Acceptance Criteria**:
- Only shows "🔧 Using tool..." indicators
- No expanded tool details
- Results appear directly in response

---

### US-2: Summary Mode for Context
**As a** power user
**I want** to see what tools are used with brief summaries
**So that** I understand agent's approach without noise

**Acceptance Criteria**:
- Tool name + brief description visible
- Details collapsed by default
- Can expand to see full input/output
- Balance between awareness and readability

---

### US-3: Full Mode for Debugging
**As a** developer or power user
**I want** complete tool visibility
**So that** I can debug, learn, and verify agent actions

**Acceptance Criteria**:
- All tool input/output visible
- Expanded by default
- JSON syntax highlighted
- Timestamps and execution time

---

### US-4: Persistent Preference
**As a** user
**I want** my verbose level remembered across sessions
**So that** I don't have to reconfigure every time

**Acceptance Criteria**:
- Level saved to localStorage
- Loads on page refresh
- Syncs across tabs (same browser)

---

## Three Levels Defined

### Level 1: MINIMAL (Quiet)
**Philosophy**: "I trust the agent, just show me results"

**Display**:
- Status indicator only: "🔧 Using bash..."
- No tool panels
- No input/output details
- Minimal visual footprint

**Use Case**:
- Clean conversations
- Non-technical users
- Focus on final answer

**Example**:
```
🤖 Assistant:
Let me search for Python files...

[tiny indicator: 🔧]

Found 23 Python files in your project:
- src/main.py
- src/utils.py
...
```

---

### Level 2: SUMMARY (Normal/Default)
**Philosophy**: "Show me what's happening, but keep it clean"

**Display**:
- Tool name + icon
- Brief summary of action
- Collapsed by default (click to expand)
- Execution time
- Success/failure indicator

**Use Case**:
- Power users
- Learning mode
- Verification without clutter

**Example**:
```
🤖 Assistant:
Let me search for Python files...

┌─ 🔧 bash ─────────────────── 0.3s ─┐
│ Command: find . -name "*.py"        │ [click to expand]
└────────────────────────────────────┘

Found 23 Python files...
```

---

### Level 3: FULL (Detailed)
**Philosophy**: "Show me everything - I want full transparency"

**Display**:
- Complete tool input (JSON formatted)
- Complete tool output
- Expanded by default
- Syntax highlighting
- Execution metrics

**Use Case**:
- Debugging
- Learning agent behavior
- Verifying security
- Development

**Example**:
```
🤖 Assistant:
Let me search for Python files...

┌─ 🔧 mcp__bash__execute ──── 0.3s ─┐
│ Input:                              │
│ {                                   │
│   "command": "find . -name '*.py'", │
│   "timeout": 30000                  │
│ }                                   │
│                                     │
│ Output:                             │
│ ./src/main.py                       │
│ ./src/utils.py                      │
│ ... (23 files total)                │
└─────────────────────────────────────┘

Found 23 Python files...
```

---

## UI Design

### Level Selector

**Option A: Dropdown** (RECOMMENDED)
```
┌─ Header ────────────────────────────┐
│  🤖 bassi         Verbosity: [▼]    │
│                   ┌─────────────┐   │
│                   │ ○ Minimal   │   │
│                   │ ● Summary   │   │ ← Selected
│                   │ ○ Full      │   │
│                   └─────────────┘   │
└─────────────────────────────────────┘
```

**Option B: Toggle Button Group**
```
┌─ Header ────────────────────────────┐
│  🤖 bassi    [Min][Sum][Full]       │
│                    ^^^^  Selected   │
└─────────────────────────────────────┘
```

**Decision**: Use Option A (dropdown) for clarity and space efficiency

---

### Tool Display by Level

#### MINIMAL Level
```
[During execution]
🔧 Using bash...

[No tool panel shown]
[Results appear directly in text]
```

#### SUMMARY Level
```
┌─ 🔧 bash ─────────────────────── 0.3s ─┐  ← Collapsed
│ Command: find files                      │
└──────────────────────────────────── [+] ┘
                                        ↑ Click to expand

[After click]
┌─ 🔧 bash ─────────────────────── 0.3s ─┐  ← Expanded
│ Input:                                   │
│   find . -name "*.py"                    │
│                                          │
│ Output:                                  │
│   ./src/main.py                          │
│   ...                                    │
└──────────────────────────────────── [-] ┘
```

#### FULL Level
```
┌─ 🔧 mcp__bash__execute ────────── 0.3s ─┐  ← Already expanded
│ Input:                                    │
│ {                                         │
│   "command": "find . -name '*.py'",       │
│   "timeout": 30000                        │
│ }                                         │
│                                           │
│ Output:                                   │
│ ./src/main.py                             │
│ ./src/utils.py                            │
│ ...                                       │
└───────────────────────────────────────── [-] ┘
```

---

## Technical Design

### Frontend State Management

**localStorage Key**: `bassi_verbose_level`

**Values**:
```javascript
enum VerboseLevel {
    MINIMAL = 'minimal',
    SUMMARY = 'summary',
    FULL = 'full'
}
```

**Default**: `SUMMARY` (balanced)

### Rendering Logic

```javascript
class BassiWebClient {
    constructor() {
        // Load preference
        this.verboseLevel = localStorage.getItem('bassi_verbose_level') || 'summary';
    }

    setVerboseLevel(level) {
        this.verboseLevel = level;
        localStorage.setItem('bassi_verbose_level', level);

        // Update existing tool calls if any
        this.updateToolCallsDisplay();
    }

    handleToolCallStart(data) {
        switch (this.verboseLevel) {
            case 'minimal':
                this.showMinimalToolIndicator(data.tool_name);
                break;
            case 'summary':
                this.showSummaryToolPanel(data.tool_name, data.input, false); // collapsed
                break;
            case 'full':
                this.showFullToolPanel(data.tool_name, data.input, true); // expanded
                break;
        }
    }

    showMinimalToolIndicator(toolName) {
        // Just update status text, no panel
        const icon = this.getToolIcon(toolName);
        this.updateConnectionStatus('online', `${icon} Using ${toolName}...`);
    }

    showSummaryToolPanel(toolName, input, expanded = false) {
        const panel = this.createToolPanel(toolName, input, expanded);
        panel.classList.add('summary-mode');
        // Add to message
    }

    showFullToolPanel(toolName, input, expanded = true) {
        const panel = this.createToolPanel(toolName, input, expanded);
        panel.classList.add('full-mode');
        // Add to message with full details
    }
}
```

---

## CSS Styling

```css
/* Verbose Level Dropdown */
.verbose-selector {
    position: relative;
    display: inline-block;
}

.verbose-selector select {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 6px 12px;
    color: var(--text-primary);
    font-size: 0.875rem;
    cursor: pointer;
}

.verbose-selector select:hover {
    background: var(--bg-hover);
}

/* Tool Panels by Level */
.tool-call.minimal-mode {
    display: none; /* No panel in minimal mode */
}

.tool-call.summary-mode .tool-header {
    padding: 8px 12px;
    font-size: 0.875rem;
}

.tool-call.summary-mode .tool-body {
    display: none; /* Collapsed by default */
}

.tool-call.summary-mode.expanded .tool-body {
    display: block;
}

.tool-call.full-mode .tool-body {
    display: block; /* Expanded by default */
}

.tool-call.full-mode .tool-input,
.tool-call.full-mode .tool-output {
    /* Full JSON display */
}

/* Minimal Mode Status Indicator */
.status-bar.minimal-mode {
    font-size: 0.75rem;
    color: var(--text-secondary);
    padding: 4px 8px;
}
```

---

## Backend Changes

**OPTION A: Frontend-Only** (RECOMMENDED)
- All filtering done in frontend
- Backend always sends full event data
- Simple, no backend changes needed

**OPTION B: Backend-Aware**
- Client sends verbose level in config
- Backend filters events before sending
- Reduces bandwidth, more complex

**Decision**: Use Option A for simplicity. Backend already sends events, frontend decides what to display.

---

## Migration Strategy

### From Current Boolean Verbose

**CLI** (`bassi/agent.py`):
```python
# Current
self.verbose = True  # or False

# After migration
self.verbose_level = VerboseLevel.SUMMARY  # enum

# Backward compatibility
@property
def verbose(self):
    return self.verbose_level != VerboseLevel.MINIMAL
```

**Web UI**:
```javascript
// Load old boolean preference
const oldVerbose = localStorage.getItem('bassi_verbose');
if (oldVerbose !== null) {
    // Migrate
    const level = oldVerbose === 'true' ? 'full' : 'minimal';
    localStorage.setItem('bassi_verbose_level', level);
    localStorage.removeItem('bassi_verbose');
}
```

---

## Testing Plan

### Unit Tests

```javascript
describe('Verbose Levels', () => {
    test('Loads saved preference', () => {
        localStorage.setItem('bassi_verbose_level', 'full');
        const client = new BassiWebClient();
        expect(client.verboseLevel).toBe('full');
    });

    test('MINIMAL shows no tool panels', () => {
        client.setVerboseLevel('minimal');
        client.handleToolCallStart({tool_name: 'bash', input: {}});
        expect(document.querySelectorAll('.tool-call')).toHaveLength(0);
    });

    test('SUMMARY shows collapsed panels', () => {
        client.setVerboseLevel('summary');
        client.handleToolCallStart({tool_name: 'bash', input: {}});
        const panel = document.querySelector('.tool-call');
        expect(panel.classList.contains('expanded')).toBe(false);
    });

    test('FULL shows expanded panels', () => {
        client.setVerboseLevel('full');
        client.handleToolCallStart({tool_name: 'bash', input: {}});
        const panel = document.querySelector('.tool-call');
        expect(panel.classList.contains('expanded')).toBe(true);
    });
});
```

### Manual Test Cases

1. **Level Switching**:
   - Set to MINIMAL, send message with tools
   - Switch to SUMMARY, verify display changes
   - Switch to FULL, verify full details shown

2. **Persistence**:
   - Set level to FULL
   - Refresh page
   - Verify still FULL

3. **Retroactive**:
   - Have conversation with tools at SUMMARY
   - Switch to FULL
   - Verify existing tool calls update (or don't - decide)

4. **Performance**:
   - Many tool calls (10+)
   - All three levels
   - Verify no lag

---

## Success Criteria

- [ ] Three levels clearly defined
- [ ] Dropdown selector in UI
- [ ] Level persists across sessions
- [ ] MINIMAL shows hints only
- [ ] SUMMARY shows collapsible panels
- [ ] FULL shows expanded panels
- [ ] Backward compatible with boolean verbose
- [ ] No performance degradation
- [ ] All tests passing

---

## Future Enhancements

- **Per-tool override**: Show some tools in FULL, others MINIMAL
- **Smart defaults**: Auto-collapse successful tools, expand errors
- **Filter by tool type**: Show bash in FULL, hide file operations
- **Retroactive level change**: Apply to past messages
- **Keyboard shortcuts**: Quick toggle via hotkey

---

**Status**: Ready for implementation
**Estimated Time**: 1-2 days
**Dependencies**: None (frontend-only)
**Next Steps**: Create implementation plan with detailed code examples
