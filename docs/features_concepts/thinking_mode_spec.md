# Thinking Mode Toggle - Feature Specification

**Feature**: Extended Thinking Mode Toggle
**Priority**: MEDIUM ⭐⭐
**Phase**: 2
**Status**: Specification
**Version**: 1.0

---

## Overview

Enable Claude's extended thinking mode where the model shows its reasoning process before providing an answer. This gives users deeper insight into how Claude approaches problems.

**Claude API Support**: Models with `:thinking` suffix (e.g., `claude-sonnet-4-5-20250929:thinking`)

---

## What is Thinking Mode?

**Regular Mode**:
- Claude generates answer directly
- Reasoning is implicit
- Faster responses
- Lower token usage

**Thinking Mode**:
- Claude shows explicit reasoning in `<thinking>` blocks
- Then provides final answer
- 2-3x slower responses
- 2-3x more tokens (higher cost)
- Better reasoning quality for complex problems

**Example**:
```
User: What's 15% of 230?

[Thinking Mode Response]
<thinking>
To calculate 15% of 230:
- Convert 15% to decimal: 0.15
- Multiply: 230 × 0.15 = 34.5
</thinking>

15% of 230 is 34.5
```

---

## User Stories

### US-1: Enable Thinking for Complex Problems
**As a** power user
**I want to** enable thinking mode for complex questions
**So that** I can see Claude's reasoning process

**Acceptance Criteria**:
- Toggle button in UI header
- Thinking blocks visible in responses
- Clear indication thinking mode is active

### US-2: Understand Cost Implications
**As a** user
**I want to** be warned about increased costs
**So that** I can make informed decisions

**Acceptance Criteria**:
- Warning shown when enabling thinking
- Token usage clearly displayed
- Cost comparison visible

### US-3: Collapse/Expand Thinking
**As a** user
**I want to** collapse thinking blocks
**So that** I can focus on final answers

**Acceptance Criteria**:
- Thinking blocks collapsed by default
- Click to expand
- Distinct styling from regular content

---

## UI Design

### Toggle Button
```
┌─ Header ────────────────────────────────┐
│  🤖 bassi          [🧠 Thinking: OFF ▼] │
│                    ─────────────────────  │
│                    │ Enable Thinking    │ │
│                    │ ⚠️  2-3x more tokens│ │
│                    └───────────────────── │
└─────────────────────────────────────────┘
```

### Thinking Block Display
```
🤖 Assistant:

┌─ 🧠 Thinking ───────────────────── [+] ┐  ← Collapsed
└─────────────────────────────────────────┘

[After click]
┌─ 🧠 Thinking Process ──────────────── [-] ┐
│ To solve this problem, I need to:         │
│ 1. Break down the requirements            │
│ 2. Consider edge cases                    │
│ 3. Plan the implementation                │
│ ...                                        │
└────────────────────────────────────────────┘

Based on this analysis, here's my answer...
```

---

## Technical Design

### Backend Changes

**File**: `bassi/agent.py`

```python
class BassiAgent:
    def __init__(self, ..., thinking_mode: bool = False):
        self.thinking_mode = thinking_mode

        # Model selection
        if thinking_mode:
            model = "claude-sonnet-4-5-20250929:thinking"
        else:
            model = "claude-sonnet-4-5-20250929"

        self.options = ClaudeAgentOptions(
            model=model,
            # ... other options
        )
```

### Frontend Implementation

```javascript
class BassiWebClient {
    constructor() {
        this.thinkingMode = localStorage.getItem('bassi_thinking_mode') === 'true';
        this.initThinkingToggle();
    }

    toggleThinkingMode() {
        this.thinkingMode = !this.thinkingMode;
        localStorage.setItem('bassi_thinking_mode', this.thinkingMode);

        // Send config change to backend
        this.ws.send(JSON.stringify({
            type: 'config_change',
            thinking_mode: this.thinkingMode
        }));

        // Update UI
        this.updateThinkingToggle();
    }

    handleThinkingBlock(data) {
        const thinkingEl = document.createElement('div');
        thinkingEl.className = 'thinking-block collapsed';
        thinkingEl.innerHTML = `
            <div class="thinking-header" onclick="this.parentElement.classList.toggle('expanded')">
                <span class="icon">🧠</span>
                <span class="label">Thinking Process</span>
                <span class="toggle">[+]</span>
            </div>
            <div class="thinking-body">
                <pre>${data.content}</pre>
            </div>
        `;
        return thinkingEl;
    }
}
```

---

## WebSocket Protocol

**New Message Types**:

```json
// Config change
{
    "type": "config_change",
    "thinking_mode": true
}

// Thinking block content
{
    "type": "thinking_block",
    "content": "Reasoning text..."
}
```

---

## Cost Warning

Show modal on first enable:
```
┌─ Enable Thinking Mode? ──────────────┐
│                                       │
│ ⚠️  Thinking mode will:               │
│   • Show Claude's reasoning           │
│   • Use 2-3x more tokens              │
│   • Cost 2-3x more per message        │
│   • Take longer to respond            │
│                                       │
│ Best for complex problems that        │
│ benefit from detailed reasoning.      │
│                                       │
│ [Cancel]              [Enable] [✓]   │
│                        Don't show again│
└───────────────────────────────────────┘
```

---

## Success Criteria

- [ ] Toggle in UI header
- [ ] Thinking blocks render correctly
- [ ] Cost warning shown
- [ ] Preference persists
- [ ] Performance acceptable (2-3x slower is expected)

---

**Estimated Time**: 2-3 days
**Dependencies**: Claude API thinking mode support
