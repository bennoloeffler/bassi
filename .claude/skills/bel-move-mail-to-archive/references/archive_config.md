# Archive Folder Configuration

## Default Archive Folder ID

**User:** loeffler@v-und-s.de (Benno Löffler)

```
AQMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwADRhNDIALgAAA-cCSmDe9C5Ai1IxFty3vKgBACIai-AjXXpFuMeLL-NexTAAAAIBVAAAAA==
```

## How This ID Was Determined

This folder ID was obtained through:
1. Querying `mcp__ms365__list-mail-folders` to list all user folders
2. Identifying the "Archive" folder in the results
3. Extracting the folder ID from the response

## Validating the Archive Folder

To verify this ID is correct:

```python
# List all mail folders
folders = mcp__ms365__list-mail-folders()

# Find the Archive folder
archive_folder = next(
    (f for f in folders["value"] if f["displayName"] == "Archive"),
    None
)

if archive_folder:
    print(f"Archive Folder ID: {archive_folder['id']}")
else:
    print("Archive folder not found!")
```

## Using Custom Archive IDs

Some users may have:
- Multiple archive folders
- Custom archive folder names (e.g., "Old Mail", "Archive 2024")
- Different folder structures

To use a custom archive folder:

1. **Identify the folder ID:**
   ```python
   folders = mcp__ms365__list-mail-folders()
   for f in folders["value"]:
       print(f"{f['displayName']}: {f['id']}")
   ```

2. **Pass custom ID to move operation:**
   ```python
   mcp__ms365__move-mail-message(
       messageId="AAMk...",
       body={"DestinationId": "your-custom-folder-id"}
   )
   ```

## Folder ID Format

Archive folder IDs follow this pattern:
- Prefix: `AQMk` (identifies as folder resource)
- Encoded user/mailbox info: `ADA4YjhhZDYwLWZiMWY...`
- Folder identifier suffix: `...IIBVAAAAA==`

Example structure (not actual, for reference):
```
AQMk[mailbox-id]ALgAAA-[folder-uuid]IIBVAAAAA==
```

## Important: Never Hardcode for Different Users

If building tools for multiple users, ALWAYS:
1. Query `mcp__ms365__list-mail-folders` for each user
2. Identify their Archive folder dynamically
3. Never reuse archive IDs across different user contexts

Hardcoding the Archive ID for one user into tools used by other users will cause moves to go to the wrong folder.

## Migration: Changing Archive Location

If a user changes their archive folder:

1. **Update the ID** in your configuration
2. **Verify** with a test move to the new folder
3. **Check** that `parentFolderId` in response matches new folder ID

Example verification:
```python
# Move one email to new archive folder
response = mcp__ms365__move-mail-message(
    messageId="test-msg-id",
    body={"DestinationId": "new-archive-folder-id"}
)

# Confirm it went to the right place
assert response["parentFolderId"] == "new-archive-folder-id", "Move failed!"
```

## Related Folders

Common MS365 Mail folder IDs:
- **Inbox:** `AQMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwADRhNDIALgAAA-cCSmDe9C5Ai1IxFty3vKgBACIai-AjXXpFuMeLL-NexTAAAAIQAAAA==`
- **Deleted Items:** (query list-mail-folders)
- **Drafts:** (query list-mail-folders)
- **Sent Items:** (query list-mail-folders)

Query `mcp__ms365__list-mail-folders` to see all available folders for a user.
