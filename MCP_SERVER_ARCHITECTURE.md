# MCP Server Architecture in Bassi

## Overview

Bassi integrates tools through two types of MCP (Model Context Protocol) servers:

1. **SDK MCP Servers** - In-process, Python-based
2. **External MCP Servers** - Subprocess, language-agnostic

---

## SDK MCP Servers (In-Process)

### Design Pattern

```python
from claude_agent_sdk import create_sdk_mcp_server, tool

@tool("tool_name", "description", {"param1": type, "param2": type})
async def tool_function(args: dict) -> dict:
    """Implementation"""
    return {"content": [{"type": "text", "text": result}]}

def create_my_mcp_server():
    return create_sdk_mcp_server(
        name="server_name",
        version="1.0.0",
        tools=[tool_function]
    )
```

### Bash Server

**File**: `bassi/mcp_servers/bash_server.py`

**Tool**: `mcp__bash__execute`

```python
@tool("execute", "Execute bash command", {
    "command": str,
    "timeout": int
})
async def bash_execute(args: dict) -> dict:
    """Execute shell command, return stdout/stderr/exit code"""
    command = args["command"]
    timeout = args.get("timeout", 30)
    
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout
    )
    
    return {
        "content": [{
            "type": "text",
            "text": f"""Exit Code: {result.returncode}
Success: {result.returncode == 0}

STDOUT:
{result.stdout or '(empty)'}

STDERR:
{result.stderr or '(empty)'}"""
        }]
    }
```

**Features**:
- Direct subprocess execution
- Timeout handling (30s default)
- Captures stdout/stderr
- Error handling

**Usage in System Prompt**:
```
mcp__bash__execute - Run shell commands
Available Unix tools: fd, rg, find, grep
```

### Web Search Server

**File**: `bassi/mcp_servers/web_search_server.py`

**Tool**: `mcp__web__search`

```python
@tool("search", "Web search via Tavily", {
    "query": str,
    "max_results": int
})
async def web_search(args: dict) -> dict:
    """Search web using Tavily API"""
    query = args["query"]
    max_results = args.get("max_results", 5)
    
    client = TavilyClient(api_key=get_tavily_api_key())
    response = client.search(query=query, max_results=max_results)
    
    # Format results with title, URL, content
    results_text = format_results(response["results"])
    
    return {
        "content": [{"type": "text", "text": results_text}]
    }
```

**Features**:
- Tavily API integration
- Configurable result count (5 default)
- Pretty-printed results
- Graceful error for missing API key

**Usage in System Prompt**:
```
mcp__web__search - Search web for current information
Returns: Results with title, URL, content snippet
```

### Registration Pattern

**In `BassiAgent.__init__()`**:

```python
# Create all SDK MCP servers
self.sdk_mcp_servers = {
    "bash": create_bash_mcp_server(),
    "web": create_web_search_mcp_server(),
}

# Add any future SDK servers here:
# "myserver": create_myserver_mcp_server(),
```

**In `BassiAgent.__init__()` allowed_tools**:

```python
allowed_tools = [
    "mcp__bash__execute",
    "mcp__web__search",
]

# Add any future SDK tools here:
# "mcp__myserver__tool_name",
```

### Return Format

All SDK MCP server tools return:

```python
# Success response
{
    "content": [
        {
            "type": "text",
            "text": "Result text here"
        }
    ]
}

# Error response
{
    "content": [
        {
            "type": "text",
            "text": "ERROR: Description"
        }
    ],
    "isError": True
}
```

---

## External MCP Servers (Subprocess)

### Configuration via .mcp.json

**Location**: `.mcp.json` (root of project)

**Format**:
```json
{
  "mcpServers": {
    "server_name": {
      "command": "executable",
      "args": ["arg1", "arg2"],
      "env": {
        "VAR_NAME": "${ENV_VAR:-default}"
      }
    }
  }
}
```

### Environment Variable Substitution

**Pattern**: `${VAR_NAME}` or `${VAR_NAME:-default}`

**Example**:
```json
{
  "env": {
    "CLIENT_ID": "${MS365_CLIENT_ID}",
    "CLIENT_SECRET": "${MS365_CLIENT_SECRET:-}",
    "API_KEY": "${CUSTOM_API_KEY}"
  }
}
```

**Processing** (in `BassiAgent._load_external_mcp_config()`):

