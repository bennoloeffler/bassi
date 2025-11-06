# Thinking Blocks - Claude's Reasoning Process

## Overview

**Status**: ✅ **Fully Implemented** (Frontend + Backend)
**Missing**: ⚠️ Extended thinking mode not enabled in Agent SDK

Claude's thinking process can be made visible in the web UI through **ThinkingBlock** objects that show the model's step-by-step reasoning before providing a final answer.

## Current Implementation

### ✅ Backend Support (Fully Implemented)

**File**: `bassi/core_v3/message_converter.py:111-115`

```python
elif isinstance(block, ThinkingBlock):
    return {
        "type": "thinking",
        "text": block.thinking,
    }
```

The message converter already handles `ThinkingBlock` objects from the Agent SDK and converts them to WebSocket events with type `"thinking"`.

### ✅ Frontend Support (Fully Implemented)

**File**: `bassi/static/app.js:1476-1508`

```javascript
handleThinking(msg) {
    // Create thinking block
    const thinkingBlock = document.createElement('div')
    thinkingBlock.className = 'thinking-block'
    thinkingBlock.innerHTML = `
        <div class="thinking-header">
            <span class="thinking-icon">💭</span>
            <span>Thinking...</span>
        </div>
        <div class="thinking-content">${this.escapeHtml(msg.text)}</div>
    `
    contentEl.appendChild(thinkingBlock)
    this.scrollToBottom()
}
```

The frontend renders thinking blocks with:
- Purple-themed visual design
- 💭 icon in header
- Italic text for the thinking content
- Proper spacing and borders

**File**: `bassi/static/style.css:677-704`

```css
.thinking-block {
    background: rgba(188, 140, 255, 0.05);
    border: 1px solid rgba(188, 140, 255, 0.2);
    border-radius: 8px;
    padding: var(--spacing-md);
    margin-bottom: var(--spacing-md);
}

.thinking-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    margin-bottom: var(--spacing-sm);
    font-weight: 600;
    color: var(--accent-purple);
    font-size: 0.875rem;
}

.thinking-content {
    color: var(--text-secondary);
    font-size: 0.875rem;
    line-height: 1.6;
    font-style: italic;
}
```

Thinking blocks are **always visible** - there's no `display: none` hiding them.

## ⚠️ What's Missing: Extended Thinking Mode

**File**: `bassi/core_v3/agent_session.py:102-111`

Currently, the Agent SDK client is configured WITHOUT extended thinking:

```python
self.sdk_options = ClaudeAgentOptions(
    allowed_tools=self.config.allowed_tools,
    system_prompt=self.config.system_prompt,
    permission_mode=self.config.permission_mode,
    mcp_servers=self.config.mcp_servers,
    cwd=self.config.cwd,
    can_use_tool=self.config.can_use_tool,
    hooks=self.config.hooks,
    setting_sources=self.config.setting_sources,
    # ❌ NO thinking configuration
)
```

## Implementation Plan

### Step 1: Enable Extended Thinking in SessionConfig

Add thinking configuration to `SessionConfig`:

```python
@dataclass
class SessionConfig:
    """Configuration for a Bassi agent session"""

    # Core settings
    allowed_tools: list[str] = field(
        default_factory=lambda: ["Bash", "ReadFile", "WriteFile"]
    )
    system_prompt: Optional[str] = None
    permission_mode: Optional[str] = None

    # ✅ Add thinking configuration
    enable_thinking: bool = False
    thinking_budget_tokens: int = 10000

    # ... rest of config
```

### Step 2: Pass Thinking Config to ClaudeAgentOptions

Update the Agent SDK options creation:

```python
# Build thinking config if enabled
thinking_config = None
if self.config.enable_thinking:
    thinking_config = {
        "type": "enabled",
        "budget_tokens": self.config.thinking_budget_tokens
    }

self.sdk_options = ClaudeAgentOptions(
    allowed_tools=self.config.allowed_tools,
    system_prompt=self.config.system_prompt,
    permission_mode=self.config.permission_mode,
    mcp_servers=self.config.mcp_servers,
    cwd=self.config.cwd,
    can_use_tool=self.config.can_use_tool,
    hooks=self.config.hooks,
    setting_sources=self.config.setting_sources,
    thinking=thinking_config,  # ✅ Enable extended thinking
)
```

### Step 3: Enable in Web Server

Update `web_server_v3.py` to enable thinking by default or via config:

```python
config = SessionConfig(
    allowed_tools=allowed_tools,
    system_prompt=system_prompt,
    permission_mode=permission_mode,
    mcp_servers=mcp_servers,
    cwd=Path.cwd(),
    can_use_tool=can_use_tool_handler,
    hooks=hooks,
    setting_sources=setting_sources,
    enable_thinking=True,  # ✅ Enable extended thinking
    thinking_budget_tokens=10000,  # Default 10K tokens for thinking
)
```

## Testing Strategy

1. **Manual Testing**:
   - Start web UI with thinking enabled
   - Ask a complex question (e.g., "Explain how the autocomplete system works step by step")
   - Verify thinking blocks appear in the UI with purple background
   - Verify thinking content shows Claude's reasoning process

2. **Unit Tests**:
   - Test `SessionConfig` with thinking enabled
   - Verify `ClaudeAgentOptions` receives correct thinking config
   - Test message converter handles ThinkingBlock correctly

3. **Integration Tests**:
   - Test full flow: user query → thinking blocks → final response
   - Verify thinking blocks render correctly in browser
   - Test with different thinking budget values

## User Experience

When extended thinking is enabled:

```
User: "Explain how bassi's autocomplete works"

💭 Thinking...
Let me analyze the autocomplete system. First, I'll look at the
command registry pattern in app.js. I see there are two types of
commands: built-in meta-commands and dynamic user commands loaded
from /api/capabilities...

[More reasoning steps...]

Bassi (Final Response):
The autocomplete system works through a two-tier architecture:
1. Built-in commands (/help, /agents, etc.) are statically defined
2. User commands are loaded from the capabilities API...
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_thinking` | bool | False | Enable extended thinking mode |
| `thinking_budget_tokens` | int | 10000 | Maximum tokens for thinking (recommended: 5K-20K) |

## References

- **Agent SDK Docs**: Extended thinking via `thinking={"type": "enabled", "budget_tokens": N}`
- **ThinkingBlock Type**: Agent SDK message type containing reasoning text
- **Streaming Support**: Thinking deltas via `thinking_delta` SSE events
- **Frontend Implementation**: `bassi/static/app.js:1476-1508`
- **Backend Implementation**: `bassi/core_v3/message_converter.py:111-115`

## Benefits

1. **Transparency**: Users see Claude's reasoning process
2. **Trust**: Understanding how the agent reaches conclusions
3. **Debugging**: Easier to identify where reasoning goes wrong
4. **Learning**: Educational value in seeing step-by-step thinking
5. **Complex Tasks**: Better handling of multi-step problems

## Trade-offs

| Aspect | Impact |
|--------|--------|
| **Token Usage** | +5K-20K tokens per response (cost increase) |
| **Latency** | +2-5 seconds for thinking phase |
| **Value** | High for complex reasoning, low for simple queries |
| **User Experience** | More transparent but potentially slower |

## Recommendation

✅ **Enable extended thinking** with conservative defaults:
- Default: `enable_thinking=True`
- Budget: `10,000 tokens` (good balance)
- Make configurable via environment variable: `BASSI_THINKING_ENABLED=true`
- Allow users to disable if speed is more important than transparency
