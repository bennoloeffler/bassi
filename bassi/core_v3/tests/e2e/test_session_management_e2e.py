"""
End-to-End Test for Session Management.

Tests the complete session management flow using real browser automation
via Chrome DevTools MCP:
- Session creation (+ New Session button)
- Session switching
- History restoration
- Connection stability
- Send button state
"""

import asyncio
import logging

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
@pytest.mark.skip(
    reason="MCP chrome-devtools integration not yet implemented"
)
async def test_session_management_full_flow(
    running_server, chrome_devtools_client
):
    """
    E2E test for complete session management flow.

    Tests:
    1. Create new session (+ New Session button)
    2. Send message in first session
    3. Create second session
    4. Send message in second session
    5. Switch back to first session
    6. Verify history restoration
    7. Verify send button always active
    8. Verify no unwanted disconnections

    Prerequisites:
        - running_server fixture: Server running at http://localhost:8765
        - chrome_devtools_client: Chrome DevTools MCP client
    """
    server_url = running_server
    client = chrome_devtools_client

    # Step 1: Navigate to app
    logger.info("Step 1: Navigate to Bassi UI")
    await client.navigate_page({"url": server_url})

    # Wait for initial connection
    await asyncio.sleep(2)

    # Step 2: Verify initial connection status
    logger.info("Step 2: Verify initial connection")
    snapshot = await client.take_snapshot({})
    assert "Disconnected" not in snapshot, "Should be connected initially"

    # Step 3: Create first session by sending a message
    logger.info("Step 3: Create first session")
    result = await client.evaluate_script(
        {
            "function": """
        () => {
            const textarea = document.querySelector('textarea');
            const sendBtn = document.querySelector('button.send-btn');
            if (!textarea || !sendBtn) {
                return {
                    success: false,
                    message: 'Input elements not found'
                };
            }
            textarea.value = 'Who was Brian Johnson?';
            textarea.dispatchEvent(
                new Event('input', { bubbles: true })
            );
            sendBtn.click();
            return { success: true, sessionId: window.bassiClient.sessionId };
        }
        """
        }
    )
    assert result["success"], "Failed to send first message"
    first_session_id = result["sessionId"]
    logger.info(f"First session created: {first_session_id[:8]}...")

    # Wait for response (auto-naming will trigger)
    await asyncio.sleep(5)

    # Step 4: Verify send button is active
    logger.info("Step 4: Verify send button state")
    result = await client.evaluate_script(
        {
            "function": """
        () => {
            const sendBtn = document.querySelector('button.send-btn');
            return { disabled: sendBtn.disabled };
        }
        """
        }
    )
    assert not result["disabled"], "Send button should not be disabled"

    # Step 5: Create second session using + New Session button
    logger.info("Step 5: Create second session")
    result = await client.evaluate_script(
        {
            "function": """
        () => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const newSessionBtn = buttons.find(
                btn => btn.textContent.includes('New Session')
            );
            if (!newSessionBtn) {
                return { success: false, message: 'Button not found' };
            }
            newSessionBtn.click();
            return { success: true };
        }
        """
        }
    )
    assert result["success"], "Failed to click + New Session button"

    # Wait for new session connection
    await asyncio.sleep(2)

    # Step 6: Get second session ID and verify it's different
    logger.info("Step 6: Verify new session created")
    result = await client.evaluate_script(
        {"function": "() => ({ sessionId: window.bassiClient.sessionId })"}
    )
    second_session_id = result["sessionId"]
    assert (
        second_session_id != first_session_id
    ), "Should have created a new session"
    logger.info(f"Second session created: {second_session_id[:8]}...")

    # Step 7: Send message in second session
    logger.info("Step 7: Send message in second session")
    result = await client.evaluate_script(
        {
            "function": """
        () => {
            const textarea = document.querySelector('textarea');
            const sendBtn = document.querySelector('button.send-btn');
            textarea.value = 'What is Python?';
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            sendBtn.click();
            return { success: true };
        }
        """
        }
    )
    assert result["success"], "Failed to send second message"
    await asyncio.sleep(3)

    # Step 8: Fetch sessions list and verify both exist
    logger.info("Step 8: Verify both sessions exist in API")
    result = await client.evaluate_script(
        {
            "function": f"""
        async () => {{
            const response = await fetch('/api/sessions');
            const sessions = await response.json();
            const first = sessions.find(
                s => s.session_id === '{first_session_id}'
            );
            const second = sessions.find(
                s => s.session_id === '{second_session_id}'
            );
            return {{
                firstFound: !!first,
                secondFound: !!second,
                firstMessageCount: first ? first.message_count : 0,
                secondMessageCount: second ? second.message_count : 0
            }};
        }}
        """
        }
    )
    assert result["firstFound"], "First session should exist in API"
    assert result["secondFound"], "Second session should exist in API"
    assert (
        result["firstMessageCount"] >= 2
    ), "First session should have >=2 messages"
    assert (
        result["secondMessageCount"] >= 2
    ), "Second session should have >=2 messages"

    # Step 9: Switch back to first session
    logger.info("Step 9: Switch back to first session")
    result = await client.evaluate_script(
        {
            "function": f"""
        () => {{
            window.bassiClient.switchSession('{first_session_id}');
            return {{ success: true }};
        }}
        """
        }
    )
    assert result["success"], "Failed to switch sessions"
    await asyncio.sleep(2)

    # Step 10: Verify session switched and history restored
    logger.info("Step 10: Verify history restoration")
    result = await client.evaluate_script(
        {
            "function": """
        () => {
            const messages = window.bassiClient.conversationEl.querySelectorAll(
                '.message'
            );
            const currentSessionId = window.bassiClient.sessionId;
            return {
                messageCount: messages.length,
                sessionId: currentSessionId,
                hasHistory: messages.length > 0
            };
        }
        """
        }
    )
    assert (
        result["sessionId"] == first_session_id
    ), "Should have switched to first session"
    assert result["hasHistory"], "Should have restored message history"
    assert (
        result["messageCount"] >= 2
    ), "Should have at least 2 messages from history"
    logger.info(
        f"Session switched successfully, restored {result['messageCount']} messages"
    )

    # Step 11: Verify no unwanted reconnections in console
    logger.info("Step 11: Check for unwanted reconnections")
    console_logs = await client.list_console_messages({})
    reconnect_logs = [
        log
        for log in console_logs.get("messages", [])
        if "Reconnecting" in log.get("text", "")
        and "Intentional disconnect" not in log.get("text", "")
    ]
    assert len(reconnect_logs) == 0, (
        f"Should not have unwanted reconnections, " f"found: {reconnect_logs}"
    )

    # Step 12: Verify session files (history.md should exist)
    logger.info("Step 12: Verify session files")
    result = await client.evaluate_script(
        {
            "function": """
        () => {
            const fileChips = window.bassiClient.sessionFiles;
            const historyFile = fileChips.find(
                f => f.name === 'history.md'
            );
            return {
                hasHistoryFile: !!historyFile,
                fileCount: fileChips.length
            };
        }
        """
        }
    )
    assert result["hasHistoryFile"], "Session should have history.md file"
    logger.info(
        f"Session has {result['fileCount']} files including history.md"
    )

    # Step 13: Rapid session creation test (pool handling)
    logger.info("Step 13: Test rapid session creation")
    for i in range(3):
        result = await client.evaluate_script(
            {
                "function": """
            () => {
                const buttons = Array.from(
                    document.querySelectorAll('button')
                );
                const newSessionBtn = buttons.find(
                    btn => btn.textContent.includes('New Session')
                );
                newSessionBtn.click();
                return { success: true };
            }
            """
            }
        )
        assert result["success"], f"Failed rapid creation attempt {i+1}"
        await asyncio.sleep(0.5)  # 500ms between clicks

    # Wait for all connections to settle
    await asyncio.sleep(2)

    # Verify no error logs from rapid creation
    console_logs = await client.list_console_messages({})
    error_logs = [
        log
        for log in console_logs.get("messages", [])
        if log.get("level") == "error"
    ]
    assert (
        len(error_logs) == 0
    ), f"Should not have errors during rapid creation: {error_logs}"

    logger.info("✅ All session management tests passed!")


