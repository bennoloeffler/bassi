# MS Graph Server - Implementation Guide

**Target**: MS Graph MCP Server for bassi
**Goal**: Enable email and calendar access via Microsoft 365
**Status**: Ready to Implement

## Quick Reference

- **Full Documentation**: `docs/features_concepts/ms_graph_server.md`
- **Azure Setup Guide**: `docs/features_concepts/azure_ad_setup.md`
- **Server File**: `bassi/mcp_servers/ms_graph_server.py` (to be created)

## What You Need to Do in Azure Portal

### 1. Register Application

**Portal**: https://portal.azure.com/

**Steps**:
1. Navigate to: Azure Active Directory → App registrations
2. Click "New registration"
3. Configure:
   - **Name**: `bassi-personal-assistant`
   - **Account types**: "Accounts in any organizational directory and personal Microsoft accounts"
   - **Redirect URI**: Select "Public client/native" platform, use `http://localhost`
4. Click "Register"

### 2. Copy These Values

After registration, copy from the Overview page:

```
Application (client) ID: ________________________________
Directory (tenant) ID:   ________________________________
```

You'll use these in bassi configuration.

### 3. Configure API Permissions

1. Go to: **API permissions** (left sidebar)
2. Click **"+ Add a permission"**
3. Select **"Microsoft Graph"**
4. Choose **"Delegated permissions"** (NOT Application)
5. Add these permissions:

**Check these boxes:**
- ☑️ `User.Read` - Sign in and read user profile
- ☑️ `offline_access` - Maintain access to data
- ☑️ `Mail.Read` - Read user mail
- ☑️ `Mail.ReadWrite` - Read and write user mail
- ☑️ `Mail.Send` - Send mail as user
- ☑️ `Calendars.Read` - Read user calendars
- ☑️ `Calendars.ReadWrite` - Read and write user calendars

6. Click **"Add permissions"**
7. Click **"Grant admin consent for [Your Organization]"**
8. Confirm by clicking **"Yes"**
9. Verify all show "Granted" status (green checkmarks)

### 4. Enable Public Client Flow

1. Go to: **Authentication** (left sidebar)
2. Scroll to **"Advanced settings"**
3. Find **"Allow public client flows"**
4. Toggle to **"Yes"**
5. Click **"Save"** at the top

### 5. Configure bassi

Add to `~/.config/bassi/config.json`:

```json
{
  "ms365_client_id": "YOUR_APPLICATION_CLIENT_ID",
  "ms365_tenant_id": "common",
  "ms365_cache_location": "~/.cache/bassi/msal_token_cache.bin"
}
```

**OR** add to `.env` file:

```bash
MS365_CLIENT_ID=YOUR_APPLICATION_CLIENT_ID
MS365_TENANT_ID=common
MS365_CACHE_LOCATION=~/.cache/bassi/msal_token_cache.bin
```

Replace `YOUR_APPLICATION_CLIENT_ID` with the actual ID from step 2.

## Implementation Checklist

### Phase 1: Foundation ✅

- [ ] Install dependencies:
  ```bash
  uv add msgraph-sdk azure-identity msal-extensions
  ```

- [ ] Create `bassi/mcp_servers/ms_graph_server.py`:
  ```python
  from anthropic_agent_sdk_python.tool import tool
  from anthropic_agent_sdk_python.mcp import create_sdk_mcp_server
  from bassi.config import get_config_manager

  # Factory function
  def create_ms_graph_mcp_server():
      return create_sdk_mcp_server(
          name="ms_graph",
          version="1.0.0",
          tools=[],  # Add tools here
      )
  ```

- [ ] Implement authentication helper:
  ```python
  async def get_graph_client():
      """Get authenticated Graph client with device code flow"""
      config = get_config_manager().get_config()

      client_id = config.get("ms365_client_id")
      if not client_id:
          raise ValueError("ms365_client_id not configured")

      tenant_id = config.get("ms365_tenant_id", "common")

      credential = DeviceCodeCredential(
          client_id=client_id,
          tenant_id=tenant_id,
      )

      scopes = [
          "User.Read",
          "Mail.Read",
          "Mail.ReadWrite",
          "Mail.Send",
          "Calendars.Read",
          "Calendars.ReadWrite",
          "offline_access",
      ]

      return GraphServiceClient(credentials=credential, scopes=scopes)
  ```

- [ ] Add error handling wrapper:
  ```python
  def handle_graph_errors(func):
      """Decorator for consistent error handling"""
      async def wrapper(args):
          try:
              return await func(args)
          except Exception as e:
              return {
                  "content": [{
                      "type": "text",
                      "text": f"ERROR: {str(e)}"
                  }],
                  "isError": True
              }
      return wrapper
  ```

- [ ] Register in `bassi/agent.py`:
  - Import: `from bassi.mcp_servers.ms_graph_server import create_ms_graph_mcp_server`
  - Add to `self.sdk_mcp_servers`: `"ms_graph": create_ms_graph_mcp_server()`

### Phase 2: Email Tools ✅

- [ ] Implement `read_emails` tool:
  ```python
  @tool(
      "mcp__ms365__read_emails",
      "Read recent emails from Outlook inbox",
      {
          "max_results": int,
          "folder": str,
          "unread_only": bool,
      }
  )
  @handle_graph_errors
  async def read_emails(args):
      # Implementation
      pass
  ```

