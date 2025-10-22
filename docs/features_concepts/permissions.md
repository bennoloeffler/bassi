# Permission Model in Bassi

## Overview

Bassi uses the Claude Agent SDK's permission system to control which operations the agent can perform. The permission model determines whether the agent needs to ask for user approval before executing tools.

## Current Configuration

**Mode**: `bypassPermissions` (Fully Autonomous)

Bassi is configured for **fully autonomous operation** - the agent executes all tools without permission prompts. This provides the best user experience for a personal assistant that you trust to:
- Read and write files
- Execute bash commands
- Search the web
- Access Microsoft 365 (email, calendar)
- Automate browser interactions

## Available Permission Modes

The Claude Agent SDK provides four permission modes:

### 1. `default` (Standard Operation)
- **Behavior**: Normal permission checks apply
- **Use Case**: Maximum safety, interactive confirmation required
- **Prompts**: User must approve each tool use
- **Best For**: Public-facing applications, untrusted environments

### 2. `acceptEdits` (Rapid Development)
- **Behavior**: Auto-approves file edits and filesystem operations
- **Auto-Approved**:
  - File edits (Edit, Write)
  - File operations (mkdir, touch, rm, mv, cp)
  - File creation/deletion
- **Still Requires Approval**:
  - Bash command execution
  - Web searches
  - MS365 operations
  - Other MCP tools
- **Best For**: Isolated development projects, safe file modifications

### 3. `bypassPermissions` (Fully Autonomous) ⭐ **CURRENT**
- **Behavior**: All tools run without permission prompts
- **Auto-Approved**: Everything!
  - File operations
  - Bash commands
  - Web searches
  - MS365 operations
  - All MCP tools
- **Safety**: Hooks can still block operations
- **Best For**: Personal assistants, trusted autonomous agents
- **⚠️ Caution**: Use only with trusted agents in controlled environments

### 4. `plan` (Planning Phase)
- **Behavior**: Read-only tools only; presents plan before execution
- **Status**: Not currently supported in SDK
- **Use Case**: Preview what agent will do before execution

## Why `bypassPermissions` for Bassi?

Bassi is configured with `bypassPermissions` because:

1. **Personal Assistant**: You're the only user, and you trust your agent
2. **Seamless UX**: No interruptions from permission prompts
3. **Autonomous Operation**: Agent can complete complex multi-step tasks independently
4. **Controlled Environment**: Running on your local machine, not a public service

### What This Means

When you ask bassi to:
- "Find my emails about the project" → Searches emails immediately ✅
- "Create a summary and save to notes.md" → Reads, writes files, no prompts ✅
- "Install the required packages" → Runs bash commands directly ✅
- "Send an email with the latest report" → Sends without asking ✅

**The agent acts immediately - no permission prompts.**

## Permission Architecture

The Claude Agent SDK uses a layered permission system (evaluated in order):

```
1. Hooks (execute first, can block tools)
   ↓
2. Deny rules (explicit blocks)
   ↓
3. Allow rules (explicit permissions)
   ↓
4. Ask rules (interactive prompts)
   ↓
5. Permission mode (default/acceptEdits/bypassPermissions)
   ↓
6. canUseTool callback (custom logic)
```

Bassi uses **permission mode** (layer 5) set to `bypassPermissions` for unrestricted operation.

## Configuration

### Code Location

`bassi/agent.py`, line 180-187:

```python
self.options = ClaudeAgentOptions(
    mcp_servers=all_mcp_servers,
    system_prompt=self.SYSTEM_PROMPT,
    allowed_tools=allowed_tools,
    permission_mode="bypassPermissions",  # Fully autonomous
    resume=resume_session_id,
    include_partial_messages=True,
)
```

### Allowed Tools

With `bypassPermissions` mode, we set `allowed_tools=None` to enable **fully dynamic tool discovery**:

```python
allowed_tools = None  # Allow ALL discovered tools from MCP servers
```

**What This Means**:
- All tools from configured MCP servers are automatically allowed
- No manual tool list maintenance required
- Add/remove MCP servers = tools automatically available/unavailable
- True "dangerously-skip-permissions" mode

