# Bassi Architecture Overview

**Last Updated**: 2025-01-22  
**Project**: bassi - Benno's Personal Assistant  
**Current Version**: 0.1.0

## Executive Summary

Bassi is a personal AI agent built on the Claude Agent SDK that provides autonomous task execution through an async CLI interface. The architecture separates concerns across three layers:

1. **CLI Layer** (`main.py`) - User interaction, commands, session management
2. **Agent Layer** (`agent.py`) - Core logic, streaming, context management
3. **MCP Layer** - Tool execution through SDK MCP servers and external MCP servers

The system emphasizes streaming responses, context persistence, and fully autonomous operation (`bypassPermissions` mode).

---

## 1. Overall Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    bassi CLI Application                     │
├─────────────────────────────────────────────────────────────┤
│  main.py - Main Loop & Commands                             │
│  ├─ Welcome banner & initialization                         │
│  ├─ User input handling (readline support)                  │
│  ├─ Command router (/, /help, /config, /edit, /reset)      │
│  └─ Session resumption (saved context from .bassi_context)  │
├─────────────────────────────────────────────────────────────┤
│  BassiAgent (agent.py)                                       │
│  ├─ MCP Server Management                                    │
│  │  ├─ SDK MCP Servers (in-process): bash, web              │
│  │  └─ External MCP Servers (.mcp.json): ms365, playwright  │
│  ├─ Context & Session Management                            │
│  │  ├─ Session ID persistence (.bassi_context.json)         │
│  │  ├─ Token tracking (cumulative usage)                    │
│  │  └─ Auto-compaction at 75% context window               │
│  ├─ Streaming & Display                                     │
│  │  ├─ Real-time text streaming (content_block_delta)       │
│  │  ├─ Message rendering (Assistant, Tool Use, Results)     │
│  │  └─ Markdown formatting (Rich console)                   │
│  └─ Verbose Mode & Status Updates                          │
├─────────────────────────────────────────────────────────────┤
│  MCP Servers                                                 │
│  ├─ Bash Server (mcp_servers/bash_server.py)                │
│  │  └─ mcp__bash__execute - Run shell commands             │
│  ├─ Web Search Server (mcp_servers/web_search_server.py)    │
│  │  └─ mcp__web__search - Tavily API search                │
│  ├─ MS365 Server (external, via .mcp.json)                  │
│  │  ├─ mcp__ms365__login - Authenticate                     │
│  │  ├─ mcp__ms365__verify-login - Check auth status         │
│  │  ├─ mcp__ms365__list-mail-messages - Read emails         │
│  │  ├─ mcp__ms365__send-mail - Send emails                  │
│  │  ├─ mcp__ms365__list-calendar-events - View calendar     │
│  │  └─ mcp__ms365__create-calendar-event - Add events       │
│  └─ Playwright Server (external, via .mcp.json)             │
│     ├─ mcp__playwright__browser_navigate - Load page        │
│     ├─ mcp__playwright__browser_click - Click element       │
│     ├─ mcp__playwright__browser_type - Type text            │
│     ├─ mcp__playwright__browser_screenshot - Capture screen │
│     └─ ... (other browser operations)                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Directory Structure

### Complete Project Layout

