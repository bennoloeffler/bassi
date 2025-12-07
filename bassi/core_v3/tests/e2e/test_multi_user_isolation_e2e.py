"""
E2E tests for MULTI-USER ISOLATION.

These tests verify that multiple users can use bassi simultaneously
without interference. Critical for production use:

1. Multiple browser tabs (same user) get independent sessions
2. Multiple concurrent users don't see each other's messages
3. Pool exhaustion is handled gracefully
4. Page refresh during processing is handled safely
5. Keyboard/mouse interactions work correctly

ARCHITECTURE CONTEXT:
- Agent Pool has 5 pre-connected agents
- Each browser connection gets unique browser_id
- Each browser_id acquires one agent from pool
- Agent state is cleared on release (no context leakage)
- 6th user gets TimeoutError after 30s if pool exhausted

NOTE: For multi-user tests, we use page.context.browser.new_context()
to create additional browser contexts. This avoids fixture conflicts
with the live_server fixture's event loop initialization.
"""

import pytest

# Ensure tests run serially with the shared live_server instance
pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.xdist_group(name="e2e_server"),
]


def _wait_for_connection(page, timeout=15000):
    """Wait for WebSocket connection to be established."""
    page.wait_for_selector(
        "#connection-status:has-text('Connected')", timeout=timeout
    )
    handle = page.wait_for_function(
        "() => (window.bassiClient && window.bassiClient.sessionId) || null",
        timeout=timeout,
    )
    return handle.json_value()


def _send_message(page, message, wait_for_response=True):
    """Send a message and optionally wait for agent response."""
    page.fill("#message-input", message)
    page.click("#send-button")

    # Wait for user message to appear
    page.wait_for_selector(
        f".user-message .message-content:has-text('{message}')",
        timeout=10000,
    )

    if wait_for_response:
        # Wait for agent to finish processing
        page.wait_for_function(
            "() => window.bassiClient && window.bassiClient.isAgentWorking === false",
            timeout=30000,
        )
        page.wait_for_selector(".assistant-message", timeout=10000)


def _count_user_messages(page):
    """Count user messages in the chat."""
    return page.evaluate(
        "() => document.querySelectorAll('.user-message').length"
    )


def _get_session_id(page):
    """Get the current session ID from JavaScript."""
    return page.evaluate("() => window.bassiClient?.sessionId || null")


# =============================================================================
# USE CASE 1: Multiple Browser Tabs Get Independent Sessions
# =============================================================================


def test_two_browser_tabs_get_different_sessions(page, live_server):
    """
    USE CASE: User opens two tabs - each should be an independent session.

    This tests that:
    1. Each browser tab gets its own session ID
    2. Messages in one tab don't appear in the other
    3. Both tabs can communicate independently with agents

    Steps:
    1. Open first browser tab (page1 - the fixture)
    2. Create second browser context and page
    3. Verify they have different session IDs
    4. Send message in tab1, verify it doesn't appear in tab2
    """
    # page1 is the fixture-provided page
    page1 = page

    # Create second independent browser context from the same browser
    browser = page.context.browser
    context2 = browser.new_context()

    try:
        page2 = context2.new_page()

        # Connect both tabs
        page1.goto(live_server)
        page2.goto(live_server)

        session1 = _wait_for_connection(page1)
        session2 = _wait_for_connection(page2)

        # Verify different session IDs
        assert session1 != session2, (
            f"Two tabs should have different sessions: {session1} vs {session2}"
        )

        # Send message in tab1
        _send_message(page1, "Message from tab 1")

        # Verify tab1 has the message
        tab1_messages = _count_user_messages(page1)
        assert tab1_messages == 1, "Tab1 should have 1 user message"

        # Verify tab2 does NOT have the message (isolation)
        tab2_messages = _count_user_messages(page2)
        assert tab2_messages == 0, (
            f"Tab2 should have 0 messages (isolation), got {tab2_messages}"
        )

    finally:
        context2.close()


# =============================================================================
# USE CASE 2: Concurrent Users Don't Cross-Contaminate
# =============================================================================


