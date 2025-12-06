# MS365 Mail Move API Documentation

## API Function: mcp__ms365__move-mail-message

Moves a message to another folder in the user's mailbox.

### Function Signature

```
mcp__ms365__move-mail-message(messageId, body, excludeResponse=False, includeHeaders=False)
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `messageId` | string | ✅ Yes | The unique identifier of the message to move. Format: `AAMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwNGE0MgBGAAA...` |
| `body` | object | ✅ Yes | JSON object containing the destination folder information |
| `body.DestinationId` | string | ✅ Yes | The folder ID where the message should be moved. For Archive: `AQMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwADRhNDIALgAAA-cCSmDe9C5Ai1IxFty3vKgBACIai-AjXXpFuMeLL-NexTAAAAIBVAAAAA==` |
| `excludeResponse` | boolean | ❌ No | If true, only returns success/failure (default: false) |
| `includeHeaders` | boolean | ❌ No | If true, includes response headers with ETag (default: false) |

### Request Body

```json
{
  "DestinationId": "AQMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwADRhNDIALgAAA-cCSmDe9C5Ai1IxFty3vKgBACIai-AjXXpFuMeLL-NexTAAAAIBVAAAAA=="
}
```

### Response (Success)

```json
{
  "id": "AAMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwNGE0MgBGAAA...",
  "parentFolderId": "AQMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwADRhNDIALgAAA-cCSmDe9C5Ai1IxFty3vKgBACIai-AjXXpFuMeLL-NexTAAAAIBVAAAAA==",
  "subject": "Email Subject Line",
  "receivedDateTime": "2025-12-04T10:35:16Z",
  "createdDateTime": "2025-12-04T10:35:16Z"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Message ID (same as input) |
| `parentFolderId` | string | **IMPORTANT:** Destination folder ID (confirms move successful if equals DestinationId) |
| `subject` | string | Message subject for reference |
| `receivedDateTime` | ISO 8601 | When the message was received |
| `createdDateTime` | ISO 8601 | When the message was created |

### Error Responses

#### ErrorInvalidIdMalformed
**Status:** 400 Bad Request  
**Cause:** Message ID format is invalid or not found  
**Solution:** Verify message ID from the current email list response (don't reuse IDs from previous operations)

```json
{
  "error": {
    "code": "ErrorInvalidIdMalformed",
    "message": "The identifier is malformed."
  }
}
```

#### ErrorItemNotFound
**Status:** 404 Not Found  
**Cause:** Message doesn't exist (may have been deleted)  
**Solution:** Refresh the email list; the message may have been removed

#### ErrorAccessDenied
**Status:** 403 Forbidden  
**Cause:** User doesn't have permission to move messages  
**Solution:** Verify authentication and Archive folder access permissions

### Critical Implementation Notes

1. **One Email Per Call:** Always move ONE email per API call. Do NOT attempt batch operations.
   - ❌ Wrong: Moving multiple messageIds in a single call
   - ✅ Correct: Call once per messageId

2. **Message ID Validation:** 
   - Valid format starts with `AAMk` followed by base64-encoded characters
   - Invalid: Using old message IDs or malformed IDs causes `ErrorInvalidIdMalformed`

3. **Folder ID Confirmation:**
   - Always check the response `parentFolderId` matches the destination
   - This confirms the move was successful

4. **No Batch Operations:**
   - Attempting to move multiple emails in a single request will fail
   - This is a common source of errors; always iterate and call individually

### Example: Correct Usage

```python
# Move ONE email to Archive
response = mcp__ms365__move-mail-message(
    messageId="AAMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwNGE0MgBGAAA...",
    body={"DestinationId": "AQMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwADRhNDIALgAAA-cCSmDe9C5Ai1IxFty3vKgBACIai-AjXXpFuMeLL-NexTAAAAIBVAAAAA=="}
)

# Verify success
if response["parentFolderId"] == archive_folder_id:
    print("✅ Email moved successfully to Archive")
else:
    print("❌ Email moved to wrong folder")
```

### Example: Bulk Operations (Correct Pattern)

```python
# Move MULTIPLE emails - iterate one at a time
message_ids = ["AAMk...", "AAMk...", "AAMk..."]
archive_folder_id = "AQMkADA4YjhhZDYwLWZiMWYt..."

results = []
for msg_id in message_ids:
    # ONE call per email
    response = mcp__ms365__move-mail-message(
        messageId=msg_id,
        body={"DestinationId": archive_folder_id}
    )
    results.append(response)
    
print(f"Moved {len(results)} emails to Archive")
```