```
/Users/benno/projects/ai/bassi/
├── bassi/                          # Main Python package
│   ├── __init__.py                # Package initialization + version
│   ├── main.py                    # CLI entry point (430 lines)
│   ├── agent.py                   # BassiAgent class (820 lines)
│   ├── config.py                  # Configuration management
│   └── mcp_servers/               # MCP server implementations
│       ├── __init__.py            # Export: create_bash_mcp_server, create_web_search_mcp_server
│       ├── bash_server.py         # Bash execution MCP server (74 lines)
│       └── web_search_server.py   # Web search MCP server (99 lines)
│
├── tests/                         # Test suite
│   ├── conftest.py               # Pytest configuration
│   ├── test_agent.py             # Agent initialization & MCP server tests
│   ├── test_config.py            # Configuration management tests
│   ├── test_use_cases.py         # Use case tests (UC-1 through UC-6)
│   ├── test_verbose.py           # Verbose mode tests
│   └── test_key_bindings.py      # Key binding tests
│
├── docs/                          # Documentation
│   ├── vision.md                 # Project vision & roadmap (iterations 1-9)
│   ├── design.md                 # Design document (architecture, commands, use cases)
│   ├── requirements.md           # Technical requirements
│   └── features_concepts/        # Feature-specific documentation
│       ├── README.md             # Features index
│       ├── web_search.md         # Web search feature docs
│       ├── permissions.md        # Permission model (bypassPermissions)
│       ├── o365_authentication.md # O365 auth & token caching
│       ├── ms_graph_server.md    # MS Graph API integration
│       ├── context_persistence.md # Context preservation
│       ├── context_compaction.md # Auto-compaction mechanism
│       ├── verbose_mode.md       # Tool call visibility
│       ├── command_selector.md   # Command menu UI
│       ├── simple_prompt_editor.md # Editor for multiline input
│       └── ...
│
├── .mcp.json                      # External MCP server configuration
├── .env.example                   # Environment variable template
├── .bassi_context.json           # Session context (auto-generated)
├── pyproject.toml                # Project configuration & dependencies
├── uv.lock                       # Locked dependencies (uv package manager)
├── check.sh                      # Quality check script (format, lint, type check, test)
├── run-agent.sh                  # Run script with logging
├── bassi_debug.log              # Debug log file (auto-generated)
├── README.md                     # User documentation
├── CLAUDE.md                     # Claude Code instructions
├── CLAUDE_BBS.md                # BBS philosophy guidelines
└── ... (other documentation files)
```

---

## 3. Core Components

### 3.1 BassiAgent Class (`bassi/agent.py`)

**Responsibilities**:
- Initialize SDK and MCP servers
- Manage conversation context and session resumption
- Stream and display responses
- Track token usage and context size
- Provide verbose mode and status updates

**Key Attributes**:
```python
class BassiAgent:
    sdk_mcp_servers: dict           # In-process: bash, web
    external_mcp_servers: dict      # External: ms365, playwright
    options: ClaudeAgentOptions     # SDK configuration
    client: ClaudeSDKClient | None  # Active SDK client
    session_id: str | None          # UUID from SDK, persisted
    context_file: Path              # .bassi_context.json location
    
    # Token tracking (cumulative across session)
    total_input_tokens: int
    total_output_tokens: int
    total_cache_creation_tokens: int
    total_cache_read_tokens: int
    total_cost_usd: float
    
    # Context management
    context_window_size: int        # 200K tokens (Claude Sonnet 4.5)
    compaction_threshold: int       # 150K tokens (75%)
    
    # Streaming state
    _streaming_response: bool
    _accumulated_text: str
    verbose: bool
```

**Key Methods**:

| Method | Signature | Purpose |
|--------|-----------|---------|
| `__init__` | `(status_callback, resume_session_id)` | Initialize agent with MCP servers |
| `chat` | `async (message: str) -> AsyncIterator` | Stream response, yield messages |
| `reset` | `async ()` | Close client, start fresh conversation |
| `interrupt` | `async ()` | Stop current agent execution |
| `save_context` | `()` | Save session_id to disk |
| `load_context` | `()` | Load session_id from disk |
| `get_context_info` | `() -> dict` | Return context usage info |
| `toggle_verbose` | `() -> bool` | Toggle verbose mode ON/OFF |
| `set_verbose` | `(value: bool)` | Set verbose mode explicitly |
| `cleanup` | `async ()` | Clean up resources on shutdown |
| `_load_external_mcp_config` | `() -> dict` | Parse .mcp.json, substitute env vars |
| `_display_available_tools` | `()` | Print tool list at startup |
| `_update_status_from_message` | `(msg)` | Update status bar (called from chat) |
| `_display_message` | `(msg)` | Format & print message (SDK or legacy format) |

**Message Flow**:

```
chat(message) 
  ↓
[Create ClaudeSDKClient if needed]
  ↓
client.query(message)  # Send query
  ↓
client.receive_response()  # Async generator of SDK messages
  ├─ StreamEvent (content_block_delta)       → Print text in real-time
  ├─ AssistantMessage (final blocks)         → Extract tool use/text
  ├─ UserMessage (tool results)              → Display results
  ├─ SystemMessage (compaction events)       → Show compaction notifications
  └─ ResultMessage (usage stats, session_id) → Update tracking
  ↓
save_context()  # Persist session_id
```

