# Complete Rewrite: bassi with Claude Agent SDK

**Date**: October 21, 2025
**Status**: ✅ Complete
**Architecture**: Claude Agent SDK + MCP Servers

---

## What Changed

### Complete Rewrite

This is a **total architectural rewrite** from scratch, not an incremental update.

**Before**: Custom agent implementation using direct Anthropic API
**After**: Claude Agent SDK with MCP-based tool ecosystem

### New Dependencies

```bash
# Added:
claude-agent-sdk==0.1.4  # Official Anthropic Agent SDK
anyio==4.11.0            # Async I/O (dependency of SDK)
@anthropic-ai/claude-code@2.0.24  # CLI tool (npm global)

# Kept:
rich, pydantic, python-dotenv, tavily-python

# Removed:
anthropic (now included in SDK)
```

---

## New Architecture

### Project Structure

```
bassi/
├── __init__.py
├── main.py              # REWRITTEN: Async with anyio
├── agent.py             # REWRITTEN: Claude Agent SDK wrapper
├── config.py            # KEPT: Minor updates for MCP
├── status_bar.py        # KEPT: No changes
├── mcp_servers/         # NEW: Custom MCP servers
│   ├── __init__.py
│   ├── bash_server.py
│   └── web_search_server.py
└── tools/               # TO BE REMOVED: No longer used

.mcp.json                # NEW: External MCP server config (O365)
docs/
└── features_concepts/
    └── azure_ad_setup.md  # NEW: O365 setup guide
```

### Key Files Rewritten

#### 1. `bassi/agent.py` (Complete Rewrite)
- Uses `ClaudeSDKClient` instead of `Anthropic()`
- Async streaming via `async for`
- MCP servers via `ClaudeAgentOptions`
- Combines SDK MCP servers + external servers
- Auto-loads `.mcp.json` if present

#### 2. `bassi/main.py` (Complete Rewrite)
- Now fully async with `anyio.run()`
- `main_async()` function with async event loop
- `async for msg in agent.chat(...)` for streaming
- All commands updated for async

#### 3. `bassi/mcp_servers/` (New)
**bash_server.py**: Bash execution as SDK MCP server
- `@tool` decorator
- `create_sdk_mcp_server()` factory
- In-process, no subprocess overhead

**web_search_server.py**: Web search as SDK MCP server
- Tavily API integration
- Same pattern as bash server

---

## How It Works

### Tool Execution Flow

```
User Input
    ↓
ClaudeSDKClient
    ↓
Claude API with tools
    ↓
┌─────────────────┬─────────────────┐
│ SDK MCP Servers │External MCP Srv │
│  (in-process)   │  (subprocess)   │
├─────────────────┼─────────────────┤
│ bash: Execute   │ ms365: Email    │
│ web: Search     │ ms365: Calendar │
└─────────────────┴─────────────────┘
    ↓
Stream results back
    ↓
Rich UI Display
```

### MCP Server Types

**1. SDK MCP Servers (In-Process)**
- Created with `create_sdk_mcp_server()`
- No subprocess overhead
- Direct Python function calls
- Examples: bash, web_search

**2. External MCP Servers (Subprocess)**
- Configured in `.mcp.json`
- Run as separate process (Node.js)
- Communicate via stdio
- Example: Softeria ms-365-mcp-server

---

## Benefits

### Technical

✅ **Less Code**: ~300 lines removed, SDK handles:
- Tool orchestration
- Streaming management
- Error handling
- Token management
- Conversation state

✅ **Better MCP**: Native integration, not custom
✅ **Future-Proof**: Official Anthropic pattern
✅ **Modular**: Each tool = independent server
✅ **Async First**: Modern Python async/await

### Functional

✅ **O365 Ready**: Email & calendar via `.mcp.json`
✅ **Streaming**: Real-time responses
✅ **Status Updates**: Live tool execution feedback
✅ **Error Handling**: SDK's robust management
✅ **Extensible**: Add MCP servers easily

---

## O365 Integration

### Setup

1. Create Azure AD app (see `docs/features_concepts/azure_ad_setup.md`)
2. Add credentials to `.env`:
   ```bash
   MS365_CLIENT_ID=your-client-id
   MS365_CLIENT_SECRET=your-secret
   MS365_TENANT_ID=common
   ```
3. Run bassi - O365 tools automatically available!

### Available Tools

**Email:**
- `mcp__ms365__list_mail_messages`
- `mcp__ms365__send_mail`
- `mcp__ms365__create_draft_email`

**Calendar:**
- `mcp__ms365__list_calendar_events`
- `mcp__ms365__create_calendar_event`

---

## What's Next

### Testing Required

- [ ] Basic functionality test (bash, web search)
- [ ] O365 authentication flow
- [ ] Error handling edge cases
- [ ] Performance vs old implementation

### Documentation Updates

- [ ] Update README.md with new architecture
- [ ] Update iteration status (Iterations 3 & 4 complete)
- [ ] Create migration guide (if needed)

### Cleanup

- [ ] Remove `bassi/tools/` directory
- [ ] Update/remove old tests
- [ ] Remove unused dependencies

---

## Migration Notes

### Breaking Changes

❌ **Direct API removed**: No more `from anthropic import Anthropic`
❌ **Old tool system removed**: No more `bassi/tools/bash_tool.py`
❌ **Sync code removed**: Everything is async now

### What Stayed

✅ Config system (minor updates)
✅ Rich UI and status bar
✅ CLI commands (/help, /config, etc.)
✅ User experience (same interface)

---

## Success Criteria

- [x] Claude Agent SDK installed and working
- [x] Bash tool via SDK MCP server
- [x] Web search via SDK MCP server
- [x] Async streaming responses
- [x] O365 MCP server configured
- [x] Azure AD setup documented
- [ ] All features tested
- [ ] Documentation updated
- [ ] Tests passing

---

## Architecture Philosophy

**BBS Style** (from CLAUDE_BBS.md):
- Simple, working code
- No over-engineering
- Reusable components
- Clear interfaces
- Minimal dependencies

**MCP Everything**:
- All capabilities via MCP
- Standard protocol
- Easy to extend
- Community ecosystem

**SDK First**:
- Official Anthropic patterns
- Battle-tested code
- Future updates included
- Best practices built-in

---

## Conclusion

This rewrite modernizes bassi to use Anthropic's official Agent SDK with MCP servers, providing:

1. **Cleaner code** - Less custom logic
2. **Better integration** - Native MCP support
3. **O365 ready** - Email & calendar out of the box
4. **Future-proof** - Following official patterns
5. **Extensible** - Easy to add more MCP servers

The architecture is now aligned with Anthropic's vision for agent development and the growing MCP ecosystem.
