# MCP Integration

## Overview

Bassi integrates Model Context Protocol (MCP) servers through the Claude Agent SDK. This allows the agent to access external tools and services like Microsoft 365, databases, and web automation.

## Architecture

```
┌─────────────────┐
│  run-web-v3.py  │ ← Loads .env file
└────────┬────────┘
         │
         ↓
┌─────────────────────────┐
│  web_server_v3.py       │
│  create_session_factory │ ← Loads .mcp.json
└────────┬────────────────┘
         │
         ↓
┌─────────────────────────┐
│  BassiAgentSession      │
│  (SessionConfig)        │ ← Passes mcp_servers to SDK
└────────┬────────────────┘
         │
         ↓
┌─────────────────────────┐
│  ClaudeSDKClient        │
│  (ClaudeAgentOptions)   │ ← Spawns MCP server subprocesses
└─────────────────────────┘
         │
         ↓
    ┌────┴────┬──────────┬────────────┐
    ↓         ↓          ↓            ↓
┌────────┐ ┌──────┐ ┌─────────┐ ┌──────────┐
│ ms365  │ │ play │ │ postgre │ │ custom   │
│ server │ │wright│ │ sql     │ │ servers  │
└────────┘ └──────┘ └─────────┘ └──────────┘
```

## Configuration Files

### 1. `.env` - Environment Variables

Located at project root: `/Users/benno/projects/ai/bassi/.env`

```bash
# Microsoft 365 credentials
MS365_CLIENT_ID=your-client-id
MS365_TENANT_ID=your-tenant-id
MS365_CLIENT_SECRET=your-client-secret
MS365_USER=user@domain.com

# Anthropic API (optional - can use Claude Code's credentials)
# ANTHROPIC_API_KEY=your-api-key
```

**Loading**: Loaded in `run-web-v3.py` using `python-dotenv` before server starts.

### 2. `.mcp.json` - MCP Server Configuration

Located at project root: `/Users/benno/projects/ai/bassi/.mcp.json`

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
    },
    "postgresql": {
      "command": "npx",
      "args": [
        "-y",
        "@executeautomation/database-server",
        "--postgresql",
        "--host", "localhost",
        "--database", "crm_data_bassi",
        "--user", "postgres",
        "--password", "somethingsecure"
      ]
    }
  }
}
```

**Loading**: Passed to `ClaudeAgentOptions` in `web_server_v3.py:create_default_session_factory()`.

## Implementation Details

### Environment Variable Loading

**File**: `run-web-v3.py`

```python
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)
```

This ensures all environment variables are available before MCP servers are spawned.

### MCP Server Loading

**File**: `bassi/core_v3/web_server_v3.py`

```python
def create_default_session_factory() -> Callable[[], BassiAgentSession]:
    def factory():
        # Load MCP servers from .mcp.json in project root
        mcp_config_path = Path(__file__).parent.parent.parent / ".mcp.json"

        if mcp_config_path.exists():
            logger.info(f"Loading MCP servers from: {mcp_config_path}")
            mcp_servers = mcp_config_path
        else:
            logger.warning(f"MCP config not found at: {mcp_config_path}")
            mcp_servers = {}

        config = SessionConfig(
            allowed_tools=["Bash", "ReadFile", "WriteFile"],
            system_prompt=None,
            permission_mode="acceptEdits",
            mcp_servers=mcp_servers,  # Path or dict
        )
        return BassiAgentSession(config)

    return factory