---

### 3.2 MCP Servers

#### SDK MCP Servers (In-Process)

**Bash Server** (`bassi/mcp_servers/bash_server.py`):
```python
@tool("execute", "Execute bash command", {"command": str, "timeout": int})
async def bash_execute(args: dict) -> dict
```
- Direct subprocess execution
- 30-second timeout default
- Captures stdout/stderr/exit code
- Error handling for timeout and exceptions

**Web Search Server** (`bassi/mcp_servers/web_search_server.py`):
```python
@tool("search", "Web search via Tavily", {"query": str, "max_results": int})
async def web_search(args: dict) -> dict
```
- Tavily API integration
- 5 results default, configurable
- Formats results with title, URL, content
- Graceful error for missing API key

**Registration**:
```python
# In BassiAgent.__init__()
self.sdk_mcp_servers = {
    "bash": create_sdk_mcp_server(name="bash", tools=[bash_execute]),
    "web": create_sdk_mcp_server(name="web", tools=[web_search]),
}
```

#### External MCP Servers (Subprocess)

Configured via `.mcp.json`:

```json
{
  "mcpServers": {
    "ms365": {
      "command": "npx",
      "args": ["-y", "@softeria/ms-365-mcp-server"],
      "env": {
        "MS365_MCP_CLIENT_ID": "${MS365_CLIENT_ID}",
        "MS365_MCP_CLIENT_SECRET": "${MS365_CLIENT_SECRET}",
        "MS365_MCP_TENANT_ID": "${MS365_TENANT_ID}"
      }
    },
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

**Environment Variable Substitution**:
- Pattern: `${VAR_NAME}` or `${VAR_NAME:-default}`
- Resolved from `os.environ` via `dotenv.load_dotenv()`
- Unknown variables default to empty string

**Loading Process**:
```python
# In BassiAgent._load_external_mcp_config()
1. Load .mcp.json if exists
2. Iterate mcpServers config
3. Substitute environment variables
4. Create MCP server config in SDK format
5. Log server names and commands
6. Return dict of external servers
```

---

### 3.3 Main CLI (`bassi/main.py`)

**Entry Points**:
```
main()                    → anyio.run(main_async)
  ↓
main_async()              → Main async loop
  ├─ print_welcome()      → Banner + API endpoint
  ├─ Load context         → Check for .bassi_context.json
  ├─ Initialize BassiAgent → Load MCP servers
  └─ Conversation loop:
      ├─ get_user_input() → readline with history
      ├─ Command routing  → /help, /config, /reset, etc.
      └─ agent.chat()     → Stream response
```

**Commands** (All case-insensitive, `/` prefix):

| Command | Action | Implementation |
|---------|--------|-----------------|
| `/` or `//` | Show command selector menu | `show_command_selector()` |
| `/help` | Show detailed help + examples | `print_help()` |
| `/config` | Display current configuration | `print_config()` |
| `/edit` | Open $EDITOR for multiline input | Opens temp file |
| `/alles_anzeigen` | Toggle verbose mode | `agent.toggle_verbose()` |
| `/reset` | Reset conversation | `agent.reset()` |
| `/quit` or `/exit` | Exit bassi | Break loop |

**Session Resumption**:
```
Startup:
  1. Check .bassi_context.json exists
  2. If yes:
     - Show "Found saved context" panel
     - Prompt "Load previous context? [y/n]"
     - If yes: Extract session_id
     - Pass resume_session_id to BassiAgent
  3. If no: Start fresh (session_id=None)
  
SDK Behavior:
  - resume=session_id parameter to ClaudeAgentOptions
  - SDK internally handles session resumption
  - SDK generates new session_id if not provided
  - Returns session_id in ResultMessage
```

---

## 4. Data Models & Configuration

### 4.1 Configuration (`bassi/config.py`)

**Config Model**:
```python
class Config(BaseModel):
    root_folders: list[str] = [home]       # Search paths
    log_level: str = "INFO"                # DEBUG, INFO, WARNING
    max_search_results: int = 50           # Unused (search limits are tool-specific)
    anthropic_api_key: str | None = None   # Can override via .env
    tavily_api_key: str | None = None      # Web search API key
```

