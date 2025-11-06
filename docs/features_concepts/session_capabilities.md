# Session Capabilities - REST API

## Overview

Session capabilities provide metadata about what the Bassi agent can do in
a given session. This includes available tools, MCP servers, slash commands,
skills, and agents.

Capabilities are exposed via a dedicated **REST API endpoint** (`/api/capabilities`)
rather than being sent over WebSocket. This provides semantic clarity and
separation of concerns.

## Problem Evolution

**V1 (Reactive Loading via WebSocket)**:
- User connects → Agent SDK eventually sends init message → Capabilities stored
- Problem: If user types `/help` before init arrives → Error message

**V2 (Proactive Empty Query)**:
- User connects → Server sends empty query `session.query("")` → SDK sends init
- Problem: "Ghost message" confusing, semantically unclear "blind passenger"

**V3 (REST API - Current)**:
- User types `/help` → Frontend fetches `/api/capabilities` → Displays help
- ✅ Clean separation: REST for metadata, WebSocket for conversations
- ✅ Lazy loading: Only fetch when needed
- ✅ Cacheable by browser

## Architecture Flow

```
┌─────────────────────┐
│  User types /help   │
└──────────┬──────────┘
           │
           ▼ GET /api/capabilities
┌─────────────────────┐
│  FastAPI Server     │
│  (web_server_v3.py) │
└──────────┬──────────┘
           │
           ▼ Create temp session, call get_server_info()
┌─────────────────────┐
│  Agent SDK Client   │
└──────────┬──────────┘
           │
           ▼ Return server_info (tools, mcp_servers, etc.)
┌─────────────────────┐
│  FastAPI Response   │ JSON Response
│  {tools: [...],     │
│   mcp_servers: [...]}
└──────────┬──────────┘
           │
           ▼ fetch() resolves
┌─────────────────────┐
│  Web Frontend       │ Displays help with capabilities
│  (app.js)           │ Caches in sessionCapabilities
└─────────────────────┘
```

## API Response Structure

### REST Endpoint: GET /api/capabilities

```json
{
  "session_id": "temp-uuid",
  "cwd": "/path/to/project",
  "model": "claude-sonnet-4-5-20250929",

  "tools": ["Task", "Bash", "Read", "Write", "Edit", ...],

  "mcp_servers": [
    {"name": "bash", "status": "connected"},
    {"name": "playwright", "status": "connected"},
    {"name": "postgresql", "status": "connected"}
  ],

  "slash_commands": [
    {
      "name": "help",
      "description": "Show available capabilities",
      "argumentHint": ""
    },
    {
      "name": "crm",
      "description": "CRM database operations",
      "argumentHint": "[query]"
    }
  ],

  "skills": ["xlsx", "pdf", "docx", "pptx", "mcp-builder"],

  "agents": [
    "general-purpose",
    "Explore",
    "debugger",
    "tester",
    "reviewer"
  ],

  "permissionMode": "bypassPermissions",
  "apiKeySource": "none",
  "claude_code_version": "2.0.31"
}
```

## Implementation

### Backend: REST Endpoint (web_server_v3.py)

```python
# In _setup_routes()
@self.app.get("/api/capabilities")
async def get_capabilities():
    """
    Get session capabilities from Agent SDK.

    Returns available tools, MCP servers, slash commands,
    skills, and agents for the current session.
    """
    # Create temporary session for introspection
    temp_service = InteractiveQuestionService()
    temp_session = self.session_factory(temp_service)

    try:
        await temp_session.connect()
        server_info = await temp_session.get_server_info()
        return JSONResponse(server_info)
    finally:
        await temp_session.disconnect()
```

**Key Points**:
- Separate REST endpoint (not WebSocket)
- Creates temporary session just for introspection
- Properly cleans up (disconnect in finally block)
- Returns JSON directly

### Frontend: Lazy Loading (app.js)

```javascript
class BassiWebClient {
    constructor() {
        this.sessionCapabilities = null  // Cache
    }

    async showDynamicHelp() {
        // Lazy load capabilities on first /help
        if (!this.sessionCapabilities) {
            await this.loadCapabilities()
        }

        // Render help UI with capabilities data
        this.renderHelpWithCapabilities()
    }

    async loadCapabilities() {
        try {
            const response = await fetch('/api/capabilities')
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`)
            }

            this.sessionCapabilities = await response.json()

            // Make globally accessible for debugging
            window.bassiCapabilities = this.sessionCapabilities

            console.log('✅ Capabilities loaded:', {
                tools: this.sessionCapabilities.tools?.length,
                mcp_servers: this.sessionCapabilities.mcp_servers?.length,
                slash_commands: this.sessionCapabilities.slash_commands?.length
            })
        } catch (error) {
            console.error('Failed to load capabilities:', error)
            this.showError('Could not load capabilities')
        }
    }
}
```

**Key Points**:
- Lazy loading: Only fetch when `/help` is typed
- Cached in memory after first fetch
- Error handling with user feedback
- Debug access via `window.bassiCapabilities`

## Usage Examples

### 1. Manual Testing (curl)

```bash
# Fetch capabilities
curl http://localhost:8765/api/capabilities | jq

# Check specific fields
curl http://localhost:8765/api/capabilities | jq '.tools'
curl http://localhost:8765/api/capabilities | jq '.mcp_servers'
```

### 2. Browser Console

```javascript
// Fetch capabilities manually
fetch('/api/capabilities')
    .then(r => r.json())
    .then(caps => console.log(caps))

// After /help is typed, access cached capabilities
window.bassiCapabilities
window.bassiCapabilities.tools
window.bassiCapabilities.mcp_servers
```

### 3. Frontend Usage

```javascript
// Check if a specific tool is available
if (this.sessionCapabilities?.tools.includes('Bash')) {
    // Show bash-related UI
}

// Get connected MCP servers
const connectedServers = this.sessionCapabilities?.mcp_servers
    .filter(s => s.status === 'connected')
    .map(s => s.name) || []
```

## Benefits

✅ **Semantic Clarity**: REST for resources, WebSocket for conversations
✅ **Clean Architecture**: Separation of metadata from chat protocol
✅ **Lazy Loading**: Only fetch when needed (performance)
✅ **Cacheable**: Browser can cache HTTP responses
✅ **Testable**: Easy to test REST endpoint independently
✅ **Debuggable**: Can curl `/api/capabilities` to inspect
✅ **No Ghost Messages**: No confusing empty queries
✅ **Always Accurate**: Data comes directly from Agent SDK

## Testing

```bash
# Unit test the endpoint
uv run pytest bassi/core_v3/tests/test_web_server_v3.py::test_capabilities_endpoint -v

# Integration test
curl http://localhost:8765/api/capabilities | jq
```

## Files Modified

- `bassi/core_v3/web_server_v3.py` - Add /api/capabilities endpoint, remove _send_startup_query()
- `bassi/static/app.js` - Fetch capabilities via REST, remove WebSocket init handling
- `docs/features_concepts/session_capabilities.md` - This documentation
