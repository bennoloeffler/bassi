# bassi - Benno's Personal Assistant

Personal assistant using Claude API. Executes bash commands, searches web, manages Microsoft 365 services, automates browser tasks, queries databases.

## Features

- 🔍 **Find & Process Files**: Search, read, modify files
- 💻 **Execute Commands**: Bash/shell command execution
- 🌐 **Web Search**: Search the web for current information (Tavily API)
- 📧 **Email & Calendar**: Microsoft 365 integration (Outlook, OneDrive, Excel, OneNote)
- 🌍 **Browser Automation**: Playwright integration for web scraping and testing
- 🗄️ **Database Access**: PostgreSQL queries and schema management
- 🐍 **Python Automation**: Execute Python code for batch processing, image manipulation, data transformation
- 💬 **Conversational Interface**: Natural language dialog with streaming responses
- 📊 **Rich CLI**: Terminal UI with status updates
- 🌐 **Web UI**: Browser-based interface with real-time streaming and tool visualization

---

## Quick Start

### 1. Install Dependencies

**Install UV Package Manager** (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Sync Project Dependencies**:
```bash
uv sync
```

**Make Scripts Executable**:
```bash
chmod +x check.sh run-agent.sh
```

### 2. Configure API Keys

**Create `.env` file**:
```bash
cp .env.example .env
```

**Edit `.env` and add your API keys**:
```bash
# Required
ANTHROPIC_API_KEY=sk-ant-your_key_here

# Optional: For Microsoft 365 integration (email, calendar, OneDrive)
MS365_CLIENT_ID=<azure-app-client-id>
MS365_TENANT_ID=<azure-tenant-id>
MS365_CLIENT_SECRET=<azure-client-secret>
MS365_USER=your-email@domain.com

# Optional: Debug mode
LOG_LEVEL=DEBUG
```

**Get Your API Keys**:
- **Anthropic**: https://console.anthropic.com/
- **Tavily**: https://www.tavily.com/ (for web search, 1000 free searches/month)
- **Microsoft 365**: See [Azure AD Setup Guide](docs/features_concepts/azure_ad_setup.md)

### 3. Run bassi

**CLI Mode** (default):
```bash
# Start bassi CLI
uv run bassi

# Or with logging to file
./run-agent.sh
```

**Web UI Mode** (new!):
```bash
# Start web UI only
uv run bassi --web --no-cli

# Start web UI + CLI (both interfaces)
uv run bassi --web

# Custom port
uv run bassi --web --port 9000
```

The web UI provides:
- 🌐 **Browser-based interface** at http://localhost:8765
- 📱 **Responsive design** - works on desktop and mobile
- ✨ **Real-time streaming** markdown responses
- 🔧 **Pretty-printed tool calls** with syntax highlighting
- 💰 **Usage statistics** - tokens, cost, duration

### 4. First Commands to Try

```bash
# Basic interaction
> hello

# File operations
> find all python files modified today
> what's in my downloads folder?

# Web search
> what's the current weather in Berlin?
> search for latest AI news

# Python automation
> compress all PNG images in ~/Pictures/vacation/ to 70% quality
> convert contacts.csv to JSON format
```

### Available MCP Tools

bassi integrates 7 MCP servers:

#### 1. Built-in Tools (Always Available)

| Tool | Purpose | Examples |
|------|---------|----------|
| **Bash Execution** | Execute shell commands | `ls -la`, `find`, `grep`, `git status` |
| **Web Search** | Search the web (Tavily API) | Current events, weather, prices, research |
| **Python Tasks** | Execute Python code in isolation | Image processing, data transformation, file batch operations |

#### 2. Microsoft 365 (ms365 MCP Server)

**Authentication** (6 tools):
- `login` - Authenticate with device code flow
- `logout` - Sign out from Microsoft account
- `verify-login` - Check authentication status
- `list-accounts` - List all available accounts
- `select-account` - Switch between accounts
- `remove-account` - Remove account from cache

**OneDrive** (6 tools):
- `list-folder-files` - List files in folder
- `download-onedrive-file-content` - Download file
- `upload-file-content` - Upload file
- `delete-onedrive-file` - Delete file
- `get-drive-root-item` - Get root folder info
- `list-drives` - List all drives

**Outlook Mail** (11 tools):
- `list-mail-folders` - Get mail folder collection
- `list-mail-messages` - List messages in mailbox
- `list-mail-folder-messages` - List messages in specific folder
- `create-draft-email` - Create draft email
- `get-mail-message` - Get specific message
- `delete-mail-message` - Delete message
- `send-mail` - Send email
- `list-mail-attachments` - List attachments
- `add-mail-attachment` - Add attachment
- `get-mail-attachment` - Get attachment info
- `move-mail-message` - Move message to folder

**Calendar** (11 tools):
- `list-calendars` - Get all user calendars
- `list-calendar-events` - List events in default calendar
- `list-specific-calendar-events` - List events in specific calendar
- `create-calendar-event` - Create event in default calendar
- `create-specific-calendar-event` - Create event in specific calendar
- `get-calendar-event` - Get event details
- `get-specific-calendar-event` - Get specific calendar event
- `update-calendar-event` - Update event
- `update-specific-calendar-event` - Update specific calendar event
- `delete-calendar-event` - Delete event
- `get-calendar-view` - Get calendar view with date range

**Contacts** (5 tools):
- `list-outlook-contacts` - List all contacts
- `create-outlook-contact` - Create new contact
- `get-outlook-contact` - Get contact details
- `update-outlook-contact` - Update contact
- `delete-outlook-contact` - Delete contact

**Excel** (5 tools):
- `list-excel-worksheets` - List worksheets in workbook
- `create-excel-chart` - Create chart
- `format-excel-range` - Format cell range
- `sort-excel-range` - Sort data range
- `get-excel-range` - Get cell range data

**OneNote** (5 tools):
- `list-onenote-notebooks` - List all notebooks
- `list-onenote-notebook-sections` - List sections in notebook
- `create-onenote-page` - Create new page
- `get-onenote-page-content` - Get page HTML content
- `list-onenote-section-pages` - List pages in section

**Planner & To-Do** (11 tools):
- `list-planner-tasks` - List planner tasks assigned to user
- `get-planner-plan` - Get plan details
- `list-plan-tasks` - List tasks in plan
- `create-planner-task` - Create planner task
- `get-planner-task` - Get task details
- `update-planner-task` - Update task
- `update-planner-task-details` - Update task details
- `list-todo-task-lists` - List to-do lists
- `list-todo-tasks` - List tasks in to-do list
- `create-todo-task` - Create to-do task
- `get-todo-task` - Get to-do task details
- `update-todo-task` - Update to-do task
- `delete-todo-task` - Delete to-do task

**Other** (2 tools):
- `get-current-user` - Get current user info
- `search-query` - Search across Microsoft 365

#### 3. Browser Automation (playwright MCP Server)

**Navigation** (21 tools):
- `browser_navigate` - Navigate to URL
- `browser_navigate_back` - Go back in history
- `browser_tabs` - List/create/close/select tabs
- `browser_close` - Close current page
- `browser_wait_for` - Wait for text to appear

**Interaction**:
- `browser_click` - Click element
- `browser_type` - Type text into element
- `browser_hover` - Hover over element
- `browser_drag` - Drag and drop elements
- `browser_press_key` - Press keyboard key
- `browser_select_option` - Select dropdown option
- `browser_fill_form` - Fill multiple form fields
- `browser_file_upload` - Upload files

**Information**:
- `browser_snapshot` - Capture accessibility snapshot
- `browser_take_screenshot` - Take screenshot
- `browser_console_messages` - Get console logs
- `browser_network_requests` - Get network requests
- `browser_handle_dialog` - Handle alert/confirm dialogs

**Advanced**:
- `browser_evaluate` - Execute JavaScript
- `browser_resize` - Resize browser window
- `browser_install` - Install browser

#### 4. Database (postgresql MCP Server)

**Query Operations** (8 tools):
- `read_query` - Execute SELECT queries
- `write_query` - Execute INSERT/UPDATE/DELETE
- `export_query` - Export results to CSV/JSON

**Schema Management**:
- `list_tables` - List all tables
- `describe_table` - View table schema
- `create_table` - Create new table
- `alter_table` - Modify table structure
- `drop_table` - Delete table (with confirmation)

**Analytics**:
- `append_insight` - Add business insight to memo
- `list_insights` - List all insights

---

## Commands

Type `/` or `//` to see the interactive command menu, or use these commands directly:

| Command | Description |
|---------|-------------|
| `/` or `//` | Show interactive command selector |
| `/help` | Detailed help with usage examples |
| `/alles_anzeigen` | Toggle verbose mode (show all tool calls) |
| `/config` | Display current configuration |
| `/edit` | Open $EDITOR for multiline input |
| `/reset` | Reset conversation context |
| `/quit` or `/exit` | Exit bassi |

**Note**: Commands are case-insensitive.

---

## Usage Examples

### File & System Operations

```bash
# Search for files
> find all python files modified today
> search for files containing "TODO" in ~/projects

# File information
> what's in my downloads folder?
> show me the largest files in ~/Documents

# System commands
> what's my current git status?
> show me disk usage
> list running processes using port 8080
```

### Web Search

```bash
# Current information
> what's the current weather in Berlin?
> find the latest Python 3.12 release notes
> search for Claude AI API pricing

# Research
> what are the best practices for Python async programming?
> find recent news about quantum computing
```

### Python Automation

```bash
# Image processing
> compress all PNG images in ~/Pictures/vacation/ to 70% quality
> convert all JPEGs to WebP format
> resize all images to 800px width

# File organization
> rename all files in Downloads to include their creation date
> organize photos by date into folders
> remove duplicate files in ~/Documents

# Data transformation
> convert contacts.csv to JSON format
> merge all CSV files in ~/data into one
> extract email addresses from all text files

# Text processing
> find all TODO comments in Python files and create a report
> replace "old_name" with "new_name" in all markdown files
> count word frequency in all text files
```

### Email & Calendar (Microsoft 365)

**Note**: Requires MS365 authentication (see Azure AD setup guide)

```bash
# Email
> list my recent emails
> show me unread emails
> create a draft email to john@example.com

# Calendar
> what's on my calendar today?
> show me all events this week
> list my calendars

# Contacts
> list my outlook contacts
> show contacts containing "Schmidt"
```

### OneDrive & Documents

**Note**: Requires MS365 authentication

```bash
# OneDrive
> list files in my OneDrive root folder
> show me what drives I have access to
> list files in OneDrive/Documents

# Operations require specific file paths:
# > download budget.xlsx from OneDrive
# > upload report.pdf to OneDrive/Documents
```

### Browser Automation

**Note**: Playwright MCP server. Requires page snapshots for element interaction.

```bash
# Navigation
> open https://example.com and take a screenshot
> navigate to https://news.ycombinator.com
> take a snapshot of the current page

# Basic operations (after taking snapshot):
> click on element with uid "123"
> type "search query" into element uid "456"

# Complex operations require multiple steps:
# 1. Navigate to page
# 2. Take snapshot to get element UIDs
# 3. Interact with specific UIDs
```

### Database Operations

**Note**: Requires PostgreSQL connection configured in `.mcp.json`

```bash
# Schema exploration
> list all tables in the database
> describe the structure of table_name
> show me the columns in users table

# Querying (requires existing tables/data)
> SELECT * FROM table_name LIMIT 10
> count rows in table_name
> export query results to CSV

# Example assumes you have configured:
# - Database host, name, user, password in .mcp.json
# - Existing database with tables
```

### Verbose Mode

```bash
# Enable verbose mode to see all tool calls
> /alles_anzeigen
✅ Verbose Modus AN - Zeige alle Tool-Aufrufe

# Now all operations show detailed information:
# - Bash commands with exit codes and full output
# - Web search with URLs and snippets
# - Python code execution with stdout/stderr
# - API calls with JSON payloads
# - Database queries with results
```

---

## Configuration

### Environment Variables (.env)

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-your_key_here

# Optional: Microsoft 365 Integration
MS365_CLIENT_ID=<azure-client-id>
MS365_TENANT_ID=<azure-tenant-id>
MS365_CLIENT_SECRET=<azure-client-secret>
MS365_USER=your-email@domain.com

# Optional: Debugging
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
BASSI_DEBUG=1    # Enable debug mode
```

### Config File (~/.config/bassi/config.json)

Optional configuration file for customizing bassi behavior:

```json
{
  "root_folders": ["/Users/benno/Documents", "/Users/benno/projects"],
  "log_level": "INFO",
  "max_search_results": 50
}
```

### MCP Server Configuration (.mcp.json)

bassi uses the Model Context Protocol (MCP) to integrate external tools. The configuration is in `.mcp.json`:

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
        "--database", "your_database",
        "--user", "postgres",
        "--password", "your_password"
      ]
    }
  }
}
```

**Note**: MCP servers are launched automatically by bassi when needed.

---

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_agent.py

# Run with coverage
uv run pytest --cov=bassi

# Watch mode (auto-rerun on changes)
uv run pytest-watch
```

### Quality Checks

Run the comprehensive quality assurance pipeline:

```bash
./check.sh
```

This runs:
1. **black** - Code formatting (78 char lines)
2. **ruff** - Linting with auto-fix
3. **mypy** - Type checking
4. **pytest** - All tests

### Development Workflow

```bash
# 1. Make your changes
vim bassi/agent.py

# 2. Run quality checks
./check.sh

# 3. Run application
./run-agent.sh

# 4. View logs
tail -f bassi_debug.log
```

### Adding Dependencies

```bash
# Add new package
uv add package-name

# Add dev dependency
uv add --dev package-name

# Update all dependencies
uv sync --upgrade

# Remove package
uv remove package-name
```

### Debugging

```bash
# Enable debug logging
BASSI_DEBUG=1 ./run-agent.sh

# View recent logs
tail -n 300 bassi_debug.log

# Follow logs in real-time
tail -f bassi_debug.log

# Check configuration
uv run bassi
> /config
```

---

## Project Structure

```
bassi/
├── bassi/                           # Main package
│   ├── __init__.py                  # Package initialization
│   ├── main.py                      # CLI entry point (521 lines)
│   ├── agent.py                     # Core agent logic (798 lines)
│   ├── config.py                    # Configuration manager (131 lines)
│   └── mcp_servers/                 # Built-in MCP servers
│       ├── __init__.py              # Server registry
│       ├── bash_server.py           # Bash command execution
│       ├── web_search_server.py     # Web search integration
│       └── task_automation_server.py # Python task automation
│
├── tests/                           # Test suite
│   ├── conftest.py                  # Pytest fixtures
│   ├── test_agent.py                # Agent tests
│   ├── test_config.py               # Configuration tests
│   ├── test_key_bindings.py         # CLI interaction tests
│   ├── test_verbose.py              # Verbose mode tests
│   ├── test_task_automation.py      # Task automation tests
│   └── test_task_automation_integration.py
│
├── docs/                            # Documentation
│   ├── vision.md                    # Project vision & roadmap
│   ├── design.md                    # Architecture & design
│   ├── requirements.md              # Technical requirements
│   └── features_concepts/           # Feature documentation
│       ├── permissions.md
│       ├── o365_authentication.md
│       ├── context_persistence.md
│       ├── task_automation.md
│       ├── web_search.md
│       ├── verbose_mode.md
│       └── [15+ more feature docs...]
│
├── _DATA_FROM_USER/                 # User-provided files
├── _DOWNLOADS_FROM_AGENT/           # Agent downloads
├── _RESULTS_FROM_AGENT/             # Agent outputs
├── _SCRIPTS_FROM_AGENT/             # Generated scripts
│
├── .mcp.json                        # MCP server configuration
├── .env.example                     # Environment variables template
├── pyproject.toml                   # Project metadata & dependencies
├── README.md                        # This file
├── CLAUDE.md                        # Claude Code instructions
├── CLAUDE_BBS.md                    # Design principles
├── check.sh                         # QA pipeline script
└── run-agent.sh                     # Launch script with logging
```

---

## Architecture

bassi is built on the **Claude Agent SDK** and **Model Context Protocol (MCP)**:

```
┌─────────────────────────────────────────┐
│           CLI (main.py)                  │
│  - User input, commands, formatting      │
│  - Status updates, progress              │
└────────────────┬────────────────────────┘
                 │
┌─────────────────────────────────────────┐
│      BassiAgent (agent.py)               │
│  - Streaming responses                   │
│  - Context management                    │
│  - Session persistence                   │
│  - Token tracking & compaction           │
└────────────────┬────────────────────────┘
                 │
        ┌────────┴────────┬──────────────┐
        │                 │              │
    Built-in MCP     External MCP      Claude
    Servers          Servers            Agent SDK
    - Bash           - MS365            Client
    - Web Search     - Playwright       │
    - Python Tasks   - PostgreSQL       │
                                        │
                              ┌─────────▼─────────┐
                              │  Anthropic API    │
                              │  (Claude Sonnet)  │
                              └───────────────────┘
```

### Key Components

- **CLI (main.py)**: Terminal interface, command handling, user interaction
- **BassiAgent (agent.py)**: Core agent logic, streaming, context management
- **ConfigManager (config.py)**: Configuration loading and validation
- **MCP Servers**: Tool implementations (bash, web search, task automation)
- **Claude Agent SDK**: Client library for Anthropic API
- **External MCP Servers**: Microsoft 365, Playwright, PostgreSQL

---

## Tech Stack

- **Python 3.11+** - Core language
- **Claude Agent SDK** (`claude-agent-sdk`) - Agent framework
- **Anthropic API** - Claude Sonnet 4.5 model
- **Rich** - Terminal UI and formatting
- **Pydantic** - Data validation and settings
- **Model Context Protocol (MCP)** - Tool integration framework
- **prompt-toolkit** - Advanced terminal input
- **UV** - Fast Python package manager

### External Integrations

- **Microsoft Graph API** (`msgraph-sdk`) - Microsoft 365 access
- **Azure Identity** (`azure-identity`) - OAuth2 authentication
- **Pillow** - Image processing
- **pandas** - Data manipulation
- **Playwright** (via MCP) - Browser automation
- **PostgreSQL** (via MCP) - Database access

---

## Roadmap

### ✅ Completed Features

- [x] CLI dialog with streaming responses
- [x] Bash command execution
- [x] Web search integration
- [x] Context persistence & auto-save
- [x] Python task automation
- [x] Microsoft 365 integration (email, calendar, OneDrive, Excel, OneNote)
- [x] Browser automation (Playwright)
- [x] Database access (PostgreSQL)
- [x] Verbose mode for debugging
- [x] Session resumption
- [x] Dynamic tool discovery
- [x] Token tracking & auto-compaction

### 🚧 In Progress

- [ ] Task scheduling with timers (Iteration 6)
- [ ] Database schema reading & SQL generation (Iteration 11)
- [ ] Advanced browser testing scenarios

### 📋 Planned Features

- [ ] Custom system prompts
- [ ] History search & export
- [ ] Customizable color themes
- [ ] Multi-modal inputs (images, PDFs)
- [ ] Additional MCP integrations
- [ ] Plugin system for custom tools
- [ ] Team collaboration features

See [docs/vision.md](docs/vision.md) for detailed iteration plan.

---

## Documentation

### Quick Reference

- **README.md** (this file) - Overview, installation, usage
- **[docs/vision.md](docs/vision.md)** - Project vision & roadmap
- **[docs/design.md](docs/design.md)** - Architecture & design decisions
- **[docs/requirements.md](docs/requirements.md)** - Technical requirements

### Feature Documentation

All features are documented in `docs/features_concepts/`:

- **[permissions.md](docs/features_concepts/permissions.md)** - Permission model
- **[o365_authentication.md](docs/features_concepts/o365_authentication.md)** - Microsoft 365 auth setup
- **[context_persistence.md](docs/features_concepts/context_persistence.md)** - Session saving
- **[task_automation.md](docs/features_concepts/task_automation.md)** - Python automation
- **[web_search.md](docs/features_concepts/web_search.md)** - Web search feature
- **[verbose_mode.md](docs/features_concepts/verbose_mode.md)** - Verbose mode details
- **[dynamic_tool_discovery.md](docs/features_concepts/dynamic_tool_discovery.md)** - Tool discovery
- **[azure_ad_setup.md](docs/features_concepts/azure_ad_setup.md)** - Azure AD configuration

### Developer Guides

- **[CLAUDE.md](CLAUDE.md)** - Instructions for Claude Code
- **[CLAUDE_BBS.md](CLAUDE_BBS.md)** - Black Box Design principles

---

## Security & Privacy

- **API Keys**: Stored in `.env` file (git-ignored)
- **Command Execution**: Runs in current working directory
- **Task Isolation**: Python code runs in subprocess with timeout
- **Token Caching**: Microsoft 365 tokens cached locally
- **Context Files**: Session data stored locally with OS permissions
- **No Data Collection**: All data stays on your machine

---

## Troubleshooting

### Common Issues

**"Missing ANTHROPIC_API_KEY"**
```bash
# Solution: Add API key to .env file
echo "ANTHROPIC_API_KEY=sk-ant-your_key" >> .env
```

**Microsoft 365 authentication fails**
```bash
# Solution: Check Azure AD configuration
# See docs/features_concepts/azure_ad_setup.md
```

**MCP server fails to start**
```bash
# Solution: Install Node.js dependencies
npx -y @softeria/ms-365-mcp-server --help
npx @playwright/mcp@latest --help
```

**Tests fail**
```bash
# Solution: Run quality checks
./check.sh
```

### Getting Help

- Check documentation in `docs/`
- Run `/help` command in bassi
- View logs: `tail -f bassi_debug.log`
- Check test output: `uv run pytest -v`

---

## Contributing

Personal project. Bug reports accepted.

### Development Guidelines

1. Follow the Black Box Design principles (see CLAUDE_BBS.md)
2. Write tests for new features
3. Run `./check.sh` before committing
4. Update documentation for new features
5. Keep modules focused and reusable

---

## License

Private project for personal use.

---

## Credits

**Built with**:
- [Claude](https://www.anthropic.com/claude) by Anthropic
- [Claude Agent SDK](https://github.com/anthropics/anthropic-sdk-python)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Rich](https://rich.readthedocs.io/) for terminal formatting
- [UV](https://astral.sh/uv) for Python package management

**MCP Server Providers**:
- [@softeria/ms-365-mcp-server](https://github.com/softeria-io/ms-365-mcp-server) - Microsoft 365 integration
- [@playwright/mcp](https://github.com/microsoft/playwright-mcp) - Browser automation
- [@executeautomation/database-server](https://github.com/executeautomation/mcp-database-server) - Database access

---

Documentation: `docs/` directory or `/help` command