**Configuration Sources** (Priority order):
1. `~/.bassi/config.json` - User config
2. `.env` file - Project environment
3. Environment variables - System/shell

**ConfigManager**:
- Singleton pattern (module-level `_config_manager`)
- Auto-creates `~/.bassi/config.json` with defaults
- Methods:
  - `get_config()` - Returns Config object
  - `get_api_key()` - Gets Anthropic key
  - `get_tavily_api_key()` - Gets web search key (optional)
  - `save_config(config)` - Persist to disk

### 4.2 Session Context (`.bassi_context.json`)

```json
{
  "session_id": "ae7bbada-f363-4f81-9df3-b24f3dea8f97",
  "timestamp": 1737535200.123,
  "last_updated": "2025-01-22 13:00:00"
}
```

**Purpose**:
- Persist session_id across CLI restarts
- Allow conversation resumption
- Track last activity time

**Lifecycle**:
```
Saved by: agent.save_context() → called after each chat() completes
Loaded by: main.py → loaded at startup, offered to user
Cleared by: Manual deletion or /reset command
```

---

## 5. Streaming & Response Handling

### 5.1 Message Types (Claude Agent SDK)

The SDK yields different message types during `client.receive_response()`:

| Message Type | Source | Purpose | Handling |
|--------------|--------|---------|----------|
| `StreamEvent` | SDK | Real-time token delivery | Extract text from content_block_delta |
| `AssistantMessage` | SDK | Final response blocks | Extract text & tool use blocks |
| `UserMessage` | SDK | Tool results | Extract tool results from content |
| `SystemMessage` | SDK | Initialization, events | Handle compaction notifications |
| `ResultMessage` | SDK | Final result, usage stats | Extract session_id, update token tracking |
| `dict` (legacy) | Fallback | Backward compatibility | Support old message format |

### 5.2 Real-Time Streaming

**Text Streaming via StreamEvent**:
```python
# SDK yields StreamEvent with content_block_delta
StreamEvent {
  event: {
    "type": "content_block_delta",
    "delta": {
      "type": "text_delta",
      "text": "This is a"  # Partial text chunk
    }
  }
}

# Handler in _display_message():
if event_type == "content_block_delta":
    delta = event.get("delta", {})
    if delta.get("type") == "text_delta":
        text = delta.get("text", "")
        if not self._streaming_response:
            print("🤖 Assistant:\n")
            self._streaming_response = True
        print(text, end="")  # Stream without newline
        self._accumulated_text += text
```

**Markdown Rendering After Streaming**:
```python
# After streaming completes (ResultMessage):
if self._streaming_response and self._accumulated_text:
    print("\n─ * 60 ─\n")
    markdown = Markdown(self._accumulated_text, code_theme="monokai")
    console.print(markdown)  # Pretty-print as markdown
    print("\n─ * 60 ─")
    self._streaming_response = False
    self._accumulated_text = ""
```

---

## 6. Context Management

### 6.1 Context Window & Auto-Compaction

**Limits**:
- Context window: 200K tokens (Claude Sonnet 4.5)
- Compaction threshold: 150K tokens (75%)
- Auto-compaction triggers at ~95% (internally by SDK)

**Token Tracking**:
```python
# Cumulative across session lifetime
self.total_input_tokens += usage.get("input_tokens", 0)
self.total_output_tokens += usage.get("output_tokens", 0)
self.total_cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
self.total_cache_read_tokens += usage.get("cache_read_input_tokens", 0)
```

**Compaction Detection**:
```python
# SystemMessage with compaction_start subtype
if subtype == "compaction_start" or "compact" in subtype.lower():
    # Show notification to user
    console.print(Panel(
        "⚡ Auto-Compaction Started",
        title="🔄 Context Management"
    ))
```

### 6.2 Context Info API

```python
agent.get_context_info() -> dict
{
    "current_size": 85000,              # tokens
    "window_size": 200000,              # tokens
    "percentage_used": 42.5,            # percent
    "compaction_threshold": 150000,     # tokens
    "will_compact_soon": False,         # bool
    "total_input_tokens": 50000,
    "total_output_tokens": 30000,
    "total_cache_creation": 5000,
    "total_cache_read": 0,
    "total_cost_usd": 1.234
}
```