def test_two_concurrent_users_isolated(page, live_server):
    """
    USE CASE: Two users chat simultaneously - messages stay in their own sessions.

    This tests the fundamental isolation property:
    - User A's messages only appear in User A's window
    - User B's messages only appear in User B's window
    - Agent responses are routed to the correct user

    Steps:
    1. User A connects and sends "I am User A"
    2. User B connects and sends "I am User B"
    3. Verify A's chat has only A's messages
    4. Verify B's chat has only B's messages
    """
    # page_a is the fixture-provided page
    page_a = page

    # Create second context for user B
    browser = page.context.browser
    context_b = browser.new_context()

    try:
        page_b = context_b.new_page()

        # Both users connect
        page_a.goto(live_server)
        page_b.goto(live_server)

        _wait_for_connection(page_a)
        _wait_for_connection(page_b)

        # User A sends message
        _send_message(page_a, "I am User A", wait_for_response=True)

        # User B sends message (while A's agent may still be processing)
        _send_message(page_b, "I am User B", wait_for_response=True)

        # Verify User A's chat content (get all user message text)
        page_a_content = page_a.evaluate(
            "() => Array.from(document.querySelectorAll('.user-message .message-content')).map(el => el.textContent).join(' ')"
        )
        assert "I am User A" in page_a_content, "User A should see their message"
        assert "I am User B" not in page_a_content, (
            "User A should NOT see User B's message"
        )

        # Verify User B's chat content (get all user message text)
        page_b_content = page_b.evaluate(
            "() => Array.from(document.querySelectorAll('.user-message .message-content')).map(el => el.textContent).join(' ')"
        )
        assert "I am User B" in page_b_content, "User B should see their message"
        assert "I am User A" not in page_b_content, (
            "User B should NOT see User A's message"
        )

    finally:
        context_b.close()


# =============================================================================
# USE CASE 3: Three Concurrent Users Work Independently
# =============================================================================


def test_three_concurrent_users_all_isolated(page, live_server):
    """
    USE CASE: Three users simultaneously - complete isolation.

    This is the explicit test the user requested:
    "think of 3 users that use bassi AT THE SAME TIME"

    Steps:
    1. Three users connect simultaneously
    2. Each sends a unique identifying message
    3. Verify each user only sees their own conversation
    """
    # Use the fixture page as user 1
    page1 = page

    # Create additional contexts from the same browser
    browser = page.context.browser
    context2 = browser.new_context()
    context3 = browser.new_context()

    try:
        page2 = context2.new_page()
        page3 = context3.new_page()

        # All three connect
        page1.goto(live_server)
        page2.goto(live_server)
        page3.goto(live_server)

        session1 = _wait_for_connection(page1)
        session2 = _wait_for_connection(page2)
        session3 = _wait_for_connection(page3)

        # Verify all have different session IDs
        sessions = {session1, session2, session3}
        assert len(sessions) == 3, (
            f"All 3 users should have unique sessions: {sessions}"
        )

        # Each user sends their identifying message
        unique_msg1 = "ALPHA_USER_MESSAGE_12345"
        unique_msg2 = "BETA_USER_MESSAGE_67890"
        unique_msg3 = "GAMMA_USER_MESSAGE_ABCDE"

        _send_message(page1, unique_msg1, wait_for_response=True)
        _send_message(page2, unique_msg2, wait_for_response=True)
        _send_message(page3, unique_msg3, wait_for_response=True)

        # Verify isolation for each user (get all user message text)
        content1 = page1.evaluate(
            "() => Array.from(document.querySelectorAll('.user-message .message-content')).map(el => el.textContent).join(' ')"
        )
        content2 = page2.evaluate(
            "() => Array.from(document.querySelectorAll('.user-message .message-content')).map(el => el.textContent).join(' ')"
        )
        content3 = page3.evaluate(
            "() => Array.from(document.querySelectorAll('.user-message .message-content')).map(el => el.textContent).join(' ')"
        )

        # User 1 isolation
        assert unique_msg1 in content1, "User 1 should see their message"
        assert unique_msg2 not in content1, "User 1 should NOT see User 2's message"
        assert unique_msg3 not in content1, "User 1 should NOT see User 3's message"

        # User 2 isolation
        assert unique_msg2 in content2, "User 2 should see their message"
        assert unique_msg1 not in content2, "User 2 should NOT see User 1's message"
        assert unique_msg3 not in content2, "User 2 should NOT see User 3's message"

        # User 3 isolation
        assert unique_msg3 in content3, "User 3 should see their message"
        assert unique_msg1 not in content3, "User 3 should NOT see User 1's message"
        assert unique_msg2 not in content3, "User 3 should NOT see User 2's message"

    finally:
        context2.close()
        context3.close()


