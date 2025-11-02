# Startup Discovery & Help System

## Overview

Bassi automatically discovers and displays all available capabilities when the web UI starts and when the user types `/help`.

## Features

### 1. Startup Discovery Display

When you connect to Bassi's web UI, you'll immediately see a welcome message showing:

- 📡 **MCP Servers** - All configured Model Context Protocol servers
- 💻 **Slash Commands** - Available project and personal commands
- 🎯 **Skills** - Loaded skills from `.claude/skills/`

**Example Output:**
```
🚀 Bassi is ready!

Available capabilities:

📡 3 MCP Servers
- ms365
- playwright
- postgresql

💻 3 Slash Commands
- /crm
- /epct
- /crm-analyse-customer

🎯 8 Skills
- crm-db
- xlsx
- pdf
- docx
- pptx
- skill-creator
- mcp-builder
- time-formatter

💡 Type /help to see this again!
```

### 2. /help Command

Type `/help`, `help`, or `/?` in the chat to display comprehensive help information:

**Includes:**
- List of all MCP servers with their commands
- All slash commands (project and personal)
- All available skills with their paths
- Usage examples for each capability type
- Tips for using Bassi effectively

**Example Help Output:**
```markdown
# Bassi Help

## Available Capabilities

### 📡 MCP Servers (3)
- **ms365** - npx
- **playwright** - npx
- **postgresql** - npx

### 💻 Slash Commands (3)

**Project Commands:**
- **/crm**

**Personal Commands:**
- **/epct**
- **/crm-analyse-customer**

### 🎯 Skills (8)
- **crm-db** - `/Users/benno/projects/ai/bassi/.claude/skills/crm-db`
- **xlsx** - `/Users/benno/projects/ai/bassi/.claude/skills/xlsx`
- (etc...)

## Usage

### Using MCP Tools
Ask me to perform actions using the MCP servers:
- "Show me all tables in the PostgreSQL database"
- "Check my emails from today"
- "Take a screenshot of example.com"

### Using Slash Commands
Invoke commands directly:
- `/crm Add company TechStart GmbH in Berlin`
- `/help` - Show this help

### Using Skills
I automatically load skills when needed:
- "Use the crm-db skill to query the database"
- "Create a PDF document"
- "Parse this Excel file"

## Tips
- I have full access to all tools - no permission prompts needed
- Ask me "what tools do you have?" for a quick list
- All MCP servers are automatically connected and ready
```

## Implementation

### Backend (web_server_v3.py)

#### Startup Discovery

When a WebSocket connection is established:

```python
# Send discovery info on connection
from bassi.core_v3.discovery import BassiDiscovery
discovery = BassiDiscovery(Path(__file__).parent.parent.parent)
discovery_summary = discovery.get_summary()

# Send as system message to web UI
await websocket.send_json({
    "type": "system_message",
    "content": "🚀 Bassi is ready!\n\n..." # formatted message
})
```

#### /help Command Handler

Intercepts `/help` in user messages:

```python
if content.strip().lower() in ["/help", "help", "/?"]:
    # Get fresh discovery data
    discovery = BassiDiscovery(...)
    discovery_summary = discovery.get_summary()

    # Format comprehensive help message
    help_message = f"""# Bassi Help
    ...
    """

    # Send as assistant message
    await websocket.send_json({
        "type": "assistant_message",
        "content": help_message
    })

    # Don't process further
    continue
```

### Frontend (app.js)

#### New Message Types

Added handlers for:

1. **system_message** - System notifications (startup info)
2. **assistant_message** - Direct assistant responses (help command)

```javascript
case 'system_message':
    this.handleSystemMessage(msg)
    break

case 'assistant_message':
    this.handleAssistantMessage(msg)
    break
```

#### Message Handlers

