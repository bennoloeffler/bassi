# Bulk Archive Sub-Agent

## Purpose

Execute bulk email archival operations in an isolated sub-agent to keep the main conversation context clean. The sub-agent handles moving multiple emails to Archive without polluting the main context with verbose operation details.

## Why Use a Sub-Agent?

**Problem:** Moving 50+ emails one at a time creates 50+ API response messages, flooding the context window.

**Solution:** Sub-agent handles all moves internally and returns only:
```
✅ Archived 47 emails
❌ Failed to archive 3 emails

Summary:
  - Deleted items: 3
  - Napkin AI notifications: 15
  - Status updates: 29
```

Instead of 50 individual operation results.

## Architecture

```
Main Context
    ↓
    Create bulk archive list (message IDs)
    ↓
    Launch Sub-Agent with:
      - List of messageIds
      - Archive folder ID (optional)
    ↓
Sub-Agent (Isolated)
    ↓
    Loop through messageIds (one at a time)
    ↓
    Call mcp__ms365__move-mail-message for each
    ↓
    Collect results internally (NOT printed)
    ↓
    Return summary to main context
    ↓
Main Context
    ↓
    Receives clean summary (3-4 lines)
```

## Usage Pattern

### Step 1: Prepare Message IDs in Main Context

```
User: "Archive these emails: [list of subjects]"

Main Agent:
  1. Query inbox for emails
  2. Identify matching emails
  3. Extract messageIds: ["AAMk...", "AAMk...", ...]
  4. Launch bulk archive sub-agent
```

### Step 2: Launch Sub-Agent

**Instruction to Claude:**
```
Launch a sub-agent to archive 50 emails. 

Pass:
- List of 50 message IDs (from previous step)
- Archive folder ID: AQMkADA4YjhhZDYwLWZiMWY...
- Task: Move each email to Archive, one at a time
- Return: Only summary (count moved, count failed)

The sub-agent should:
1. Move emails one at a time using mcp__ms365__move-mail-message
2. Track successes and failures internally
3. Return a 2-3 line summary to main context
```

### Step 3: Receive Summary

Sub-agent returns:
```json
{
  "total": 50,
  "archived": 47,
  "failed": 3,
  "failed_ids": ["AAMk...", "AAMk...", "AAMk..."],
  "summary": "✅ Successfully archived 47 emails. 3 failed (may have been deleted)."
}
```

Main context receives only this summary - no verbose output.

## Sub-Agent Implementation Details

### Critical Rules

1. **One Email Per Call:** Loop through messageIds, move ONE per iteration
   ```python
   for message_id in message_ids:
       response = mcp__ms365__move-mail-message(
           messageId=message_id,
           body={"DestinationId": archive_folder_id}
       )
       # Track result, don't print
       if response.get("parentFolderId") == archive_folder_id:
           success_count += 1
       else:
           failed.append(message_id)
   ```

2. **Silent Iteration:** Collect results but don't print intermediate steps
   - ❌ Print after each email: "Email moved... Email moved... Email moved..."
   - ✅ Collect and return only final summary

3. **Error Handling:** Catch errors gracefully
   ```python
   try:
       response = mcp__ms365__move-mail-message(...)
       # Track success
   except Exception as e:
       failed.append({
           "message_id": message_id,
           "error": str(e)
       })
   ```

4. **Return Summary Only:** 2-3 lines maximum
   ```python
   return {
       "archived": 47,
       "failed": 3,
       "summary": f"✅ Archived {47} emails. ❌ Failed on {3}."
   }
   ```

## Example: Main Context Conversation

### Before Sub-Agent (Context Explosion)

```
User: Archive 50 emails
Agent: Moving email 1... ✅ Moved
Agent: Moving email 2... ✅ Moved
Agent: Moving email 3... ✅ Moved
Agent: Moving email 4... ✅ Moved
[... 46 more move confirmations ...]
```

Result: 50+ messages in context, wastes tokens.

### After Sub-Agent (Context Efficient)

```
User: Archive 50 emails
Agent: [Identifies 50 emails]
Agent: Launching bulk archive sub-agent...

[Sub-Agent runs internally, moves all 50 emails]

Agent: ✅ Successfully archived 47 emails. 
       ❌ 3 failed (may have been deleted).
```

Result: Context stays clean, operation completes efficiently.

## Sub-Agent Task Prompt Template

Use this prompt when launching the sub-agent:

```
You are a bulk email archival agent. Your job is to archive multiple emails
to the Archive folder in Microsoft 365 Mail, WITHOUT polluting the context.

CRITICAL RULES:
1. Move ONE email per call - NEVER batch operations
2. Do NOT print progress after each move
3. Collect all results internally
4. Return ONLY a 2-3 line summary when done

INPUTS:
- messageIds: [list of 50+ email message IDs]
- archive_folder_id: AQMkADA4YjhhZDYwLWZiMWY...

EXECUTION:
1. Loop through messageIds
2. For each ID, call: mcp__ms365__move-mail-message(messageId=id, body={"DestinationId": archive_folder_id})
3. Track successes and failures internally (do not print)
4. After all moves complete, return JSON summary

RETURN FORMAT:
{
  "archived": <number>,
  "failed": <number>,
  "summary": "<one line summary>"
}

Do not print anything else. Return only the JSON above.
```

## Error Handling

### Common Errors and Recovery

| Error | Cause | Sub-Agent Action |
|-------|-------|-----------------|
| ErrorInvalidIdMalformed | Bad message ID | Log, skip, continue with next |
| ErrorItemNotFound | Email deleted | Log, skip, continue |
| ErrorAccessDenied | Permission error | Log, report in summary |
| Network timeout | Temporary issue | Retry once, then skip |

Sub-agent should catch these and log internally, not stop the entire batch.

## Performance Notes

- **Batch of 50 emails:** ~10-15 seconds (1 API call per 0.2-0.3 sec)
- **Batch of 100 emails:** ~20-30 seconds
- **Batch of 500 emails:** ~100-150 seconds

For very large batches (500+), consider breaking into chunks:
- Chunk 1: Move first 100
- Chunk 2: Move next 100
- Etc.

Each chunk gets its own summary line.

## Integration with Main Skill

The `bel-move-mail-to-archive` skill is designed for:
- **Single moves:** Direct API call, works inline
- **Bulk moves:** Launch sub-agent (this file describes how)

The sub-agent uses the same Archive folder ID and one-at-a-time pattern as the main skill, just encapsulated to avoid context pollution.