```

### Session Configuration Flow

1. **SessionConfig** (bassi/core_v3/agent_session.py:30-53)
   - Holds `mcp_servers: dict[str, Any] | Path | str`
   - Gets passed to `BassiAgentSession`

2. **BassiAgentSession** (bassi/core_v3/agent_session.py:67-252)
   - Converts `SessionConfig` to `ClaudeAgentOptions`
   - Passes `mcp_servers` to SDK

3. **ClaudeSDKClient** (from claude-agent-sdk package)
   - Receives `mcp_servers` parameter
   - If it's a Path/str: loads JSON config
   - If it's a dict: uses directly
   - Spawns MCP server subprocesses with environment variables

## Environment Variable Substitution

The `.mcp.json` file supports environment variable substitution using `${VAR_NAME}` syntax:

```json
"env": {
  "MS365_MCP_CLIENT_ID": "${MS365_CLIENT_ID}"
}
```

The Claude Agent SDK automatically replaces `${MS365_CLIENT_ID}` with the value from the environment.

**Flow**:
1. `run-web-v3.py` loads `.env` → environment variables set
2. SDK reads `.mcp.json` and finds `${MS365_CLIENT_ID}`
3. SDK replaces with actual value from `os.environ`
4. SDK spawns MCP server with substituted values

## Available MCP Servers

### 1. Microsoft 365 (`ms365`)

**Package**: `@softeria/ms-365-mcp-server`

**Tools**: Email, calendar, contacts management

**Configuration**: Requires Azure AD app registration with:
- Client ID
- Client Secret
- Tenant ID

**Usage in prompts**:
- "Check my emails from today"
- "Schedule a meeting tomorrow at 3pm"
- "List my contacts"

### 2. Playwright (`playwright`)

**Package**: `@playwright/mcp@latest`

**Tools**: Web browser automation, screenshot capture, form filling

**Usage in prompts**:
- "Navigate to example.com and take a screenshot"
- "Fill out the form on this page"
- "Click the login button"

### 3. PostgreSQL (`postgresql`)

**Package**: `@executeautomation/database-server`

**Tools**: Database queries, schema inspection

**Configuration**: Database connection parameters in `.mcp.json`

**Usage in prompts**:
- "List all tables in the database"
- "Query users where active = true"
- "Show the schema for the contacts table"

## Testing MCP Configuration

Run the configuration validation script:

```bash
uv run python test_mcp_config.py
```

This will:
- ✅ Check if `.mcp.json` exists
- ✅ List configured servers
- ✅ Validate environment variable substitution
- ✅ Show which environment variables are set/missing

## Adding New MCP Servers

1. **Add to `.mcp.json`**:
```json
{
  "mcpServers": {
    "my-server": {
      "command": "npx",
      "args": ["-y", "@scope/my-mcp-server"],
      "env": {
        "MY_API_KEY": "${MY_API_KEY}"
      }
    }
  }
}
```

2. **Add environment variables to `.env`**:
```bash
MY_API_KEY=your-api-key
```

3. **Restart the server**:
```bash
./run-web-v3.py
```

The MCP server will be automatically loaded and available to the agent.

## Troubleshooting

### MCP servers not loading

**Check logs**:
```bash
tail -n 100 server.log | grep -i "mcp"
```

**Verify configuration**:
```bash
uv run python test_mcp_config.py
```

### Environment variables not substituted

**Ensure `.env` is loaded**:
- Check `run-web-v3.py` has `load_dotenv()` call
- Verify `.env` file exists and has correct values
- Restart the server to reload environment

### MCP server fails to start

**Common issues**:
1. Missing Node.js or npm
2. Network issues downloading packages
3. Invalid credentials in environment variables
4. Port conflicts

**Check MCP server logs**:
The SDK will log subprocess output to stderr.

## Security Considerations

1. **Never commit `.env` to git**
   - Add `.env` to `.gitignore`
   - Use `.env.example` for templates

2. **Protect credentials**
   - Use environment variables for all secrets
   - Rotate credentials regularly
   - Use least-privilege access

3. **Database access**
   - Use read-only credentials when possible
   - Restrict database access by IP
   - Audit database queries

## Discovery: Finding Available Tools and Commands

### Built-in Discovery Method

Bassi provides a `get_server_info()` method to discover all available capabilities:

```python
# In Python code
async with BassiAgentSession(config) as session:
    info = await session.get_server_info()

    # info contains:
    # - commands: Available slash commands
    # - output_style: Current output settings
    # - capabilities: Server capabilities
    # - Available MCP tools
```

### From Web UI

Send a WebSocket message to get server info:

```javascript
// JavaScript in web UI
websocket.send(JSON.stringify({
    type: "get_server_info"
}));

// Receive response
{
    type: "server_info",
    data: {
        commands: [...],
        output_style: "...",
        capabilities: {...}
    }
}
```

### Discovery Commands

When using Bassi through the chat interface, you can ask:

- **"What tools do you have?"** - Lists all available tools
- **"Show me MCP tools"** - Shows MCP server tools
- **"What commands are available?"** - Lists slash commands
- **"List PostgreSQL tools"** - Shows tools from specific MCP server

The agent will use `get_server_info()` internally to answer.

### Testing Discovery

Run the discovery test script:

```bash
uv run python test_discovery.py
```

This will:
- Connect to Claude Code
- Call `get_server_info()`
- Display all available commands, tools, and capabilities

## References

- [Claude Agent SDK - MCP Documentation](https://docs.claude.com/en/api/agent-sdk/mcp)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [MCP Server Registry](https://github.com/modelcontextprotocol/servers)
- [Claude Code Discovery Commands](https://docs.claude.com/en/docs/claude-code/slash-commands)
