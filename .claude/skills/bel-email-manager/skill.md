---
name: email-manager
description: "Manages Microsoft 365 emails: analyze inbox, categorize by business relevance, create actionable tables, move emails to folders, and forward messages. Uses MS365 MCP server for email operations."
---

# Email Manager Skill

This skill provides comprehensive email management capabilities using the Microsoft 365 MCP server.

## Core Capabilities

1. **Email Analysis & Categorization**
   - Retrieve emails from specific time periods
   - Categorize by business relevance (sales, administrative, spam)
   - Create structured tables with sender, subject, relevance, and action items
   - Priority ranking for sales-relevant contacts

2. **Email Organization**
   - Move emails to specific folders (Archive, Rechnungen, etc.)
   - Batch operations for organizing multiple emails
   - Smart folder detection and management

3. **Email Forwarding**
   - Forward individual or multiple emails
   - Preserve original formatting and content
   - Add forwarding context when needed

## MCP Server Integration

This skill uses the **MS365 MCP Server** which provides Microsoft 365/Outlook integration.

### Configuration

The MS365 MCP server must be configured in `.mcp.json`:

```json
{
  "mcpServers": {
    "ms365": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-ms365@latest"]
    }
  }
}
```

### Authentication

The MS365 MCP server uses OAuth2 device code flow:
1. First call to any MS365 tool triggers authentication
2. User receives device code and URL
3. User authorizes on Microsoft's website
4. Token is cached for future use

Check authentication status:
```
mcp__ms365__verify-login
```

## Available Tools

### Email Retrieval & Search

**`mcp__ms365__list-mail-messages`**
- List emails from mailbox
- Filter by date: `receivedDateTime ge 2025-11-05T00:00:00Z`
- Select specific fields: `["id", "subject", "from", "receivedDateTime"]`
- Sort and paginate results
- Example filters:
  ```
  receivedDateTime ge 2025-11-05T00:00:00Z
  contains(subject, 'invoice')
  from/emailAddress/address eq 'sender@example.com'
  ```

**`mcp__ms365__get-mail-message`**
- Get full details of a specific email
- Returns complete message including body, attachments, metadata
- Supports expand/select for specific fields

**`mcp__ms365__list-mail-folder-messages`**
- List emails from specific folder
- Same filtering capabilities as list-mail-messages
- Useful for browsing organized emails

### Folder Management

**`mcp__ms365__list-mail-folders`**
- Get all available email folders
- Returns folder IDs, names, counts
- Identify target folders for organization

**`mcp__ms365__move-mail-message`**
- Move email to different folder
- Requires message ID and destination folder ID
- Atomic operation with error handling

### Email Actions

**`mcp__ms365__send-mail`**
- Send new email or forward existing email
- Supports HTML and text content
- Attachments, CC, BCC support
- Save to sent items optional

**`mcp__ms365__delete-mail-message`**
- Delete specific email
- Moves to "Deleted Items" folder
- Permanent deletion requires additional step

**`mcp__ms365__create-draft-email`**
- Create email draft without sending
- Edit later or send programmatically

### Search

**`mcp__ms365__search-query`**
- Advanced search across mailbox
- Full-text search in subject, body, attachments
- Complex query syntax support

## Common Workflows

### 1. Analyze Recent Emails

```javascript
// Get emails from last 2 days
mcp__ms365__list-mail-messages({
  filter: "receivedDateTime ge 2025-11-05T00:00:00Z",
  select: ["id", "subject", "from", "receivedDateTime", "bodyPreview"],
  orderby: ["receivedDateTime desc"],
  top: 100
})

// Categorize by business relevance:
// - HIGH: Known clients, opportunities, partners
// - MEDIUM: New contacts, potential leads
// - LOW: Administrative, newsletters
// - SPAM: Undeliverable, junk

// Create table:
// | Absender | Betreff | Relevanz | TODO |
```

### 2. Organize Invoices