---

## 7. Permission Model

**Configuration**: `permission_mode="bypassPermissions"` (Line 184 in agent.py)

**Effect**: Agent executes all tools without permission prompts

**Why This Design**:
1. **Personal Assistant**: Single trusted user
2. **Autonomous Operation**: No interruptions for complex tasks
3. **Controlled Environment**: Local machine only
4. **UX**: Seamless, immediate action

**Available Modes**:
| Mode | Behavior | Use Case |
|------|----------|----------|
| `default` | Ask for each operation | Maximum safety |
| `acceptEdits` | Auto-approve file edits | Safe file changes |
| `bypassPermissions` | All tools auto-approved | Personal assistant (current) |

**Safety Mechanisms**:
- MCP servers run in separate processes
- Agent limited to configured tools only
- System prompt guides appropriate behavior
- All operations logged to `bassi_debug.log`

---

## 8. System Prompt Architecture

**Location**: `agent.py`, lines 54-104

**Purpose**: Instruct Claude on capabilities and behavior

**Key Sections**:
1. Role: "You are bassi, Benno's personal assistant"
2. Task breakdown strategy: "Break down complex tasks into steps"
3. Tool usage instructions: "Use these specific mcp__ tools"
4. MS365 Authentication: "Verify login before using O365 tools"
5. Available tools: Bash, web search, MS365, Playwright
6. Important warnings: "Do NOT use built-in tools - only use mcp__"

**Tool Naming Convention**:
- `mcp__<server_name>__<tool_name>`
- Examples:
  - `mcp__bash__execute`
  - `mcp__web__search`
  - `mcp__ms365__login`
  - `mcp__playwright__browser_navigate`

---

## 9. Dependency Management

**Tool**: `uv` (Python package manager)

**Dependencies** (`pyproject.toml`):

| Package | Version | Purpose |
|---------|---------|---------|
| `anthropic` | >=0.40.0 | SDK (supersedes claude-ai) |
| `claude-agent-sdk` | >=0.1.4 | Agent framework |
| `rich` | >=13.9.4 | Terminal UI/formatting |
| `pydantic` | >=2.10.6 | Data validation |
| `python-dotenv` | >=1.0.1 | .env file loading |
| `tavily-python` | >=0.7.12 | Web search API |
| `mcp` | >=1.18.0 | MCP protocol |
| `prompt-toolkit` | >=3.0.52 | Advanced input (future) |
| `msgraph-sdk` | >=1.46.0 | Microsoft Graph API |
| `azure-identity` | >=1.25.1 | Azure auth |

**Common Commands**:
```bash
uv sync              # Install/update dependencies
uv add package       # Add new dependency
uv remove package    # Remove dependency
uv run pytest        # Run tests
```

---

## 10. Testing Architecture

**Test Structure**:
```
tests/
├── conftest.py          # Pytest configuration
├── test_agent.py        # Agent initialization & MCP servers
├── test_config.py       # Configuration management
├── test_use_cases.py    # Use case tests (UC-1 through UC-6)
├── test_verbose.py      # Verbose mode behavior
└── test_key_bindings.py # Terminal key handling
```

**Key Test Patterns**:

| Test | Type | Purpose |
|------|------|---------|
| `test_agent_imports` | Unit | Verify agent module loads |
| `test_agent_initialization_requires_api_key` | Unit | Agent initializes with SDK |
| `test_agent_has_mcp_servers` | Unit | Bash & web servers registered |
| `test_agent_chat_integration` | Integration | (Skipped by default) |
| `test_use_case_*` | Functional | Complete workflows |

**Running Tests**:
```bash
uv run pytest              # All tests
uv run pytest -v           # Verbose
uv run pytest tests/test_agent.py  # Single file
./check.sh                 # Format + lint + type + test
```

---

## 11. Logging & Debugging

**Log File**: `bassi_debug.log` (auto-created)

