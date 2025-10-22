# bassi - Benno's Personal Assistant

A personal AI agent that helps you get things done using the computer:
- Finds and uses files on computer
- Executes bash commands
- Searches the web for current information
- Plans and executes multi-step tasks

**Future capabilities**: emails, calendar, web browser

## Quick Start

### 1. Install Dependencies

```bash
# Install UV package manager (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync
```

### 2. Configure

Create `.env` file with your API keys:
```bash
cp .env.example .env
# Edit .env and add:
# ANTHROPIC_API_KEY=your_anthropic_key_here
# TAVILY_API_KEY=your_tavily_key_here  (optional, for web search)
```

Get your API keys:
- Anthropic: https://console.anthropic.com/
- Tavily: https://www.tavily.com/ (1,000 free searches/month)

Make scripts executable:
```bash
chmod +x check.sh run-agent.sh
```

### 3. Run

```bash
# Start bassi
uv run bassi

# Or with logging
./run-agent.sh
```

## Features

- 🤖 **AI-Powered**: Claude for intelligent task execution
- 💬 **Conversational**: Natural language dialog
- 🎨 **Rich CLI**: Colorful terminal output with beautiful panels
- 🔧 **Tool Use**: Bash commands (fd, rg, find, grep, etc.) and web search
- 🐍 **Python Automation**: Execute Python code for batch processing tasks
- 🌐 **Web Search**: Search the web for current information using Tavily API
- 📡 **STREAMING**: Responses appear in real-time as they're generated!
- ⏳ **Status Lines**: Always see what's happening - no silent waiting!
  - `⏳ CALLING API...........` during API calls
  - `⚡ EXECUTING BASH: cmd` during bash execution
  - `🔍 SEARCHING WEB: query` during web search
- 🔍 **Verbose Mode**: `/alles_anzeigen` shows all tool calls in detail (ON by default)
- ⌨️ **Command Help**: Type `/` to see all available commands
- ⚙️ **Configurable**: Settings in `~/.bassi/config.json`

## Commands

Type `/` to see all available commands:
- `/` - Show command list
- `/help` - Detailed help with examples
- `/alles_anzeigen` - Toggle verbose mode (show all tool calls)
- `/config` - Show configuration
- `/reset` - Reset conversation
- `/quit` - Exit bassi

## Usage Examples

```bash
# File operations
find all python files modified today
what's in my downloads folder?
create a backup script for my documents

# Web search
what's the current weather in Berlin?
search for latest Python 3.12 features
find recent news about AI developments

# Python automation (NEW!)
compress all PNG images in ~/Pictures/vacation/ to 70% quality
rename all files in Downloads to include their creation date
convert contacts.csv to JSON format
find all TODO comments in Python files and create a report

# Verbose mode
> /alles_anzeigen
✅ Verbose Modus AN - Zeige alle Tool-Aufrufe

# Now all tool calls are shown with details:
# - Bash commands with exit codes and output
# - Web search results with URLs and snippets
# - Python code execution with full output
# - File search with all matches
# - Full JSON input/output for debugging
```

## Configuration

Edit `~/.bassi/config.json`:
```json
{
  "root_folders": ["/Users/benno/Documents", "/Users/benno/projects"],
  "log_level": "INFO",
  "max_search_results": 50,
  "tavily_api_key": "your_tavily_key_here"
}
```

**Note**: API keys can be set either in `.env` file or in `~/.bassi/config.json`

## Development

```bash
# Run tests
uv run pytest

# Run quality checks (format, lint, type check, test)
./check.sh

# Add dependencies
uv add package-name
```

## Project Structure

```
bassi/              # Main package
├── main.py         # CLI entry point
├── agent.py        # Anthropic API integration
├── config.py       # Configuration manager
└── tools/          # Agent tools
    ├── bash_tool.py      # Bash command execution
    └── web_search_tool.py # Web search via Tavily API
tests/              # Tests
docs/               # Documentation
    ├── features_concepts/ # Feature documentation
    └── ...
```

## Roadmap

### ✅ Iteration 1 (Completed)
- CLI dialog with agent
- Bash command execution (including fd/rg for fast file search)
- Real-time streaming responses
- Status bar with live updates

### ✅ Iteration 2 (Completed - Current)
- Web search using Tavily API
- AI-optimized search results
- 1,000 free searches per month

### Future Iterations
- Email (O365)
- Calendar
- Browser automation
- Task scheduling
- Python script creation and execution

## Tech Stack

- Python 3.11+
- Anthropic API (Claude)
- Rich (CLI)
- Pydantic (validation)
- UV (package manager)