```javascript
handleSystemMessage(msg) {
    const systemEl = document.createElement('div')
    systemEl.className = 'system-message message-fade-in'
    systemEl.innerHTML = `
        <div class="system-content">
            ${this.formatMarkdown(msg.content)}
        </div>
    `
    this.conversationEl.appendChild(systemEl)
    this.scrollToBottom()
}

handleAssistantMessage(msg) {
    const assistantEl = document.createElement('div')
    assistantEl.className = 'assistant-message message-fade-in'
    assistantEl.innerHTML = `
        <div class="message-header">
            <span class="message-icon">🤖</span>
            <span>Bassi</span>
        </div>
        <div class="message-content">
            ${this.formatMarkdown(msg.content)}
        </div>
    `
    this.conversationEl.appendChild(assistantEl)
    this.scrollToBottom()
}
```

#### Markdown Formatter

Simple markdown formatting for help messages:

```javascript
formatMarkdown(text) {
    let html = this.escapeHtml(text)

    // Headers: #, ##, ###
    html = html.replace(/^### (.*$)/gm, '<h3>$1</h3>')
    html = html.replace(/^## (.*$)/gm, '<h2>$1</h2>')
    html = html.replace(/^# (.*$)/gm, '<h1>$1</h1>')

    // Bold: **text**
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

    // Italic: *text*
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')

    // Code: `code`
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>')

    // Line breaks
    html = html.replace(/\n/g, '<br>')

    return html
}
```

### Styling (style.css)

Existing styles used:

- `.system-message` - Blue background for system notifications
- `.assistant-message` - Assistant response styling
- `.message-fade-in` - Smooth fade-in animation

## Discovery Process

### On Server Startup (Terminal)

```bash
./run-web-v3.py
```

Shows in terminal:
```
======================================================================
BASSI DISCOVERY - Available Capabilities
======================================================================

📡 MCP SERVERS: 3
   • ms365
     Command: npx
     Package: @softeria/ms-365-mcp-server
   • playwright
     Command: npx
     Package: @playwright/mcp@latest
   • postgresql
     Command: npx
     Package: @executeautomation/database-server

💻 SLASH COMMANDS: 3
   Project commands (1):
   • /crm
   Personal commands (2):
   • /epct
   • /crm-analyse-customer

🎯 SKILLS: 8
   • crm-db
   • xlsx
   • pdf
   (etc...)

======================================================================
```

### On Web UI Connection

User opens browser → Connects to WebSocket → Receives system message with capabilities

### On /help Command

User types `/help` → Server intercepts → Sends formatted help → Displays in chat

## Files Modified

### Backend
- `bassi/core_v3/web_server_v3.py`
  - Added startup discovery message (lines 116-134)
  - Added /help command handler (lines 189-249)

### Frontend
- `bassi/static/app.js`
  - Added message type handlers (lines 306-312)
  - Added `handleSystemMessage()` (lines 667-678)
  - Added `handleAssistantMessage()` (lines 680-695)
  - Added `formatMarkdown()` (lines 742-764)

### Discovery Module
- `bassi/core_v3/discovery.py`
  - Provides `BassiDiscovery` class
  - Methods: `discover_mcp_servers()`, `discover_slash_commands()`, `discover_skills()`
  - Method: `get_summary()` - returns all discovered capabilities

## Usage Examples

### Startup

1. Start Bassi: `./run-web-v3.py`
2. Open browser: `http://localhost:8765`
3. See welcome message with all capabilities

### Getting Help

In the chat:
```
/help
```

OR

```
help
```

OR

```
/?
```

All trigger the same comprehensive help display.

### Asking About Tools

You can also ask naturally:
```
What tools do you have?
```

```
Show me available MCP servers
```

```
What skills are loaded?
```

The agent will use the discovery system to answer.

## Benefits

1. **Immediate Visibility** - Users see what's available right away
2. **Self-Service** - `/help` command for quick reference
3. **Always Current** - Discovery runs fresh each time
4. **No Configuration** - Automatic discovery from filesystem and config files
5. **Comprehensive** - Shows MCP servers, commands, and skills in one place

## See Also

- [MCP Integration](./mcp_integration.md) - MCP server configuration
- [CRM Command](./crm_command.md) - Example slash command usage
- [Discovery Module](../../bassi/core_v3/discovery.py) - Source code
