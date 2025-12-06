"""
E2E Tests for Session UX Behaviors.

Tests user-facing behaviors:
- history.md not appearing in file listings
- Chat formatting consistency between real-time and restored sessions
- No message duplication when switching sessions

Uses Chrome DevTools MCP for real browser testing.
"""

import pytest

# Mark all tests to run on same worker (shared live_server)
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.xdist_group(name="e2e_server"),
]


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="MCP chrome-devtools integration not yet implemented"
)
async def test_history_md_not_in_file_list(
    running_server, chrome_devtools_client
):
    """
    Test that history.md does NOT appear in session file listings.

    User requirement: "it should not be shown as file, because it is the CONTENT of the chat"

    This was Bug #3 from SESSION_MANAGEMENT_FIXES_2025-11-15.md
    """
    try:
        # Navigate to app
        await chrome_devtools_client.navigate_page({"url": running_server})

        # Wait for page load
        await chrome_devtools_client.wait_for({"text": "Bassi"})

        # Take snapshot to find "New Session" button
        snapshot = await chrome_devtools_client.take_snapshot({})

        # Find and click "+ New Session" button
        new_session_btn = None
        for element in snapshot.get("elements", []):
            if "New Session" in element.get("name", ""):
                new_session_btn = element.get("uid")
                break

        assert new_session_btn, "Could not find '+ New Session' button"
        await chrome_devtools_client.click({"uid": new_session_btn})

        # Wait for session to be created
        await chrome_devtools_client.wait_for({"text": "Type a message"})

        # Send a message to create some history
        snapshot = await chrome_devtools_client.take_snapshot({})

        # Find input field
        input_field = None
        for element in snapshot.get("elements", []):
            role = element.get("role", "")
            if role == "textbox" and "Type a message" in element.get(
                "name", ""
            ):
                input_field = element.get("uid")
                break

        assert input_field, "Could not find message input field"

        # Type a test message
        await chrome_devtools_client.fill(
            {"uid": input_field, "value": "test message for file listing"}
        )

        # Find and click send button
        snapshot = await chrome_devtools_client.take_snapshot({})
        send_btn = None
        for element in snapshot.get("elements", []):
            if (
                element.get("name") == "Send"
                and element.get("role") == "button"
            ):
                send_btn = element.get("uid")
                break

        assert send_btn, "Could not find Send button"
        await chrome_devtools_client.click({"uid": send_btn})

        # Wait for response to complete
        import asyncio

        await asyncio.sleep(5)  # Wait for agent response

        # Now check the file list via API
        import httpx

        # Get session ID from frontend
        script_result = await chrome_devtools_client.evaluate_script(
            {"function": "() => { return window.bassiApp.sessionId; }"}
        )
        session_id = script_result.get("result", {}).get("value")

        assert session_id, "Session ID not found in frontend state"

        # Fetch file list from API
        response = httpx.get(
            f"{running_server}/api/sessions/{session_id}/files"
        )
        assert (
            response.status_code == 200
        ), f"API returned {response.status_code}"

        files = response.json()

        # Verify history.md is NOT in the list
        file_names = [f.get("path") for f in files]
        assert "history.md" not in file_names, (
            "❌ BUG: history.md appeared in file list! "
            "It should be excluded as it's conversation content, not a user file."
        )

        print("✅ history.md correctly excluded from file listings")

    except Exception as e:
        pytest.fail(f"Test failed: {e}")


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="MCP chrome-devtools integration not yet implemented"
)
async def test_no_message_duplication_on_session_switch(
    running_server, chrome_devtools_client
):
    """
    Test that messages are NOT duplicated when switching sessions.

    User concern: "there are many repetitions of the chat when reactivated"

    This test verifies:
    1. Messages saved once to history.md
    2. Messages rendered once when switching back
    3. No duplicate rendering from user_message_echo events
    4. No duplicate rendering from multiple loadSessionHistory() calls
    """
    try:
        # Navigate to app
        await chrome_devtools_client.navigate_page({"url": running_server})
        await chrome_devtools_client.wait_for({"text": "Bassi"})

        # Send a message
        snapshot = await chrome_devtools_client.take_snapshot({})

        input_uid = None
        for el in snapshot.get("elements", []):
            if el.get("role") == "textbox" and "Type a message" in el.get(
                "name", ""
            ):
                input_uid = el.get("uid")
                break

        await chrome_devtools_client.fill(
            {"uid": input_uid, "value": "test for duplication"}
        )

        snapshot = await chrome_devtools_client.take_snapshot({})
        send_uid = None
        for el in snapshot.get("elements", []):
            if el.get("name") == "Send" and el.get("role") == "button":
                send_uid = el.get("uid")
                break

        await chrome_devtools_client.click({"uid": send_uid})

        # Wait for response
        import asyncio

        await asyncio.sleep(5)

        # Count messages in UI (should be 1 user + 1 assistant = 2 total)
        message_count_realtime = await chrome_devtools_client.evaluate_script(
            {
                "function": """() => {
                const conv = document.querySelector('.conversation');
                return conv ? conv.children.length : 0;
            }"""
            }
        )
        realtime_count = message_count_realtime.get("result", {}).get(
            "value", 0
        )

        assert (
            realtime_count == 2
        ), f"Expected 2 messages (1 user + 1 assistant), got {realtime_count}"

        # Get session ID
        session_id_result = await chrome_devtools_client.evaluate_script(
            {"function": "() => { return window.bassiApp.sessionId; }"}
        )
        first_session_id = session_id_result.get("result", {}).get("value")

        # Verify history file (via API)
        import httpx

        response = httpx.get(
            f"{running_server}/api/sessions/{first_session_id}/messages"
        )
        assert response.status_code == 200

        messages_from_api = response.json().get("messages", [])
        assert (
            len(messages_from_api) == 2
        ), f"Expected 2 messages in history, got {len(messages_from_api)}"

        # Create new session
        snapshot = await chrome_devtools_client.take_snapshot({})
        new_session_btn = None
        for el in snapshot.get("elements", []):
            if "New Session" in el.get("name", ""):
                new_session_btn = el.get("uid")
                break

        await chrome_devtools_client.click({"uid": new_session_btn})
        await asyncio.sleep(2)

        # Switch back to first session
        snapshot = await chrome_devtools_client.take_snapshot({})
        session_link = None
        for el in snapshot.get("elements", []):
            if first_session_id[:8] in el.get("name", ""):
                session_link = el.get("uid")
                break

        await chrome_devtools_client.click({"uid": session_link})
        await asyncio.sleep(2)

        # Count messages after restoration
        message_count_restored = await chrome_devtools_client.evaluate_script(
            {
                "function": """() => {
                const conv = document.querySelector('.conversation');
                return conv ? conv.children.length : 0;
            }"""
            }
        )
        restored_count = message_count_restored.get("result", {}).get(
            "value", 0
        )

        # CRITICAL: Should still be 2 messages, NOT duplicated
        assert restored_count == 2, (
            f"❌ MESSAGE DUPLICATION BUG! Expected 2 messages after restore, "
            f"got {restored_count}. Messages were duplicated during session switch!"
        )

        # Also verify via API that history file wasn't duplicated
        response2 = httpx.get(
            f"{running_server}/api/sessions/{first_session_id}/messages"
        )
        messages_after_switch = response2.json().get("messages", [])

        assert len(messages_after_switch) == 2, (
            f"❌ HISTORY FILE DUPLICATION! Expected 2 messages in history after switch, "
            f"got {len(messages_after_switch)}"
        )

        print(
            "✅ No message duplication: UI has 2 messages, history has 2 messages"
        )

    except Exception as e:
        pytest.fail(f"Test failed: {e}")
