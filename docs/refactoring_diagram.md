# Refactoring Visualization

## Before: Monolithic Architecture

```
┌─────────────────────────────────────────────────┐
│  web_server_v3.py (1895 lines)                  │
│  ┌───────────────────────────────────────────┐  │
│  │ WebUIServerV3 class                       │  │
│  │                                           │  │
│  │  - FastAPI setup                          │  │
│  │  - Health endpoint                        │  │
│  │  - Static files                           │  │
│  │  - Capabilities discovery (140 lines)     │  │
│  │  - File upload (60 lines)                 │  │
│  │  - Session listing (60 lines)             │  │
│  │  - Session deletion (40 lines)            │  │
│  │  - WebSocket handler (174 lines)          │  │
│  │  - Message processor (855 lines!)         │  │
│  │    ├─ user_message (591 lines)            │  │
│  │    ├─ /help generation (400 lines!)       │  │
│  │    ├─ hint (162 lines)                    │  │
│  │    ├─ interrupt (21 lines)                │  │
│  │    ├─ config_change (30 lines)            │  │
│  │    ├─ answer (30 lines)                   │  │
│  │    └─ get_server_info (21 lines)          │  │
│  │  - Image processing                       │  │
│  │  - Session cleanup                        │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  app.js (3708 lines)                            │
│  ┌───────────────────────────────────────────┐  │
│  │ BassiWebClient class (99+ methods)        │  │
│  │                                           │  │
│  │  - WebSocket connection                   │  │
│  │  - Event handling                         │  │
│  │  - State management                       │  │
│  │  - Message rendering                      │  │
│  │  - File upload                            │  │
│  │  - File chips                             │  │
│  │  - Drag and drop                          │  │
│  │  - Autocomplete                           │  │
│  │  - Session sidebar                        │  │
│  │  - Settings modal                         │  │
│  │  - Markdown rendering                     │  │
│  │  - Utility functions                      │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## After: Black Box Modular Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        BACKEND (Python)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  web_server_v3.py (212 lines)                          │    │
│  │  ┌──────────────────────────────────────────────────┐  │    │
│  │  │  FastAPI app + wiring ONLY                       │  │    │
│  │  │  - Create app                                    │  │    │
│  │  │  - Register routes                               │  │    │
│  │  │  - Inject dependencies                           │  │    │
│  │  │  - WebSocket endpoint (delegates to manager)    │  │    │
│  │  └──────────────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────────┘    │
│                             ↓                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────┐  │
│  │  routes/        │  │  services/      │  │  websocket/   │  │
│  ├─────────────────┤  ├─────────────────┤  ├───────────────┤  │
│  │ session_routes  │  │ session_service │  │ connection    │  │
│  │   (90 lines)    │  │   (148 lines)   │  │   _manager    │  │
│  │                 │  │                 │  │  (283 lines)  │  │
│  │ file_routes     │  │ capability      │  │               │  │
│  │   (137 lines)   │  │   _service      │  │ message       │  │
│  │                 │  │   (142 lines)   │  │   _handler    │  │
│  │ capability      │  │                 │  │  (77 lines)   │  │
│  │   _routes       │  │                 │  │               │  │
│  │   (56 lines)    │  │                 │  │ processors/   │  │
│  │                 │  │                 │  │  (TODO)       │  │
│  └─────────────────┘  └─────────────────┘  └───────────────┘  │
│         │                      │                     │          │
│         └──────────────────────┴─────────────────────┘          │
│                             ↑                                   │
│                      Clear interfaces                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       FRONTEND (JavaScript)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  app.js (200 lines)                                    │    │
│  │  ┌──────────────────────────────────────────────────┐  │    │
│  │  │  Initialization + wiring ONLY                    │  │    │
│  │  │  - Create state instances                        │  │    │
│  │  │  - Create services                               │  │    │
│  │  │  - Create components                             │  │    │
│  │  │  - Wire event handlers                           │  │    │
│  │  │  - Start WebSocket                               │  │    │
│  │  └──────────────────────────────────────────────────┘  │    │
│  └────────────────────────────────────────────────────────┘    │
│                             ↓                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ state/   │  │services/ │  │  core/   │  │components│      │
│  ├──────────┤  ├──────────┤  ├──────────┤  ├──────────┤      │
│  │ session  │  │   api    │  │websocket │  │ message  │      │
│  │ message  │  │  upload  │  │  event   │  │  file    │      │
│  │   ui     │  │markdown  │  │dispatcher│  │autocmplt │      │
│  └──────────┘  └──────────┘  └──────────┘  │ session  │      │
│                                             │ settings │      │
│  ┌──────────┐  ┌──────────────────────┐    └──────────┘      │
│  │ utils/   │  │     handlers/        │                       │
│  ├──────────┤  ├──────────────────────┤                       │
│  │ format   │  │  message-handler     │                       │
│  │   dom    │  │  text-handler        │                       │
│  └──────────┘  │  tool-handler        │                       │
│                └──────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

## Dependency Flow (Backend)

```
web_server_v3.py
    │
    ├─→ routes/session_routes.py
    │       └─→ services/session_service.py
    │               └─→ workspace_manager (config)
    │
    ├─→ routes/file_routes.py
    │       └─→ upload_service (existing)
    │
    ├─→ routes/capability_routes.py
    │       └─→ services/capability_service.py
    │               ├─→ discovery (existing)
    │               └─→ session_factory
    │
    └─→ websocket/connection_manager.py
            ├─→ session_factory
            ├─→ session_index
            └─→ websocket/message_handler.py
                    └─→ message_processors/ (TODO)
