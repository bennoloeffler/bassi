# V3 Backend Refactoring - Black Box Design

## Overview

The V3 backend (`bassi/core_v3/web_server_v3.py`) was **1895 lines** of monolithic code. This document tracks the refactoring to **Black Box Design** principles.

## Goals

1. **Replaceability**: Each module can be rewritten using only its interface
2. **Single Responsibility**: Each module has one clear purpose
3. **Testability**: Small modules are easy to unit test
4. **Maintainability**: New developers can understand one module at a time
5. **Target Size**: Main file should be <200 lines (just wiring)

## Architecture

### Before (Monolithic)

```
web_server_v3.py (1895 lines)
├── FastAPI app creation
├── Route setup (sessions, files, capabilities, upload)
├── WebSocket connection handling
├── Message processing (855 lines!)
├── Image processing
├── Help command generation
└── Session cleanup
```

### After (Modular)

```
bassi/core_v3/
├── web_server_v3_new.py (~200 lines)    # Wiring only
├── routes/
│   ├── session_routes.py                # Session CRUD
│   ├── file_routes.py                   # File upload/list
│   └── capability_routes.py             # Capabilities discovery
├── services/
│   ├── session_service.py               # Session business logic
│   └── capability_service.py            # Tool/MCP/agent discovery
├── websocket/
│   ├── connection_manager.py            # Connection lifecycle
│   ├── message_handler.py               # Message routing
│   └── message_processors/              # (TODO: Extract from old file)
│       ├── user_message_processor.py    # Handle user messages
│       ├── hint_processor.py            # Handle hints
│       ├── config_processor.py          # Handle config changes
│       ├── answer_processor.py          # Handle question answers
│       ├── interrupt_processor.py       # Handle interrupts
│       └── server_info_processor.py     # Handle server info requests
```

## Completed Modules

### ✅ Services Layer

**bassi/core_v3/services/session_service.py** (148 lines)
- Interface:
  - `list_sessions(limit, offset)` → List session metadata
  - `get_session(session_id)` → Session details
  - `delete_session(session_id)` → Delete session
- Dependencies: `workspace_manager` from config

**bassi/core_v3/services/capability_service.py** (142 lines)
- Interface:
  - `get_capabilities()` → Dict with tools, mcp_servers, commands, skills, agents
- Dependencies: `BassiDiscovery`, `session_factory`

### ✅ Routes Layer

**bassi/core_v3/routes/session_routes.py** (90 lines)
- Endpoints:
  - `GET /api/sessions` → List sessions
  - `GET /api/sessions/{id}` → Get session
  - `DELETE /api/sessions/{id}` → Delete session
- Dependencies: `SessionService`

**bassi/core_v3/routes/file_routes.py** (137 lines)
- Endpoints:
  - `POST /api/upload` → Upload file to session
  - `GET /api/sessions/{id}/files` → List session files
- Dependencies: `workspaces` dict, `UploadService`

**bassi/core_v3/routes/capability_routes.py** (56 lines)
- Endpoints:
  - `GET /api/capabilities` → Get capabilities
- Dependencies: `CapabilityService`

### ✅ WebSocket Layer

**bassi/core_v3/websocket/connection_manager.py** (283 lines)
- Interface:
  - `handle_connection(websocket, session_id?, message_processor)` → Full lifecycle
  - `cleanup_connection(connection_id, websocket)` → Resource cleanup
  - `get_session(connection_id)` → Get active session
  - `get_workspace(connection_id)` → Get workspace
- Dependencies: `session_factory`, `session_index`, `workspace_base_path`

**bassi/core_v3/websocket/message_handler.py** (77 lines)
- Interface:
  - `dispatch(websocket, data, connection_id)` → Route message by type
- Dependencies: Message processors (6 types)

### ✅ Coordination Layer

**bassi/core_v3/web_server_v3_new.py** (212 lines)
- Responsibilities:
  - FastAPI app creation
  - Dependency injection
  - Route registration
  - WebSocket endpoint wiring
- Dependencies: All above modules

## TODO: Phase 2 - Extract Message Processors

The `_process_message` method in the original file is **855 lines**. It handles 6 message types:

1. **user_message** (~591 lines)
   - Multimodal content handling
   - Image processing
   - /help command (400+ lines of HTML generation!)
   - Agent query execution
   - Stream handling

2. **interrupt** (~21 lines)
   - Interrupt current agent query

3. **hint** (~162 lines)
   - Process user hints
   - Stream agent response

4. **config_change** (~30 lines)
   - Update session config

5. **get_server_info** (~21 lines)
   - Return server metadata

6. **answer** (~30 lines)
   - Answer interactive questions

### Extraction Plan (Phase 2)

1. **Start with simplest processors first:**
   - `interrupt_processor.py` (21 lines)
   - `server_info_processor.py` (21 lines)
   - `config_processor.py` (30 lines)
   - `answer_processor.py` (30 lines)

2. **Then tackle complex ones:**
   - `hint_processor.py` (162 lines)
   - `user_message_processor.py` (591 lines)
     - Extract `/help` generation to separate service
     - Extract image processing to service
     - Extract stream handling to utility

3. **Create supporting services:**
   - `help_service.py` - Generate /help HTML
   - `image_service.py` - Process multimodal images
   - `stream_handler.py` - Handle SDK stream events

## Testing Strategy

1. **Unit Tests** (services, processors)
   - Each service should have unit tests
   - Mock dependencies (workspace, session_factory)

2. **Integration Tests** (routes)
   - Test route handlers with real FastAPI TestClient
   - Mock services

3. **E2E Tests** (WebSocket flow)
   - Test full WebSocket connection flow
   - Use existing E2E test patterns from `bassi/core_v3/tests/`

## Migration Path

### Step 1: Run Existing Tests ✅ NEXT
```bash
uv run pytest bassi/core_v3/tests/ -v
```

### Step 2: Update Imports
- Change imports to use new module structure
- Update `cli.py` to use `web_server_v3_new.py`

### Step 3: Verify Functionality
- Start server with new code
- Test WebSocket connection
- Test file upload
- Test session management

### Step 4: Rename Files
Once verified working:
```bash
mv bassi/core_v3/web_server_v3.py bassi/core_v3/web_server_v3_old.py
mv bassi/core_v3/web_server_v3_new.py bassi/core_v3/web_server_v3.py
```

### Step 5: Extract Remaining Processors (Phase 2)
Follow the extraction plan above.

## Benefits Achieved

1. **Code Organization**: Related code grouped by responsibility
2. **Reduced Complexity**: No single file >300 lines (except old message processor)
3. **Clear Dependencies**: Each module lists its dependencies in docstring
4. **Black Box Principle**: Can replace any module using only its interface
5. **Better Testing**: Each module can be tested independently

## Files to Delete After Migration

- `bassi/core_v3/web_server_v3_old.py` (once fully migrated)

## Related Documentation

- [CLAUDE_BBS.md](../CLAUDE_BBS.md) - Black Box Design principles
- [DUAL_MODE_IMPLEMENTATION.md](DUAL_MODE_IMPLEMENTATION.md) - V1 vs V3 architecture
