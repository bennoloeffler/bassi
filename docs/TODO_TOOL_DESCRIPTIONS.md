# TODO: Implement MCP Tool Descriptions

## Problem

Currently, tool descriptions in the help modal are not available because:

1. **Agent SDK Init Message**: Only contains tool **names** (strings), not schemas or descriptions
2. **No Metadata**: The `SystemMessage(subtype='init')` data structure contains:
   - `tools`: `["Task", "Bash", "mcp__ms365__send_email", ...]` (just names)
   - `mcp_servers`: `[{"name": "ms365", "status": "connected"}, ...]` (just name/status)
   - No tool schemas, no descriptions, no parameter info

3. **MCP Protocol**: MCP servers DO have tool schemas with full descriptions, but they're not exposed through the Agent SDK's init message

## Current Workaround

The modal shows:
```
Tool descriptions are not currently available.
This tool is provided by the [server] MCP server.

Note: The Claude Agent SDK only provides tool names, not descriptions.
Tool schemas with descriptions exist in the MCP server but require additional querying.
```

## Proper Solution

### Option 1: Query MCP Servers Directly (Recommended)

MCP servers expose tool schemas via the `tools/list` RPC method. We need to:

1. **Backend: Fetch Tool Schemas**
   ```python
   # In bassi/core_v3/mcp_tool_schemas.py
   async def fetch_mcp_tool_schemas(mcp_servers: dict) -> dict:
       """
       Query each MCP server for its tool schemas.

       Returns:
           {
               "server_name": {
                   "tool_name": {
                       "description": "...",
                       "inputSchema": {...},
                       "parameters": [...]
                   }
               }
           }
       """
       schemas = {}
       for server_name, server_config in mcp_servers.items():
           # Connect to MCP server
           # Send tools/list RPC request
           # Parse response and store schemas
           pass
       return schemas
   ```

2. **Backend: Add Endpoint**
   ```python
   # In bassi/core_v3/web_server_v3.py
   @self.app.get("/api/tool-schemas")
   async def get_tool_schemas():
       """Return tool schemas for all MCP servers"""
       schemas = await fetch_mcp_tool_schemas(self.mcp_servers)
       return JSONResponse(schemas)
   ```

3. **Frontend: Fetch and Cache Schemas**
   ```javascript
   // In bassi/static/app.js
   async loadToolSchemas() {
       const response = await fetch('/api/tool-schemas')
       this.toolSchemas = await response.json()
   }

   getToolDescription(toolName, serverName) {
       const schema = this.toolSchemas?.[serverName]?.[toolName]
       if (schema) {
           return `
               <p>${schema.description}</p>
               <h4>Parameters:</h4>
               <ul>
                   ${schema.parameters.map(p => `
                       <li><strong>${p.name}</strong>: ${p.description}</li>
                   `).join('')}
               </ul>
           `
       }
       return '<p><em>No description available</em></p>'
   }
   ```

### Option 2: Agent SDK Enhancement

Request that the Agent SDK team enhance the init message to include tool schemas:

```python
# Proposed enhancement to Agent SDK
SystemMessage(
    subtype='init',
    data={
        'tools': [
            {
                'name': 'mcp__ms365__send_email',
                'description': 'Send an email via Microsoft 365',
                'schema': {...},  # Full JSON schema
                'server': 'ms365'
            },
            ...
        ],
        # ...
    }
)
```

### Option 3: Extract from MCP Config + Documentation

Parse MCP server documentation or config files:

1. Ship with hardcoded descriptions for known servers (ms365, playwright, postgresql)
2. Load from `.mcp-tool-descriptions.json` file (user-provided)
3. Fall back to "No description available"

This is a hybrid approach - better than nothing, but not as good as Option 1.

## Implementation Plan

1. **Phase 1: Quick Fix** ✅ (DONE)
   - Remove hardcoded descriptions
   - Show explanatory message in modal
   - Add this TODO document

2. **Phase 2: Backend Schema Fetching** (TODO)
   - Create `bassi/core_v3/mcp_tool_schemas.py`
   - Implement MCP server querying
   - Add `/api/tool-schemas` endpoint
   - Cache schemas in memory

3. **Phase 3: Frontend Integration** (TODO)
   - Fetch schemas on startup
   - Update `getToolDescription()` to use real schemas
   - Show parameter information
   - Add "Try this tool" example generator

4. **Phase 4: Enhanced UX** (TODO)
   - Show parameter types and examples
   - Generate sample tool calls
   - Link to MCP server documentation
   - Show which tools require permissions

## Technical Details

### MCP Protocol - tools/list Request

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

### MCP Protocol - tools/list Response

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "send_email",
        "description": "Send an email message through Microsoft 365",
        "inputSchema": {
          "type": "object",
          "properties": {
            "to": {
              "type": "string",
              "description": "Recipient email address"
            },
            "subject": {
              "type": "string",
              "description": "Email subject line"
            },
            "body": {
              "type": "string",
              "description": "Email body content"
            }
          },
          "required": ["to", "subject", "body"]
        }
      }
    ]
  }
}
```

## References

- [MCP Specification](https://modelcontextprotocol.io/docs/specification)
- [MCP Protocol - tools/list](https://modelcontextprotocol.io/docs/specification/basic/tools#listing-tools)
- [Claude Agent SDK Documentation](https://docs.claude.com/en/docs/claude-code/agent-sdk)

## Related Issues

- Slash command descriptions: Already available via `get_server_info().commands`
- Skill descriptions: Unknown if available (TODO: investigate)
- Agent descriptions: Unknown if available (TODO: investigate)
