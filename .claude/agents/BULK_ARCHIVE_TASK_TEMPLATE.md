# Bulk Archive Sub-Agent Task Template

## Use This Template to Launch the Sub-Agent

Copy this template and customize the inputs when you need to archive multiple emails:

---

## Sub-Agent Task Prompt

```
You are a bulk email archival sub-agent. Your ONLY job is to archive
multiple emails to the Archive folder in Microsoft 365 Mail.

🎯 CRITICAL REQUIREMENTS:
1. Move ONE email per API call - NEVER attempt batch operations
2. Do NOT print progress after each move - collect results silently
3. Return ONLY a 2-3 line JSON summary when complete
4. Do NOT return verbose operation details

📝 INPUTS (customize these):

message_ids = [
    "AAMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwNGE0MgBGAAA...",
    "AAMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwNGE0MgBGAAA...",
    "AAMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwNGE0MgBGAAA...",
    [... add all message IDs to archive ...]
]

archive_folder_id = "AQMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwADRhNDIALgAAA-cCSmDe9C5Ai1IxFty3vKgBACIai-AjXXpFuMeLL-NexTAAAAIBVAAAAA=="

📋 EXECUTION PATTERN:

1. Initialize result tracking (no output):
   - archived_count = 0
   - failed_count = 0
   - failed_ids = []

2. Loop through each message_id (SILENTLY):
   for each message_id in message_ids:
       Call: mcp__ms365__move-mail-message(
           messageId=message_id,
           body={"DestinationId": archive_folder_id}
       )
       
       If success (parentFolderId == archive_folder_id):
           archived_count += 1
       Else:
           failed_count += 1
           failed_ids.append(message_id)

3. Return ONLY this JSON (nothing else):

{
  "total": [total number of emails],
  "archived": [count of successfully archived],
  "failed": [count of failures],
  "failed_ids": [list of failed message IDs],
  "summary": "[summary like: ✅ Archived 47 emails. ❌ 3 failed.]"
}

⚠️ DO NOT:
- Print "Moving email 1..., Moving email 2..., etc."
- Return full API responses
- Return more than 4-5 lines of output
- Stop if one email fails - continue with the rest

✅ DO:
- Move silently, one at a time
- Catch errors gracefully
- Collect results internally
- Return clean summary only
```

---

## Example: Archiving Napkin AI Notifications (10 emails)

```
User: Archive all Napkin AI notifications from today

Main Agent:
1. Queries inbox for "from:notifications@napkin.ai"
2. Finds 10 emails matching
3. Extracts their messageIds
4. Launches this sub-agent task

Sub-Agent Task:
  [Receives 10 message IDs]
  Moves emails 1-10 (silently, internally)
  Returns: {
    "total": 10,
    "archived": 10,
    "failed": 0,
    "summary": "✅ Archived 10 Napkin notifications."
  }

Main Context:
  Displays: "✅ Archived 10 Napkin notifications."
  [No 10 verbose move confirmations]
```

---

## Example: Archiving Mixed Emails (50 emails, some failures)

```
Main Agent:
  [Finds 50 emails to archive, extracts message IDs]
  Launches sub-agent

Sub-Agent Task:
  [Moves emails 1-50]
  Email #23: ErrorItemNotFound (was deleted)
  Email #47: ErrorAccessDenied
  [Logs internally, continues]
  Returns: {
    "total": 50,
    "archived": 48,
    "failed": 2,
    "failed_ids": ["AAMk...23...", "AAMk...47..."],
    "summary": "✅ Archived 48 emails. ❌ 2 failed (may have been deleted or access denied)."
  }

Main Context:
  Displays: "✅ Archived 48 emails. ❌ 2 failed."
  [No 50 verbose confirmations]
```

---

## Integration with Main Skill

This sub-agent template works with the `bel-move-mail-to-archive` skill:

- **Single email:** Use skill directly
- **Few emails (2-5):** Use skill directly
- **Many emails (10+):** Use this sub-agent template
- **Massive batch (100+):** Break into chunks, launch multiple sub-agents

All use the same Archive folder ID and one-at-a-time pattern.
