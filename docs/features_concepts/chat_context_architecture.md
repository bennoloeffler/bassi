# Chat Context vs Browser Session Architecture

**Status:** Implementing  
**Created:** 2025-11-28

## Problem Statement

The codebase previously used "session" for two very different concepts:
1. **Browser WebSocket connections** (ephemeral, one per browser tab)
2. **Chat history/workspace** (persistent, can be resumed from any browser)

This caused:
- Naming confusion in code and docs
- Difficulty understanding context switching behavior
- Tight coupling between agent instances and browser connections

## New Terminology

### Chat Context (`chat_context` / `chat_id`)
**What:** A persistent conversation with history, uploaded files, and workspace.

- **Identifier:** `chat_id` (UUID)
- **Storage:** `chats/{chat_id}/` directory
- **Persistence:** Survives browser close, can be resumed later
- **Contains:**
  - `history.md` - Conversation history
  - `session.json` → renamed to `chat.json` - Metadata
  - `DATA_FROM_USER/` - Uploaded files
  - `RESULTS_FROM_AGENT/` - Agent outputs
  - `SCRIPTS_FROM_AGENT/` - Generated scripts
  - `DATA_FROM_AGENT/` - Agent downloads

### Browser Session (`browser_session` / `browser_id`)
**What:** An ephemeral WebSocket connection from a browser tab.

- **Identifier:** `browser_id` (auto-generated on connect)
- **Lifetime:** Until WebSocket disconnects (tab close, network drop)
- **Properties:**
  - Has exactly one assigned agent from the pool
  - May be viewing/editing any chat_context
  - Multiple browser_sessions can exist simultaneously

### Agent
**What:** A Claude Agent SDK client instance that can execute queries.

- **Lifetime:** Started with server, lives in pool until shutdown
- **Properties:**
  - Connected to Claude API
  - Can be assigned to browser_session
  - Released back to pool when browser_session ends
  - State cleared between assignments

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Web Server                                  │
│                                                                       │
│  ┌─────────────────┐                                                  │
│  │   Agent Pool    │  (5 agents, started on server boot)             │
│  │   ┌─────────┐   │                                                  │
│  │   │ Agent 1 │ ◄─┼──┐                                               │
│  │   └─────────┘   │  │                                               │
│  │   ┌─────────┐   │  │  acquire()                                    │
│  │   │ Agent 2 │   │  │                                               │
│  │   └─────────┘   │  │                                               │
│  │   ┌─────────┐   │  │                                               │
│  │   │ Agent 3 │   │  │                                               │
│  │   └─────────┘   │  │                                               │
│  │   ┌─────────┐   │  │                                               │
│  │   │ Agent 4 │   │  │                                               │
│  │   └─────────┘   │  │                                               │
│  │   ┌─────────┐   │  │                                               │
│  │   │ Agent 5 │   │  │                                               │
│  │   └─────────┘   │  │                                               │
│  └─────────────────┘  │                                               │
│                       │                                               │
│  ┌────────────────────┼─────────────────────────────────────────┐    │
│  │  Browser Session 1 │  (WebSocket connection from Chrome)     │    │
│  │                    │                                         │    │
│  │  browser_id: abc   │                                         │    │
│  │  agent: Agent 1  ◄─┘                                         │    │
│  │  current_chat_id: chat-123                                   │    │
│  │                                                              │    │
│  │  Can switch to any chat_context:                             │    │
│  │  - chat-123 (current)                                        │    │
│  │  - chat-456                                                  │    │
│  │  - chat-789                                                  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Browser Session 2 (WebSocket connection from Firefox)       │    │
│  │                                                              │    │
│  │  browser_id: def                                             │    │
│  │  agent: Agent 2                                              │    │
│  │  current_chat_id: chat-456                                   │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       Persistent Storage                              │
│                                                                       │
│  chats/                                                               │
│  ├── chat-123/                    ◄── ChatWorkspace                   │
│  │   ├── chat.json                    (was: session.json)             │
│  │   ├── history.md                                                   │
│  │   ├── DATA_FROM_USER/                                              │
│  │   ├── RESULTS_FROM_AGENT/                                          │
│  │   └── ...                                                          │
│  ├── chat-456/                                                        │
│  │   └── ...                                                          │
│  ├── chat-789/                                                        │
│  │   └── ...                                                          │
│  └── .index.json                  ◄── ChatIndex                       │
│                                                                       │
│  chats-human-readable/            ◄── Symlinks for browsing           │
│  ├── 2025-11-28T10-30__german-chat__chat-12/                          │
│  └── ...                                                              │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Agent Pool Lifecycle