**Configuration** (`agent.py`, lines 29-41):
```python
logging.basicConfig(
    level=logging.INFO,  # Default: INFO
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("bassi_debug.log")]
)

# Enable DEBUG via env var:
if os.getenv("BASSI_DEBUG"):
    logger.setLevel(logging.DEBUG)
```

**Key Log Points**:
- Agent initialization & MCP server loading
- API configuration & endpoint
- External MCP server commands
- Chat interactions & session IDs
- Message streaming & processing
- Context compaction events
- Error handling & exceptions

**Debugging**:
```bash
# View recent logs
tail -n 100 bassi_debug.log

# Enable debug logging
export BASSI_DEBUG=1
./run-agent.sh

# Filter specific patterns
grep "MCP" bassi_debug.log
grep "ERROR" bassi_debug.log
```

---

## 12. Async Architecture

**Event Loop**: `anyio` (async runner)

**Entry Point**:
```python
def main():
    anyio.run(main_async)  # Run async event loop

async def main_async():
    # Main CLI loop with async/await
    agent = BassiAgent()
    async for msg in agent.chat(user_input):
        # Process streamed messages
```

**Key Async Operations**:

| Operation | Method | Awaited |
|-----------|--------|---------|
| Create SDK client | `ClaudeSDKClient(options)` | `await client.__aenter__()` |
| Send query | `client.query(message)` | `await` implicit in async loop |
| Receive messages | `client.receive_response()` | `async for msg in ...` |
| Interrupt agent | `agent.interrupt()` | `await agent.interrupt()` |
| Reset agent | `agent.reset()` | `await agent.reset()` |
| Close client | `client.__aexit__()` | `await client.__aexit__()` |

**No Multi-Threading**:
- Single-threaded async execution
- Bash commands run synchronously (blocking)
- MCP servers handle their own threading
- CLI remains responsive during streaming

---

## 13. Example Flow: Complete Conversation

```
User Start:
  $ uv run bassi

1. main()
   ├─ Print welcome banner
   ├─ Check for .bassi_context.json
   ├─ Initialize BassiAgent
   │  ├─ Load SDK MCP servers (bash, web)
   │  ├─ Load external MCP servers (.mcp.json)
   │  ├─ Create ClaudeAgentOptions with all servers
   │  ├─ Display available tools panel
   │  └─ Save context file
   └─ Start main_async loop

2. main_async() Conversation Loop:

   User Input: "What is the weather in Berlin?"
   ↓
   main.py:
   ├─ get_user_input() → "What is the weather..."
   ├─ Check if command (starts with /) → No
   ├─ Call agent.chat(message)
   ↓
   agent.py - chat():
   ├─ Create ClaudeSDKClient (if needed)
   ├─ Call client.query(message)
   ├─ Start receiving messages: async for msg in client.receive_response()
   │  
   │  Message 1: StreamEvent (content_block_delta)
   │  ├─ _display_message() → print "🤖 Assistant:\n"
   │  ├─ Extract text: "I'll search for the weather in Berlin"
   │  ├─ Print text in real-time
   │  └─ Accumulate in _accumulated_text
   │
   │  Message 2: AssistantMessage (tool use block)
   │  ├─ Extract: ToolUseBlock(name="mcp__web__search", input={...})
   │  ├─ Display panel: "🔧 Tool: mcp__web__search"
   │  └─ SDK handles tool execution internally
   │
   │  Message 3: UserMessage (tool result)
   │  ├─ Extract: ToolResultBlock with search results
   │  ├─ Display panel: "✅ Tool Result" + formatted results
   │  └─ Agent reads results, continues response
   │
   │  Message 4: StreamEvent (more response text)
   │  ├─ Extract text: "Based on the search results..."
   │  ├─ Print in real-time
   │  └─ Accumulate in _accumulated_text
   │
   │  Message 5: ResultMessage (final result)
   │  ├─ Extract: usage, cost, session_id
   │  ├─ Render accumulated text as markdown
   │  ├─ Display usage: "⏱️  245ms | 💰 $0.0012"
   │  ├─ Update session_id: self.session_id = sdk_session_id
   │  └─ Update token counts (cumulative)
   │
   ├─ save_context() → Write session_id to .bassi_context.json
   └─ Return to main loop
   
   Back in main_async:
   ├─ Display response complete
   ├─ Prompt next: "You: "
   └─ Loop back to get_user_input()

3. User types: /reset
   ├─ main.py recognizes /reset command
   ├─ Call agent.reset()
   │  ├─ Close ClaudeSDKClient
   │  ├─ Set client = None
   │  ├─ Print "Conversation reset."
   └─ Loop continues with fresh agent

4. User types: /quit
   ├─ main.py recognizes /quit
   ├─ Print "Goodbye! 👋"
   ├─ Break main loop
   ├─ Cleanup (finally block)
   │  ├─ Close remaining resources
   │  └─ Restore terminal state
   └─ Exit process
```