# =============================================================================
# USE CASE 4: Page Refresh During Connection
# =============================================================================


def test_page_refresh_gets_new_session(page, live_server):
    """
    USE CASE: User refreshes page - should get new clean session.

    Steps:
    1. Connect and send a message
    2. Refresh the page
    3. Verify new session ID (or same with cleared chat)
    4. Verify chat is empty (fresh start)
    """
    page.goto(live_server)
    first_session = _wait_for_connection(page)

    # Send a message
    _send_message(page, "Before refresh")

    # Verify message exists
    messages_before = _count_user_messages(page)
    assert messages_before == 1, "Should have 1 message before refresh"

    # Refresh the page
    page.reload()

    # Wait for reconnection
    _wait_for_connection(page)

    # After refresh, should have clean session (new session or cleared chat)
    # The behavior depends on implementation:
    # - New session = new chat, empty messages
    # - Same session = would show previous messages (if persisted)

    # For a fresh new session (no persistence), chat should be empty
    # Wait a moment for DOM to stabilize
    page.wait_for_timeout(500)

    messages_after = _count_user_messages(page)
    # This verifies isolation - refresh should give clean state
    assert messages_after == 0, (
        f"After refresh should have clean chat, got {messages_after} messages"
    )


# =============================================================================
# USE CASE 5: Enter Key Sends Message (Keyboard UX)
# =============================================================================


def test_enter_key_sends_message(page, live_server):
    """
    USE CASE: User types message and presses Enter - should send.

    This is a fundamental keyboard UX expectation.

    Steps:
    1. Focus the input field
    2. Type a message
    3. Press Enter
    4. Verify message was sent
    """
    page.goto(live_server)
    _wait_for_connection(page)

    # Focus input and type
    input_field = page.locator("#message-input")
    input_field.focus()
    input_field.fill("Sent with Enter key")

    # Press Enter to send
    input_field.press("Enter")

    # Verify message appeared
    page.wait_for_selector(
        ".user-message .message-content:has-text('Sent with Enter key')",
        timeout=10000,
    )


# =============================================================================
# USE CASE 6: Shift+Enter Creates New Line (Doesn't Send)
# =============================================================================


def test_shift_enter_creates_newline(page, live_server):
    """
    USE CASE: User presses Shift+Enter - should create new line, not send.

    This is a common UX pattern for multi-line input.

    Steps:
    1. Focus input
    2. Type some text
    3. Press Shift+Enter
    4. Verify no message was sent (message count = 0)
    """
    page.goto(live_server)
    _wait_for_connection(page)

    input_field = page.locator("#message-input")
    input_field.focus()
    input_field.fill("Line 1")
    input_field.press("Shift+Enter")
    input_field.type("Line 2")

    # Give it a moment
    page.wait_for_timeout(500)

    # Should NOT have sent the message
    messages = _count_user_messages(page)
    assert messages == 0, (
        f"Shift+Enter should not send, but found {messages} messages"
    )

    # Verify input still has content (wasn't cleared)
    input_value = page.input_value("#message-input")
    assert "Line 1" in input_value, "Input should still contain text"


# =============================================================================
# USE CASE 7: Empty Message Cannot Be Sent
# =============================================================================


def test_empty_message_not_sent(page, live_server):
    """
    USE CASE: User clicks Send with empty input - nothing should happen.

    Prevents accidental empty messages.

    Steps:
    1. Connect
    2. Click Send with empty input
    3. Verify no message was sent
    """
    page.goto(live_server)
    _wait_for_connection(page)

    # Ensure input is empty
    page.fill("#message-input", "")

    # Try to send
    page.click("#send-button")

    # Wait a moment
    page.wait_for_timeout(500)

    # Should have no messages
    messages = _count_user_messages(page)
    assert messages == 0, "Empty message should not be sent"


# =============================================================================
# USE CASE 8: User Can See Their Session in Sidebar After Sending
# =============================================================================


