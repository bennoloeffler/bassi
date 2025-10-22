# bassi - Design Document

**Version**: 1.0
**Last Updated**: 2025-01-21

## Overview

bassi is Benno's personal AI assistant - a CLI application that provides an intelligent, conversational interface to Claude using the Claude Agent SDK. It features real-time streaming responses, persistent context, automatic context management, and integrated tools for bash execution and web search.

## Philosophy

1. **Simple CLI Dialog** - Clean, colorful terminal interface
2. **Streaming First** - Real-time response streaming for immediate feedback
3. **Context Persistence** - Remember conversations across sessions
4. **Tool Integration** - Seamless bash and web search capabilities
5. **BBS-Style Simplicity** - Don't over-engineer, keep it straightforward

## Architecture

### Core Components

```
bassi/
├── __init__.py          # Package initialization
├── main.py              # CLI entry point, commands, main loop
├── agent.py             # BassiAgent - core logic
├── config.py            # Configuration management
└── mcp_servers/         # MCP server implementations
    ├── bash_server.py           # Bash command execution
    ├── web_search_server.py     # Web search (DuckDuckGo)
    └── task_automation_server.py # Python task automation
```

### BassiAgent Class

**File**: `bassi/agent.py`

**Purpose**: Main agent logic using Claude Agent SDK

**Methods**:
- `__init__(status_callback, resume_session_id)` - Initialize agent with MCP servers
- `chat(message)` - Main async iterator for streaming responses
- `reset()` - Reset conversation (close client, start fresh)
- `interrupt()` - Interrupt current agent run
- `save_context()` - Save session_id to .bassi_context.json
- `load_context()` - Load session_id from .bassi_context.json
- `get_context_info()` - Get context size, usage, compaction status
- `toggle_verbose()` - Toggle verbose mode ON/OFF
- `set_verbose(value)` - Set verbose mode explicitly
- `_update_status_from_message(msg)` - Update status bar
- `_display_message(msg)` - Display streamed messages with formatting

**Key Features**:
- **Streaming**: Handles `StreamEvent` messages with `content_block_delta` for real-time text
- **Markdown Rendering**: After streaming completes, renders full response as formatted markdown
- **Context Window**: 200K tokens (Claude Sonnet 4.5)
- **Auto-Compaction**: Triggers at 150K tokens (75% of window)
- **Token Tracking**: Cumulative tracking across session
- **Verbose Mode**: Controls visibility of tool calls and details

## Commands

All commands start with `/` and are case-insensitive.

| Command | Description | Implementation |
|---------|-------------|----------------|
| `/help` | Show detailed help and examples | `print_help()` in main.py |
| `/config` | Display current configuration | `print_config()` in main.py |
| `/edit` | Open $EDITOR for multiline input | Opens temp file in $EDITOR |
| `/alles_anzeigen` | Toggle verbose mode | `agent.toggle_verbose()` |
| `/reset` | Reset conversation history | `agent.reset()` |
| `/quit` or `/exit` | Exit bassi | Exit main loop |
| `/` or `//` | Show command selector menu | `show_command_selector()` |

## Use Cases

### UC-1: First-Time Startup

**Trigger**: User runs `bassi` with no previous context

**Flow**:
1. No `.bassi_context.json` file exists
2. Agent initializes fresh (no resume_session_id)
3. Welcome banner displayed
4. User prompted for input
5. Session starts fresh

**Expected Result**: New conversation with no history

**Test**: `tests/test_agent.py::test_agent_initialization_requires_api_key`

---

### UC-2: Resume Previous Session

**Trigger**: User runs `bassi` with existing `.bassi_context.json`

**Flow**:
1. Context file found
2. User prompted: "Load previous context? [y/n]"
3. If yes:
   - `session_id` loaded from file
   - Agent initialized with `resume_session_id`
   - SDK loads full conversation history
4. If no:
   - Start fresh session

**Expected Result**: Full conversation history restored (if user chooses yes)

**Test**: `tests/test_context_persistence.py` (needs to be added)

---

### UC-3: Basic Conversation

**Trigger**: User types a message