---

## 14. Key Architectural Decisions

### 1. **SDK MCP Servers vs External MCP Servers**

**SDK Servers** (in-process):
- ✅ No subprocess overhead
- ✅ Direct integration with Claude SDK
- ✅ Simple decorator-based definition
- ❌ Limited to Python implementation
- Use for: Bash, web search (trusted, simple tools)

**External Servers** (subprocess):
- ✅ Language agnostic (Node.js, etc.)
- ✅ Process isolation (safer)
- ✅ NPM ecosystem (Playwright, @softeria/ms-365-mcp-server)
- ❌ Subprocess overhead
- ❌ Complex config (environment variables)
- Use for: MS365, Playwright (complex, external APIs)

### 2. **bypassPermissions Over default Mode**

**bypassPermissions Chosen Because**:
- Bassi is for single trusted user (Benno)
- Personal assistant needs autonomy
- No multi-user concerns
- UX: No permission prompts interrupting tasks
- Trade-off: Assumes trust in Claude's behavior

**Mitigation**:
- All operations logged to `bassi_debug.log`
- System prompt guides appropriate behavior
- MCP servers still have their own security boundaries

### 3. **Streaming Architecture with Markdown Rendering**

**Real-Time Text via StreamEvent**:
- Print text immediately as tokens arrive
- User sees response appearing in real-time
- Status updates during API calls

**Deferred Markdown Rendering**:
- Accumulate streamed text
- After response complete, render as pretty markdown
- Better formatting than streaming raw text

**Trade-off**: Slight delay between streaming completion and markdown render, but much better visual presentation.

### 4. **Session Persistence via .bassi_context.json**

**Not using database or file storage because**:
- Single simple file easier than DB setup
- Session ID only (not full conversation history)
- SDK manages conversation history internally
- User can delete file to start fresh

**Limitation**: No conversation history recovery after SDK session expires. But simplicity wins for personal assistant.

### 5. **Dynamic Tool Discovery from .mcp.json**

**Why not hardcode tools**:
- Different users may have different external servers
- Allows adding tools without code changes
- Environment variable substitution flexible

**Why not auto-discover from subprocess**:
- Too complex, subprocess communication overhead
- User explicitly chooses what to expose

---

## 15. Integration Points

### 15.1 Claude Agent SDK Integration

**What the SDK Provides**:
1. `ClaudeSDKClient` - Main API client
2. `ClaudeAgentOptions` - Configuration
3. `create_sdk_mcp_server` - Define in-process MCP servers
4. `@tool` decorator - Define tools
5. Message types - Stream events, assistant messages, etc.
6. Session resumption - Handle session_id internally

**What Bassi Does**:
1. Creates SDK MCP servers (bash, web)
2. Loads external servers (.mcp.json)
3. Passes all to ClaudeAgentOptions
4. Calls client.query() and iterates receive_response()
5. Displays messages with formatting
6. Saves session_id to disk

### 15.2 External MCP Server Integration

**MS365 MCP Server** (`@softeria/ms-365-mcp-server`):
- Via NPX subprocess
- Environment variables: CLIENT_ID, CLIENT_SECRET, TENANT_ID
- Token caching (automatic)
- Tools: login, list-mail, send-mail, list-calendar, create-event

**Playwright MCP Server** (`@playwright/mcp`):
- Via NPX subprocess
- Browser automation via MCP tools
- Tools: navigate, click, type, screenshot, etc.

### 15.3 External APIs