1. Load environment via `dotenv.load_dotenv()`
2. For each `${VAR}` pattern:
   - Extract variable name
   - Check `os.environ`
   - Use default if specified (after `:-`)
   - Default to empty string if not found

### MS365 MCP Server

**Configuration**:
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
    }
  }
}
```

**Tools** (available via MCP):
- `mcp__ms365__login` - Authenticate
- `mcp__ms365__verify-login` - Check auth status
- `mcp__ms365__list-mail-messages` - Read emails
- `mcp__ms365__send-mail` - Send emails
- `mcp__ms365__list-calendar-events` - View calendar
- `mcp__ms365__create-calendar-event` - Add events

**Features**:
- Token caching (automatic)
- Interactive browser-based auth
- Full email & calendar access
- Softeria enterprise server

**Setup**:
1. Register app in Azure AD
2. Get CLIENT_ID, CLIENT_SECRET, TENANT_ID
3. Add to `.env` file
4. First use: agent calls `mcp__ms365__login` → browser auth → token cached

### Playwright MCP Server

**Configuration**:
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

**Tools** (available via MCP):
- `mcp__playwright__browser_navigate` - Load URL
- `mcp__playwright__browser_click` - Click element
- `mcp__playwright__browser_type` - Type text
- `mcp__playwright__browser_screenshot` - Capture screen
- `mcp__playwright__browser_select` - Select option
- `mcp__playwright__browser_hover` - Hover element
- `mcp__playwright__browser_evaluate` - Execute JS
- `mcp__playwright__browser_install` - Setup browsers

**Features**:
- Headless browser automation
- Cross-platform (Chromium, Firefox, Safari)
- Screenshots & visual feedback
- JavaScript evaluation

### Loading External Servers

**Flow** (in `BassiAgent.__init__()` via `_load_external_mcp_config()`):

```
1. Check if .mcp.json exists
   ↓ No → Log "No .mcp.json found" → Return {}
   ↓ Yes → Continue
   
2. Parse JSON
   ↓ Error → Log error → Return {}
   ↓ OK → Continue
   
3. For each mcpServer:
   a. Get command and args
   b. Load env variables
   c. Substitute ${VAR} patterns
   d. Create MCP server config
   e. Log server registration
   
4. Return dict of all servers
   
5. In __init__:
   all_mcp_servers = {
       **self.sdk_mcp_servers,
       **self.external_mcp_servers
   }
```

### Subprocess Management

**How SDK handles external servers**:

1. SDK creates subprocess via `command` and `args`
2. Subprocess communicates via stdin/stdout (MCP protocol)
3. SDK translates tool calls to MCP messages
4. Tool results flow back through MCP

**Environment Inheritance**:

- Subprocess inherits parent environment
- Additional env vars added from config
- No shell expansion (args are literal)

---

## Tool Naming Convention

### Tool Name Format

```
mcp__<server_name>__<tool_name>

Examples:
- mcp__bash__execute          (SDK: bash server)
- mcp__web__search            (SDK: web server)
- mcp__ms365__login           (External: ms365 server)
- mcp__ms365__list-mail-messages
- mcp__ms365__send-mail
- mcp__ms365__list-calendar-events
- mcp__ms365__create-calendar-event
- mcp__playwright__browser_navigate
- mcp__playwright__browser_click
- mcp__playwright__browser_type
- mcp__playwright__browser_screenshot
```

### Tool Registration

**Allowed Tools List** (in `BassiAgent.__init__()`):

```python
allowed_tools = [
    "mcp__bash__execute",
    "mcp__web__search",
]

# Add if MS365 configured:
if "ms365" in self.external_mcp_servers:
    allowed_tools.extend([
        "mcp__ms365__login",
        "mcp__ms365__verify-login",
        "mcp__ms365__list-mail-messages",
        "mcp__ms365__send-mail",
        "mcp__ms365__list-calendar-events",
        "mcp__ms365__create-calendar-event",
    ])

# Add if Playwright configured:
if "playwright" in self.external_mcp_servers:
    allowed_tools.extend([
        "mcp__playwright__browser_navigate",
        "mcp__playwright__browser_screenshot",
        "mcp__playwright__browser_click",
        "mcp__playwright__browser_type",
        # ... more tools
    ])