**Flow**:
1. User input captured via readline
2. Message sent to `agent.chat(message)`
3. Agent streams response in real-time
4. Each `StreamEvent` with `content_block_delta` printed immediately
5. When complete, full response rendered as markdown
6. Usage stats displayed (tokens, cost, context percentage)
7. Context saved to `.bassi_context.json`

**Expected Result**: Real-time streaming response, then formatted markdown

**Test**: `tests/test_agent.py::test_agent_chat_integration` (needs full implementation)

---

### UC-4: Web Search

**Trigger**: User asks question requiring current information

**Flow**:
1. Agent determines web search needed
2. Uses `mcp__web__search` tool
3. Tool call displayed (if verbose)
4. Search query and results displayed
5. Agent synthesizes answer from results

**Expected Result**: Current information retrieved and answered

**Test**: `tests/test_web_search.py` (needs to be created)

---

### UC-5: Bash Execution

**Trigger**: User requests file operations or system commands

**Flow**:
1. Agent determines bash execution needed
2. Uses `mcp__bash__execute` tool
3. Tool call displayed (if verbose)
4. Command and results displayed
5. Agent explains results

**Expected Result**: Command executed, results shown

**Test**: `tests/test_bash_execution.py` (needs to be created)

---

### UC-6: Context Compaction

**Trigger**: Context size reaches 150K tokens (75% of 200K window)

**Flow**:
1. Context size tracked via cumulative token counts
2. When >= 150K tokens:
   - Warning displayed in usage stats: "⚠️ Approaching compaction threshold"
3. When SDK triggers auto-compaction:
   - SystemMessage with `subtype="compaction_start"` received
   - Message displayed: "⚡ Context approaching limit - auto-compacting..."
   - SDK automatically compacts context
4. Conversation continues with compacted context

**Expected Result**: Automatic context management, no user intervention

**Test**: `tests/test_compaction.py` (needs to be created)

---

### UC-7: Toggle Verbose Mode

**Trigger**: User types `/alles_anzeigen`

**Flow**:
1. Command recognized
2. `agent.toggle_verbose()` called
3. State toggled
4. Message displayed: "Verbose mode: ON" or "Verbose mode: OFF"

**Expected Result**: Tool calls visibility toggled

**Test**: `tests/test_verbose.py::test_verbose_toggle` ✓ (exists)

---

### UC-8: Reset Conversation

**Trigger**: User types `/reset`

**Flow**:
1. Command recognized
2. `agent.reset()` called
3. Client properly closed via `__aexit__`
4. `self.client = None`
5. Message displayed: "Conversation reset."
6. Next message starts fresh session with new session_id

**Expected Result**: Conversation history cleared, fresh start

**Test**: `tests/test_agent.py::test_agent_reset` ✓ (exists)

---

### UC-9: Multiline Input

**Trigger**: User types `/edit`

**Flow**:
1. Command recognized
2. `$EDITOR` environment variable checked (default: vim)
3. Temporary file created
4. Editor opened
5. User writes multiline content and saves
6. Content read from temp file
7. Preview displayed (first 200 chars)
8. Content sent to agent as message

**Expected Result**: Multiline input sent to agent

**Test**: `tests/test_multiline_input.py` (needs to be created)

---

### UC-10: View Configuration

**Trigger**: User types `/config`

**Flow**:
1. Command recognized
2. Configuration loaded from `get_config_manager()`
3. Display:
   - Config file path
   - Root folders
   - Log level
   - Max search results

**Expected Result**: Configuration displayed

**Test**: `tests/test_config.py::test_config_manager_loads_existing_config` ✓ (exists)

---

### UC-11: Get Help

**Trigger**: User types `/help`

**Flow**:
1. Command recognized
2. Help text displayed:
   - All available commands
   - Usage examples for:
     - File operations
     - Web search
     - Email & calendar (when configured)

**Expected Result**: Comprehensive help displayed

**Test**: `tests/test_key_bindings.py::test_slash_help_shows_help` ✓ (exists)

---

### UC-12: Command Menu

**Trigger**: User types `/` or `//`

