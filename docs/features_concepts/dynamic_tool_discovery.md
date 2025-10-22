# Dynamic Tool Discovery

**Status**: Fully Implemented ✅
**Version**: 2.0
**Last Updated**: 2025-01-22

## Overview

Bassi uses **fully dynamic tool discovery** via the Claude Agent SDK. Tools are NOT hardcoded anywhere - instead, the SDK automatically discovers and allows all tools from configured MCP servers.

**Key Innovation**: Setting `allowed_tools=None` enables automatic tool allowlisting - no manual maintenance required!

## Architecture

### **Automatic Tool Allowlisting (`allowed_tools=None`)**

The key to fully dynamic discovery is setting `allowed_tools=None` in `ClaudeAgentOptions`:

```python
# bassi/agent.py, lines 176-187
allowed_tools = None  # Allow ALL discovered tools!

self.options = ClaudeAgentOptions(
    mcp_servers=all_mcp_servers,
    system_prompt=self.SYSTEM_PROMPT,
    allowed_tools=allowed_tools,  # None = allow all
    permission_mode="bypassPermissions",
    ...
)
```

**What This Means**:
- `allowed_tools=None` → Allow all tools from configured MCP servers
- `allowed_tools=[]` → Allow none (restrictive)
- `allowed_tools=[...]` → Allow only specific tools (manual list)

**Benefits**:
✅ Zero maintenance - add MCP servers and their tools are immediately available
✅ No hardcoded tool lists to keep in sync
✅ True "dangerously-skip-permissions" mode for MCP tools
✅ Scales effortlessly to 100+ tools

### **How It Works**