```

---

## System Prompt Integration

### Tool Documentation in Prompt

**Location**: `BassiAgent.SYSTEM_PROMPT` (lines 54-104)

**Pattern**:
```python
SYSTEM_PROMPT = """
You are bassi, Benno's personal assistant.

IMPORTANT: You must use these specific tools:
- mcp__bash__execute: Execute shell commands
- mcp__web__search: Search the web
- mcp__ms365__login: Authenticate to Microsoft 365
- mcp__ms365__list-mail-messages: Read emails
- [etc...]

Do NOT use the built-in Bash or other tools - only use the mcp__ prefixed tools.

Available Unix tools via mcp__bash__execute:
- fd: Fast file search
- rg: Fast content search
- find: Classic file search
- grep: Classic content search
"""
```

### Dynamic Tool Documentation

**Future Enhancement** (in `_display_available_tools()`):

Currently hardcoded. Could be made dynamic:

```python
# Get available tools from allowed_tools list
tools_by_server = {}
for tool in self.options.allowed_tools:
    parts = tool.split("__")
    if len(parts) >= 3 and parts[0] == "mcp":
        server_name = parts[1]
        tool_name = "__".join(parts[2:])
        if server_name not in tools_by_server:
            tools_by_server[server_name] = []
        tools_by_server[server_name].append(tool_name)

# Display grouped by server
for server_name, tools in tools_by_server.items():
    print(f"{server_name}: {len(tools)} tool(s)")
    # Show first 3 tools as preview
```

---

## Adding New MCP Servers

### Adding SDK MCP Server

1. **Create server file**: `bassi/mcp_servers/<name>_server.py`
   ```python
   from claude_agent_sdk import create_sdk_mcp_server, tool
   
   @tool("tool_name", "description", {"param": type})
   async def my_tool(args: dict) -> dict:
       # Implementation
       return {"content": [{"type": "text", "text": result}]}
   
   def create_<name>_mcp_server():
       return create_sdk_mcp_server(
           name="<name>",
           version="1.0.0",
           tools=[my_tool]
       )
   ```

2. **Export from init**: `bassi/mcp_servers/__init__.py`
   ```python
   from bassi.mcp_servers.<name>_server import create_<name>_mcp_server
   
   __all__ = [
       "create_bash_mcp_server",
       "create_web_search_mcp_server",
       "create_<name>_mcp_server",  # Add this
   ]
   ```

3. **Register in agent**: `bassi/agent.py` __init__
   ```python
   from bassi.mcp_servers import create_<name>_mcp_server
   
   self.sdk_mcp_servers = {
       "bash": create_bash_mcp_server(),
       "web": create_web_search_mcp_server(),
       "<name>": create_<name>_mcp_server(),  # Add this
   }
   ```

4. **Add to allowed tools**: `bassi/agent.py` __init__
   ```python
   allowed_tools = [
       "mcp__bash__execute",
       "mcp__web__search",
       "mcp__<name>__<tool_name>",  # Add this
   ]
   ```

5. **Update system prompt**: `bassi/agent.py` SYSTEM_PROMPT
   ```python
   SYSTEM_PROMPT = """
   ...
   - mcp__<name>__<tool_name>: Description
   ...
   """
   ```

6. **Test**: Create test in `tests/test_agent.py`

### Adding External MCP Server

1. **Update .mcp.json**:
   ```json
   {
     "mcpServers": {
       "myserver": {
         "command": "npx",
         "args": ["@org/my-mcp-server"],
         "env": {
           "API_KEY": "${MY_API_KEY:-}"
         }
       }
     }
   }
   ```

2. **Add environment variables**: `.env`
   ```
   MY_API_KEY=your_key_here
   ```

3. **Update allowed tools**: `bassi/agent.py` __init__
   ```python
   if "myserver" in self.external_mcp_servers:
       allowed_tools.extend([
           "mcp__myserver__tool1",
           "mcp__myserver__tool2",
       ])
   ```

4. **Update system prompt**: Document tool usage

5. **Test**: Manual testing with agent

---

## Tool Execution Flow

### How Tools Are Called

```
User: "Search for Python documentation"
  ↓
Agent system prompt says: "Use mcp__web__search for web searches"
  ↓
Claude decides: "I should call mcp__web__search with query='Python documentation'"
  ↓
SDK MCP Infrastructure:
  - Formats request as MCP message
  - Routes to appropriate server (SDK or subprocess)
  