**Flow**:
1. Command recognized
2. Interactive numbered menu displayed:
   ```
   1. /help - Show detailed help
   2. /config - Display configuration
   3. /edit - Open $EDITOR
   4. /alles_anzeigen - Toggle verbose mode
   5. /reset - Reset conversation
   6. /quit - Exit bassi
   ```
3. User enters number
4. Selected command executed

**Expected Result**: User-friendly command selection

**Test**: `tests/test_key_bindings.py::test_slash_command_menu` ✓ (exists)

---

### UC-13: Interrupt Agent

**Trigger**: User presses `Ctrl+C` during agent execution

**Flow**:
1. KeyboardInterrupt caught in main loop
2. `agent.interrupt()` called
3. SDK interrupt() called
4. Message displayed: "⚠️ Agent interrupted"
5. Control returns to prompt
6. User can continue conversation

**Expected Result**: Agent gracefully interrupted, conversation continues

**Test**: `tests/test_interrupt.py` (needs to be created)

---

### UC-14: Exit Application

**Trigger**: User presses `Ctrl+C` at prompt OR types `/quit` or `/exit`

**Flow**:
1. Command recognized OR EOF/KeyboardInterrupt at prompt
2. Message displayed: "Goodbye! 👋"
3. Terminal restored to cooked mode
4. Application exits cleanly

**Expected Result**: Graceful exit

**Test**: `tests/test_key_bindings.py::test_slash_quit_exits_cleanly` ✓ (exists)

## Auto-Compacting Context

### Overview

bassi automatically manages context to prevent exceeding Claude's 200K token window.

### Mechanism

1. **Token Tracking**: Cumulative tracking of:
   - Input tokens
   - Cache creation tokens
   - Cache read tokens
   - Output tokens

2. **Threshold Detection**:
   - Context window: 200,000 tokens
   - Compaction threshold: 150,000 tokens (75%)
   - Warning displayed when >= 150K tokens

3. **Auto-Compaction**:
   - Handled automatically by Claude Agent SDK
   - SystemMessage received: `subtype="compaction_start"`
   - Message displayed to user
   - Context summarized/compacted by SDK
   - Conversation continues seamlessly

4. **Display**:

   **Verbose mode shows simple, honest metrics:**
   ```
   ⏱️  4548ms | 💰 $0.0147 | 💵 Total: $1.23
   ```

   **When compaction happens:**
   ```
   ⚡ Context window at ~95% - auto-compacting...
   ```

   **Note**: We don't display cumulative token counts because:
   - After auto-compaction, they don't reflect actual context size
   - SDK manages context internally with auto-compaction at ~95%
   - Only SDK knows the real context state after compaction
   - Showing misleading numbers would be dishonest

### Implementation

**File**: `bassi/agent.py`

**Tracking** (lines 121-126):
```python
self.total_input_tokens = 0
self.total_output_tokens = 0
self.total_cache_creation_tokens = 0
self.total_cache_read_tokens = 0
self.total_cost_usd = 0.0
```

**Threshold** (lines 133-135):
```python
self.context_window_size = 200000  # 200K tokens
self.compaction_threshold = 150000  # Compact at 75%
```

**Detection** (lines 177-204):
```python
def get_context_info(self) -> dict:
    current_context_size = (
        self.total_input_tokens
        + self.total_cache_creation_tokens
        + self.total_cache_read_tokens
    )
    will_compact_soon = current_context_size >= self.compaction_threshold
    # ...
```

**Display** (lines 357-364):
```python
if subtype == "compaction_start" or "compact" in subtype.lower():
    self.console.print(
        "\n[bold yellow]⚡ Context approaching limit - auto-compacting...[/bold yellow]\n"
    )
```

## Streaming Implementation

### Real-Time Streaming

**Enabled via**: `include_partial_messages=True` in ClaudeAgentOptions

**Message Flow**:
1. SDK sends `StreamEvent` messages
2. Event type: `content_block_delta`
3. Delta type: `text_delta`
4. Text chunks streamed in real-time