@pytest.mark.e2e
@pytest.mark.xdist_group(name="e2e_server")
@pytest.mark.skip(
    reason="MCP chrome-devtools integration not yet implemented"
)
async def test_session_creation_no_unwanted_reconnect(
    running_server, chrome_devtools_client
):
    """
    Regression test: Verify "+ New Session" doesn't trigger unwanted reconnection.

    Bug history:
    - Original bug: Clicking "+ New Session" caused immediate disconnection loop
    - Root cause 1: websocket.accept() called after pool.acquire()
    - Root cause 2: createNewSession() didn't set isIntentionalDisconnect flag

    This test verifies both fixes are working.
    """
    server_url = running_server
    client = chrome_devtools_client

    # Navigate to app
    await client.navigate_page({"url": server_url})
    await asyncio.sleep(2)

    # Clear console logs
    await client.evaluate_script({"function": "() => console.clear()"})

    # Click + New Session
    result = await client.evaluate_script(
        {
            "function": """
        () => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const newSessionBtn = buttons.find(
                btn => btn.textContent.includes('New Session')
            );
            if (!newSessionBtn) {
                return { success: false };
            }
            newSessionBtn.click();
            return { success: true };
        }
        """
        }
    )
    assert result["success"], "Failed to click button"

    # Wait for connection
    await asyncio.sleep(2)

    # Check console logs for unwanted reconnection
    console_logs = await client.list_console_messages({})
    log_texts = [
        log.get("text", "") for log in console_logs.get("messages", [])
    ]

    # Should see "Intentional disconnect" message
    intentional_disconnect = any(
        "Intentional disconnect" in text for text in log_texts
    )
    assert (
        intentional_disconnect
    ), "Should have intentional disconnect message"

    # Should NOT see "Resuming session" after new session creation
    resuming_logs = [text for text in log_texts if "Resuming session" in text]
    assert (
        len(resuming_logs) == 0
    ), f"Should not resume newly created session: {resuming_logs}"

    logger.info("✅ No unwanted reconnection after + New Session")