For SDK Server (bash, web):
  - Direct function call
  - async def bash_execute(args)
  - Returns result
  
For External Server (ms365, playwright):
  - Subprocess communication via stdin/stdout
  - MCP protocol message format
  - Subprocess responds with result
  
  ↓
SDK collects result
  ↓
Agent receives: UserMessage with ToolResultBlock
  ↓
Agent reads result and continues response generation
```

### Error Handling

**SDK Server Errors**:
```python
try:
    # Tool implementation
except Exception as e:
    return {
        "content": [{"type": "text", "text": f"ERROR: {e}"}],
        "isError": True
    }
```

**External Server Errors**:
- Subprocess communication errors logged
- SDK returns error message to agent
- Agent can retry or explain error

---

## Tool Interaction Patterns

### Sequential Tool Calls

```
User: "Find Python files and show their count"
  ↓
Agent:
  1. Call mcp__bash__execute with "find . -name '*.py' | wc -l"
  2. Receive result: "42 Python files"
  3. Continue response
```

### Tool + Tool Composition

```
User: "Search for latest AI news and tell me about it"
  ↓
Agent:
  1. Call mcp__web__search with "latest AI news 2025"
  2. Receive results
  3. Use those results in response
  (Note: Bash not used, but could be)
```

### Tool Parallelization

(Handled by SDK internally - agent decisions are sequential, but SDK may optimize)

---

## Testing MCP Servers

### Unit Tests

```python
# tests/test_agent.py

def test_agent_has_mcp_servers():
    agent = BassiAgent()
    
    # Check SDK servers
    assert "bash" in agent.sdk_mcp_servers
    assert "web" in agent.sdk_mcp_servers
    
    # Check tools are allowed
    assert "mcp__bash__execute" in agent.options.allowed_tools
    assert "mcp__web__search" in agent.options.allowed_tools

def test_mcp_server_registration():
    agent = BassiAgent()
    
    # Check external servers if configured
    if "ms365" in agent.external_mcp_servers:
        assert "mcp__ms365__login" in agent.options.allowed_tools
```

### Integration Tests

```python
# Requires API key, typically skipped

async def test_bash_execution():
    agent = BassiAgent()
    result = await agent.chat("Run: echo hello")
    # Check result contains "hello"
```

---

## Performance Considerations

### SDK MCP Servers (In-Process)

- **Pros**: No subprocess overhead, immediate execution
- **Cons**: Blocks event loop (use async carefully)
- **Use for**: Simple, synchronous operations (bash, web search)

### External MCP Servers (Subprocess)

- **Pros**: Language-agnostic, isolated, handles own async
- **Cons**: Subprocess overhead, communication latency
- **Use for**: Complex operations (browser, APIs with auth)

### Optimization

- Bash commands: Generally fast (<1s)
- Web search: Network-bound (2-5s typical)
- MS365: Depends on API, usually <2s
- Playwright: Varies widely (2-10s), headless is fast

---

## Debugging MCP Servers

### Log File

**Location**: `bassi_debug.log`

**MCP-related logs**:
```
[INFO] 📦 Loaded external MCP server: ms365
[INFO]    Command: npx
[INFO]    Args: ['-y', '@softeria/ms-365-mcp-server']
[INFO]    Env vars: ['MS365_MCP_CLIENT_ID', 'MS365_MCP_CLIENT_SECRET', ...]
```

### Enable Debug Mode

```bash
export BASSI_DEBUG=1
./run-agent.sh
```

**Debug logs include**:
- MCP server initialization
- Tool calls and arguments
- Results and errors
- Message types and content

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Tool not found | Not in allowed_tools | Add to allowed_tools list |
| Permission denied | External server not executable | Check .mcp.json syntax |
| API key error | ${VAR} not substituted | Check .env has API key |
| Subprocess error | External server crash | Check subprocess logs |
| Timeout | Long operation | Increase timeout or optimize |

---

## Summary

**MCP Servers** are the bridge between Claude and tools:

- **SDK Servers**: Fast, simple, Python-based (bash, web)
- **External Servers**: Complex, isolated, language-agnostic (ms365, playwright)
- **Configuration**: `.mcp.json` for external, code for SDK
- **Execution**: Transparent to user, handled by SDK
- **Naming**: `mcp__<server>__<tool>` convention
- **Addition**: Well-defined patterns for both types

Architecture is **extensible and production-ready** for all planned features.

