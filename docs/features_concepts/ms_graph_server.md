# MS Graph Server - Microsoft 365 Integration

**Status**: Planning Phase
**Version**: 1.0
**Last Updated**: 2025-01-22

## Overview

The MS Graph Server is an MCP (Model Context Protocol) server that provides bassi with access to Microsoft 365 services, specifically:
- **Email** (Outlook/Exchange) - Read, send, search emails
- **Calendar** - Read, create, modify calendar events

This document provides comprehensive research, analysis, and implementation planning for the MS Graph Server.

## Vision Alignment

This feature aligns with **Iteration 3** (email) and **Iteration 4** (calendar) from `docs/vision.md`:

> Iteration 3: extend to read emails or save emails in drafts
> Iteration 4: extend to read calendar

## Architecture Analysis

### Existing MCP Server Pattern

Based on analysis of existing servers (`bash_server.py`, `web_search_server.py`), the pattern is:

```python
from anthropic_agent_sdk_python.tool import tool
from bassi.config import get_config_manager

# 1. Define tools with @tool decorator
@tool("mcp__ms365__read_emails", "Read recent emails", {"max_results": int})
async def read_emails(args: dict[str, Any]) -> dict[str, Any]:
    # Implementation
    return {"content": [{"type": "text", "text": result}]}

# 2. Create factory function
def create_ms_graph_mcp_server():
    return create_sdk_mcp_server(
        name="ms_graph",
        version="1.0.0",
        tools=[read_emails, send_email, read_calendar, create_event],
    )
```

### Integration Points

The MS Graph Server will be integrated into `bassi/agent.py`:

1. **Import** (line 23-26 area):
   ```python
   from bassi.mcp_servers.ms_graph_server import create_ms_graph_mcp_server
   ```

2. **Instantiation** (line 102-105 area):
   ```python
   self.sdk_mcp_servers = {
       "bash": create_bash_mcp_server(),
       "web": create_web_search_mcp_server(),
       "ms_graph": create_ms_graph_mcp_server(),  # NEW
   }
   ```

3. **Tool Allowlisting** (line 113-116 area):
   ```python
   allowed_tools = [
       "mcp__bash__execute",
       "mcp__web__search",
       "mcp__ms365__read_emails",      # NEW
       "mcp__ms365__send_email",       # NEW
       "mcp__ms365__read_calendar",    # NEW
       "mcp__ms365__create_event",     # NEW
   ]
   ```

4. **System Prompt** (line 68-72 area):
   Add directives telling Claude it can access email and calendar.

## Microsoft Graph API Research

### Authentication Options

There are **3 authentication flows** available:

| Flow | Use Case | User Interaction | Best For |
|------|----------|------------------|----------|
| **Device Code Flow** | CLI/browserless apps | Shows code, user visits URL | ✅ **bassi** (personal assistant) |
| **Interactive Browser** | Desktop apps with browser | Opens browser automatically | Desktop GUI apps |
| **Client Secret** | Daemon/background services | None (app-only) | Servers, automation |

**Decision**: Use **Device Code Flow** for bassi because:
- Personal assistant (delegated access)
- CLI application (no GUI)
- User authenticates once, tokens cached
- Best UX for terminal apps

### Required Dependencies

```bash
# Microsoft Graph SDK for Python
uv add msgraph-sdk

# Azure Identity for authentication
uv add azure-identity

# Optional: MSAL extensions for token caching
uv add msal-extensions
```

### Authentication Implementation

```python
from azure.identity import DeviceCodeCredential
from msgraph import GraphServiceClient

# Initialize credential
credential = DeviceCodeCredential(
    client_id=config.get("ms365_client_id"),
    tenant_id=config.get("ms365_tenant_id", "common"),
)

# Define scopes
scopes = [
    "User.Read",              # Read user profile
    "Mail.Read",              # Read emails
    "Mail.ReadWrite",         # Read/write emails
    "Mail.Send",              # Send emails
    "Calendars.Read",         # Read calendars
    "Calendars.ReadWrite",    # Read/write calendars
    "offline_access",         # Maintain access
]

# Create Graph client
client = GraphServiceClient(credentials=credential, scopes=scopes)
```