```
┌─────────────────────────────────────────────────────────────┐
│                     STARTUP SEQUENCE                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. BassiAgent initializes                                  │
│     ├─ Create SDK MCP servers (bash, web, task_automation) │
│     └─ Load external MCP servers from .mcp.json             │
│                                                              │
│  2. Agent SDK queries each MCP server                       │
│     ├─ Calls list_tools() on each server                   │
│     ├─ Collects tool schemas (name, description, params)    │
│     └─ Builds complete tool catalog                         │
│                                                              │
│  3. Tool catalog injected into Claude's context             │
│     ├─ System prompt provides high-level guidance          │
│     ├─ SDK injects detailed tool schemas automatically      │
│     └─ Claude has access to ALL discovered tools            │
│                                                              │
│  4. Display tools to user at startup                        │
│     └─ Shows complete list of available tools               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### **Tool Discovery Process**

**SDK MCP Servers** (in-process):
```python
self.sdk_mcp_servers = {
    "bash": create_bash_mcp_server(),
    "web": create_web_search_mcp_server(),
    "task_automation": create_task_automation_server(),
}
```

**External MCP Servers** (subprocess):
```json
{
  "mcpServers": {
    "ms365": {
      "command": "npx",
      "args": ["-y", "@softeria/ms-365-mcp-server"]
    },
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

**Agent SDK Integration**:
```python
ClaudeAgentOptions(
    sdk_mcp_servers=list(self.sdk_mcp_servers.values()),
    external_mcp_servers=self.external_mcp_servers,
    # SDK automatically discovers tools from all servers
)
```

---

## System Prompt Strategy: Category-Based Guidance

### **The Problem**

**❌ Old Approach (Static Tool Listing)**:
```
IMPORTANT: You must use these specific tools:
- mcp__bash__execute: Execute shell commands
- mcp__web__search: Search the web
- mcp__ms365__login: Authenticate to Microsoft 365
- mcp__ms365__verify-login: Check authentication
- mcp__ms365__list-mail-messages: Read emails
... (20+ more lines)
```

**Issues**:
- ❌ Becomes stale when tools change
- ❌ Requires manual updates for new tools
- ❌ Duplicates what SDK already provides
- ❌ Doesn't scale with many tools
- ❌ Creates documentation drift

---

### **✅ Current Approach (Category-Based + SDK Injection)**

**System Prompt Provides**:
1. **High-level categories** (File Ops, Web Search, Automation, etc.)
2. **Tool selection guidance** (when to use which category)
3. **Workflow patterns** (e.g., MS365 auth sequence)
4. **General best practices**

**Agent SDK Provides**:
1. **Complete tool catalog** with names
2. **Detailed tool descriptions**
3. **Parameter schemas** (types, required fields)
4. **Tool availability** (dynamically discovered)

---

## System Prompt Structure

### **Category Organization**

```markdown
# Tool Categories & Usage Guidelines

## 1. File Operations & System Commands
**Use: Bash tools**
- File search: fd (fast) or find (classic)
- Content search: rg (fast) or grep (classic)
- Git operations, system info, etc.

## 2. Web Information & Research
**Use: Web search tools**
- Current events, real-time data, documentation

## 3. Batch Automation & Data Processing
**Use: Python automation tools**
- Image processing, file organization, data transformation

## 4. Email & Calendar Management
**Use: MS365 tools**
⚠️ CRITICAL - Always verify-login first!

## 5. Browser Automation
**Use: Playwright tools**
- Navigate, click, type, screenshot

## 6. Database Access
**Use: Database tools (if configured)**
- SQL queries, schema introspection
```

### **Key Principles**

1. **Category, Not Tool Names**
   - "Use bash tools" NOT "Use mcp__bash__execute"
   - Scales as tools are added to categories

2. **Workflow Patterns, Not Tool Lists**
   - MS365 auth sequence (verify → login → use)
   - File organization conventions

3. **Trust the SDK**
   - "The Agent SDK provides complete tool schemas"
   - Claude discovers actual tools dynamically

4. **Minimal Maintenance**
   - Only update for NEW categories
   - Individual tools don't need prompt changes

---

## Startup Tool Display

### **Purpose**

Give users visibility into **exactly which tools** are available in their configuration.

### **Format**

```
╭──────────────────────────────────────────────────────────────╮
│ 🔧 Available MCP Servers & Tools                             │
╰──────────────────────────────────────────────────────────────╯

📦 SDK MCP Servers (in-process):
  • bash
  • web
  • task_automation

🌐 External MCP Servers:
  • ms365
    Command: npx -y @softeria/ms-365-mcp-server
  • playwright
    Command: npx @playwright/mcp@latest

📋 Total Available Tools: 16
  • Bash: 1 tool(s)
    → execute
  • Ms365: 6 tool(s)
    → create-calendar-event
    → list-calendar-events
    → list-mail-messages
    → login
    → send-mail
    → verify-login
  • Playwright: 8 tool(s)
    → browser_click
    → browser_close
    → browser_hover
    → browser_navigate
    → browser_screenshot
    → browser_scroll
    → browser_select
    → browser_type
  • Task Automation: 1 tool(s)
    → execute_python
  • Web: 1 tool(s)
    → search
```

### **Implementation**

The display is **fully dynamic**:
- Parses `allowed_tools` from Agent SDK options
- Groups by server using tool naming convention (`mcp__<server>__<tool>`)
- Shows ALL tools, not just a sample
- Color-codes SDK vs external servers
- Updates automatically when configuration changes

---

## Benefits

### **For Users**

✅ **Always Accurate** - Tool list reflects reality
✅ **Full Visibility** - See exactly what's available
✅ **Easy to Understand** - Grouped by server and purpose
✅ **Configuration Aware** - Shows only configured tools

### **For Developers**

✅ **Zero Maintenance** - No prompt updates needed for new tools
✅ **Scalable** - Works with 10 or 100 tools
✅ **Flexible** - Add/remove servers without code changes
✅ **Self-Documenting** - Display explains tool organization

### **For Claude**

✅ **Complete Context** - SDK provides full tool catalog
✅ **High-Level Guidance** - Knows when to use which category
✅ **Detailed Schemas** - Has exact parameter requirements
✅ **Dynamic Discovery** - Works with any tool configuration

---

## Adding New Tools

With `allowed_tools=None`, adding tools is incredibly simple:

### **SDK MCP Server** (in-process)

1. Create server: `bassi/mcp_servers/new_server.py`
2. Use `@tool` decorator pattern
3. Register in `agent.py`:
   ```python
   self.sdk_mcp_servers = {
       # ... existing servers
       "new_server": create_new_server(),
   }
   ```
4. **That's it!**
   - Tools automatically discovered by SDK
   - Automatically allowed (no `allowed_tools` list to update!)
   - Claude has immediate access

### **External MCP Server** (subprocess)

1. Add to `.mcp.json`:
   ```json
   {
     "mcpServers": {
       "new_server": {
         "command": "npx",
         "args": ["-y", "some-mcp-package"]
       }
     }
   }
   ```
2. **That's it!**
   - Server starts automatically
   - Tools automatically discovered by SDK
   - Automatically allowed (no code changes needed!)
   - Claude has immediate access

### **System Prompt Updates**

**Only needed if**:
- Adding a NEW category (e.g., "Video Processing")
- Changing workflow patterns (e.g., auth sequence)
- Adding general guidance

**NOT needed for**:
- Individual tool additions (automatic!)
- Individual tool removals (automatic!)
- Tool parameter changes (SDK handles it!)
- Tool description updates (SDK handles it!)

---

## Tool Naming Convention

All tools follow the pattern:
```
mcp__<server_name>__<tool_name>
```

**Examples**:
- `mcp__bash__execute`
- `mcp__web__search`
- `mcp__task_automation__execute_python`
- `mcp__ms365__list-mail-messages`
- `mcp__playwright__browser_navigate`

This convention enables:
- Automatic grouping by server
- Namespace isolation (no tool name conflicts)
- Clear tool ownership
- Dynamic parsing for display

---

## Testing Dynamic Discovery

### **Verify Tool List**

```bash
# Start bassi
./run-agent.sh

# Check startup output shows ALL tools
# Should see:
# - All SDK servers listed
# - All external servers listed
# - Total tool count
# - Tools grouped by server with full names
```

### **Verify Claude Has Access**

```bash
# In bassi chat:
> what tools do you have available?

# Claude should describe ALL discovered tools
# Not just the ones in the system prompt
```

### **Add a New Tool**

```bash
# Add new SDK server
# bassi/mcp_servers/test_server.py

# Register in agent.py
# Restart bassi

# New tool should appear in startup display
# Claude should immediately have access
# No prompt changes needed
```

---

## Related Documentation

- **Agent Architecture**: `ARCHITECTURE_OVERVIEW.md`
- **MCP Server Patterns**: `MCP_SERVER_ARCHITECTURE.md`
- **Design Philosophy**: `docs/design.md`

---

## Future Enhancements

1. **Tool Search Command**
   - `/tools search <keyword>` to find relevant tools
   - Filter by category, server, or description

2. **Tool Help Command**
   - `/tool <name>` to show detailed tool schema
   - Display parameters, types, examples

3. **Tool Usage Analytics**
   - Track which tools are used most
   - Identify unused tools
   - Optimize tool descriptions

4. **Dynamic Prompt Injection**
   - Generate tool category hints from server metadata
   - Automatic prompt updates based on tool usage patterns

---

**Document Status**: Complete
**Next Review**: After adding 5+ new tool categories
