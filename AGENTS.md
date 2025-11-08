# AGENTS

## Architecture Snapshot
- The CLI (`bassi/main.py`) and web stack (`bassi/core_v3`) both wrap `BassiAgent` / `BassiAgentSession` to stream Claude Agent SDK responses while wiring in MCP servers for bash, web search, task automation, Microsoft 365, and Playwright capabilities (`docs/ARCHITECTURE_OVERVIEW.md`).  
- Session-aware storage (`bassi/core_v3/session_workspace.py` + `session_index.py`) persists uploads, scripts, and chat metadata under `chats/`, while the FastAPI web server exposes `/api/upload`, `/api/capabilities`, and WebSocket streaming endpoints.  
- The web client (`bassi/static/app.js`) renders streaming markdown, interactive tool call panels, verbose levels, interrupt handling, and multimodal uploads; CLI mode uses Rich for the console experience.

## Maintainability & Stability Opportunities
1. ✅ **FIXED: Centralize logging configuration** – Moved `configure_logging()` calls from module level (`bassi/agent.py`, `bassi/core_v3/web_server_v3.py`) to entry points (`bassi/main.py:650`, `bassi/core_v3/cli.py:24`). Logging now configured once per process, eliminating handler conflicts.
2. **Increase agent test coverage** – the top-level tests only cover module import and constructor happy paths; the only chat test is skipped (`tests/test_agent.py:1-88`). Add fixtures that stub the Claude SDK (e.g., via dependency injection or adapter interface) so we can unit-test streaming, verbose toggling, and context persistence without real API calls.
3. ✅ **FIXED: Stream uploads directly to disk** – Replaced `content_chunks = []` list accumulation with streaming to temporary file (`bassi/core_v3/session_workspace.py:132-165`). Memory usage: O(n) → O(1) at CHUNK_SIZE (64KB). Hash calculated during write in single pass.
4. ✅ **FIXED: Thinking mode toggle functional** – Added model switching infrastructure (`agent_session.py:40-41,127-131,181-223`), WebSocket config_change handler (`web_server_v3.py:1231-1255`), and UI integration (`app.js:228-235`). Toggle now controls actual model behavior: `claude-sonnet-4-5-20250929` ↔ `claude-sonnet-4-5-20250929:thinking` with automatic reconnection.
5. **Expose safer permission modes & hooks** – everything currently runs in `bypassPermissions` with no `hooks` or `can_use_tool` callbacks, even though the docs flag these SDK features as unimplemented opportunities (`docs/features_concepts/permissions.md:9-75`, `docs/agent_sdk_usage_review.md:206-307`). Add an environment-configurable permission mode plus hook-based filters (e.g., to block destructive bash commands or gate MS365 actions) to improve safety and traceability.
6. ✅ **DOCUMENTED: Session workspace contract** – Backend API `/api/sessions/{id}/files` fully implemented (`bassi/core_v3/web_server_v3.py:335-377`). Frontend file browser UI not yet built. Updated spec (`docs/features_concepts/session_workspace_tasks.md`) to reflect actual state: backend complete, frontend pending. Current "ephemeral staging" behavior documented.

## Documented Features Still Outstanding
| Feature | Source | Gap Observed | Suggested Next Step |
| --- | --- | --- | --- |
| Tool schema/description fetching | `docs/TODO_TOOL_DESCRIPTIONS.md:1-150` | Help modal still shows placeholders because the backend never queries MCP `tools/list` and no `/api/tool-schemas` endpoint exists. | Implement `mcp_tool_schemas.fetch()` + `/api/tool-schemas`, cache schemas, and hydrate the modal with real descriptions/examples. |
| SDK hooks & permission callbacks | `docs/agent_sdk_usage_review.md:206-307` | Hooks (`PreToolUse`) and `can_use_tool` callbacks remain unimplemented despite being highlighted as high-value safeguards. | Introduce hook matchers for bash/MS365 to enforce allow/deny policies and surface telemetry, and expose toggleable policies via config. |
| Hot reload quality-of-life | `docs/HOT_RELOAD_V3.md:317-375` | Docs note missing browser auto-refresh, module-level HMR, and config reload; today developers still need manual F5 and manual restarts for `.env` changes. | Add SSE-based static watcher for instant refresh, consider Vite/HMR for frontend, and watch `.env`/`.mcp.json` to trigger graceful reloads. |
| Session workspace UI parity | `docs/features_concepts/session_workspace_tasks.md:157-199` | Spec calls for a collapsible file area with persisted session IDs and a `/api/sessions/{id}/files` view, but frontend only stages current uploads and discards them after sending. | Implement local session persistence plus a file browser backed by the existing `SessionWorkspace.list_files()` endpoint so users can re-use previous uploads. |
| Native Python MS Graph MCP server | `docs/features_concepts/ms_graph_server.md:3-75` | Planning doc targets a first-party `create_ms_graph_mcp_server()` but repo still depends on the external Softeria server via `.mcp.json`. | Decide whether to continue relying on the external server or build the in-repo server; update docs either way to avoid dual roadmaps. |

## Suggested Next Steps
1. Prioritize infrastructure fixes (logging, upload streaming, permission hooks) so both CLI and web paths share the same observability and safety guarantees.
2. Schedule the feature work that still lives only in specs (tool schemas, thinking mode, session file browser) and update docs as soon as milestones land to prevent drift.
3. Expand automated tests around `BassiAgentSession`, file uploads, and WebSocket config changes by mocking the Claude SDK—this will make future refactors much safer.