### API Permissions Required

#### Delegated Permissions (User Context)

**Email Permissions:**
- `Mail.Read` - Read user's mailbox
- `Mail.ReadWrite` - Read and modify user's mailbox
- `Mail.Send` - Send mail as the user

**Calendar Permissions:**
- `Calendars.Read` - Read user's calendars
- `Calendars.ReadWrite` - Read and modify user's calendars

**Optional:**
- `User.Read` - Read user profile (basic info)
- `offline_access` - Maintain access to data (refresh tokens)

### Permission Scopes Format

Scopes use the format: `https://graph.microsoft.com/<permission>`

Examples:
- `https://graph.microsoft.com/Mail.Read`
- `https://graph.microsoft.com/Calendars.ReadWrite`
- Or shorthand in SDK: `Mail.Read`, `Calendars.ReadWrite`

## Proposed Tool Design

### Tool 1: Read Emails

```python
@tool(
    "mcp__ms365__read_emails",
    "Read recent emails from Outlook/Exchange inbox",
    {
        "max_results": int,  # default: 10
        "folder": str,       # default: "inbox" (options: inbox, sent, drafts, deleted)
        "unread_only": bool, # default: False
        "search_query": str, # optional: search emails
    }
)
async def read_emails(args: dict[str, Any]) -> dict[str, Any]:
    """
    Read recent emails from user's mailbox.

    Returns:
        List of emails with: subject, sender, date, preview, has_attachments
    """
```

**Example Output:**
```
Found 5 emails in inbox:

1. [UNREAD] "Project Update" from alice@example.com (2025-01-22 10:30)
   Preview: Hey team, here's the latest update on the project...
   Attachments: report.pdf

2. "Meeting Notes" from bob@example.com (2025-01-21 14:15)
   Preview: Thanks for attending today's meeting. Here are...
```

### Tool 2: Send Email

```python
@tool(
    "mcp__ms365__send_email",
    "Send an email via Outlook/Exchange",
    {
        "to": list,          # list of email addresses
        "subject": str,
        "body": str,
        "cc": list,          # optional
        "bcc": list,         # optional
        "importance": str,   # optional: "low", "normal", "high"
    }
)
async def send_email(args: dict[str, Any]) -> dict[str, Any]:
    """
    Send an email message.

    Returns:
        Confirmation message with sent status
    """
```

### Tool 3: Read Calendar

```python
@tool(
    "mcp__ms365__read_calendar",
    "Read calendar events from Outlook/Exchange",
    {
        "start_date": str,   # ISO format: "2025-01-22" (default: today)
        "end_date": str,     # ISO format: "2025-01-29" (default: today + 7 days)
        "max_results": int,  # default: 20
    }
)
async def read_calendar(args: dict[str, Any]) -> dict[str, Any]:
    """
    Read calendar events for a date range.

    Returns:
        List of events with: subject, start, end, location, attendees
    """
```

**Example Output:**
```
Calendar events for 2025-01-22 to 2025-01-29:

📅 2025-01-22 (Wednesday)
  09:00-10:00 | Team Standup
              | Location: Conference Room A
              | Attendees: alice@example.com, bob@example.com

  14:00-15:30 | Client Meeting
              | Location: Virtual (Teams link)
              | Attendees: client@company.com, manager@example.com

📅 2025-01-23 (Thursday)
  10:00-11:00 | Project Review
              | Location: Office 301
```

### Tool 4: Create Calendar Event

```python
@tool(
    "mcp__ms365__create_event",
    "Create a new calendar event in Outlook/Exchange",
    {
        "subject": str,
        "start": str,        # ISO 8601: "2025-01-22T14:00:00"
        "end": str,          # ISO 8601: "2025-01-22T15:00:00"
        "location": str,     # optional
        "attendees": list,   # optional: list of email addresses
        "body": str,         # optional: event description
    }
)
async def create_event(args: dict[str, Any]) -> dict[str, Any]:
    """
    Create a new calendar event.

    Returns:
        Confirmation with event ID and details
    """
```