**Benefits**:
✅ Zero maintenance overhead
✅ Scales effortlessly to any number of tools
✅ Automatic discovery and allowlisting
✅ No hardcoded tool lists to keep in sync

## Switching Permission Modes

If you want to change the permission mode:

### Option 1: Modify Code (Permanent)

Edit `bassi/agent.py` line 184:

```python
# For maximum safety (approve each operation)
permission_mode="default"

# For file edits only (still asks for bash/web/etc)
permission_mode="acceptEdits"

# For full autonomy (current setting)
permission_mode="bypassPermissions"
```

### Option 2: Environment Variable (Future Enhancement)

We could add an environment variable to control this:

```bash
# In .env
BASSI_PERMISSION_MODE=bypassPermissions  # or default, acceptEdits
```

Then in code:
```python
permission_mode=os.getenv("BASSI_PERMISSION_MODE", "bypassPermissions")
```

## Security Considerations

### Trust Model

`bypassPermissions` assumes:
- You trust the AI model (Claude)
- You trust your prompts/instructions
- You're running in a safe environment
- You understand the agent's capabilities

### Safety Mechanisms

Even with `bypassPermissions`, you still have safety through:

1. **MCP Server Sandboxing**: External MCP servers run in separate processes
2. **Tool Limitations**: Agent only has access to configured tools
3. **System Prompt**: Agent is instructed on appropriate behavior
4. **File System Access**: Limited to directories the agent can reach
5. **Logging**: All operations logged to `bassi_debug.log`

### When NOT to Use `bypassPermissions`

**Don't use this mode if**:
- Running a public-facing service
- Multiple users share the agent
- You don't fully trust the agent's behavior
- Operating on sensitive/production systems without backups
- You want to review each operation before execution

**Instead, use**:
- `default` mode for maximum safety
- `acceptEdits` for controlled file operations
- Custom hooks for granular control

## Comparison to Claude Code

This is similar to Claude Code's `--dangerously-skip-permissions` flag:

| Claude Code | Bassi Agent SDK | Effect |
|-------------|-----------------|--------|
| `--dangerously-skip-permissions` | `permission_mode="bypassPermissions"` | No prompts for any operations |
| Default (interactive) | `permission_mode="default"` | Ask for each operation |
| `--allowedTools Read,Bash` | `allowed_tools=["mcp__bash__execute"]` | Whitelist specific tools |

## Best Practices

### For Personal Use (Recommended)

✅ Use `bypassPermissions` for:
- Personal projects
- Trusted environments
- Autonomous task completion
- Development workflows

### For Production/Public Services

❌ Don't use `bypassPermissions` for:
- Multi-user applications
- Public APIs
- Untrusted environments
- Production systems without review

### Recommended: Start Conservative, Relax as Needed

1. **Start**: `default` mode (safest)
2. **Learn**: Observe what the agent does
3. **Trust**: Switch to `acceptEdits` when comfortable with file operations
4. **Autonomous**: Switch to `bypassPermissions` when fully confident

## Monitoring and Logging

All operations are logged regardless of permission mode:

**Log file**: `bassi_debug.log`

View recent activity:
```bash
tail -n 100 bassi_debug.log
```

Filter for specific operations:
```bash
grep "Tool:" bassi_debug.log | tail -n 20  # Last 20 tool uses
grep "ERROR" bassi_debug.log              # Errors only
```

## Future Enhancements

Potential improvements:

1. **Environment Variable Configuration**: Control permission mode via `.env`
2. **CLI Flag**: `./run-agent.sh --permission-mode=default`
3. **Interactive Mode Switching**: Switch modes during conversation
4. **Tool-Specific Permissions**: Different modes for different tool categories
5. **Audit Log**: Dedicated audit trail for all operations
6. **Rollback**: Undo/rollback mechanism for dangerous operations

## References

- [Claude Agent SDK - Permissions](https://docs.claude.com/en/api/agent-sdk/permissions)
- [Claude Code - Dangerously Skip Permissions](https://github.com/anthropics/claude-code/issues/1498)
- Claude Agent SDK Source: Permission handling implementation
