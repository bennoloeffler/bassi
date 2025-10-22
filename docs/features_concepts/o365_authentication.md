# Microsoft 365 Authentication

## Overview

Bassi integrates with Microsoft 365 (Outlook email and calendar) through the `@softeria/ms-365-mcp-server` MCP server. This feature provides seamless authentication with automatic token caching.

## How It Works

### Architecture

1. **MCP Server**: The `@softeria/ms-365-mcp-server` runs as an external MCP server configured in `.mcp.json`
2. **Token Caching**: Credentials are cached securely in the OS credential store (fallback to file if unavailable)
3. **Agent Integration**: The bassi agent automatically handles authentication through the system prompt and available tools

### Authentication Flow

#### First-Time Authentication

When you first use MS365 features (email or calendar), the agent will:

1. Check authentication status with `mcp__ms365__verify-login`
2. If not authenticated, call `mcp__ms365__login`
3. The login tool will:
   - Check for cached tokens (automatic)
   - If no valid token found, initiate device code flow
   - Display a URL and code for browser authentication
   - Wait for you to complete authentication in your browser
4. Once authenticated, proceed with the requested MS365 operation

#### Subsequent Sessions

On subsequent runs:

1. The agent checks authentication status with `mcp__ms365__verify-login`
2. If cached token is valid, proceeds immediately
3. No browser authentication required - fully automatic!

### Available Tools

The agent has access to these MS365 tools:

- `mcp__ms365__login`: Authenticate to Microsoft 365 (checks cache first, then browser auth if needed)
- `mcp__ms365__verify-login`: Check current authentication status
- `mcp__ms365__list-mail-messages`: Read emails from Outlook
- `mcp__ms365__send-mail`: Send emails via Outlook
- `mcp__ms365__list-calendar-events`: View calendar events
- `mcp__ms365__create-calendar-event`: Create calendar events

## Configuration

### Required Environment Variables

Set these in your `.env` file:

```bash
MS365_CLIENT_ID=your-client-id
MS365_CLIENT_SECRET=your-client-secret  # Optional, for client secret flow
MS365_TENANT_ID=your-tenant-id
```

### MCP Server Configuration

The MS365 server is configured in `.mcp.json`:

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
    }
  }
}
```

## Agent Behavior

### System Prompt Instructions

The agent is instructed to:

1. **Always check authentication first**: Before any MS365 operation, verify login status
2. **Automatic login handling**: If not authenticated, automatically call the login tool
3. **User-friendly**: Provide clear instructions if browser authentication is needed
4. **Efficient**: Leverage cached tokens to avoid repeated authentication

### Example User Interactions

#### Reading Emails

```
User: "Show me my latest emails"

Agent:
1. Calls verify-login to check authentication
2. If authenticated: Lists emails immediately
3. If not authenticated:
   - Calls login tool
   - Displays authentication URL and code
   - Waits for authentication
   - Lists emails
```

#### Sending Emails

```
User: "Send an email to john@example.com with subject 'Meeting' and body 'See you at 3pm'"

Agent:
1. Verifies authentication
2. If needed, handles login flow
3. Sends email with specified details
4. Confirms success
```

## Security

### Token Storage

- **Primary**: OS credential store (Keychain on macOS, Credential Manager on Windows, Secret Service on Linux)
- **Fallback**: Encrypted file storage
- **Scope**: User-level storage, not accessible to other users

### Token Expiration

- Tokens expire based on Microsoft's OAuth 2.0 policies
- When expired, the login flow automatically triggers
- No manual token management required

## Troubleshooting

### Authentication Fails

If authentication fails:

1. **Check environment variables**: Ensure `MS365_CLIENT_ID` and `MS365_TENANT_ID` are set correctly
2. **Clear cached credentials**: Run manual logout if needed
3. **Check browser**: Ensure you can access Microsoft's authentication pages
4. **Review logs**: Check `bassi_debug.log` for detailed error messages

### Manual Login (CLI)

You can manually authenticate using:

```bash
npx @softeria/ms-365-mcp-server --login
```

This is useful for:
- Pre-authenticating before starting bassi
- Troubleshooting authentication issues
- Verifying credentials

### Manual Logout (CLI)

To clear cached credentials:

```bash
npx @softeria/ms-365-mcp-server --logout
```

### Verify Login (CLI)

To check authentication status:

```bash
npx @softeria/ms-365-mcp-server --verify-login
```

## Implementation Details

### Code Location

- **Agent**: `bassi/agent.py` (lines 54-104, 134-147)
  - System prompt includes authentication instructions
  - MS365 tools added to allowed_tools list
  - Login and verify-login tools exposed to agent

### Key Implementation Points

1. **Automatic Tool Discovery**: Tools are dynamically loaded from the MCP server
2. **Environment Variable Substitution**: `.mcp.json` supports `${VAR_NAME}` syntax
3. **Token Caching**: Handled entirely by the MCP server, no application code needed
4. **Agent Intelligence**: System prompt guides the agent to handle auth automatically

## Future Enhancements

Potential improvements:

1. **Pre-flight check**: Verify authentication on agent startup and display status
2. **Token refresh UI**: Better user feedback during token refresh
3. **Multi-account support**: Support multiple MS365 accounts
4. **Offline mode**: Graceful handling when MS365 is unavailable

## References

- [Softeria MS365 MCP Server](https://github.com/Softeria/ms-365-mcp-server)
- [Microsoft Graph API](https://docs.microsoft.com/en-us/graph/)
- [OAuth 2.0 Device Code Flow](https://docs.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-device-code)