```javascript
// 1. Find invoice emails
mcp__ms365__list-mail-messages({
  filter: "contains(subject, 'Rechnung') or contains(subject, 'Invoice')"
})

// 2. Get folder list and find "Rechnungen" folder
mcp__ms365__list-mail-folders()

// 3. Move each invoice
mcp__ms365__move-mail-message({
  messageId: "email-id",
  body: { DestinationId: "rechnungen-folder-id" }
})
```

### 3. Forward Invoices

```javascript
// 1. Get invoice email
mcp__ms365__get-mail-message({ messageId: "invoice-id" })

// 2. Forward with original content
mcp__ms365__send-mail({
  body: {
    Message: {
      subject: "FW: " + original.subject,
      body: { contentType: "html", content: original.body.content },
      toRecipients: [{ emailAddress: { address: "recipient@example.com" }}]
    },
    SaveToSentItems: true
  }
})
```

## Best Practices

1. **Date Filtering**: Always use ISO 8601 format for dates
   - `2025-11-05T00:00:00Z` (UTC timezone)
   - Use `receivedDateTime ge` for "since" queries

2. **Field Selection**: Use `select` parameter to reduce response size
   - Only request fields you need
   - Reduces token usage significantly

3. **Error Handling**:
   - 404 errors: Email already moved/deleted
   - Large responses: Use pagination or field selection
   - Authentication: Check login status first

4. **Batch Operations**:
   - Process emails in parallel when possible
   - Use TodoWrite to track multi-email operations
   - Handle individual failures gracefully

5. **Folder Operations**:
   - Always verify folder IDs before moving
   - Cache folder list to avoid repeated lookups
   - Use folder names as fallback for user-friendly messages

## Example: Full Email Analysis Workflow

```javascript
// 1. Verify authentication
mcp__ms365__verify-login()

// 2. Get recent emails
const emails = await mcp__ms365__list-mail-messages({
  filter: "receivedDateTime ge 2025-11-05T00:00:00Z",
  select: ["id", "subject", "from", "receivedDateTime", "bodyPreview"],
  top: 100
})

// 3. Categorize emails
const categorized = {
  business: [],
  administrative: [],
  spam: []
}

for (const email of emails) {
  const sender = email.from.emailAddress.address
  const subject = email.subject

  if (isKnownClient(sender) || containsSalesKeywords(subject)) {
    categorized.business.push({
      sender: email.from.emailAddress.name,
      subject: subject,
      relevance: "HIGH",
      todo: determineTodo(email)
    })
  } else if (isAdministrative(subject)) {
    categorized.administrative.push(email)
  } else {
    categorized.spam.push(email)
  }
}

// 4. Create markdown table
const table = createMarkdownTable(categorized.business)

// 5. Organize emails
await organizeEmails(categorized)
```

## Performance Considerations

- **Token Usage**: Email bodies can be large (10K+ tokens)
  - Use `select` to limit fields
  - Use `excludeResponse: true` when only success/failure matters
  - Paginate large result sets

- **Rate Limits**: Microsoft Graph API has rate limits
  - Batch operations when possible
  - Add delays for very large operations
  - Handle 429 (Too Many Requests) errors

- **Parallel Operations**: Most operations can be parallelized
  - Multiple `get-mail-message` calls in parallel
  - Multiple `move-mail-message` calls in parallel
  - Do NOT parallelize operations that depend on each other

## Troubleshooting

**Authentication Issues**
- Run `mcp__ms365__verify-login` to check status
- Re-authenticate if token expired
- Check `.mcp.json` configuration

**Email Not Found (404)**
- Email may have been moved/deleted already
- Verify message ID is correct
- Check if email is in different folder

**Response Too Large**
- Use `excludeResponse: true` parameter
- Select only needed fields with `select`
- Reduce `top` parameter for pagination

**Folder Not Found**
- Run `list-mail-folders` to verify folder structure
- Use exact folder ID from list response
- Note: Folder names may differ from display names