**Anthropic API**:
- Endpoint: `https://api.anthropic.com` (or override via ANTHROPIC_BASE_URL)
- Model: Claude Sonnet 4.5 (or configured)
- Authentication: ANTHROPIC_API_KEY

**Tavily API**:
- Web search service
- 1,000 free requests/month
- Key: TAVILY_API_KEY (optional)

**Microsoft Graph API** (via MS365 MCP Server):
- Email operations
- Calendar operations
- Requires O365 tenant + app registration

---

## 16. Future Architecture Considerations

### Planned Features (from Vision.md)

**Iteration 3-9** (future):
- ✅ Iteration 1: Dialog + bash + streaming
- ✅ Iteration 2: Web search
- ⏳ Iteration 3: Email (MS365 MCP server)
- ⏳ Iteration 4: Calendar (MS365 MCP server)
- ⏳ Iteration 5: Conversation storage & metadata
- ⏳ Iteration 6: Task scheduling/timers
- ⏳ Iteration 7: Browser automation (Playwright)
- ⏳ Iteration 8: Python script creation/execution
- ⏳ Iteration 9: Software installation

### Architectural Readiness

**Current Architecture Supports**:
- Adding new SDK MCP servers (simple: define tool + create_sdk_mcp_server)
- Adding new external MCP servers (easy: add to .mcp.json)
- Token tracking & context compaction (already implemented)
- Verbose mode & logging (already implemented)
- Session resumption (already implemented)

**Would Require**:
- New tool definitions (e.g., for Python script execution)
- External server integration (e.g., Python execution sandbox)
- Feature documentation (follow `docs/features_concepts/` pattern)
- Test coverage for new features

---

## 17. Quality Assurance

### Check Script (`./check.sh`)

Runs in order:
1. `black .` - Code formatting
2. `ruff check --fix .` - Linting with auto-fix
3. `mypy .` - Type checking
4. `uv run pytest` - Unit tests

### Configuration

**Black** (line length 78):
```toml
[tool.black]
line-length = 78
target-version = ["py311"]
```

**Ruff** (linting):
```toml
[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]  # PEP 8, unused imports, naming
ignore = ["E501"]  # Line too long (handled by black)
```

**Mypy** (type checking):
```toml
[tool.mypy]
disallow_untyped_defs = false  # Lenient for now
check_untyped_defs = true       # But check usage
```

**Pytest** (testing):
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
markers = ["integration: requires API keys", "asyncio: async tests"]
```

---

## 18. Documentation Structure

**Documentation Files**:
```
docs/
├── vision.md                    # Project roadmap (iterations 1-9)
├── design.md                    # Architecture & design decisions
├── requirements.md              # Technical requirements
└── features_concepts/
    ├── web_search.md            # Web search feature
    ├── permissions.md           # Permission model documentation
    ├── o365_authentication.md   # MS365 auth & token caching
    ├── ms_graph_server.md       # MS Graph API integration
    ├── context_persistence.md   # Context preservation
    ├── context_compaction.md    # Auto-compaction mechanism
    ├── verbose_mode.md          # Tool visibility
    ├── command_selector.md      # Command menu
    └── ...
```

**Documentation Standards** (from CLAUDE.md):
1. Feature documentation in `docs/features_concepts/<feature_name>.md`
2. Each feature gets a name and dedicated documentation
3. Document before implementation
4. Update docs when feature is complete

---

## Summary

Bassi is a **well-architected personal assistant** with clear separation of concerns:

| Layer | Components | Purpose |
|-------|-----------|---------|
| **CLI** | main.py | User interaction, commands, session management |
| **Agent** | agent.py | Core logic, streaming, context, MCP coordination |
| **MCP** | bash, web, ms365, playwright | Tool execution (SDK or external) |
| **Config** | config.py, .env, .bassi_context.json | Settings, credentials, session state |

**Key Strengths**:
- Clean async architecture with streaming responses
- Flexible MCP server integration (SDK + external)
- Session persistence & resumption
- Token tracking & auto-compaction
- Fully autonomous operation for personal use
- Comprehensive logging & debugging

**Ready for Extension**:
- Easy to add new SDK MCP servers
- Simple to add external MCP servers via .mcp.json
- Testing infrastructure in place
- Documentation pattern established
- Quality check pipeline automated