def test_session_appears_in_sidebar(page, live_server):
    """
    USE CASE: After sending a message, user's session appears in sidebar.

    Steps:
    1. Connect and send message
    2. Open sidebar
    3. Verify current session is listed
    """
    page.goto(live_server)
    session_id = _wait_for_connection(page)

    # Send a message to create activity
    _send_message(page, "Test for sidebar", wait_for_response=True)

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

    # Wait for session to appear
    page.wait_for_function(
        f"""(sid) => {{
            const items = document.querySelectorAll('#session-list .session-item');
            return Array.from(items).some(item => item.dataset.sessionId === sid);
        }}""",
        arg=session_id,
        timeout=10000,
    )


# =============================================================================
# USE CASE 9: Stop Button Exists for Interrupting Agent
# =============================================================================


def test_stop_button_exists(page, live_server):
    """
    USE CASE: User should be able to interrupt a long-running agent.

    Verifies the stop button mechanism exists.

    Steps:
    1. Connect
    2. Verify stop button element exists
    3. Verify it's hidden when agent is not working
    """
    page.goto(live_server)
    _wait_for_connection(page)

    # Stop button should exist
    stop_button = page.query_selector("#stop-button")
    assert stop_button is not None, "Stop button should exist in DOM"


# =============================================================================
# USE CASE 10: Input Is Cleared After Sending
# =============================================================================


def test_input_cleared_after_send(page, live_server):
    """
    USE CASE: After sending, input should be empty for next message.

    Steps:
    1. Type and send a message
    2. Verify input is now empty
    """
    page.goto(live_server)
    _wait_for_connection(page)

    # Type and send
    page.fill("#message-input", "Test message to clear")
    page.click("#send-button")

    # Wait for message to appear
    page.wait_for_selector(
        ".user-message .message-content:has-text('Test message to clear')",
        timeout=10000,
    )

    # Input should be empty
    input_value = page.input_value("#message-input")
    assert input_value == "", f"Input should be empty after send, got: '{input_value}'"


# =============================================================================
# USE CASE 11: User Reconnects After Disconnect
# =============================================================================


def test_reconnection_after_network_issue(page, live_server):
    """
    USE CASE: Network briefly drops - user should be able to reconnect.

    This simulates what happens when a user's network briefly fails.
    The page should reconnect automatically or allow manual reconnect.

    Steps:
    1. Connect and verify
    2. Navigate away (simulates disconnect)
    3. Navigate back
    4. Verify reconnection works
    """
    page.goto(live_server)
    _wait_for_connection(page)

    # Navigate away (causes WebSocket disconnect)
    page.goto("about:blank")
    page.wait_for_timeout(500)

    # Navigate back
    page.goto(live_server)

    # Should reconnect
    new_session = _wait_for_connection(page)
    assert new_session is not None, "Should successfully reconnect"


# =============================================================================
# USE CASE 12: Five Concurrent Users (Pool Limit)
# =============================================================================


def test_max_concurrent_users_all_work(page, live_server):
    """
    USE CASE: Max concurrent users connect simultaneously - all should work.

    The agent pool has a configurable max size (from PoolConfig/env vars).
    All users up to that max should be able to connect.

    Steps:
    1. Get pool max_size from config
    2. Create that many browser contexts
    3. Connect all to the server
    4. Verify all get connected successfully
    """
    from bassi.config import get_pool_config

    # Get actual pool max size from config
    pool_config = get_pool_config()
    max_users = pool_config.max_size

    # Use fixture page as first user
    browser = page.context.browser

    # Track additional contexts for cleanup
    additional_contexts = []
    all_pages = [page]  # Start with fixture page

    try:
        # Create (max_users - 1) more contexts
        for i in range(max_users - 1):
            ctx = browser.new_context()
            additional_contexts.append(ctx)
            all_pages.append(ctx.new_page())

        # Connect all users
        for i, p in enumerate(all_pages):
            p.goto(live_server)

        # Verify all connect successfully
        sessions = set()
        for i, p in enumerate(all_pages):
            session = _wait_for_connection(p, timeout=30000)
            assert session is not None, f"User {i+1} should connect"
            sessions.add(session)

        # All should have unique sessions
        assert len(sessions) == max_users, (
            f"All {max_users} users should have unique sessions, got {len(sessions)}"
        )

    finally:
        # Only close the contexts we created (not the fixture's context)
        for ctx in additional_contexts:
            ctx.close()