### Server Startup
```python
async def startup():
    # Start first agent synchronously (blocks until ready)
    first_agent = await agent_pool.create_agent()
    await first_agent.connect()
    
    # Start remaining 4 agents asynchronously
    asyncio.create_task(agent_pool.warm_remaining(count=4))
    
    # Server is ready to accept connections
```

### Browser Connection
```python
async def on_websocket_connect(websocket, chat_id=None):
    browser_id = generate_uuid()
    
    # Acquire agent from pool (blocks if none available)
    agent = await agent_pool.acquire(timeout=30)
    
    # Prepare agent for this browser session
    agent.reset_state()
    
    # Load chat context if resuming
    if chat_id:
        workspace = ChatWorkspace.load(chat_id)
        agent.restore_context(workspace.load_history())
    
    browser_sessions[browser_id] = BrowserSession(
        browser_id=browser_id,
        agent=agent,
        current_chat_id=chat_id,
        websocket=websocket,
    )
```

### Chat Context Switch
```python
async def switch_chat(browser_id, new_chat_id):
    session = browser_sessions[browser_id]
    
    # Save current chat if needed
    if session.current_chat_id:
        workspace = ChatWorkspace.load(session.current_chat_id)
        workspace.save_history(session.agent.get_history())
    
    # Clear agent state
    session.agent.reset_state()
    
    # Load new chat context
    workspace = ChatWorkspace.load(new_chat_id)
    session.agent.restore_context(workspace.load_history())
    
    session.current_chat_id = new_chat_id
```

### Browser Disconnection
```python
async def on_websocket_disconnect(browser_id):
    session = browser_sessions[browser_id]
    
    # Save any unsaved work
    if session.current_chat_id:
        workspace = ChatWorkspace.load(session.current_chat_id)
        workspace.save_history(session.agent.get_history())
    
    # Release agent back to pool
    await agent_pool.release(session.agent)
    
    # Clean up browser session
    del browser_sessions[browser_id]
```

## Naming Convention Changes

### Files to Rename
| Old Name | New Name |
|----------|----------|
| `session_workspace.py` | `chat_workspace.py` |
| `session_index.py` | `chat_index.py` |
| `session_naming.py` | `chat_naming.py` |
| `session.json` (in chats/) | `chat.json` |

### Classes to Rename
| Old Name | New Name |
|----------|----------|
| `SessionWorkspace` | `ChatWorkspace` |
| `SessionIndex` | `ChatIndex` |
| `SessionNamingService` | `ChatNamingService` |

### Variables/Parameters to Rename
| Old Name | New Name | Context |
|----------|----------|---------|
| `session_id` | `chat_id` | When referring to chat context |
| `session_id` | `browser_id` | When referring to WebSocket connection |
| `connection_id` | `browser_id` | Consistent naming for browser connections |
| `active_sessions` | `browser_sessions` | Dict of active browser connections |
| `workspaces` | `chat_workspaces` | Dict of loaded chat workspaces |

### Keep Unchanged
- `BassiAgentSession` - This is the SDK wrapper, "session" is appropriate
- `SessionConfig` - Configuration for SDK session
- `SessionStats` - Statistics for SDK session

## API Changes

### WebSocket URL
```
Old: /ws?session_id=xxx
New: /ws?chat_id=xxx
```

### REST Endpoints
```
Old: GET /api/sessions
New: GET /api/chats

Old: GET /api/sessions/{session_id}
New: GET /api/chats/{chat_id}

Old: GET /api/sessions/{session_id}/messages
New: GET /api/chats/{chat_id}/messages

Old: DELETE /api/sessions/{session_id}
New: DELETE /api/chats/{chat_id}
```

### WebSocket Events
```json
// Old
{"type": "connected", "session_id": "xxx"}

// New
{"type": "connected", "chat_id": "xxx", "browser_id": "yyy"}
```

## Migration Notes

1. Existing `chats/` directories remain unchanged (UUIDs stay same)
2. `session.json` files auto-migrate to `chat.json` on first load
3. Frontend `sessionId` becomes `chatId`
4. Browser's `sessionStorage` key changes from `bassi_session_id` to `bassi_chat_id`

## Implementation Order

1. Create new files with new names (keep old for compatibility)
2. Update imports progressively
3. Add deprecation warnings to old names
4. Update tests
5. Update docs
6. Remove old files after stabilization

