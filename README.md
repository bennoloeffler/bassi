# bassi - Benno's Personal Assistant

Web-based AI assistant powered by Claude Agent SDK with an **Agent Pool** architecture. Executes bash commands, searches web, manages Microsoft 365 services, queries databases, and more.

## Features

- **Web-Based Interface**: Real-time streaming responses in your browser
- **Agent Pool**: Pre-connected Claude agents for instant response (no startup delay)
- **Multiple Sessions**: Manage multiple chat sessions with persistent history
- **File Upload**: Upload files and images for context
- **MCP Integration**: Microsoft 365, PostgreSQL, and custom tools
- **Claude Code Compatible**: Custom skills, commands, and agents via `.claude/` directory

---

## Quick Start

### 0. Clone this repo
**go to your project directory**, then, e.g. in  
`/Users/your-name/projects/ai` type

```bash
git clone https://github.com/bennoloeffler/bassi.git
```
this will result in a folder called `bassi` in current folder, e.g.:   
`/Users/your-name/projects/ai/bassi`

go to that folder:
`cd bassi`


### 1. Install Dependencies

**Install UV Package Manager** (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Sync Project Dependencies**:
```bash
uv sync
```

### 2. Configure Environment

**Create `.env` file**:
```bash
cp .env.example .env
```

**Edit `.env` and add your configuration / API keys**:
```bash
# Required ONLY, if you have no claude code subscription...
# ANTHROPIC_API_KEY=sk-ant-your_key_here

# Optional: Agent Pool Configuration
AGENT_INITIAL_POOL_SIZE=1    # Agents to create at startup
AGENT_KEEP_IDLE_SIZE=1       # Target idle agents to maintain
AGENT_MAX_POOL_SIZE=4        # Maximum concurrent agents

# Optional: Microsoft 365 Integration
MS365_CLIENT_ID=<azure-app-client-id>
MS365_TENANT_ID=<azure-tenant-id>
MS365_CLIENT_SECRET=<azure-client-secret>
MS365_USER=your-email@domain.com

# Optional: Debug mode
LOG_LEVEL=DEBUG
```

**Get Your API Key**:
- **Anthropic**: https://console.anthropic.com/

### 3. Run bassi


**Development (with hot reload)**:
```bash
./run-agent-web.sh
```

Access the web UI at: **http://localhost:8765**

### 4. First Interaction

Open your browser to http://localhost:8765 and start chatting:

- "/help" (shows all tools available)
- "Show me emails from today and write Sales relevant info to crm-db"

### 5. Add datasources/mcp-server

Open your browser to http://localhost:8765 and start chatting:

- you can open `.mcp.json`and add mcp servers
- you may use the claude cli to do that: 
  `claude mcp add -s project `



---

## Architecture

bassi uses an **Agent Pool** architecture for fast, concurrent access:

```
Browser Tab 1  ──┐
Browser Tab 2  ──┼──►  WebSocket Server  ──►  Agent Pool  ──►  Claude API
Browser Tab 3  ──┘         │                    │
                           │                    ├── Agent 1 (pre-connected)
                      FastAPI Routes            ├── Agent 2 (pre-connected)
                           │                    ├── Agent 3 (on-demand)
                      File Upload               └── Agent N (up to max)
                      Session Mgmt
```

### Key Concepts

| Term | Description |
|------|-------------|
| **Browser Session** | Ephemeral WebSocket connection from a browser tab |
| **Chat Session** | Persistent conversation history + workspace files |
| **Agent** | Claude SDK client from the pool (pre-connected, reusable) |
| **Agent Pool** | Pool of pre-connected agents for instant response |

A browser connects, acquires an agent from the pool, and can switch between chat sessions.

---

## Project Structure

```
bassi/
├── bassi/                          # Main package
│   ├── core_v3/                    # Web application (current architecture)
│   │   ├── cli.py                  # Entry point (launches web server)
│   │   ├── web_server_v3.py        # FastAPI server with Agent Pool
│   │   ├── agent_session.py        # Claude SDK wrapper
│   │   ├── chat_workspace.py       # Chat context storage
│   │   ├── routes/                 # HTTP endpoint handlers
│   │   ├── services/               # Business logic
│   │   │   └── agent_pool.py       # Dynamic agent pool
│   │   ├── websocket/              # WebSocket handlers
│   │   └── tests/                  # Test suite (400+ tests)
│   │       ├── unit/               # Fast isolated tests
│   │       ├── integration/        # API tests with TestClient
│   │       └── e2e/                # Playwright browser tests
│   ├── static/                     # Web UI (HTML, CSS, JS)
│   ├── config.py                   # Configuration management
│   └── mcp_servers/                # Built-in MCP servers
│
├── chats/                          # Chat session storage
│   └── {chat_id}/                  # Per-session directory
│       ├── chat.json               # Metadata
│       ├── history.md              # Conversation history
│       └── DATA_FROM_USER/         # Uploaded files
│
├── .claude/                        # Claude Code configuration
│   ├── commands/                   # Custom slash commands
│   ├── skills/                     # Custom skills
│   ├── agents/                     # Custom agents
│   └── settings.local.json         # Local settings
│
├── .mcp.json                       # MCP server configuration
├── .env                            # Environment variables (git-ignored)
├── .env.example                    # Environment template
│
├── run-agent-web.sh                # Development server with hot reload
├── run-tests.sh                    # Test runner script
├── check.sh                        # QA pipeline (format, lint, test)
│
├── docs/                           # Documentation
│   ├── vision.md                   # Project vision & roadmap
│   ├── design.md                   # Architecture & design
│   └── features_concepts/          # Feature documentation
│
├── CLAUDE.md                       # Claude Code instructions
└── pyproject.toml                  # Project dependencies
```

---

## Configuration

### Environment Variables (.env)

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-your_key_here

# Agent Pool Configuration
AGENT_INITIAL_POOL_SIZE=1    # Agents created at startup (first blocks)
AGENT_KEEP_IDLE_SIZE=1       # Target idle agents (triggers background creation)
AGENT_MAX_POOL_SIZE=4        # Maximum pool size (hard limit)

# Microsoft 365 Integration
MS365_CLIENT_ID=<azure-client-id>
MS365_TENANT_ID=<azure-tenant-id>
MS365_CLIENT_SECRET=<azure-client-secret>
MS365_USER=your-email@domain.com

# Debugging
LOG_LEVEL=DEBUG
```

### MCP Server Configuration (.mcp.json)

bassi uses the Model Context Protocol (MCP) for external tool integration:

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
    "postgresql": {
      "command": "npx",
      "args": [
        "-y", "@executeautomation/database-server",
        "--postgresql",
        "--host", "localhost",
        "--database", "your_database",
        "--user", "postgres",
        "--password", "your_password"
      ]
    }
  }
}
```

### Claude Code Configuration (.claude/)

bassi integrates with Claude Code via the `.claude/` directory:

```
.claude/
├── commands/                    # Custom slash commands (*.md files)
│   ├── adresse-erstellen.md     # Create contact from text
│   ├── crm.md                   # CRM data operations
│   └── email-analysis.md        # Email analysis
│
├── skills/                      # Custom skills (directories)
│   ├── bel-crm-db/              # CRM database skill
│   ├── pdf/                     # PDF manipulation
│   ├── xlsx/                    # Excel/spreadsheet
│   ├── docx/                    # Word documents
│   └── ...                      # 17+ custom skills
│
├── agents/                      # Custom agents
│   └── bulk-archive-agent.md    # Bulk email archiving
│
└── settings.local.json          # Local settings
    {
      "permissions": {
        "allow": ["WebSearch", "WebFetch(domain:github.com)"]
      },
      "enabledMcpjsonServers": ["ms365", "postgresql"]
    }
```

---

## Development

### Running the Server

```bash
# Production mode
uv run bassi

# Development mode with hot reload
./run-agent-web.sh

# View logs
tail -f /tmp/bassi-web.log
```

Hot reload features:
- **Backend**: Auto-restarts in 2-3 seconds on Python file changes
- **Frontend**: Press F5 to reload browser after editing static files

### Running Tests

```bash
# Run all tests (unit, integration, e2e)
./run-tests.sh

# Run specific test suite
./run-tests.sh unit           # Fast isolated tests
./run-tests.sh integration    # API tests with TestClient
./run-tests.sh e2e            # Playwright browser tests

# Run with pytest directly
uv run pytest bassi/core_v3/tests/ -v

# Run with coverage
uv run pytest --cov=bassi
```

### Quality Checks

```bash
# Complete QA pipeline (format, lint, type check, test)
./check.sh

# Individual checks
uv run black .           # Format code
uv run ruff check --fix . # Lint with auto-fix
uv run mypy bassi/       # Type checking
```

### Adding Dependencies

```bash
uv add package-name          # Add runtime dependency
uv add --dev package-name    # Add dev dependency
uv sync                      # Sync all dependencies
```

---

## MCP Tools

bassi integrates multiple MCP servers for extended capabilities:

### Built-in Tools (Always Available)

| Tool | Purpose |
|------|---------|
| **Bash Execution** | Execute shell commands |
| **Web Search** | Search the web (Tavily API) |
| **Python Tasks** | Execute Python code in isolation |

### Microsoft 365 (Optional)

Requires Azure AD setup. See `docs/features_concepts/azure_ad_setup.md`.

- Email: List, read, send, draft, move messages
- Calendar: Create, update, delete events
- Contacts: Manage Outlook contacts
- OneDrive: Upload, download, list files
- OneNote: Create pages, list notebooks

### PostgreSQL (Optional)

Database queries and schema management via MCP.

---

## Tech Stack

- **Python 3.11+** - Core language
- **FastAPI** - Web framework
- **Claude Agent SDK** - Agent framework
- **Anthropic API** - Claude Sonnet 4.5 model
- **UV** - Fast Python package manager
- **Model Context Protocol (MCP)** - Tool integration
- **Playwright** - E2E testing

---

## Security & Privacy

- **API Keys**: Stored in `.env` file (git-ignored)
- **Local Data**: All chat history and files stored locally
- **No Data Collection**: Nothing sent to third parties
- **Token Caching**: Microsoft 365 tokens cached locally

---

## Troubleshooting

### Common Issues

**"Missing ANTHROPIC_API_KEY"**
```bash
echo "ANTHROPIC_API_KEY=sk-ant-your_key" >> .env
```

**Port 8765 already in use**
```bash
lsof -ti :8765 | xargs kill -9
```

**Tests fail**
```bash
./check.sh  # Run full QA pipeline
```

### Logs

```bash
# Development server log
tail -f /tmp/bassi-web.log

# Debug log
tail -f bassi_debug.log
```

---

## Documentation

- **[docs/vision.md](docs/vision.md)** - Project vision & roadmap
- **[docs/design.md](docs/design.md)** - Architecture & design
- **[docs/features_concepts/](docs/features_concepts/)** - Feature documentation
- **[CLAUDE.md](CLAUDE.md)** - Claude Code instructions

---

## License

Private project for personal use.

---

## Credits

**Built with**:
- [Claude](https://www.anthropic.com/claude) by Anthropic
- [Claude Agent SDK](https://github.com/anthropics/anthropic-sdk-python)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [UV](https://astral.sh/uv) for Python package management

**MCP Server Providers**:
- [@softeria/ms-365-mcp-server](https://github.com/softeria-io/ms-365-mcp-server)
- [@executeautomation/database-server](https://github.com/executeautomation/mcp-database-server)
- [@playwright/mcp](https://github.com/microsoft/playwright-mcp)
- [leann-mcp](https://github.com/uniAIDevs/leann)


## Plans / Ideas
- V5: have bassi within an own directory: CLAUDE.md and .mcp.json .claude/
- V6: have it on a server with backend in AZURE.
- V7: have user logins