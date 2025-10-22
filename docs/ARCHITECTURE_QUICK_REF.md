# Bassi Architecture - Quick Reference

## Three-Layer Architecture

```
CLI (main.py)
    ↓ User input & commands
Agent (agent.py)
    ↓ Streaming, context, MCP coordination
MCP Servers
    ├─ SDK: bash, web (in-process)
    └─ External: ms365, playwright (subprocess)
```

## Core Files

| File | Lines | Purpose |
|------|-------|---------|
| `bassi/main.py` | 510 | CLI loop, commands, session management |
| `bassi/agent.py` | 824 | Core agent logic, streaming, MCP coordination |
| `bassi/config.py` | 132 | Configuration management |
| `bassi/mcp_servers/bash_server.py` | 74 | Bash execution tool |
| `bassi/mcp_servers/web_search_server.py` | 99 | Web search tool (Tavily) |

## Key Concepts

### MCP Servers (Tool Execution)

**SDK MCP Servers** (in-process):
- `bash` → `mcp__bash__execute`
- `web` → `mcp__web__search`

**External MCP Servers** (subprocess, via .mcp.json):
- `ms365` → `mcp__ms365__*` (email, calendar)
- `playwright` → `mcp__playwright__*` (browser automation)

### Agent State

- **session_id** - Persisted to `.bassi_context.json`, passed to SDK for resumption
- **context_file** - `.bassi_context.json` (auto-created)
- **context_window** - 200K tokens, compacts at 150K (75%)
- **verbose** - Toggle with `/alles_anzeigen` command

### Message Flow

```
user.chat(message)
  → client.query(message)
  → client.receive_response()  [async generator]
    → StreamEvent (real-time text)
    → AssistantMessage (final blocks)
    → UserMessage (tool results)
    → SystemMessage (compaction events)
    → ResultMessage (usage, session_id)
  → save_context()
```

### Commands

| Command | Effect |
|---------|--------|
| `/` | Show command menu |
| `/help` | Show detailed help |
| `/config` | Show configuration |
| `/edit` | Open $EDITOR |
| `/alles_anzeigen` | Toggle verbose |
| `/reset` | Reset conversation |
| `/quit` | Exit |

## Configuration

**Priority** (highest first):
1. `~/.bassi/config.json`
2. `.env` file
3. Environment variables

**Key Variables**:
- `ANTHROPIC_API_KEY` - Required
- `TAVILY_API_KEY` - Optional (web search)
- `MS365_CLIENT_ID`, `MS365_CLIENT_SECRET`, `MS365_TENANT_ID` - For O365

## Permission Model

**Mode**: `bypassPermissions` (fully autonomous)

Why: Personal assistant, single trusted user, no permission prompts

## Async Architecture

- Single-threaded async/await
- `anyio.run(main_async)` entry point
- No multi-threading
- Bash commands block (sync)

## Testing

```bash
uv run pytest              # All tests
./check.sh                 # Format + lint + type + test
```

**Test Files**:
- `tests/test_agent.py` - Agent initialization & MCP servers
- `tests/test_config.py` - Configuration
- `tests/test_use_cases.py` - Complete workflows
- `tests/test_verbose.py` - Verbose mode
- `tests/test_key_bindings.py` - Terminal handling

## Logging

**File**: `bassi_debug.log`

**Enable DEBUG**:
```bash
export BASSI_DEBUG=1
./run-agent.sh
```

## Session Resumption Flow

```
1. Startup: Check .bassi_context.json exists
2. If yes: Prompt "Load previous context?"
3. If yes: Extract session_id → resume_session_id
4. Pass to BassiAgent(resume_session_id=...)
5. SDK handles resumption internally
6. After chat: session_id saved to disk
```

## Adding a New SDK MCP Server

1. Create `bassi/mcp_servers/<name>_server.py`
2. Define tool function with `@tool` decorator
3. Call `create_sdk_mcp_server()` to create server
4. Export from `bassi/mcp_servers/__init__.py`
5. Register in `BassiAgent.__init__()`:
   ```python
   self.sdk_mcp_servers[<name>] = create_<name>_mcp_server()
   ```
6. Add tool name to `allowed_tools` list

## Adding a New External MCP Server

1. Update `.mcp.json`:
   ```json
   {
     "mcpServers": {
       "myserver": {
         "command": "npx",
         "args": ["@org/my-mcp-server"],
         "env": {
           "API_KEY": "${MY_API_KEY}"
         }
       }
     }
   }
   ```
2. Add environment variables to `.env`
3. Add tool names to `allowed_tools` in `BassiAgent.__init__()`
4. Update system prompt with tool usage instructions

## Dependencies

**Key Packages**:
- `claude-agent-sdk` - Agent framework
- `anthropic` - Claude API
- `rich` - Terminal UI
- `pydantic` - Data validation
- `tavily-python` - Web search
- `msgraph-sdk` - Microsoft Graph
- `mcp` - MCP protocol

**Package Manager**: `uv` (not pip)

```bash
uv sync                 # Install/update
uv add <package>        # Add dependency
uv remove <package>     # Remove dependency
```

## System Prompt

**Location**: `agent.py` lines 54-104

**Key Sections**:
1. Role definition
2. Task breakdown strategy
3. Tool naming convention (`mcp__*`)
4. MS365 authentication instructions
5. Warnings about built-in tools

## Design Decisions

| Decision | Why |
|----------|-----|
| SDK MCP for bash/web | Fast, in-process, simple |
| External MCP for ms365/playwright | Language-agnostic, isolated, complex APIs |
| bypassPermissions | Personal assistant, autonomous, trusted |
| Streaming + markdown | Real-time + pretty formatting |
| Session in .json | Simple, no DB needed |
| Dynamic .mcp.json | Flexible, no code changes |

## Future Roadmap

**Vision**: 9 iterations planned

Current: ✅ Iterations 1-2 (dialog + bash + web)

Next: ⏳ Iterations 3-9 (email, calendar, storage, scheduling, browser, python, software)

Architecture ready for all planned features.