- [ ] Implement `send_email` tool:
  ```python
  @tool(
      "mcp__ms365__send_email",
      "Send an email via Outlook",
      {
          "to": list,
          "subject": str,
          "body": str,
          "cc": list,
          "importance": str,
      }
  )
  @handle_graph_errors
  async def send_email(args):
      # Implementation
      pass
  ```

- [ ] Add to allowlist in `bassi/agent.py`:
  ```python
  allowed_tools = [
      # ... existing tools
      "mcp__ms365__read_emails",
      "mcp__ms365__send_email",
  ]
  ```

- [ ] Update system prompt to mention email capabilities

### Phase 3: Calendar Tools ✅

- [ ] Implement `read_calendar` tool:
  ```python
  @tool(
      "mcp__ms365__read_calendar",
      "Read calendar events from Outlook",
      {
          "start_date": str,
          "end_date": str,
          "max_results": int,
      }
  )
  @handle_graph_errors
  async def read_calendar(args):
      # Implementation
      pass
  ```

- [ ] Implement `create_event` tool:
  ```python
  @tool(
      "mcp__ms365__create_event",
      "Create a new calendar event",
      {
          "subject": str,
          "start": str,
          "end": str,
          "location": str,
          "attendees": list,
          "body": str,
      }
  )
  @handle_graph_errors
  async def create_event(args):
      # Implementation
      pass
  ```

- [ ] Add to allowlist in `bassi/agent.py`:
  ```python
  allowed_tools = [
      # ... existing tools
      "mcp__ms365__read_calendar",
      "mcp__ms365__create_event",
  ]
  ```

- [ ] Update system prompt to mention calendar capabilities

### Phase 4: Testing ✅

- [ ] Create `tests/test_ms_graph_server.py`:
  - Test configuration loading
  - Test error handling
  - Mock API responses

- [ ] Manual integration tests:
  - Test authentication flow
  - Test reading emails
  - Test sending email
  - Test reading calendar
  - Test creating event

- [ ] Document test results

### Phase 5: Documentation ✅

- [ ] Update `docs/design.md`:
  - Add MS Graph Server to Tools section
  - Document use cases

- [ ] Update `/help` command in `bassi/main.py`:
  - Add email examples
  - Add calendar examples

- [ ] Create usage examples:
  ```
  Examples:

  Email:
  - "Show me my recent 10 emails"
  - "Show me unread emails from today"
  - "Send an email to alice@example.com about the meeting"

  Calendar:
  - "What's on my calendar today?"
  - "Show me my meetings this week"
  - "Create a meeting tomorrow at 2pm with bob@example.com"
  ```

## Testing the Implementation

### First-Time Authentication

```bash
./run-agent.sh
> show me my recent emails
```

Expected output:
```
To sign in, use a web browser to open:
https://microsoft.com/devicelogin

And enter the code: A1B2C3D4
```

1. Open URL in browser
2. Enter code
3. Sign in with Microsoft account
4. Accept permissions
5. Return to bassi - should show emails

### Subsequent Uses

Token is cached, no re-authentication needed:

```bash
> show me my calendar today
> send a test email to myself
```

## Common Issues

### "ms365_client_id not configured"
- Add client ID to config file
- Check file location: `~/.config/bassi/config.json`

### "Insufficient permissions"
- Re-run Azure portal steps
- Ensure all permissions granted
- Try deleting token cache: `rm ~/.cache/bassi/msal_token_cache.bin`

### "Token expired"
- Delete token cache
- Re-authenticate with device code flow

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         bassi CLI                            │
├─────────────────────────────────────────────────────────────┤
│                      BassiAgent                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              MCP Server Registry                      │  │
│  │  - bash_server                                        │  │
│  │  - web_search_server                                  │  │
│  │  - ms_graph_server  ◄── NEW                          │  │
│  └──────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                   ms_graph_server.py                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Tools:                                               │  │
│  │  - mcp__ms365__read_emails                           │  │
│  │  - mcp__ms365__send_email                            │  │
│  │  - mcp__ms365__read_calendar                         │  │
│  │  - mcp__ms365__create_event                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ▼                                  │
│               msgraph-sdk-python                             │
│                  azure-identity                              │
│                           ▼                                  │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          │  Device Code Flow
                          │  (First time: User authenticates)
                          │  (Subsequent: Token cache used)
                          ▼
           ┌──────────────────────────────┐
           │   Microsoft Graph API         │
           │   https://graph.microsoft.com │
           ├──────────────────────────────┤
           │  - Mail (Outlook/Exchange)    │
           │  - Calendar                   │
           └──────────────────────────────┘
```

## Next Steps After Implementation

1. **Test thoroughly** with real Azure account
2. **Document edge cases** encountered
3. **Consider enhancements**:
   - Email search functionality
   - Draft saving (per vision.md)
   - Calendar event updates/deletion
   - Attachment handling
   - HTML email bodies

4. **Update vision.md** to mark Iteration 3 & 4 as complete

## References

- **Full Design Doc**: `docs/features_concepts/ms_graph_server.md`
- **Azure Setup**: `docs/features_concepts/azure_ad_setup.md`
- **MS Graph SDK**: https://github.com/microsoftgraph/msgraph-sdk-python
- **Graph API Docs**: https://learn.microsoft.com/en-us/graph/api/overview

---

**Ready to implement!** Follow the checklist above, and refer to the full documentation for detailed code examples.