**Implementation** (agent.py:327-348):
```python
if msg_class_name == "StreamEvent":
    event = getattr(msg, "event", {})
    if event.get("type") == "content_block_delta":
        delta = event.get("delta", {})
        if delta.get("type") == "text_delta":
            text = delta.get("text", "")
            # Print header on first chunk
            if not self._streaming_response:
                self.console.print("\n[bold green]🤖 Assistant:[/bold green]\n")
                self._streaming_response = True
            # Stream text directly
            self.console.print(text, end="")
            self._accumulated_text += text
```

### Markdown Rendering

**After streaming completes**, the full response is rendered as formatted markdown.

**Implementation** (agent.py:448-457):
```python
if self._streaming_response:
    if self._accumulated_text:
        self.console.print("\n")
        self.console.print("[dim]─" * 60 + "[/dim]")
        markdown = Markdown(self._accumulated_text, code_theme="monokai")
        self.console.print(markdown)
        self.console.print("[dim]─" * 60 + "[/dim]")
```

**Benefits**:
- Immediate feedback during generation
- Formatted output for readability
- Code syntax highlighting
- Proper markdown rendering (lists, headers, etc.)

## Context Persistence

### Storage

**File**: `.bassi_context.json` in current working directory

**Content**:
```json
{
  "session_id": "ae7bbada-f363-4f81-9df3-b24f3dea8f97",
  "timestamp": 1705852800.0,
  "last_updated": "2025-01-21 14:30:00"
}
```

### Session Resumption

**Mechanism**:
1. On startup, check for `.bassi_context.json`
2. If found, prompt user to load previous context
3. If yes, pass `session_id` to `ClaudeAgentOptions(resume=session_id)`
4. SDK loads full conversation history from `~/.claude/projects/.../session_id.jsonl`
5. Conversation continues where it left off

**Implementation** (main.py:230-282):
```python
# Check for saved context
resume_session_id: str | None = None
context_file = Path.cwd() / ".bassi_context.json"
if context_file.exists():
    saved_context = json.loads(context_file.read_text())
    load_choice = Prompt.ask("Load previous context?", choices=["y", "n"], default="y")
    if load_choice.lower() == "y":
        resume_session_id = saved_context.get("session_id")

# Initialize agent with resume
agent = BassiAgent(
    status_callback=update_status,
    resume_session_id=resume_session_id,
)
```

## Configuration

### File Location

**Path**: `~/.config/bassi/config.json` (or XDG_CONFIG_HOME)

### Configuration Options

```json
{
  "root_folders": [
    "~/Documents",
    "~/Projects"
  ],
  "log_level": "INFO",
  "max_search_results": 10
}
```

### Config Manager

**File**: `bassi/config.py`

**Class**: `ConfigManager`

**Methods**:
- `get_config()` - Load and return configuration
- `save_config(config)` - Save configuration to file

## Tools (MCP Servers)

### Bash Execution

**Server**: `bassi/mcp_servers/bash_server.py`

**Tool**: `mcp__bash__execute`

**Purpose**: Execute shell commands

**Capabilities**:
- File operations (ls, cat, etc.)
- Search (fd, rg, find, grep)
- System commands
- Git operations

**Safety**: Commands executed in current working directory

---

### Web Search

**Server**: `bassi/mcp_servers/web_search_server.py`

**Tool**: `mcp__web__search`

**Purpose**: Search the web for current information

**Backend**: DuckDuckGo

**Use Cases**:
- Current events
- Real-time data (weather, prices, etc.)
- Fact-checking
- Research

---

### Task Automation

**Server**: `bassi/mcp_servers/task_automation_server.py`

**Tool**: `mcp__task_automation__execute_python`

**Purpose**: Execute Python code for repeatable automation tasks

**Capabilities**:
- Image processing (compress, resize, convert)
- File organization (batch rename, sort)
- Data transformation (CSV/JSON processing)
- Text processing (batch operations)
- Any Python automation task

**Safety**: Subprocess isolation with timeout enforcement

**Documentation**: See `docs/features_concepts/task_automation.md` for details

## Testing Strategy

### Test Structure