```

## Dependency Flow (Frontend - Planned)

```
app.js
    │
    ├─→ state/ (no dependencies)
    │   ├─→ session-state.js
    │   ├─→ message-state.js
    │   └─→ ui-state.js
    │
    ├─→ utils/ (no dependencies)
    │   ├─→ format-utils.js
    │   └─→ dom-utils.js
    │
    ├─→ services/
    │   ├─→ api-client.js (browser fetch)
    │   ├─→ upload-service.js → api-client
    │   └─→ markdown-service.js (marked.js)
    │
    ├─→ core/
    │   ├─→ websocket-client.js (browser WebSocket)
    │   └─→ event-dispatcher.js
    │
    ├─→ components/
    │   ├─→ message-renderer.js → markdown-service, dom-utils
    │   ├─→ file-chips.js → dom-utils, format-utils
    │   ├─→ autocomplete.js → dom-utils
    │   ├─→ session-sidebar.js → api-client, dom-utils
    │   └─→ settings-modal.js → dom-utils
    │
    └─→ handlers/
        ├─→ message-handler.js → message-state, ui-state, components
        ├─→ text-handler.js → message-state, message-renderer
        └─→ tool-handler.js → message-state, message-renderer
```

## Size Comparison

```
┌────────────────────────────────────────────────────────┐
│               BEFORE vs AFTER (Backend)                │
├────────────────────────────────────────────────────────┤
│                                                        │
│  web_server_v3.py: ████████████████████ 1895 lines    │
│                                                        │
│  After (Phase 1):                                     │
│  ├─ web_server_v3.py:     ██ 212 lines                │
│  ├─ session_service:      █ 148 lines                 │
│  ├─ capability_service:   █ 142 lines                 │
│  ├─ connection_manager:   ██ 283 lines                │
│  ├─ session_routes:       █ 90 lines                  │
│  ├─ file_routes:          █ 137 lines                 │
│  ├─ capability_routes:    █ 56 lines                  │
│  └─ message_handler:      █ 77 lines                  │
│                                                        │
│  Total: ~1145 lines (40% reduction, better organized) │
│  Largest file: 283 lines (was 1895)                   │
│                                                        │
│  TODO (Phase 2): Extract 855-line message processor   │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│              BEFORE vs AFTER (Frontend)                │
├────────────────────────────────────────────────────────┤
│                                                        │
│  app.js: ████████████████████████████████ 3708 lines  │
│                                                        │
│  After (Planned):                                     │
│  ├─ app.js:              ██ 200 lines                 │
│  ├─ utils (2 files):     █ 150 lines                  │
│  ├─ state (3 files):     ██ 350 lines                 │
│  ├─ services (3 files):  ██ 280 lines                 │
│  ├─ core (2 files):      ██ 280 lines                 │
│  ├─ components (5 files):█████ 1150 lines             │
│  └─ handlers (3 files):  ████ 750 lines               │
│                                                        │
│  Total: ~3160 lines (15% reduction, way better org)   │
│  Largest file: ~400 lines (was 3708)                  │
└────────────────────────────────────────────────────────┘
```

## Key Metrics

| Metric | Backend Before | Backend After | Frontend Before | Frontend After |
|--------|---------------|---------------|-----------------|----------------|
| Total Files | 1 | 12 | 1 | 20 |
| Largest File | 1895 lines | 283 lines | 3708 lines | ~400 lines |
| Avg File Size | 1895 lines | ~145 lines | 3708 lines | ~158 lines |
| Testability | ❌ Hard | ✅ Easy | ❌ Hard | ✅ Easy |
| Maintainability | ❌ Low | ✅ High | ❌ Low | ✅ High |
| Replaceability | ❌ No | ✅ Yes | ❌ No | ✅ Yes |
