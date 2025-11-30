# Model Switching

## Overview

Bassi supports dynamic model switching to optimize cost and performance. Users can choose between three model tiers:

| Level | Model | Description | Use Case |
|-------|-------|-------------|----------|
| 1 | Haiku 4.5 | Fastest, cheapest | Quick answers, simple tasks |
| 2 | Sonnet 4.5 | Balanced | Everyday tasks |
| 3 | Opus 4.5 | Most capable | Complex work |

## Behavior

### Default: Start with Haiku (Level 1)

All conversations start with Haiku by default. This optimizes for cost while still providing good results for most queries.

### Auto-Escalation

When the agent encounters **3 consecutive errors** (tool failures, invalid responses, etc.), it automatically escalates to the next model level:

1. **Haiku** fails 3x → escalate to **Sonnet**
2. **Sonnet** fails 3x → escalate to **Opus**
3. **Opus** fails → stay at Opus (no higher model available)

When auto-escalation occurs, the user is notified via a system message:
```
[System] Model upgraded to Sonnet 4.5 after 3 consecutive failures
```

### Manual Override

Users can manually select a model at any time through:
1. **Model icon** in the settings bar (left side)
2. **Settings modal** → Model selection dropdown

## UI Components

### Settings Bar Model Icon

Located at the left side of the settings bar (before thinking/permissions icons):

```
[AI] [💡] [🔒] [⚙️] Connected
```

- **Icon**: AI chip/brain icon with level indicator
- **Colors**:
  - Haiku: Green (fast/efficient)
  - Sonnet: Blue (balanced)
  - Opus: Purple (powerful)
- **Tooltip**: Shows current model name
- **Click**: Opens settings modal to model section

### Settings Modal

New section in settings modal:

```
─────────────────────────────────────
Model Selection
Choose the AI model for your conversations

○ Haiku 4.5    - Fastest for quick answers
● Sonnet 4.5   - Best for everyday tasks
○ Opus 4.5    - Most capable for complex work

Auto-escalate on failures: [✓]
─────────────────────────────────────
```

## Implementation

### Model IDs

```python
MODEL_LEVELS = {
    1: {
        "id": "claude-haiku-4-5-20250929",
        "name": "Haiku 4.5",
        "description": "Fastest for quick answers",
        "icon_color": "green",
    },
    2: {
        "id": "claude-sonnet-4-5-20250929",
        "name": "Sonnet 4.5",
        "description": "Best for everyday tasks",
        "icon_color": "blue",
    },
    3: {
        "id": "claude-opus-4-5-20250929",
        "name": "Opus 4.5",
        "description": "Most capable for complex work",
        "icon_color": "purple",
    },
}

DEFAULT_MODEL_LEVEL = 1  # Start with Haiku
MAX_MODEL_LEVEL = 3
FAILURES_BEFORE_ESCALATION = 3
```

### State Management

Model settings are stored in two places:

1. **User preference** (`~/.bassi/config.json`):
   - `default_model_level`: User's preferred starting level (1-3)
   - `auto_escalate`: Whether to auto-escalate on failures (default: true)

2. **Session state** (BrowserSession):
   - `current_model_level`: Active model for this session
   - `consecutive_failures`: Counter for auto-escalation

### API Endpoints

```
GET  /api/settings/model         → Current model settings
POST /api/settings/model         → Update model settings
```

Request/Response:
```json
{
  "model_level": 1,
  "auto_escalate": true
}
```

### WebSocket Events

**Model change notification** (server → client):
```json
{
  "type": "model_changed",
  "model_level": 2,
  "model_name": "Sonnet 4.5",
  "reason": "auto_escalation" | "user_selection"
}
```

**Model change request** (client → server):
```json
{
  "type": "model_change",
  "model_level": 2
}
```

### Browser Session Changes

The `BrowserSession` tracks:
- `current_model_level: int` - Active model (1-3)
- `consecutive_failures: int` - For auto-escalation
- `auto_escalate: bool` - Whether to auto-escalate

On error detection:
```python
async def on_agent_error(self, error_msg: str):
    self.consecutive_failures += 1

    if self.auto_escalate and self.consecutive_failures >= 3:
        if self.current_model_level < MAX_MODEL_LEVEL:
            await self.escalate_model()
            self.consecutive_failures = 0

async def escalate_model(self):
    self.current_model_level += 1
    # Reconnect agent with new model
    await self._switch_agent_model()
    # Notify user
    await self._send_model_notification("auto_escalation")
```

On successful response:
```python
async def on_agent_success(self):
    self.consecutive_failures = 0  # Reset counter
```

### Agent Session Changes

`SessionConfig` already supports `model_id`. The pool agent factory will:
1. Read `model_level` from browser session state
2. Map to `model_id` using `MODEL_LEVELS`
3. Create agent with correct model

For model switches during session:
- Agent in pool keeps SDK connection
- Model switch requires creating new agent OR updating existing agent's model

## Testing

Test scenarios:
1. **Default model**: New session starts with Haiku
2. **Manual switch**: User selects Sonnet → model changes immediately
3. **Auto-escalation**: 3 errors → escalates to next level
4. **Max level**: At Opus, errors don't escalate further
5. **Success reset**: Successful response resets failure counter
6. **Persistence**: User preference saved to config.json
7. **UI sync**: Model icon reflects current model color

## Files Changed

- `bassi/core_v3/services/config_service.py` - Model preference storage
- `bassi/core_v3/routes/settings.py` - API endpoints
- `bassi/core_v3/models/browser_session.py` - Model tracking
- `bassi/core_v3/websocket/browser_session_manager.py` - Model change handling
- `bassi/core_v3/agent_session.py` - Model configuration
- `bassi/shared/agent_protocol.py` - Model ID resolution
- `bassi/static/index.html` - Model icon + settings section
- `bassi/static/style.css` - Model icon styles
- `bassi/static/app.js` - Model switching logic
