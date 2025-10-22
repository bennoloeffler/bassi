# Tool Approval Error Fix

## Issue
When executing bash commands, the agent was showing an approval error before successfully running the command:

```
╭──────────────── ❌ Tool Error ────────────────╮
│ This command requires approval                │
╰───────────────────────────────────────────────╯
```

Then it would succeed using `mcp__bash__execute` instead.

## Root Cause

The Claude Agent SDK provides access to **two different types of tools**:

1. **Built-in Claude Code tools**: `Bash`, `Read`, `Write`, etc.
   - These require user approval for security
   - Controlled by `permission_mode` setting
   - Available globally in Claude Code

2. **MCP Server tools**: `mcp__bash__execute`, `mcp__web__search`, etc.
   - These are our custom tools defined in MCP servers
   - Listed in `allowed_tools` configuration
   - Run without approval (within the agent's control)

**The Problem:**
The system prompt said "use bash commands" generically, so Claude tried the built-in `Bash` tool first. When that was rejected (not in `allowed_tools`), it fell back to `mcp__bash__execute` which worked.

## Solution

Updated the system prompt to be **explicit** about which tools to use:

### Before:
```python
SYSTEM_PROMPT = """
You have access to:
- bash: Execute shell commands (use fd/rg for fast file search)
- web: Search the web for current information
"""
```

### After:
```python
SYSTEM_PROMPT = """
IMPORTANT: You must use these specific tools:
- mcp__bash__execute: Execute shell commands (use fd/rg for fast file search)
- mcp__web__search: Search the web for current information

Do NOT use the built-in Bash or other tools - only use the mcp__ prefixed tools.
"""
```

## Why It Works Now

1. The system prompt explicitly instructs Claude to use `mcp__bash__execute`
2. Claude follows the instruction and calls the correct tool on the first try
3. No approval error because we're using MCP tools (in our `allowed_tools` list)
4. Clean execution without the error → success pattern

## Example Output

### Before Fix:
```
🤖 Assistant: I'll list files...

╭──────── Tool Use ────────╮
│ 🔧 Tool: Bash            │  ← Wrong tool!
╰──────────────────────────╯

╭──────── ❌ Tool Error ────────╮
│ This command requires approval │  ← Error
╰────────────────────────────────╯

╭──────── Tool Use ────────────╮
│ 🔧 Tool: mcp__bash__execute  │  ← Fallback
╰──────────────────────────────╯

╭──────── ✅ Tool Result ──────╮
│ ... files listed ...         │  ← Success
╰──────────────────────────────╯
```

### After Fix:
```
🤖 Assistant: I'll list files...

╭──────── Tool Use ────────────╮
│ 🔧 Tool: mcp__bash__execute  │  ← Correct tool first try!
╰──────────────────────────────╯

╭──────── ✅ Tool Result ──────╮
│ ... files listed ...         │  ← Success
╰──────────────────────────────╯
```

## Configuration Summary

**Agent Options:**
```python
ClaudeAgentOptions(
    mcp_servers=self.sdk_mcp_servers,  # Our custom MCP servers
    allowed_tools=[
        "mcp__bash__execute",  # ✅ Allowed (no approval needed)
        "mcp__web__search",    # ✅ Allowed (no approval needed)
    ],
    permission_mode="acceptEdits",  # Only for built-in file tools
)
```

**Available Tools:**
- ✅ `mcp__bash__execute` - Our MCP server (no approval)
- ✅ `mcp__web__search` - Our MCP server (no approval)
- ❌ `Bash` - Built-in tool (requires approval, not in allowed_tools)
- ❌ `Read`, `Write`, etc. - Built-in tools (requires approval based on permission_mode)

## Testing
- ✅ No approval errors when running bash commands
- ✅ Direct execution without fallback
- ✅ All quality checks pass

## Files Changed
- `bassi/agent.py` - Updated `SYSTEM_PROMPT` to specify MCP tools explicitly