```
tests/
├── conftest.py                      # Shared fixtures
├── test_agent.py                    # Agent logic tests
├── test_config.py                   # Configuration tests
├── test_key_bindings.py             # CLI interaction tests
├── test_verbose.py                  # Verbose mode tests
├── test_task_automation.py          # Task automation tests
└── test_task_automation_integration.py # Integration tests
```

### Coverage Goals

- **Agent**: All methods, edge cases
- **Commands**: All 7 commands
- **Use Cases**: All 14 use cases
- **Context**: Save, load, resume
- **Streaming**: Real-time display
- **Compaction**: Warning, trigger, handling
- **Tools**: Bash execution, web search
- **Error Handling**: All failure modes

### Running Tests

```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/test_agent.py

# With coverage
uv run pytest --cov=bassi

# Quality checks (formatting, linting, types, tests)
./check.sh
```

## Future Enhancements

1. **O365 Integration** - Email, calendar access (via MCP server)
2. **External MCP Servers** - Load from `.mcp.json`
3. **Custom Prompts** - User-configurable system prompts
4. **History Search** - Search conversation history
5. **Export** - Export conversations to markdown
6. **Themes** - Customizable color schemes

## Technical Details

### Dependencies

- **claude-agent-sdk**: Claude Agent SDK for Python
- **rich**: Terminal formatting and rendering
- **anyio**: Async framework
- **anthropic**: Core Anthropic API library

### Logging

**File**: `bassi_debug.log` in current directory

**Level**: INFO (or DEBUG if `BASSI_DEBUG=1` environment variable set)

**Usage**:
```bash
# Enable debug logging
BASSI_DEBUG=1 ./run-agent.sh

# View logs
tail -f bassi_debug.log
```

### Terminal Handling

- **Mode**: Cooked mode (canonical input with echo)
- **History**: Readline-based (~/.bassi_history)
- **Interruption**: Ctrl+C handled gracefully
- **Restoration**: Terminal mode restored on exit

## Security Considerations

1. **API Key**: Required in `ANTHROPIC_API_KEY` environment variable
2. **Command Execution**: All bash commands executed in current directory
3. **Web Search**: Read-only, no data sent
4. **Context Files**: Stored locally, not shared
5. **Logs**: May contain sensitive data, keep secure

## Troubleshooting

### Common Issues

**Issue**: "ANTHROPIC_API_KEY not set"
**Solution**: Set environment variable: `export ANTHROPIC_API_KEY=your-key`

**Issue**: "No streaming output"
**Solution**: Ensure `PYTHONUNBUFFERED=1` in `run-agent.sh` or use `python -u`

**Issue**: "Context not resuming"
**Solution**: Check `.bassi_context.json` exists and contains valid `session_id`

**Issue**: "Commands not working"
**Solution**: Ensure commands start with `/` and are lowercase

## Appendix: File Reference

### Core Files

| File | Purpose | Lines | Key Functions |
|------|---------|-------|---------------|
| `bassi/__init__.py` | Package init | 6 | Version export |
| `bassi/agent.py` | Agent logic | 560 | BassiAgent class |
| `bassi/main.py` | CLI entry | 459 | main(), main_async() |
| `bassi/config.py` | Configuration | ~200 | ConfigManager class |
| `bassi/mcp_servers/bash_server.py` | Bash tool | ~100 | create_bash_mcp_server() |
| `bassi/mcp_servers/web_search_server.py` | Web search | ~100 | create_web_search_mcp_server() |

### Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Project overview, quick start |
| `docs/design.md` | This document - comprehensive design |
| `docs/vision.md` | Project vision and goals |
| `docs/requirements.md` | Technical requirements |
| `docs/features_concepts/` | Feature-specific documentation |

### Test Files

| File | Purpose |
|------|---------|
| `tests/test_agent.py` | Agent logic tests |
| `tests/test_config.py` | Configuration tests |
| `tests/test_key_bindings.py` | CLI interaction tests |
| `tests/test_verbose.py` | Verbose mode tests |

---

**Document Status**: Complete
**Next Review**: After major feature additions