## Configuration Design

### Configuration File

Add to `bassi/config.py` (or user's config):

```json
{
  "ms365_client_id": "",
  "ms365_tenant_id": "common",
  "ms365_cache_location": "~/.cache/bassi/msal_token_cache.bin"
}
```

### Environment Variables (Alternative)

```bash
# .env file
MS365_CLIENT_ID=your-app-client-id
MS365_TENANT_ID=common  # or specific tenant ID
MS365_CACHE_LOCATION=~/.cache/bassi/msal_token_cache.bin
```

### Token Caching

Use `msal-extensions` for secure token caching:

```python
from msal_extensions import (
    FilePersistence,
    PersistedTokenCache,
)

cache_location = config.get("ms365_cache_location", "~/.cache/bassi/msal_token_cache.bin")
cache = PersistedTokenCache(FilePersistence(cache_location))

# Pass cache to credential
credential = DeviceCodeCredential(
    client_id=client_id,
    tenant_id=tenant_id,
    cache=cache,  # Token caching
)
```

**Benefits:**
- User authenticates once
- Tokens cached securely
- Automatic refresh
- No re-authentication needed

## Error Handling Strategy

### Error Categories

1. **Configuration Errors**
   - Missing `ms365_client_id`
   - Invalid credentials

2. **Authentication Errors**
   - Token expired (handle refresh)
   - User canceled device code flow
   - Insufficient permissions

3. **API Errors**
   - Network timeout
   - Rate limiting
   - Invalid requests

### Error Response Format

```python
{
    "content": [{"type": "text", "text": "ERROR: <message>"}],
    "isError": True
}
```

### Example Error Handling

```python
try:
    # API call
    messages = await client.me.messages.get()
except Exception as e:
    if "consent" in str(e).lower():
        return {
            "content": [{
                "type": "text",
                "text": "ERROR: Insufficient permissions. Please re-run authentication and grant required permissions."
            }],
            "isError": True
        }
    elif "token" in str(e).lower():
        return {
            "content": [{
                "type": "text",
                "text": "ERROR: Authentication token expired. Please re-authenticate."
            }],
            "isError": True
        }
    else:
        return {
            "content": [{
                "type": "text",
                "text": f"ERROR: Failed to read emails: {str(e)}"
            }],
            "isError": True
        }
```

## Implementation Plan

### Phase 1: Foundation (Day 1)

1. **Setup Dependencies**
   ```bash
   uv add msgraph-sdk azure-identity msal-extensions
   ```

2. **Create Server File**
   - `bassi/mcp_servers/ms_graph_server.py`
   - Basic structure with factory function
   - Configuration loading

3. **Implement Authentication**
   - Device code flow
   - Token caching
   - Error handling

4. **Register in Agent**
   - Import in `agent.py`
   - Add to `sdk_mcp_servers`
   - Update system prompt

### Phase 2: Email Tools (Day 2)

1. **Implement `read_emails` Tool**
   - Read inbox messages
   - Support filtering (unread, folders)
   - Format output nicely

2. **Implement `send_email` Tool**
   - Send basic emails
   - Support CC, BCC
   - Importance levels

3. **Testing**
   - Unit tests for email tools
   - Integration test with real API (manual)

### Phase 3: Calendar Tools (Day 3)

1. **Implement `read_calendar` Tool**
   - Read events for date range
   - Format output with emojis
   - Timezone handling

2. **Implement `create_event` Tool**
   - Create simple events
   - Support attendees
   - Support location

3. **Testing**
   - Unit tests for calendar tools
   - Integration test with real API (manual)

### Phase 4: Polish & Documentation (Day 4)

1. **Error Handling**
   - Comprehensive error messages
   - Graceful degradation
   - User-friendly prompts

2. **Documentation**
   - Update `docs/design.md`
   - Usage examples in `/help`
   - Azure setup guide

3. **Integration Testing**
   - End-to-end tests
   - User acceptance testing

## Testing Strategy

### Unit Tests

```python
# tests/test_ms_graph_server.py

def test_read_emails_requires_config():
    """Test that read_emails fails without configuration"""

def test_send_email_validation():
    """Test that send_email validates input parameters"""

def test_calendar_date_parsing():
    """Test that calendar handles various date formats"""
```

### Integration Tests (Manual)

Due to requiring real Azure AD authentication:

1. **Email Flow Test**
   - Run bassi
   - Ask: "Show me my recent emails"
   - Verify authentication flow
   - Verify emails displayed correctly

2. **Send Email Test**
   - Ask: "Send a test email to myself"
   - Verify email sent
   - Check inbox

3. **Calendar Test**
   - Ask: "What's on my calendar this week?"
   - Verify events displayed
   - Test date range handling

4. **Create Event Test**
   - Ask: "Create a meeting tomorrow at 2pm"
   - Verify event created
   - Check calendar

### Mock Testing

For automated tests, mock the Microsoft Graph API:

```python
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_graph_client():
    client = MagicMock()
    client.me.messages.get = AsyncMock(return_value=mock_messages)
    return client
```

## Azure/O365 Backend Setup

### Prerequisites

- Azure account (free tier works)
- Microsoft 365 account (personal or work)
- Admin rights to register applications

### Step 1: Register Azure AD Application

1. **Go to Azure Portal**
   - Navigate to: https://portal.azure.com/
   - Sign in with your Microsoft account

2. **Open Azure Active Directory**
   - Search for "Azure Active Directory" in top search bar
   - Or navigate: Home → Azure Active Directory

3. **Register New Application**
   - Click **App registrations** (left sidebar)
   - Click **+ New registration**

4. **Configure Application**
   - **Name**: `bassi-personal-assistant`
   - **Supported account types**:
     - For personal use: "Accounts in any organizational directory and personal Microsoft accounts"
     - For work only: "Accounts in this organizational directory only"
   - **Redirect URI**:
     - Platform: **Public client/native (mobile & desktop)**
     - URI: `http://localhost` (or leave blank for device code flow)
   - Click **Register**

### Step 2: Copy Application IDs

After registration, you'll see the application overview page.

**Copy these values** (you'll need them for configuration):

1. **Application (client) ID**
   - Format: `12345678-1234-1234-1234-123456789abc`
   - This is your `ms365_client_id`

2. **Directory (tenant) ID**
   - Format: `87654321-4321-4321-4321-987654321abc`
   - This is your `ms365_tenant_id`
   - For personal accounts, use `"common"` instead

### Step 3: Configure API Permissions

1. **Open API Permissions**
   - In your app registration, click **API permissions** (left sidebar)

2. **Add Microsoft Graph Permissions**
   - Click **+ Add a permission**
   - Select **Microsoft Graph**
   - Choose **Delegated permissions** (NOT Application permissions)

3. **Add These Permissions:**

   **Basic:**
   - ☑️ `User.Read` - Sign in and read user profile
   - ☑️ `offline_access` - Maintain access to data

   **Email:**
   - ☑️ `Mail.Read` - Read user mail
   - ☑️ `Mail.ReadWrite` - Read and write access to user mail
   - ☑️ `Mail.Send` - Send mail as a user

   **Calendar:**
   - ☑️ `Calendars.Read` - Read user calendars
   - ☑️ `Calendars.ReadWrite` - Have full access to user calendars

4. **Grant Admin Consent**
   - Click **Grant admin consent for [Your Organization]**
   - Click **Yes** to confirm
   - All permissions should show "Granted" status with green checkmark

### Step 4: Enable Public Client Flow

1. **Open Authentication Settings**
   - Click **Authentication** (left sidebar)

2. **Configure Public Client**
   - Scroll to **Advanced settings**
   - Find **Allow public client flows**
   - Toggle **Yes**
   - Click **Save**

### Step 5: Configure bassi

Add credentials to your bassi configuration:

**Option A: Configuration File** (`~/.config/bassi/config.json`):
```json
{
  "ms365_client_id": "12345678-1234-1234-1234-123456789abc",
  "ms365_tenant_id": "common",
  "ms365_cache_location": "~/.cache/bassi/msal_token_cache.bin"
}
```

**Option B: Environment Variables** (`.env` file):
```bash
MS365_CLIENT_ID=12345678-1234-1234-1234-123456789abc
MS365_TENANT_ID=common
MS365_CACHE_LOCATION=~/.cache/bassi/msal_token_cache.bin
```

### Step 6: First-Time Authentication

1. **Start bassi:**
   ```bash
   ./run-agent.sh
   ```

2. **Trigger MS365 Feature:**
   ```
   > show me my recent emails
   ```

3. **Device Code Flow:**
   - bassi will display:
     ```
     To sign in, use a web browser to open:
     https://microsoft.com/devicelogin

     And enter the code: A1B2C3D4
     ```

4. **Authenticate:**
   - Open URL in browser
   - Enter the code shown
   - Sign in with your Microsoft account
   - Review and accept permissions
   - You'll see "You're all set" message

5. **Return to bassi:**
   - Authentication complete!
   - Token cached for future use
   - bassi will now show your emails

### Step 7: Verify Setup

Test each feature:

```bash
# Test email reading
> show me my recent 5 emails

# Test calendar
> what's on my calendar today?

# Test email sending (be careful!)
> send a test email to myself with subject "Testing bassi"
```

## Security Considerations

### Best Practices

1. **Never Commit Secrets**
   - Add `.env` to `.gitignore`
   - Never commit `config.json` with real IDs
   - Use placeholders in docs

2. **Minimal Permissions**
   - Only request permissions actually needed
   - Start with read-only, add write later
   - Review permissions regularly

3. **Token Security**
   - Tokens cached in secure location
   - Use `msal-extensions` for OS-level security (Keychain/Credential Manager)
   - Token auto-refresh handled by SDK

4. **User Consent**
   - Always ask before sending emails
   - Confirm before creating calendar events
   - Show preview of actions

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Token theft | OS-level secure storage (Keychain/Credential Manager) |
| Accidental email send | Confirmation prompts in prompt engineering |
| Over-permissioned app | Minimal permission set, user consent required |
| Unauthorized access | Device code flow requires user interaction |

## Open Questions

1. **Token Cache Location**
   - Use `~/.cache/bassi/` for Linux/macOS?
   - Use OS credential store (Keychain/Credential Manager)?
   - Decision: Start with file cache, migrate to OS store later

2. **Multi-Account Support**
   - Support multiple MS365 accounts?
   - Decision: Single account for v1, multi-account in future

3. **Email Drafts**
   - Support saving drafts (per vision.md Iteration 3)?
   - Decision: Add in v2 if requested

4. **Calendar Timezone**
   - Handle timezone conversions?
   - Decision: Use user's local timezone by default

## Resources

### Official Documentation

- **Microsoft Graph Python SDK**: https://github.com/microsoftgraph/msgraph-sdk-python
- **Microsoft Graph API Reference**: https://learn.microsoft.com/en-us/graph/api/overview
- **Azure Identity Python**: https://learn.microsoft.com/en-us/python/api/azure-identity/
- **Graph Permissions Reference**: https://learn.microsoft.com/en-us/graph/permissions-reference

### Tutorials

- **Device Code Flow**: https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-device-code
- **Register Azure App**: https://learn.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app
- **Python Graph Samples**: https://github.com/microsoftgraph/msgraph-sdk-python/tree/main/docs

### Blog Posts (Referenced in Research)

- Darren Robinson's Blog: Microsoft Graph with MSAL Python
  - https://blog.darrenjrobinson.com/microsoft-graph-using-msal-with-python-and-delegated-permissions/
  - Excellent walkthrough of device code flow with Python

## Appendix: Code Examples from Research

### Device Code Authentication (Full Example)

```python
import asyncio
from azure.identity import DeviceCodeCredential
from msgraph import GraphServiceClient

async def authenticate_and_get_user():
    # Create credential
    credential = DeviceCodeCredential(
        client_id='CLIENT_ID',
        tenant_id='TENANT_ID',  # or 'common' for personal accounts
    )

    # Define scopes
    scopes = [
        "User.Read",
        "Mail.Read",
        "Calendars.Read",
    ]

    # Create client
    client = GraphServiceClient(credentials=credential, scopes=scopes)

    # Test by getting current user
    user = await client.me.get()
    if user:
        print(f"Authenticated as: {user.display_name}")
        print(f"Email: {user.user_principal_name}")
        print(f"User ID: {user.id}")

    return client

# Run
client = asyncio.run(authenticate_and_get_user())
```

### Read Emails Example

```python
async def get_recent_emails(client, max_results=10):
    """Get recent emails from inbox"""
    from msgraph.generated.me.messages.messages_request_builder import (
        MessagesRequestBuilder
    )

    # Configure request
    query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
        top=max_results,
        orderby=["receivedDateTime DESC"],
        select=["subject", "from", "receivedDateTime", "bodyPreview", "isRead"],
    )

    request_config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
        query_parameters=query_params
    )

    # Get messages
    messages = await client.me.messages.get(request_configuration=request_config)

    if messages and messages.value:
        for msg in messages.value:
            print(f"[{'UNREAD' if not msg.is_read else 'READ'}] {msg.subject}")
            print(f"  From: {msg.from_.email_address.address}")
            print(f"  Date: {msg.received_date_time}")
            print(f"  Preview: {msg.body_preview[:100]}...")
            print()
```

### Send Email Example

```python
async def send_email(client, to_address, subject, body):
    """Send an email"""
    from msgraph.generated.models.message import Message
    from msgraph.generated.models.email_address import EmailAddress
    from msgraph.generated.models.recipient import Recipient
    from msgraph.generated.models.item_body import ItemBody
    from msgraph.generated.models.body_type import BodyType
    from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
        SendMailPostRequestBody
    )

    # Create recipient
    to_email = EmailAddress()
    to_email.address = to_address

    to_recipient = Recipient()
    to_recipient.email_address = to_email

    # Create body
    email_body = ItemBody()
    email_body.content = body
    email_body.content_type = BodyType.Text

    # Create message
    message = Message()
    message.subject = subject
    message.to_recipients = [to_recipient]
    message.body = email_body

    # Send
    request_body = SendMailPostRequestBody()
    request_body.message = message
    request_body.save_to_sent_items = True

    await client.me.send_mail.post(request_body)
    print(f"Email sent to {to_address}")
```

### Read Calendar Example

```python
async def get_calendar_events(client, start_date, end_date):
    """Get calendar events for date range"""
    from msgraph.generated.me.calendar_view.calendar_view_request_builder import (
        CalendarViewRequestBuilder
    )

    # Configure request
    query_params = CalendarViewRequestBuilder.CalendarViewRequestBuilderGetQueryParameters(
        start_date_time=start_date.isoformat(),
        end_date_time=end_date.isoformat(),
        select=["subject", "start", "end", "location", "attendees"],
        orderby=["start/dateTime"],
    )

    request_config = CalendarViewRequestBuilder.CalendarViewRequestBuilderGetRequestConfiguration(
        query_parameters=query_params
    )

    # Get events
    events = await client.me.calendar_view.get(request_configuration=request_config)

    if events and events.value:
        for event in events.value:
            print(f"📅 {event.subject}")
            print(f"   {event.start.date_time} to {event.end.date_time}")
            if event.location:
                print(f"   Location: {event.location.display_name}")
            if event.attendees:
                attendee_list = [a.email_address.address for a in event.attendees]
                print(f"   Attendees: {', '.join(attendee_list)}")
            print()
```

---

**Document Status**: Complete - Ready for Implementation
**Next Steps**: Begin Phase 1 (Foundation) after user approval
