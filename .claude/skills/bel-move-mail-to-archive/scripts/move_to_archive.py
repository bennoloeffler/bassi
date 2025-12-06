#!/usr/bin/env python3
"""
Move a single email to Archive folder in Microsoft 365 Mail.

This script encapsulates the email move operation to keep context clean
and enable bulk operations via external orchestration.

Usage:
    python move_to_archive.py --message-id "AAMkADA4YjhhZDYwLWZi..." [--archive-id "AQMkADA4..."]

Returns:
    JSON with operation result or error message
"""

import argparse
import json
import sys

# Default Archive folder ID (from live testing)
DEFAULT_ARCHIVE_FOLDER_ID = "AQMkADA4YjhhZDYwLWZiMWYtNDVkMy1hNjE3LWI3YzRlMzAwADRhNDIALgAAA-cCSmDe9C5Ai1IxFty3vKgBACIai-AjXXpFuMeLL-NexTAAAAIBVAAAAA=="


def move_email_to_archive(
    message_id: str, archive_folder_id: str = None
) -> dict:
    """
    Move a single email to Archive folder.

    Args:
        message_id: The MS365 message ID to move
        archive_folder_id: Optional custom Archive folder ID (uses default if not provided)

    Returns:
        dict: Result with status, message, and optional parentFolderId confirmation

    Note:
        This function should be called with mcp__ms365__move-mail-message API.
        Integrate with Claude's AI tools in the actual deployment.
    """

    if not message_id:
        return {
            "status": "error",
            "message": "message_id is required",
            "code": "MISSING_MESSAGE_ID",
        }

    if not archive_folder_id:
        archive_folder_id = DEFAULT_ARCHIVE_FOLDER_ID

    # Validate message ID format (basic check)
    if not message_id.startswith("AAMk"):
        return {
            "status": "error",
            "message": f"Invalid message ID format. Expected format starting with 'AAMk', got: {message_id[:20]}...",
            "code": "INVALID_MESSAGE_ID_FORMAT",
        }

    # Return the operation parameters (to be executed via API)
    return {
        "status": "ready",
        "message": "Email move operation ready to execute",
        "operation": {
            "api_function": "mcp__ms365__move-mail-message",
            "parameters": {
                "messageId": message_id,
                "body": {"DestinationId": archive_folder_id},
            },
        },
        "archive_folder_id": archive_folder_id,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Move a single email to Archive folder in MS365 Mail"
    )
    parser.add_argument(
        "--message-id",
        "-m",
        required=True,
        help="The MS365 message ID of the email to move",
    )
    parser.add_argument(
        "--archive-id",
        "-a",
        default=None,
        help=f"Custom Archive folder ID (default: {DEFAULT_ARCHIVE_FOLDER_ID[:50]}...)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="Output result as JSON (default: True)",
    )

    args = parser.parse_args()

    # Execute the move
    result = move_email_to_archive(
        message_id=args.message_id, archive_folder_id=args.archive_id
    )

    # Output result
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["status"] == "ready":
            print(f"✅ Ready to move: {result['message']}")
            print(f"   Message ID: {args.message_id}")
            print(f"   Archive Folder: {result['archive_folder_id'][:50]}...")
        else:
            print(f"❌ Error: {result['message']}")
            sys.exit(1)

    return 0 if result["status"] != "error" else 1


if __name__ == "__main__":
    sys.exit(main())
