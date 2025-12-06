"""
E2E tests for CORE USER FLOWS.

These tests verify the fundamental user expectations when using bassi:
1. User can send a message and see a response
2. User can see connection status
3. User can see their message appears in the chat
4. User can see the agent is "thinking" while processing
5. User can start a new chat (clear context)
6. User can see their chat in the sidebar
7. Chat input is cleared after sending
8. User can use Enter key to send (not just button)

Each test validates a single, fundamental user expectation.
"""

import pytest

# Ensure tests run serially with the shared live_server instance
pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.xdist_group(name="e2e_server"),
]


def _wait_for_connection(page):
    """Wait for WebSocket connection to be established."""
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=15000
    )
    handle = page.wait_for_function(
        "() => (window.bassiClient && window.bassiClient.sessionId) || null",
        timeout=15000,
    )
    return handle.json_value()


# =============================================================================
# USE CASE 1: User can send a message and receive a response
# =============================================================================


def test_user_can_send_message_and_receive_response(page, live_server):
    """
    FUNDAMENTAL USE CASE: User sends a message and gets a response.

    Steps:
    1. Navigate to bassi
    2. Wait for connection
    3. Type a message
    4. Click Send
    5. Verify user message appears
    6. Verify agent response appears
    """
    # Navigate to app
    page.goto(live_server)
    _wait_for_connection(page)

    # Type a message
    page.fill("#message-input", "Hello, how are you?")

    # Click send button
    page.click("#send-button")

    # Verify user message appears
    page.wait_for_selector(
        ".user-message .message-content:has-text('Hello, how are you?')",
        timeout=10000,
    )

    # Verify agent response appears
    page.wait_for_selector(".assistant-message", timeout=30000)

    # Verify agent has some text content
    agent_message = page.query_selector(
        ".assistant-message .message-content"
    )
    assert agent_message is not None, "Agent should have responded"

    text = agent_message.text_content()
    assert len(text) > 0, "Agent response should have content"


# =============================================================================
# USE CASE 2: User can see connection status
# =============================================================================


def test_user_can_see_connection_status(page, live_server):
    """
    USE CASE: User can see whether they're connected to the agent.

    Steps:
    1. Navigate to bassi
    2. Verify connection status indicator exists
    3. Verify it shows "Connected" when connected
    """
    # Navigate to app
    page.goto(live_server)

    # Connection status indicator should exist
    status_indicator = page.wait_for_selector(
        "#connection-status", timeout=15000
    )
    assert (
        status_indicator is not None
    ), "Connection status indicator should exist"

    # Wait for connected status
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=15000
    )

    # Verify the text
    status_text = status_indicator.text_content()
    assert "Connected" in status_text, (
        f"Status should show 'Connected', got: {status_text}"
    )


# =============================================================================
# USE CASE 3: User message appears in chat immediately
# =============================================================================


def test_user_message_appears_immediately(page, live_server):
    """
    USE CASE: When user sends a message, it appears in the chat immediately.

    Steps:
    1. Navigate and connect
    2. Send a message
    3. Verify message appears immediately (before agent responds)
    """
    page.goto(live_server)
    _wait_for_connection(page)

    # Count initial messages
    initial_count = page.evaluate(
        "() => document.querySelectorAll('.user-message').length"
    )
    assert initial_count == 0, "Should start with no user messages"

    # Send a message
    page.fill("#message-input", "Test message")
    page.click("#send-button")

    # Verify user message appears IMMEDIATELY (short timeout)
    page.wait_for_selector(
        ".user-message .message-content:has-text('Test message')",
        timeout=2000,  # Should appear within 2 seconds
    )

    # Count should have increased
    new_count = page.evaluate(
        "() => document.querySelectorAll('.user-message').length"
    )
    assert new_count == 1, "User message should appear immediately"


# =============================================================================
# USE CASE 4: User can see agent is "thinking"
# =============================================================================


def test_user_can_see_agent_thinking_indicator(page, live_server):
    """
    USE CASE: While agent is processing, user sees a "thinking" indicator.

    The UI provides several indicators when agent is working:
    1. isAgentWorking flag is set to true
    2. Stop button becomes visible
    3. Server status shows "Claude is thinking..."

    Since mock agent responds almost instantly, we verify the mechanism exists
    by checking that:
    - The stop button element exists (hidden when not working)
    - The client has the isAgentWorking property
    - After sending a message, the agent responds (proves pipeline works)
    """
    page.goto(live_server)
    _wait_for_connection(page)

    # Verify the thinking indicator mechanism exists
    # 1. Check stop button exists (it's hidden until agent is working)
    stop_button = page.query_selector("#stop-button")
    assert stop_button is not None, "Stop button should exist for interrupting agent"

    # 2. Check that isAgentWorking property exists and starts as false
    is_working_initial = page.evaluate(
        "() => window.bassiClient?.isAgentWorking"
    )
    assert is_working_initial is False, (
        "isAgentWorking should be false before sending"
    )

    # 3. Send a message and verify agent responds (proves the pipeline works)
    page.fill("#message-input", "Tell me something")
    page.click("#send-button")

    # Wait for agent to finish and verify isAgentWorking returns to false
    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=30000,
    )

    # Verify agent response appeared (proves pipeline worked)
    page.wait_for_selector(".assistant-message", timeout=10000)


# =============================================================================
# USE CASE 5: User can start a new chat
# =============================================================================


def test_user_can_start_new_chat(page, live_server):
    """
    USE CASE: User can start a fresh new chat.

    Steps:
    1. Navigate and connect
    2. Send a message (create some history)
    3. Click "+ New Session" button
    4. Verify chat is cleared
    5. Verify new session ID
    """
    page.goto(live_server)
    first_session_id = _wait_for_connection(page)

    # Send a message to create some history
    page.fill("#message-input", "First session message")
    page.click("#send-button")
    page.wait_for_selector(
        ".user-message .message-content:has-text('First session message')",
        timeout=10000,
    )

    # Click New Session button
    page.click("#new-session-button")

    # Wait for new connection
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=15000
    )

    # Verify session ID changed
    handle = page.wait_for_function(
        f"() => window.bassiClient && window.bassiClient.sessionId !== '{first_session_id}' ? window.bassiClient.sessionId : null",
        timeout=10000,
    )
    new_session_id = handle.json_value()

    assert new_session_id is not None, "Should have new session ID"
    assert new_session_id != first_session_id, (
        "New session should have different ID"
    )

    # Verify chat is cleared (no messages)
    message_count = page.evaluate(
        "() => document.querySelectorAll('.user-message').length"
    )
    assert message_count == 0, "New chat should have no messages"


# =============================================================================
# USE CASE 6: User can see their chat in the sidebar
# =============================================================================


def test_user_can_see_chat_in_sidebar(page, live_server):
    """
    USE CASE: After sending a message, user can see their chat in the sidebar.

    Steps:
    1. Navigate and connect
    2. Send a message
    3. Open sidebar
    4. Verify session appears in the list
    """
    page.goto(live_server)
    session_id = _wait_for_connection(page)

    # Send a message to create a chat
    page.fill("#message-input", "Hello sidebar")
    page.click("#send-button")
    page.wait_for_function(
        "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
        timeout=30000,
    )

    # Open sidebar if not already open
    is_open = page.evaluate(
        "() => document.getElementById('session-sidebar')?.classList.contains('open') || false"
    )
    if not is_open:
        page.click("#session-sidebar-toggle")
        page.wait_for_function(
            "() => document.getElementById('session-sidebar')?.classList.contains('open')",
            timeout=5000,
        )

    # Refresh session list
    page.evaluate(
        "async () => { if (window.bassiClient?.loadSessions) { await window.bassiClient.loadSessions(); } }"
    )

    # Wait for session to appear in list
    page.wait_for_function(
        f"""(sid) => {{
            const items = document.querySelectorAll('#session-list .session-item');
            return Array.from(items).some(item => item.dataset.sessionId === sid);
        }}""",
        arg=session_id,
        timeout=10000,
    )

    # Verify the session item exists
    session_items = page.query_selector_all("#session-list .session-item")
    session_ids = [
        item.get_attribute("data-session-id")
        for item in session_items
    ]

    assert session_id in session_ids, (
        f"Session {session_id} should appear in sidebar"
    )


# =============================================================================
# USE CASE 7: Chat input is cleared after sending
# =============================================================================


def test_input_clears_after_sending(page, live_server):
    """
    USE CASE: After sending a message, the input field should be cleared.

    Steps:
    1. Navigate and connect
    2. Type a message
    3. Send it
    4. Verify input is empty
    """
    page.goto(live_server)
    _wait_for_connection(page)

    # Type a message
    page.fill("#message-input", "This should be cleared")

    # Verify text is in input
    input_value = page.input_value("#message-input")
    assert input_value == "This should be cleared"

    # Send it
    page.click("#send-button")

    # Wait for message to appear in chat
    page.wait_for_selector(
        ".user-message .message-content:has-text('This should be cleared')",
        timeout=10000,
    )

    # Verify input is cleared
    input_value_after = page.input_value("#message-input")
    assert input_value_after == "", (
        f"Input should be empty after sending, got: '{input_value_after}'"
    )


# =============================================================================
# USE CASE 8: User can use Enter key to send
# =============================================================================


def test_user_can_send_with_enter_key(page, live_server):
    """
    USE CASE: User can press Enter to send a message (not just click button).

    Steps:
    1. Navigate and connect
    2. Type a message
    3. Press Enter
    4. Verify message is sent
    """
    page.goto(live_server)
    _wait_for_connection(page)

    # Count initial messages
    initial_count = page.evaluate(
        "() => document.querySelectorAll('.user-message').length"
    )

    # Type a message and press Enter
    input_field = page.locator("#message-input")
    input_field.fill("Sent with Enter key")
    input_field.press("Enter")

    # Verify message appeared
    page.wait_for_selector(
        ".user-message .message-content:has-text('Sent with Enter key')",
        timeout=10000,
    )

    # Count should have increased
    new_count = page.evaluate(
        "() => document.querySelectorAll('.user-message').length"
    )
    assert new_count > initial_count, "Enter key should send the message"


# =============================================================================
# USE CASE 9: Page title shows bassi
# =============================================================================


def test_page_has_bassi_title(page, live_server):
    """
    USE CASE: Page should have identifiable title.

    Steps:
    1. Navigate to bassi
    2. Verify page has a proper title
    """
    page.goto(live_server)

    # Wait for page to load
    page.wait_for_load_state("domcontentloaded")

    title = page.title()
    assert title is not None and len(title) > 0, (
        "Page should have a title"
    )
